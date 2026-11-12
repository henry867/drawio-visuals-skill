#!/usr/bin/env python3
"""Lightweight native Draw.io inspection and file operations.

This script intentionally does not create diagrams, lay them out, or implement
a renderer. Creation stays in Mermaid/native XML. It can invoke an installed
Draw.io Desktop CLI for no-clobber exports, generate a static HTML shell for the
official remote Viewer or selected-page Web SVG export, and report deterministic
geometry/topology findings.
"""

import json
import sys


def _emit_version_error():
    payload = {
        "version": 1,
        "ok": False,
        "error": {
            "code": "PYTHON_VERSION_UNSUPPORTED",
            "message": "drawio_file.py requires Python 3.10 or newer.",
            "details": {"current": ".".join(str(part) for part in sys.version_info[:3])},
        },
    }
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


if sys.version_info < (3, 10):
    _emit_version_error()
    raise SystemExit(2)

import argparse
import base64
import binascii
import copy
import hashlib
import html
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
import zlib


VERSION = 1
MAX_INPUT_BYTES = 25 * 1024 * 1024
MAX_PATCH_BYTES = 1024 * 1024
MAX_EXPANDED_BYTES = 100 * 1024 * 1024
MAX_PAGES = 15
MAX_CELLS = 100_000
DEFAULT_QUERY_LIMIT = 50
MAX_QUERY_LIMIT = 200
MAX_VERSIONS = 200
MAX_LAYOUT_COMPARISONS = 5_000_000
MAX_LAYOUT_FINDINGS = 10_000
MAX_LAYOUT_RISK_ITEMS = 2_000
MAX_EDGE_PAIR_EVENTS = 32
SAFE_ATTR_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]*$")
VERSIONED_STEM = re.compile(r"^(?P<base>.+)-v(?P<number>[0-9]{3})$")
HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
DOUBLE_ESCAPED_MARKUP = re.compile(
    r"&lt;\s*/?\s*(?:b|br|div|em|font|i|p|span|strong|u)(?:\s|/|&gt;)",
    re.IGNORECASE,
)
DRAWIO_FORMATS = frozenset(("png", "svg", "pdf"))
DRAWIO_WEB_ORIGIN = "https://embed.diagrams.net"
DRAWIO_WEB_MODEL_DEFAULTS = {
    "grid": "1",
    "gridSize": "10",
    "guides": "1",
    "tooltips": "1",
    "connect": "1",
    "arrows": "1",
    "fold": "1",
    "pageScale": "1",
    "math": "0",
    "shadow": "0",
}
SVG_DOCTYPE = re.compile(
    rb"<!DOCTYPE\s+svg\s+PUBLIC\s+['\"]-//W3C//DTD SVG 1\.1//EN['\"]\s+"
    rb"['\"]http://www\.w3\.org/Graphics/SVG/1\.1/DTD/svg11\.dtd['\"]\s*>",
    re.IGNORECASE,
)
SVG_ACTIVE_ELEMENTS = frozenset(
    (
        "script",
        "iframe",
        "object",
        "embed",
        "link",
        "meta",
        "base",
        "set",
        "animate",
        "animatetransform",
        "animatemotion",
        "animatecolor",
        "discard",
    )
)
SVG_ACTIVE_DATA_MIMES = frozenset(
    (
        "text/html",
        "text/javascript",
        "text/css",
        "text/xml",
        "application/javascript",
        "application/ecmascript",
        "application/xhtml+xml",
        "application/xml",
        "image/svg+xml",
    )
)


class CliError(Exception):
    def __init__(self, code, message, details=None, exit_code=3):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.exit_code = exit_code


class Page:
    def __init__(self, index, page_id, name, encoding, diagram, model):
        self.index = index
        self.id = page_id
        self.name = name
        self.encoding = encoding
        self.diagram = diagram
        self.model = model
        self.changed = False


class Document:
    def __init__(self, path, source_bytes, root, bare, pages):
        self.path = path
        self.source_bytes = source_bytes
        self.root = root
        self.bare = bare
        self.pages = pages
        self.revision = revision_for(source_bytes)


class LogicalCell:
    def __init__(self, outer, cell, wrapper):
        self.outer = outer
        self.cell = cell
        self.wrapper = wrapper
        self.id = (wrapper.get("id") if wrapper is not None else cell.get("id")) or ""


def revision_for(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def local_name(tag):
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def xml_parser():
    return ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))


def reject_unsafe_xml(data, context):
    upper = data.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise CliError(
            "UNSAFE_XML",
            "DOCTYPE and entity declarations are not supported.",
            {"context": context},
        )


def parse_xml_bytes(data, context):
    reject_unsafe_xml(data, context)
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CliError(
            "INVALID_UTF8",
            "Draw.io XML must be UTF-8.",
            {"context": context, "offset": exc.start},
        ) from exc
    try:
        return ET.fromstring(text, parser=xml_parser())
    except ET.ParseError as exc:
        raise CliError(
            "INVALID_XML",
            "XML parsing failed.",
            {"context": context, "error": str(exc)},
        ) from exc


def direct_child(element, name):
    matches = [child for child in list(element) if local_name(child.tag) == name]
    if len(matches) != 1:
        raise CliError(
            "INVALID_STRUCTURE",
            "Expected exactly one direct child.",
            {"element": local_name(element.tag), "child": name, "count": len(matches)},
        )
    return matches[0]


def inflate_raw_bounded(data, remaining, page_label):
    if remaining < 0:
        raise CliError("EXPANDED_SIZE_LIMIT", "Expanded page limit exceeded.")
    inflater = zlib.decompressobj(-zlib.MAX_WBITS)
    try:
        output = inflater.decompress(data, remaining + 1)
        if len(output) > remaining or inflater.unconsumed_tail:
            raise CliError(
                "EXPANDED_SIZE_LIMIT",
                "Expanded page limit exceeded.",
                {"page": page_label, "limit": MAX_EXPANDED_BYTES},
            )
        flushed = inflater.flush(remaining - len(output) + 1)
        output += flushed
    except zlib.error as exc:
        raise CliError(
            "INVALID_COMPRESSED_PAGE",
            "Raw DEFLATE decoding failed.",
            {"page": page_label, "error": str(exc)},
        ) from exc
    if len(output) > remaining:
        raise CliError(
            "EXPANDED_SIZE_LIMIT",
            "Expanded page limit exceeded.",
            {"page": page_label, "limit": MAX_EXPANDED_BYTES},
        )
    if not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
        raise CliError(
            "INVALID_COMPRESSED_PAGE",
            "Compressed page is truncated or has trailing data.",
            {"page": page_label},
        )
    return output


def validate_percent_payload(text, page_label):
    index = 0
    while True:
        index = text.find("%", index)
        if index < 0:
            return
        if (
            index + 2 >= len(text)
            or text[index + 1] not in HEX_DIGITS
            or text[index + 2] not in HEX_DIGITS
        ):
            raise CliError(
                "INVALID_COMPRESSED_PAGE",
                "Compressed page contains an invalid percent escape.",
                {"page": page_label, "offset": index},
            )
        index += 3


def decompress_page(payload, remaining, page_label):
    try:
        compressed = base64.b64decode(payload.strip().encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError) as exc:
        raise CliError(
            "INVALID_COMPRESSED_PAGE",
            "Page is not canonical Base64.",
            {"page": page_label},
        ) from exc
    inflated = inflate_raw_bounded(compressed, remaining, page_label)
    try:
        percent_text = inflated.decode("ascii")
    except UnicodeDecodeError as exc:
        raise CliError(
            "UNSUPPORTED_ENCODING",
            "Only canonical percent-encoded Draw.io compressed pages are supported.",
            {"page": page_label},
        ) from exc
    if percent_text.lstrip().startswith("<"):
        raise CliError(
            "UNSUPPORTED_ENCODING",
            "Legacy raw-XML compressed pages are outside this lightweight V1.",
            {"page": page_label},
        )
    validate_percent_payload(percent_text, page_label)
    xml_bytes = urllib.parse.unquote_to_bytes(percent_text)
    if len(xml_bytes) > remaining:
        raise CliError(
            "EXPANDED_SIZE_LIMIT",
            "Expanded page limit exceeded.",
            {"page": page_label, "limit": MAX_EXPANDED_BYTES},
        )
    model = parse_xml_bytes(xml_bytes, "compressed page " + page_label)
    if local_name(model.tag) != "mxGraphModel":
        raise CliError(
            "INVALID_STRUCTURE",
            "Compressed page root must be mxGraphModel.",
            {"page": page_label, "root": local_name(model.tag)},
        )
    return model, len(xml_bytes)


def load_document(path):
    source_path = Path(path).expanduser().resolve()
    try:
        stat = source_path.stat()
    except FileNotFoundError as exc:
        raise CliError("FILE_NOT_FOUND", "Input file does not exist.", {"path": str(source_path)}) from exc
    if not source_path.is_file():
        raise CliError("INVALID_PATH", "Input must be a file.", {"path": str(source_path)})
    if stat.st_size > MAX_INPUT_BYTES:
        raise CliError(
            "INPUT_SIZE_LIMIT",
            "Input file exceeds the lightweight V1 limit.",
            {"path": str(source_path), "limit": MAX_INPUT_BYTES, "size": stat.st_size},
        )
    source_bytes = source_path.read_bytes()
    if len(source_bytes) > MAX_INPUT_BYTES:
        raise CliError(
            "INPUT_SIZE_LIMIT",
            "Input file exceeds the lightweight V1 limit.",
            {"path": str(source_path), "limit": MAX_INPUT_BYTES, "size": len(source_bytes)},
        )
    root = parse_xml_bytes(source_bytes, str(source_path))
    root_name = local_name(root.tag)
    pages = []
    expanded_total = 0
    if root_name == "mxGraphModel":
        pages.append(Page(0, None, "Page 1", "plain", None, root))
        expanded_total = len(ET.tostring(root, encoding="utf-8"))
        bare = True
    elif root_name == "mxfile":
        bare = False
        diagrams = [child for child in list(root) if local_name(child.tag) == "diagram"]
        if not diagrams:
            raise CliError("INVALID_STRUCTURE", "mxfile must contain at least one diagram page.")
        if len(diagrams) > MAX_PAGES:
            raise CliError(
                "PAGE_COUNT_LIMIT",
                "Document has too many pages.",
                {"pages": len(diagrams), "limit": MAX_PAGES},
            )
        for index, diagram in enumerate(diagrams):
            page_id = diagram.get("id")
            page_name = diagram.get("name") or "Page " + str(index + 1)
            label = page_id or page_name
            element_children = [child for child in list(diagram) if isinstance(child.tag, str)]
            if element_children:
                if len(element_children) != 1 or local_name(element_children[0].tag) != "mxGraphModel":
                    raise CliError(
                        "INVALID_STRUCTURE",
                        "Plain page must contain exactly one mxGraphModel.",
                        {"page": label},
                    )
                model = element_children[0]
                page_size = len(ET.tostring(model, encoding="utf-8"))
                encoding = "plain"
            else:
                payload = (diagram.text or "").strip()
                if not payload:
                    raise CliError("INVALID_STRUCTURE", "Empty diagram pages are not supported.", {"page": label})
                model, page_size = decompress_page(
                    payload, MAX_EXPANDED_BYTES - expanded_total, label
                )
                encoding = "compressed"
            expanded_total += page_size
            if expanded_total > MAX_EXPANDED_BYTES:
                raise CliError(
                    "EXPANDED_SIZE_LIMIT",
                    "Expanded document exceeds the lightweight V1 limit.",
                    {"limit": MAX_EXPANDED_BYTES},
                )
            pages.append(Page(index, page_id, page_name, encoding, diagram, model))
    else:
        raise CliError(
            "INVALID_STRUCTURE",
            "Expected an mxfile or mxGraphModel root.",
            {"root": root_name},
        )
    document = Document(source_path, source_bytes, root, bare, pages)
    validate_document(document)
    return document


def model_root(page):
    return direct_child(page.model, "root")


def parse_logical_cell(element, page):
    tag = local_name(element.tag)
    if tag == "mxCell":
        if not element.get("id"):
            raise CliError("INVALID_CELL", "mxCell is missing id.", {"page": page.id or page.name})
        return LogicalCell(element, element, None)
    if tag not in ("object", "UserObject"):
        return None
    cell_children = [child for child in list(element) if local_name(child.tag) == "mxCell"]
    other_elements = [
        child
        for child in list(element)
        if isinstance(child.tag, str) and local_name(child.tag) != "mxCell"
    ]
    if len(cell_children) != 1 or other_elements:
        raise CliError(
            "UNSUPPORTED_WRAPPER",
            "Wrapper must contain exactly one direct mxCell and no other element children.",
            {"page": page.id or page.name, "wrapper": tag},
        )
    wrapper_id = element.get("id")
    inner_id = cell_children[0].get("id")
    if not wrapper_id or (inner_id and inner_id != wrapper_id):
        raise CliError(
            "UNSUPPORTED_WRAPPER",
            "Wrapper identity is missing or conflicts with its inner mxCell.",
            {"page": page.id or page.name, "wrapperId": wrapper_id, "innerId": inner_id},
        )
    return LogicalCell(element, cell_children[0], element)


def logical_cells(page):
    cells = []
    for child in list(model_root(page)):
        logical = parse_logical_cell(child, page)
        if logical is not None:
            cells.append(logical)
    return cells


def logical_cell_map(page):
    result = {}
    for logical in logical_cells(page):
        if logical.id in result:
            raise CliError(
                "DUPLICATE_CELL_ID",
                "Logical cell ID is duplicated within a page.",
                {"page": page.id or page.name, "cellId": logical.id},
            )
        result[logical.id] = logical
    return result


def logical_label(logical):
    if logical.wrapper is not None and logical.wrapper.get("label") is not None:
        return logical.wrapper.get("label", "")
    return logical.cell.get("value", "")


def probable_double_escaped_markup(value):
    return bool(value and DOUBLE_ESCAPED_MARKUP.search(value))


def validate_xml_text(value, context):
    if not isinstance(value, str):
        raise CliError("INVALID_PATCH", context + " must be a string.")
    for character in value:
        codepoint = ord(character)
        if not (
            codepoint in (0x9, 0xA, 0xD)
            or 0x20 <= codepoint <= 0xD7FF
            or 0xE000 <= codepoint <= 0xFFFD
            or 0x10000 <= codepoint <= 0x10FFFF
        ):
            raise CliError(
                "INVALID_XML_TEXT",
                context + " contains a character XML 1.0 cannot represent.",
                {"codepoint": "U+%04X" % codepoint},
            )
    return value


def validate_geometry(logical, page):
    geometries = [child for child in list(logical.cell) if local_name(child.tag) == "mxGeometry"]
    if len(geometries) > 1:
        raise CliError(
            "INVALID_GEOMETRY",
            "A cell cannot contain multiple direct mxGeometry elements.",
            {"page": page.id or page.name, "cellId": logical.id},
        )
    if not geometries:
        return
    geometry = geometries[0]
    for name in ("x", "y", "width", "height"):
        value = geometry.get(name)
        if value is None:
            continue
        try:
            number = float(value)
        except ValueError as exc:
            raise CliError(
                "INVALID_GEOMETRY",
                "Geometry values must be finite numbers.",
                {"page": page.id or page.name, "cellId": logical.id, "attribute": name},
            ) from exc
        if not math.isfinite(number) or (name in ("width", "height") and number < 0):
            raise CliError(
                "INVALID_GEOMETRY",
                "Geometry values must be finite and dimensions non-negative.",
                {"page": page.id or page.name, "cellId": logical.id, "attribute": name},
            )


def misplaced_waypoint_arrays(logical):
    return [
        child
        for child in list(logical.cell)
        if local_name(child.tag) == "Array" and child.get("as") == "points"
    ]


def misplaced_waypoint_warnings(validation):
    return [
        warning
        for warning in validation["warnings"]
        if warning.get("code") == "MISPLACED_WAYPOINT_ARRAY"
    ]


def require_no_misplaced_waypoints(validation):
    misplaced = misplaced_waypoint_warnings(validation)
    if misplaced:
        raise CliError(
            "MISPLACED_WAYPOINT_ARRAY",
            "Waypoint arrays must be nested inside the cell's mxGeometry element.",
            {
                "cells": [
                    {"page": item["page"], "cellId": item["cellId"]}
                    for item in misplaced
                ]
            },
        )


def validate_parent_hierarchy(cell_map, page):
    checked = set()
    for cell_id in cell_map:
        path = set()
        current = cell_id
        while current and current not in checked:
            if current in path:
                raise CliError(
                    "PARENT_CYCLE",
                    "Cell containment must not contain a parent cycle.",
                    {
                        "page": page.id or page.name,
                        "cellId": current,
                        "parent": cell_map[current].cell.get("parent"),
                    },
                )
            path.add(current)
            current = cell_map[current].cell.get("parent")
        checked.update(path)


def validate_document(document):
    warnings = []
    page_ids = set()
    total_cells = 0
    for page in document.pages:
        if page.id:
            if page.id in page_ids:
                raise CliError("DUPLICATE_PAGE_ID", "Page IDs must be unique.", {"pageId": page.id})
            page_ids.add(page.id)
        root = model_root(page)
        cell_map = logical_cell_map(page)
        total_cells += len(cell_map)
        if total_cells > MAX_CELLS:
            raise CliError(
                "CELL_COUNT_LIMIT",
                "Document has too many logical cells.",
                {"cells": total_cells, "limit": MAX_CELLS},
            )
        for sentinel in ("0", "1"):
            if sentinel not in cell_map:
                raise CliError(
                    "MISSING_SENTINEL",
                    "Each page requires root cells 0 and 1.",
                    {"page": page.id or page.name, "cellId": sentinel},
                )
        for logical in cell_map.values():
            for attribute in ("parent", "source", "target"):
                target = logical.cell.get(attribute)
                if target and target not in cell_map:
                    raise CliError(
                        "DANGLING_REFERENCE",
                        "Cell reference does not exist on the same page.",
                        {
                            "page": page.id or page.name,
                            "cellId": logical.id,
                            "attribute": attribute,
                            "target": target,
                        },
                    )
            validate_geometry(logical, page)
            if misplaced_waypoint_arrays(logical):
                warnings.append(
                    {
                        "code": "MISPLACED_WAYPOINT_ARRAY",
                        "page": page.id or page.name,
                        "cellId": logical.id,
                        "message": (
                            "Waypoint Array elements must be children of mxGeometry; Draw.io ignores "
                            "direct mxCell waypoint arrays."
                        ),
                    }
                )
            label = logical_label(logical)
            if probable_double_escaped_markup(label):
                warnings.append(
                    {
                        "code": "POSSIBLE_DOUBLE_ESCAPED_LABEL",
                        "page": page.id or page.name,
                        "cellId": logical.id,
                        "message": (
                            "Label contains escaped HTML-like markup; use set-label with a decoded "
                            "logical value when rich text is intended."
                        ),
                    }
                )
        validate_parent_hierarchy(cell_map, page)
        unknown = [
            local_name(child.tag)
            for child in list(root)
            if isinstance(child.tag, str)
            and local_name(child.tag) not in ("mxCell", "object", "UserObject")
        ]
        if unknown:
            warnings.append(
                {
                    "code": "UNKNOWN_ROOT_ELEMENTS_PRESERVED",
                    "page": page.id or page.name,
                    "elements": sorted(set(unknown)),
                }
            )
    return {"pages": len(document.pages), "cells": total_cells, "warnings": warnings}


def cell_geometry(logical):
    return next(
        (child for child in list(logical.cell) if local_name(child.tag) == "mxGeometry"),
        None,
    )


def native_style(cell):
    result = {}
    for token in cell.get("style", "").split(";"):
        if not token:
            continue
        if "=" in token:
            key, value = token.split("=", 1)
        else:
            key, value = token, "1"
        result[key] = value
    return result


def visual_container_kind(logical):
    styles = native_style(logical.cell)
    if styles.get("swimlane") == "1":
        return "swimlane"
    if styles.get("container") == "1":
        return "container"
    return None


def plain_label_lines(value):
    if value is None:
        return []
    text = html.unescape(value)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(?:div|p|li|tr|h[1-6])\s*>", "\n", text)
    text = re.sub(r"<[^>]*>", "", text)
    return [line.strip() for line in text.splitlines()] or [""]


def character_em_width(character):
    if character.isspace():
        return 0.33
    if unicodedata.east_asian_width(character) in ("W", "F"):
        return 1.0
    return 0.6


def estimated_text_metrics(value, font_size, wrap_width=None):
    lines = plain_label_lines(value)
    if not lines or not any(lines):
        return {"width": 0.0, "height": 0.0, "lines": 0}
    widths = [sum(character_em_width(char) for char in line) * font_size for line in lines]
    rendered_lines = len(lines)
    if wrap_width is not None and wrap_width > 0:
        rendered_lines = sum(max(1, math.ceil(width / wrap_width)) for width in widths)
        estimated_width = min(max(widths, default=0.0), wrap_width)
    else:
        estimated_width = max(widths, default=0.0)
    return {
        "width": estimated_width + 8.0,
        "height": rendered_lines * font_size * 1.2 + 8.0,
        "lines": rendered_lines,
    }


def expanded_rectangle(rectangle, margin):
    return {
        "x": rectangle["x"] - margin,
        "y": rectangle["y"] - margin,
        "width": rectangle["width"] + margin * 2,
        "height": rectangle["height"] + margin * 2,
        "right": rectangle["right"] + margin,
        "bottom": rectangle["bottom"] + margin,
    }


def union_rectangles(rectangles):
    rectangles = list(rectangles)
    if not rectangles:
        return None
    left = min(rectangle["x"] for rectangle in rectangles)
    top = min(rectangle["y"] for rectangle in rectangles)
    right = max(rectangle["right"] for rectangle in rectangles)
    bottom = max(rectangle["bottom"] for rectangle in rectangles)
    return {
        "x": left,
        "y": top,
        "width": right - left,
        "height": bottom - top,
        "right": right,
        "bottom": bottom,
    }


def compact_rectangle(rectangle):
    if rectangle is None:
        return None
    return {
        key: round(rectangle[key], 3)
        for key in ("x", "y", "width", "height")
    }


def layout_page(page, expect_single_page=False):
    """Report geometric collisions without choosing or changing a layout."""
    cell_map = logical_cell_map(page)
    page_cells = list(cell_map.values())
    rectangles = {}
    collisions = []
    warnings = []
    advisories = []
    warning_keys = set()
    advisory_keys = set()
    risk_items = []
    resolving = set()

    def limit_error(kind, limit):
        raise CliError(
            "LAYOUT_CHECK_LIMIT",
            "Page exceeds a safe output limit for the lightweight layout check.",
            {
                "page": page.id or page.name,
                "limitKind": kind,
                "limit": limit,
            },
        )

    def reserve_finding():
        if len(collisions) + len(warnings) + len(advisories) >= MAX_LAYOUT_FINDINGS:
            limit_error("findings", MAX_LAYOUT_FINDINGS)

    def add_risk(reason, rectangle, cell_ids, priority=2):
        if rectangle is None:
            return
        if len(risk_items) >= MAX_LAYOUT_RISK_ITEMS:
            limit_error("riskItems", MAX_LAYOUT_RISK_ITEMS)
        risk_items.append(
            {
                "reason": reason,
                "bounds": rectangle,
                "cellIds": sorted(cell_id for cell_id in set(cell_ids) if cell_id),
                "priority": priority,
            }
        )

    def warn(code, cell_id, reason=None, dedupe_key=None, **details):
        key = (code, cell_id, reason, dedupe_key)
        if key in warning_keys:
            return
        reserve_finding()
        warning_keys.add(key)
        item = {"code": code, "page": page.id or page.name, "cellId": cell_id}
        if reason is not None:
            item["reason"] = reason
        item.update(details)
        warnings.append(item)

    def advise(code, cell_id, reason=None, dedupe_key=None, **details):
        key = (code, cell_id, reason, dedupe_key)
        if key in advisory_keys:
            return
        reserve_finding()
        advisory_keys.add(key)
        item = {"code": code, "page": page.id or page.name, "cellId": cell_id}
        if reason is not None:
            item["reason"] = reason
        item.update(details)
        advisories.append(item)

    def rectangle_for(cell_id):
        if cell_id in rectangles:
            return rectangles[cell_id]
        logical = cell_map.get(cell_id)
        if logical is None or logical.cell.get("vertex") != "1":
            return None
        if cell_id in resolving:
            warn("UNVERIFIABLE_GEOMETRY", cell_id, "parent-cycle")
            return None
        geometry = cell_geometry(logical)
        if geometry is None:
            warn("UNVERIFIABLE_GEOMETRY", cell_id, "missing-geometry")
            return None
        if geometry.get("relative") == "1":
            warn("UNVERIFIABLE_GEOMETRY", cell_id, "relative-vertex")
            return None
        if geometry.get("width") is None or geometry.get("height") is None:
            warn("UNVERIFIABLE_GEOMETRY", cell_id, "missing-dimensions")
            return None

        resolving.add(cell_id)
        try:
            x = float(geometry.get("x", "0"))
            y = float(geometry.get("y", "0"))
            width = float(geometry.get("width"))
            height = float(geometry.get("height"))
            parent_id = logical.cell.get("parent")
            parent = cell_map.get(parent_id) if parent_id else None
            if parent is not None and parent.cell.get("vertex") == "1":
                parent_rectangle = rectangle_for(parent.id)
                if parent_rectangle is None:
                    warn("UNVERIFIABLE_GEOMETRY", cell_id, "unresolved-parent")
                    return None
                x += parent_rectangle["x"]
                y += parent_rectangle["y"]
            elif parent is not None and parent.cell.get("edge") == "1":
                warn("UNVERIFIABLE_GEOMETRY", cell_id, "edge-relative-label")
                return None
            rectangle = {
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "right": x + width,
                "bottom": y + height,
            }
            rectangles[cell_id] = rectangle
            return rectangle
        finally:
            resolving.discard(cell_id)

    vertex_ids = [
        logical.id
        for logical in page_cells
        if logical.cell.get("vertex") == "1"
    ]
    edge_count = sum(1 for logical in page_cells if logical.cell.get("edge") == "1")
    vertex_pair_checks = len(vertex_ids) * (len(vertex_ids) - 1) // 2
    if vertex_pair_checks > MAX_LAYOUT_COMPARISONS:
        raise CliError(
            "LAYOUT_CHECK_LIMIT",
            "Page is too large for the lightweight quadratic layout check.",
            {
                "page": page.id or page.name,
                "vertices": len(vertex_ids),
                "edges": edge_count,
                "vertexPairs": vertex_pair_checks,
                "edgeVertexSegmentChecks": 0,
                "edgeEdgeSegmentChecks": 0,
                "labelPairs": 0,
                "estimatedComparisons": vertex_pair_checks,
                "limit": MAX_LAYOUT_COMPARISONS,
            },
        )
    for cell_id in vertex_ids:
        rectangle_for(cell_id)

    def ancestors(cell_id):
        result = set()
        current = cell_map.get(cell_id)
        while current is not None:
            parent_id = current.cell.get("parent")
            if not parent_id or parent_id in result:
                break
            result.add(parent_id)
            current = cell_map.get(parent_id)
        return result

    ancestor_map = {cell_id: ancestors(cell_id) for cell_id in cell_map}

    def intersection(first, second):
        left = max(first["x"], second["x"])
        top = max(first["y"], second["y"])
        right = min(first["right"], second["right"])
        bottom = min(first["bottom"], second["bottom"])
        if left < right and top < bottom:
            return {
                "x": left,
                "y": top,
                "width": right - left,
                "height": bottom - top,
            }
        return None

    def page_bounds():
        if page.model.get("page", "1") != "1":
            return None
        try:
            scale = float(page.model.get("pageScale", "1"))
            width = float(page.model.get("pageWidth", "0")) * scale
            height = float(page.model.get("pageHeight", "0")) * scale
        except ValueError:
            return None
        if not all(math.isfinite(value) and value > 0 for value in (width, height)):
            return None
        return {
            "x": 0.0,
            "y": 0.0,
            "width": width,
            "height": height,
            "right": width,
            "bottom": height,
        }

    declared_page = page_bounds()

    for vertex_id, rectangle in rectangles.items():
        logical = cell_map[vertex_id]
        label = logical_label(logical)
        if label is None or not label.strip():
            continue
        styles = native_style(logical.cell)
        try:
            font_size = float(styles.get("fontSize", "12"))
        except ValueError:
            font_size = 12.0
        available_width = max(1.0, rectangle["width"] - 8.0)
        metrics = estimated_text_metrics(
            label,
            font_size,
            available_width if styles.get("whiteSpace") == "wrap" else None,
        )
        available_height = rectangle["height"]
        if visual_container_kind(logical) == "swimlane":
            try:
                available_height = float(styles.get("startSize", "40"))
            except ValueError:
                available_height = 40.0
        width_risk = styles.get("whiteSpace") != "wrap" and metrics["width"] > rectangle["width"]
        height_risk = metrics["height"] > available_height
        if width_risk or height_risk:
            warn(
                "TEXT_CLIP_RISK",
                vertex_id,
                "conservative-text-estimate",
                estimated=metrics,
                available={"width": rectangle["width"], "height": available_height},
            )
            add_risk("TEXT_CLIP_RISK", rectangle, [vertex_id])

    comparable_vertices = [cell_id for cell_id in vertex_ids if cell_id in rectangles]
    for index, first_id in enumerate(comparable_vertices):
        for second_id in comparable_vertices[index + 1 :]:
            if first_id in ancestor_map.get(second_id, set()) or second_id in ancestor_map.get(first_id, set()):
                continue
            overlap = intersection(rectangles[first_id], rectangles[second_id])
            if overlap is not None:
                reserve_finding()
                collisions.append(
                    {
                        "type": "VERTEX_OVERLAP",
                        "page": page.id or page.name,
                        "cellIds": [first_id, second_id],
                        "overlap": overlap,
                    }
                )
                add_risk("VERTEX_OVERLAP", union_rectangles((rectangles[first_id], rectangles[second_id])), [first_id, second_id], 3)

    for child_id in comparable_vertices:
        child = cell_map[child_id]
        parent_id = child.cell.get("parent")
        if parent_id not in rectangles:
            continue
        child_rectangle = rectangles[child_id]
        parent_rectangle = rectangles[parent_id]
        if (
            child_rectangle["x"] < parent_rectangle["x"]
            or child_rectangle["y"] < parent_rectangle["y"]
            or child_rectangle["right"] > parent_rectangle["right"]
            or child_rectangle["bottom"] > parent_rectangle["bottom"]
        ):
            reserve_finding()
            collisions.append(
                {
                    "type": "CHILD_OUTSIDE_PARENT",
                    "page": page.id or page.name,
                    "cellId": child_id,
                    "parentId": parent_id,
                }
            )
            add_risk("CHILD_OUTSIDE_PARENT", child_rectangle, [child_id, parent_id], 3)

    def center(rectangle):
        return (
            rectangle["x"] + rectangle["width"] / 2,
            rectangle["y"] + rectangle["height"] / 2,
        )

    def strict_segment_intersects_rectangle(start, end, rectangle):
        epsilon = 1e-7
        left = rectangle["x"] + epsilon
        top = rectangle["y"] + epsilon
        right = rectangle["right"] - epsilon
        bottom = rectangle["bottom"] - epsilon
        if left >= right or top >= bottom:
            return False
        delta_x = end[0] - start[0]
        delta_y = end[1] - start[1]
        lower = 0.0
        upper = 1.0
        for p, q in (
            (-delta_x, start[0] - left),
            (delta_x, right - start[0]),
            (-delta_y, start[1] - top),
            (delta_y, bottom - start[1]),
        ):
            if p == 0:
                if q < 0:
                    return False
                continue
            ratio = q / p
            if p < 0:
                lower = max(lower, ratio)
            else:
                upper = min(upper, ratio)
            if lower > upper:
                return False
        return lower <= upper

    def point_from_element(point, offset):
        x = point.get("x")
        y = point.get("y")
        if x is None or y is None:
            return None
        try:
            point_x = float(x)
            point_y = float(y)
        except ValueError:
            return None
        if not math.isfinite(point_x) or not math.isfinite(point_y):
            return None
        return point_x + offset[0], point_y + offset[1]

    def point_along_path(path, fraction):
        lengths = [
            math.hypot(end[0] - start[0], end[1] - start[1])
            for start, end in zip(path, path[1:])
        ]
        total = sum(lengths)
        if total <= 0:
            return path[0], (1.0, 0.0)
        remaining = max(0.0, min(1.0, fraction)) * total
        for index, ((start, end), length) in enumerate(zip(zip(path, path[1:]), lengths)):
            if remaining <= length or index == len(lengths) - 1:
                ratio = 0.0 if length == 0 else remaining / length
                point = (
                    start[0] + (end[0] - start[0]) * ratio,
                    start[1] + (end[1] - start[1]) * ratio,
                )
                direction = (
                    1.0 if length == 0 else (end[0] - start[0]) / length,
                    0.0 if length == 0 else (end[1] - start[1]) / length,
                )
                return point, direction
            remaining -= length
        return path[-1], (1.0, 0.0)

    def swimlane_header_rectangle(logical, rectangle):
        styles = native_style(logical.cell)
        try:
            start_size = float(styles.get("startSize", "40"))
        except ValueError:
            start_size = 40.0
        if styles.get("horizontal", "1") == "0":
            width = min(rectangle["width"], max(0.0, start_size))
            return {
                "x": rectangle["x"], "y": rectangle["y"],
                "width": width, "height": rectangle["height"],
                "right": rectangle["x"] + width, "bottom": rectangle["bottom"],
            }
        height = min(rectangle["height"], max(0.0, start_size))
        return {
            "x": rectangle["x"], "y": rectangle["y"],
            "width": rectangle["width"], "height": height,
            "right": rectangle["right"], "bottom": rectangle["y"] + height,
        }

    def explicit_port(rectangle, styles, x_key, y_key):
        if x_key not in styles or y_key not in styles:
            return None, None, "missing"
        try:
            relative_x = float(styles[x_key])
            relative_y = float(styles[y_key])
        except (TypeError, ValueError):
            return None, None, "invalid"
        if (
            not math.isfinite(relative_x)
            or not math.isfinite(relative_y)
            or not 0.0 <= relative_x <= 1.0
            or not 0.0 <= relative_y <= 1.0
        ):
            return None, None, "invalid"
        point = (
            rectangle["x"] + rectangle["width"] * relative_x,
            rectangle["y"] + rectangle["height"] * relative_y,
        )
        return point, (relative_x, relative_y), "valid"

    def native_shape_kind(vertex_id):
        if vertex_id not in cell_map:
            return None
        styles = native_style(cell_map[vertex_id].cell)
        shape = styles.get("shape")
        perimeter = styles.get("perimeter")
        perimeter_shapes = {
            "rectanglePerimeter": "rectangle",
            "ellipsePerimeter": "ellipse",
            "rhombusPerimeter": "rhombus",
            "trianglePerimeter": "triangle",
            "hexagonPerimeter": "hexagon",
        }
        if perimeter in perimeter_shapes:
            return perimeter_shapes[perimeter]
        if styles.get("rhombus") == "1" or shape == "rhombus":
            return "rhombus"
        if (
            shape in (None, "rectangle", "rect")
            and styles.get("ellipse") != "1"
            and visual_container_kind(cell_map[vertex_id]) is None
        ):
            return "rectangle"
        if visual_container_kind(cell_map[vertex_id]) is not None:
            return "rectangle"
        return shape or next(
            (
                token
                for token in ("ellipse", "triangle", "hexagon")
                if styles.get(token) == "1"
            ),
            "unsupported",
        )

    def cardinal_port_side(relative_port):
        if relative_port is None:
            return None
        relative_x, relative_y = relative_port
        for side, point in (
            ("left", (0.0, 0.5)),
            ("right", (1.0, 0.5)),
            ("top", (0.5, 0.0)),
            ("bottom", (0.5, 1.0)),
        ):
            if point_equal(relative_port, point, tolerance=1e-9):
                return side
        return None

    def resolve_explicit_port(vertex_id, rectangle, edge_styles, role, relative_port):
        raw_point = (
            rectangle["x"] + rectangle["width"] * relative_port[0],
            rectangle["y"] + rectangle["height"] * relative_port[1],
        )
        shape_kind = native_shape_kind(vertex_id)
        perimeter_key = "exitPerimeter" if role == "source" else "entryPerimeter"
        if (
            shape_kind not in {"rhombus", "ellipse"}
            or edge_styles.get(perimeter_key, "1") == "0"
        ):
            return raw_point, {
                "shape": shape_kind,
                "rawPoint": raw_point,
                "projectedPoint": raw_point,
                "projected": False,
            }
        delta_x = relative_port[0] - 0.5
        delta_y = relative_port[1] - 0.5
        if math.hypot(delta_x, delta_y) <= geometry_epsilon:
            return raw_point, {
                "shape": shape_kind,
                "rawPoint": raw_point,
                "projectedPoint": raw_point,
                "projected": False,
            }
        if shape_kind == "rhombus":
            scale = 0.5 / (abs(delta_x) + abs(delta_y))
            projected_relative = (0.5 + delta_x * scale, 0.5 + delta_y * scale)
        else:
            # mxPerimeter.EllipsePerimeter intersects the center-to-anchor ray
            # with the ellipse, using integer-truncated deltas before solving.
            pixel_dx = int(raw_point[0] - (rectangle["x"] + rectangle["width"] / 2))
            pixel_dy = int(raw_point[1] - (rectangle["y"] + rectangle["height"] / 2))
            if pixel_dx == 0 and pixel_dy == 0:
                projected_relative = relative_port
            else:
                radius_x = rectangle["width"] / 2
                radius_y = rectangle["height"] / 2
                scale = 1.0 / math.sqrt(
                    (pixel_dx / radius_x) ** 2 + (pixel_dy / radius_y) ** 2
                )
                projected_relative = (
                    0.5 + pixel_dx * scale / rectangle["width"],
                    0.5 + pixel_dy * scale / rectangle["height"],
                )
        projected_point = (
            math.floor(
                rectangle["x"] + rectangle["width"] * projected_relative[0] + 0.5
            ),
            math.floor(
                rectangle["y"] + rectangle["height"] * projected_relative[1] + 0.5
            ),
        )
        return projected_point, {
            "shape": shape_kind,
            "rawPoint": raw_point,
            "projectedPoint": projected_point,
            "projected": cardinal_port_side(relative_port) is None,
        }

    def boundary_port_side(relative_port):
        if relative_port is None:
            return None
        relative_x, relative_y = relative_port
        on_left = math.isclose(relative_x, 0.0, abs_tol=1e-9)
        on_right = math.isclose(relative_x, 1.0, abs_tol=1e-9)
        on_top = math.isclose(relative_y, 0.0, abs_tol=1e-9)
        on_bottom = math.isclose(relative_y, 1.0, abs_tol=1e-9)
        if (on_left or on_right) and (on_top or on_bottom):
            return None
        if on_left:
            return "left"
        if on_right:
            return "right"
        if on_top:
            return "top"
        if on_bottom:
            return "bottom"
        return None

    def supported_port_geometry(vertex_id, edge_styles, role, relative_port):
        if vertex_id not in cell_map or relative_port is None:
            return False, "missing-boundary-port"
        side = boundary_port_side(relative_port)
        if side is None:
            return False, "corner-or-interior-port"
        vertex_styles = native_style(cell_map[vertex_id].cell)
        try:
            rotation = float(vertex_styles.get("rotation", "0"))
        except ValueError:
            return False, "invalid-rotation"
        if not math.isclose(rotation, 0.0, abs_tol=geometry_epsilon):
            return False, "rotated-vertex"
        if vertex_styles.get("flipH") == "1" or vertex_styles.get("flipV") == "1":
            return False, "flipped-vertex"
        if vertex_styles.get("direction", "east") != "east":
            return False, "direction-transform"
        dx_keys = ("exitDx", "exitDy") if role == "source" else ("entryDx", "entryDy")
        for key in dx_keys:
            try:
                if not math.isclose(float(edge_styles.get(key, "0")), 0.0, abs_tol=geometry_epsilon):
                    return False, "endpoint-offset"
            except ValueError:
                return False, "invalid-endpoint-offset"
        perimeter_key = "exitPerimeter" if role == "source" else "entryPerimeter"
        shape_kind = native_shape_kind(vertex_id)
        if shape_kind in {"rhombus", "ellipse", "hexagon"}:
            if cardinal_port_side(relative_port) is None:
                return False, f"non-cardinal-{shape_kind}-port"
            return True, None
        if shape_kind == "triangle":
            if cardinal_port_side(relative_port) not in {"left", "right"}:
                return False, "non-axial-triangle-port"
            return True, None
        if edge_styles.get(perimeter_key, "1") != "0" and shape_kind != "rectangle":
            return False, "unsupported-perimeter"
        return True, None

    def target_approach_matches(side, waypoint, port, rectangle):
        if side == "left":
            return waypoint[0] < rectangle["x"] and abs(waypoint[1] - port[1]) <= 1.0
        if side == "right":
            return waypoint[0] > rectangle["right"] and abs(waypoint[1] - port[1]) <= 1.0
        if side == "top":
            return waypoint[1] < rectangle["y"] and abs(waypoint[0] - port[0]) <= 1.0
        if side == "bottom":
            return waypoint[1] > rectangle["bottom"] and abs(waypoint[0] - port[0]) <= 1.0
        return True

    def source_departure_matches(side, waypoint, port, rectangle):
        if side == "left":
            return waypoint[0] < rectangle["x"] and abs(waypoint[1] - port[1]) <= 1.0
        if side == "right":
            return waypoint[0] > rectangle["right"] and abs(waypoint[1] - port[1]) <= 1.0
        if side == "top":
            return waypoint[1] < rectangle["y"] and abs(waypoint[0] - port[0]) <= 1.0
        if side == "bottom":
            return waypoint[1] > rectangle["bottom"] and abs(waypoint[0] - port[0]) <= 1.0
        return True

    geometry_epsilon = 1e-7

    def non_zero_segments(path):
        return [
            {"index": index, "start": start, "end": end}
            for index, (start, end) in enumerate(zip(path, path[1:]))
            if math.hypot(end[0] - start[0], end[1] - start[1]) > geometry_epsilon
        ]

    def segment_orientation(segment):
        delta_x = segment["end"][0] - segment["start"][0]
        delta_y = segment["end"][1] - segment["start"][1]
        if abs(delta_x) <= geometry_epsilon:
            return "vertical"
        if abs(delta_y) <= geometry_epsilon:
            return "horizontal"
        return "diagonal"

    def polyline_bend_count(path):
        orientations = [segment_orientation(segment) for segment in non_zero_segments(path)]
        return sum(
            first != second for first, second in zip(orientations, orientations[1:])
        )

    def redundant_waypoint_indexes(path, waypoint_count):
        redundant = []
        for waypoint_index in range(waypoint_count):
            path_index = waypoint_index + 1
            previous = path[path_index - 1]
            current = path[path_index]
            following = path[path_index + 1]
            if point_equal(previous, current) or point_equal(current, following):
                redundant.append(waypoint_index)
                continue
            cross = (current[0] - previous[0]) * (following[1] - current[1]) - (
                current[1] - previous[1]
            ) * (following[0] - current[0])
            if abs(cross) <= geometry_epsilon:
                redundant.append(waypoint_index)
        return redundant

    def point_equal(first, second, tolerance=geometry_epsilon):
        return math.isclose(first[0], second[0], abs_tol=tolerance) and math.isclose(
            first[1], second[1], abs_tol=tolerance
        )

    def point_on_segment(point, start, end):
        cross = (point[0] - start[0]) * (end[1] - start[1]) - (
            point[1] - start[1]
        ) * (end[0] - start[0])
        if abs(cross) > geometry_epsilon:
            return False
        return (
            min(start[0], end[0]) - geometry_epsilon
            <= point[0]
            <= max(start[0], end[0]) + geometry_epsilon
            and min(start[1], end[1]) - geometry_epsilon
            <= point[1]
            <= max(start[1], end[1]) + geometry_epsilon
        )

    def segment_relation(first, second):
        a, b = first["start"], first["end"]
        c, d = second["start"], second["end"]
        ab = (b[0] - a[0], b[1] - a[1])
        cd = (d[0] - c[0], d[1] - c[1])
        denominator = ab[0] * cd[1] - ab[1] * cd[0]
        offset = (c[0] - a[0], c[1] - a[1])
        if abs(denominator) <= geometry_epsilon:
            if abs(offset[0] * ab[1] - offset[1] * ab[0]) > geometry_epsilon:
                return None
            axis = 0 if abs(ab[0]) >= abs(ab[1]) else 1
            first_low, first_high = sorted((a[axis], b[axis]))
            second_low, second_high = sorted((c[axis], d[axis]))
            low = max(first_low, second_low)
            high = min(first_high, second_high)
            if high - low > geometry_epsilon:
                def projected_point(value, start, end):
                    delta = end[axis] - start[axis]
                    ratio = 0.0 if abs(delta) <= geometry_epsilon else (value - start[axis]) / delta
                    return (
                        start[0] + (end[0] - start[0]) * ratio,
                        start[1] + (end[1] - start[1]) * ratio,
                    )
                return {
                    "kind": "collinear-overlap",
                    "overlap": [projected_point(low, a, b), projected_point(high, a, b)],
                }
            if math.isclose(high, low, abs_tol=geometry_epsilon):
                point = next(
                    (candidate for candidate in (a, b, c, d) if point_on_segment(candidate, a, b) and point_on_segment(candidate, c, d)),
                    None,
                )
                if point is not None:
                    return {"kind": "touch", "point": point}
            return None
        t = (offset[0] * cd[1] - offset[1] * cd[0]) / denominator
        u = (offset[0] * ab[1] - offset[1] * ab[0]) / denominator
        if not (-geometry_epsilon <= t <= 1 + geometry_epsilon and -geometry_epsilon <= u <= 1 + geometry_epsilon):
            return None
        point = (a[0] + t * ab[0], a[1] + t * ab[1])
        endpoint = (
            t <= geometry_epsilon
            or t >= 1 - geometry_epsilon
            or u <= geometry_epsilon
            or u >= 1 - geometry_epsilon
        )
        return {"kind": "touch" if endpoint else "proper-crossing", "point": point}

    def segment_rectangle_distance(segment, rectangle):
        start, end = segment["start"], segment["end"]
        if strict_segment_intersects_rectangle(start, end, rectangle):
            return 0.0
        corners = (
            (rectangle["x"], rectangle["y"]),
            (rectangle["right"], rectangle["y"]),
            (rectangle["right"], rectangle["bottom"]),
            (rectangle["x"], rectangle["bottom"]),
        )
        sides = tuple(
            {"start": corners[index], "end": corners[(index + 1) % len(corners)]}
            for index in range(len(corners))
        )
        if any(segment_relation(segment, side) is not None for side in sides):
            return 0.0

        def point_segment_distance(point, first, second):
            delta = (second[0] - first[0], second[1] - first[1])
            length_squared = delta[0] * delta[0] + delta[1] * delta[1]
            if length_squared <= geometry_epsilon:
                return math.hypot(point[0] - first[0], point[1] - first[1])
            ratio = ((point[0] - first[0]) * delta[0] + (point[1] - first[1]) * delta[1]) / length_squared
            ratio = max(0.0, min(1.0, ratio))
            projected = (first[0] + ratio * delta[0], first[1] + ratio * delta[1])
            return math.hypot(point[0] - projected[0], point[1] - projected[1])

        distances = [
            point_segment_distance(corner, start, end) for corner in corners
        ]
        distances.extend(
            point_segment_distance(point, side["start"], side["end"])
            for point in (start, end)
            for side in sides
        )
        return min(distances)

    checked_edges = 0
    exact_edges = 0
    approximate_edges = 0
    unverifiable_edges = 0
    labeled_edges = 0
    unverifiable_labels = 0
    label_records = []
    route_records = []
    autoroute_transit_records = []
    autoroute_vertex_segment_checks = 0
    bend_quality_records = []
    bend_quality_vertex_segment_checks = 0
    port_entries = []
    cell_order = {logical.id: index for index, logical in enumerate(page_cells)}
    sibling_order = {}
    sibling_counts = {}
    for logical in page_cells:
        parent_key = logical.cell.get("parent")
        sibling_order[logical.id] = sibling_counts.get(parent_key, 0)
        sibling_counts[parent_key] = sibling_order[logical.id] + 1
    for edge in page_cells:
        if edge.cell.get("edge") != "1":
            continue
        if misplaced_waypoint_arrays(edge):
            warn(
                "MISPLACED_WAYPOINT_ARRAY",
                edge.id,
                "waypoints-outside-geometry",
            )
        geometry = cell_geometry(edge)
        label = logical_label(edge)
        has_label_position = False
        if label is not None and label.strip():
            labeled_edges += 1
            unverifiable_labels += 1
            if geometry is not None:
                has_label_position = geometry.get("x") is not None or geometry.get("y") is not None
                has_label_position = has_label_position or any(
                    local_name(child.tag) == "mxPoint" and child.get("as") == "offset"
                    for child in list(geometry)
                )
            warn(
                "UNVERIFIABLE_EDGE_LABEL",
                edge.id,
                "renderer-dependent-bounds",
                placement="explicit" if has_label_position else "default",
            )
            if not has_label_position:
                advise("EDGE_LABEL_WITHOUT_OFFSET", edge.id, "default-placement")

        if geometry is None:
            warn("UNVERIFIABLE_ROUTE", edge.id, "missing-geometry")
            unverifiable_edges += 1
            continue
        styles = native_style(edge.cell)
        edge_style = styles.get("edgeStyle", "")
        renderer_dependent = (
            bool(edge_style and edge_style != "none")
            or styles.get("orthogonal") == "1"
        )
        missing_ports = [
            key for key in ("exitX", "exitY", "entryX", "entryY") if key not in styles
        ]
        if missing_ports:
            advise(
                "MISSING_EXPLICIT_PORT",
                edge.id,
                "renderer-selects-endpoints",
                missing=missing_ports,
            )
        offset = (0.0, 0.0)
        parent_id = edge.cell.get("parent")
        if parent_id in rectangles:
            offset = (rectangles[parent_id]["x"], rectangles[parent_id]["y"])

        source_id = edge.cell.get("source")
        target_id = edge.cell.get("target")
        start = center(rectangles[source_id]) if source_id in rectangles else None
        end = center(rectangles[target_id]) if target_id in rectangles else None
        source_port = None
        target_port = None
        source_projection = None
        target_projection = None
        invalid_ports = []
        if source_id in rectangles:
            port, source_port, port_status = explicit_port(
                rectangles[source_id], styles, "exitX", "exitY"
            )
            if port_status == "valid":
                start, source_projection = resolve_explicit_port(
                    source_id, rectangles[source_id], styles, "source", source_port
                )
            elif port_status == "invalid":
                invalid_ports.extend(["exitX", "exitY"])
        if target_id in rectangles:
            port, target_port, port_status = explicit_port(
                rectangles[target_id], styles, "entryX", "entryY"
            )
            if port_status == "valid":
                end, target_projection = resolve_explicit_port(
                    target_id, rectangles[target_id], styles, "target", target_port
                )
            elif port_status == "invalid":
                invalid_ports.extend(["entryX", "entryY"])
        if invalid_ports:
            warn(
                "UNVERIFIABLE_ROUTE",
                edge.id,
                "invalid-explicit-port",
                invalid=invalid_ports,
            )
            unverifiable_edges += 1
            continue
        waypoints = []
        invalid_point = False
        for child in list(geometry):
            tag = local_name(child.tag)
            role = child.get("as")
            if tag == "mxPoint" and role in ("sourcePoint", "targetPoint"):
                point = point_from_element(child, offset)
                if point is None:
                    invalid_point = True
                if role == "sourcePoint" and start is None:
                    start = point
                elif role == "targetPoint" and end is None:
                    end = point
            elif tag == "Array" and role == "points":
                for point_element in list(child):
                    if local_name(point_element.tag) != "mxPoint":
                        continue
                    point = point_from_element(point_element, offset)
                    if point is None:
                        invalid_point = True
                    else:
                        waypoints.append(point)

        if invalid_point:
            warn("UNVERIFIABLE_ROUTE", edge.id, "invalid-explicit-point")
            unverifiable_edges += 1
            continue

        if start is None or end is None:
            warn("UNVERIFIABLE_ROUTE", edge.id, "missing-endpoint")
            unverifiable_edges += 1
            continue

        label_path = [start, *waypoints, end]
        if label is not None and label.strip():
            try:
                font_size = float(styles.get("fontSize", "12"))
            except ValueError:
                font_size = 12.0
            metrics = estimated_text_metrics(label, font_size)
            try:
                relative_x = float(geometry.get("x", "0"))
                orthogonal_y = float(geometry.get("y", "0"))
            except ValueError:
                relative_x = 0.0
                orthogonal_y = 0.0
            anchor, direction = point_along_path(label_path, (relative_x + 1.0) / 2.0)
            label_offset = (0.0, 0.0)
            for child in list(geometry):
                if local_name(child.tag) == "mxPoint" and child.get("as") == "offset":
                    parsed = point_from_element(child, (0.0, 0.0))
                    if parsed is not None:
                        label_offset = parsed
                    break
            anchor = (
                anchor[0] - direction[1] * orthogonal_y + label_offset[0],
                anchor[1] + direction[0] * orthogonal_y + label_offset[1],
            )
            label_rectangle = {
                "x": anchor[0] - metrics["width"] / 2,
                "y": anchor[1] - metrics["height"] / 2,
                "width": metrics["width"],
                "height": metrics["height"],
                "right": anchor[0] + metrics["width"] / 2,
                "bottom": anchor[1] + metrics["height"] / 2,
            }
            label_records.append(
                {
                    "edgeId": edge.id,
                    "sourceId": source_id,
                    "targetId": target_id,
                    "bounds": label_rectangle,
                    "explicitPlacement": has_label_position,
                }
            )

        if styles.get("curved") == "1":
            warn("UNVERIFIABLE_ROUTE", edge.id, "curved-edge")
            unverifiable_edges += 1
            continue

        segments = non_zero_segments(label_path)
        if not segments:
            warn("UNVERIFIABLE_ROUTE", edge.id, "zero-length-path")
            unverifiable_edges += 1
            continue
        source_side = boundary_port_side(source_port)
        target_side = boundary_port_side(target_port)
        source_port_supported = False
        target_port_supported = False
        for role, vertex_id, relative_port, projection in (
            ("source", source_id, source_port, source_projection),
            ("target", target_id, target_port, target_projection),
        ):
            if (
                renderer_dependent
                and relative_port is not None
                and projection is not None
                and projection["projected"]
            ):
                raw_point = projection["rawPoint"]
                projected_point = projection["projectedPoint"]
                advise(
                    "EDGE_SHAPE_PORT_PROJECTION_RISK",
                    edge.id,
                    "orthogonal-port-projects-to-nonrectangular-perimeter",
                    dedupe_key=role,
                    endpoint=role,
                    vertexId=vertex_id,
                    shape=projection["shape"],
                    relativePort={"x": relative_port[0], "y": relative_port[1]},
                    rawPoint={"x": raw_point[0], "y": raw_point[1]},
                    projectedPoint={"x": projected_point[0], "y": projected_point[1]},
                    projectionDistance=round(
                        math.hypot(
                            projected_point[0] - raw_point[0],
                            projected_point[1] - raw_point[1],
                        ),
                        3,
                    ),
                )
                add_risk(
                    "EDGE_SHAPE_PORT_PROJECTION_RISK",
                    rectangles.get(vertex_id),
                    [edge.id, vertex_id],
                    1,
                )
        if source_port is not None:
            source_port_supported, unsupported_reason = supported_port_geometry(
                source_id, styles, "source", source_port
            )
            if not source_port_supported:
                warn(
                    "UNVERIFIABLE_PORT_GEOMETRY",
                    edge.id,
                    unsupported_reason,
                    dedupe_key="source",
                    endpoint="source",
                    vertexId=source_id,
                )
        if target_port is not None:
            target_port_supported, unsupported_reason = supported_port_geometry(
                target_id, styles, "target", target_port
            )
            if not target_port_supported:
                warn(
                    "UNVERIFIABLE_PORT_GEOMETRY",
                    edge.id,
                    unsupported_reason,
                    dedupe_key="target",
                    endpoint="target",
                    vertexId=target_id,
                )
        if renderer_dependent and waypoints and segments:
            for role, vertex_id, relative_port, projection, adjacent_point, supported in (
                (
                    "source",
                    source_id,
                    source_port,
                    source_projection,
                    segments[0]["end"],
                    source_port_supported,
                ),
                (
                    "target",
                    target_id,
                    target_port,
                    target_projection,
                    segments[-1]["start"],
                    target_port_supported,
                ),
            ):
                if relative_port is None or projection is None:
                    continue
                if supported and not projection["projected"]:
                    continue
                anchor = projection["projectedPoint"]
                if not (
                    math.isclose(adjacent_point[0], anchor[0], abs_tol=1.0)
                    or math.isclose(adjacent_point[1], anchor[1], abs_tol=1.0)
                ):
                    warn(
                        "EDGE_TERMINAL_DOGLEG_RISK",
                        edge.id,
                        "orthogonal-last-mile-requires-extra-bend",
                        dedupe_key=role,
                        endpoint=role,
                        vertexId=vertex_id,
                        shape=projection["shape"],
                        anchor={"x": anchor[0], "y": anchor[1]},
                        adjacentPathPoint={
                            "x": adjacent_point[0],
                            "y": adjacent_point[1],
                        },
                    )
                    add_risk(
                        "EDGE_TERMINAL_DOGLEG_RISK",
                        union_rectangles(
                            (
                                rectangles.get(vertex_id),
                                {
                                    "x": adjacent_point[0] - 1.0,
                                    "y": adjacent_point[1] - 1.0,
                                    "width": 2.0,
                                    "height": 2.0,
                                    "right": adjacent_point[0] + 1.0,
                                    "bottom": adjacent_point[1] + 1.0,
                                },
                            )
                        ),
                        [edge.id, vertex_id],
                        3,
                    )
            redundant_indexes = redundant_waypoint_indexes(label_path, len(waypoints))
            if redundant_indexes:
                warn(
                    "EDGE_REDUNDANT_WAYPOINT",
                    edge.id,
                    "duplicate-or-collinear-waypoint",
                    waypointIndexes=redundant_indexes,
                )
                add_risk(
                    "EDGE_REDUNDANT_WAYPOINT",
                    union_rectangles(
                        {
                            "x": waypoints[index][0] - 2.0,
                            "y": waypoints[index][1] - 2.0,
                            "width": 4.0,
                            "height": 4.0,
                            "right": waypoints[index][0] + 2.0,
                            "bottom": waypoints[index][1] + 2.0,
                        }
                        for index in redundant_indexes
                    ),
                    [edge.id],
                    2,
                )
            if source_port_supported and target_port_supported:
                excluded = {source_id, target_id, parent_id}
                excluded.update(ancestor_map.get(source_id, set()))
                excluded.update(ancestor_map.get(target_id, set()))
                comparable = [
                    (vertex_id, rectangle)
                    for vertex_id, rectangle in rectangles.items()
                    if vertex_id not in excluded
                    and visual_container_kind(cell_map[vertex_id]) is None
                ]
                if math.isclose(start[0], end[0], abs_tol=geometry_epsilon) or math.isclose(
                    start[1], end[1], abs_tol=geometry_epsilon
                ):
                    candidates = [(0, non_zero_segments((start, end)))]
                else:
                    candidates = [
                        (
                            1,
                            non_zero_segments((start, (end[0], start[1]), end)),
                        ),
                        (
                            1,
                            non_zero_segments((start, (start[0], end[1]), end)),
                        ),
                    ]
                valid_candidates = []
                for bend_count, candidate_segments in candidates:
                    if not candidate_segments:
                        continue
                    if not source_departure_matches(
                        source_side,
                        candidate_segments[0]["end"],
                        start,
                        rectangles[source_id],
                    ):
                        continue
                    if not target_approach_matches(
                        target_side,
                        candidate_segments[-1]["start"],
                        end,
                        rectangles[target_id],
                    ):
                        continue
                    valid_candidates.append((bend_count, candidate_segments))
                bend_quality_vertex_segment_checks += sum(
                    len(candidate_segments) * len(comparable)
                    for _, candidate_segments in valid_candidates
                )
                bend_quality_records.append(
                    {
                        "edgeId": edge.id,
                        "path": label_path,
                        "actualBends": polyline_bend_count(label_path),
                        "candidates": valid_candidates,
                        "comparable": comparable,
                    }
                )
        if source_port_supported:
            port_entries.append(
                {
                    "edgeId": edge.id,
                    "vertexId": source_id,
                    "role": "source",
                    "side": source_side,
                    "point": start,
                }
            )
        if target_port_supported:
            port_entries.append(
                {
                    "edgeId": edge.id,
                    "vertexId": target_id,
                    "role": "target",
                    "side": target_side,
                    "point": end,
                }
            )
        if (
            renderer_dependent
            and waypoints
            and segments
            and source_port_supported
            and source_id in rectangles
            and not source_departure_matches(
                source_side, segments[0]["end"], start, rectangles[source_id]
            )
        ):
            first_point = segments[0]["end"]
            warn(
                "SOURCE_PORT_DEPARTURE_MISMATCH",
                edge.id,
                "first-segment-not-on-source-port-normal",
                sourceId=source_id,
                sourceSide=source_side,
                sourcePort={"x": start[0], "y": start[1]},
                firstPathPoint={"x": first_point[0], "y": first_point[1]},
            )
            add_risk(
                "SOURCE_PORT_DEPARTURE_MISMATCH",
                union_rectangles(
                    (
                        rectangles[source_id],
                        {
                            "x": first_point[0] - 1.0,
                            "y": first_point[1] - 1.0,
                            "width": 2.0,
                            "height": 2.0,
                            "right": first_point[0] + 1.0,
                            "bottom": first_point[1] + 1.0,
                        },
                    )
                ),
                [edge.id, source_id],
                3,
            )
        if (
            renderer_dependent
            and waypoints
            and segments
            and target_port_supported
            and target_id in rectangles
            and not target_approach_matches(
                target_side, segments[-1]["start"], end, rectangles[target_id]
            )
        ):
            last_point = segments[-1]["start"]
            warn(
                "TARGET_PORT_APPROACH_MISMATCH",
                edge.id,
                "last-waypoint-not-on-target-port-normal",
                targetId=target_id,
                targetSide=target_side,
                targetPort={"x": end[0], "y": end[1]},
                lastWaypoint={"x": last_point[0], "y": last_point[1]},
            )
            add_risk(
                "TARGET_PORT_APPROACH_MISMATCH",
                union_rectangles(
                    (
                        rectangles[target_id],
                        {
                            "x": last_point[0] - 1.0,
                            "y": last_point[1] - 1.0,
                            "width": 2.0,
                            "height": 2.0,
                            "right": last_point[0] + 1.0,
                            "bottom": last_point[1] + 1.0,
                        },
                    )
                ),
                [edge.id, target_id],
                3,
            )
        if renderer_dependent and not waypoints:
            if math.isclose(start[0], end[0], abs_tol=geometry_epsilon) or math.isclose(
                start[1], end[1], abs_tol=geometry_epsilon
            ):
                candidate_paths = [("direct", non_zero_segments((start, end)))]
            else:
                candidate_paths = [
                    (
                        "horizontal-first",
                        non_zero_segments((start, (end[0], start[1]), end)),
                    ),
                    (
                        "vertical-first",
                        non_zero_segments((start, (start[0], end[1]), end)),
                    ),
                ]
            excluded = {source_id, target_id, parent_id}
            excluded.update(ancestor_map.get(source_id, set()))
            excluded.update(ancestor_map.get(target_id, set()))
            comparable = [
                (vertex_id, rectangle)
                for vertex_id, rectangle in rectangles.items()
                if vertex_id not in excluded
                and visual_container_kind(cell_map[vertex_id]) is None
            ]
            autoroute_vertex_segment_checks += sum(
                len(candidate_segments) * len(comparable)
                for _, candidate_segments in candidate_paths
            )
            for vertex_id, rectangle in comparable:
                blocked_candidates = [
                    candidate_name
                    for candidate_name, candidate_segments in candidate_paths
                    if any(
                        strict_segment_intersects_rectangle(
                            segment["start"], segment["end"], rectangle
                        )
                        for segment in candidate_segments
                    )
                ]
                if blocked_candidates:
                    autoroute_transit_records.append(
                        {
                            "edgeId": edge.id,
                            "vertexId": vertex_id,
                            "candidatePaths": blocked_candidates,
                            "allSimpleCandidatesBlocked": len(blocked_candidates)
                            == len(candidate_paths),
                        }
                    )
            warn("UNVERIFIABLE_ROUTE", edge.id, "renderer-dependent-routing", edgeStyle=edge_style)
            unverifiable_edges += 1
            continue
        certainty = "approximate" if renderer_dependent else "exact"
        if certainty == "approximate":
            warn("ROUTE_APPROXIMATION", edge.id, "renderer-dependent-waypoints", edgeStyle=edge_style)
            approximate_edges += 1
        else:
            exact_edges += 1

        path = label_path
        route_records.append(
            {
                "edgeId": edge.id,
                "sourceId": source_id,
                "targetId": target_id,
                "parentId": parent_id,
                "documentOrder": cell_order[edge.id],
                "siblingOrder": sibling_order[edge.id],
                "pathPoints": path,
                "segments": segments,
                "certainty": certainty,
                "sourcePort": start if source_port_supported else None,
                "targetPort": end if target_port_supported else None,
                "styles": styles,
                "curved": styles.get("curved") == "1",
                "jumpStyle": styles.get("jumpStyle", "none"),
                "noJump": styles.get("noJump") == "1",
            }
        )
        checked_edges += 1

    total_edge_pairs = edge_count * (edge_count - 1) // 2
    checked_edge_pairs = len(route_records) * (len(route_records) - 1) // 2
    edge_vertex_segment_checks = (
        autoroute_vertex_segment_checks + bend_quality_vertex_segment_checks
    )
    for record in route_records:
        excluded = {record["sourceId"], record["targetId"], record["parentId"]}
        excluded.update(ancestor_map.get(record["sourceId"], set()))
        excluded.update(ancestor_map.get(record["targetId"], set()))
        comparable_count = sum(vertex_id not in excluded for vertex_id in rectangles)
        edge_vertex_segment_checks += len(record["segments"]) * comparable_count
    edge_edge_segment_checks = sum(
        len(first["segments"]) * len(second["segments"])
        for index, first in enumerate(route_records)
        for second in route_records[index + 1 :]
    )
    label_pair_checks = len(label_records) * (len(label_records) - 1) // 2
    comparison_count = (
        vertex_pair_checks
        + edge_vertex_segment_checks
        + edge_edge_segment_checks
        + label_pair_checks
    )
    if comparison_count > MAX_LAYOUT_COMPARISONS:
        raise CliError(
            "LAYOUT_CHECK_LIMIT",
            "Page is too large for the lightweight segment-aware layout check.",
            {
                "page": page.id or page.name,
                "vertices": len(vertex_ids),
                "edges": edge_count,
                "vertexPairs": vertex_pair_checks,
                "edgeVertexSegmentChecks": edge_vertex_segment_checks,
                "edgeEdgeSegmentChecks": edge_edge_segment_checks,
                "labelPairs": label_pair_checks,
                "estimatedComparisons": comparison_count,
                "limit": MAX_LAYOUT_COMPARISONS,
            },
        )

    for transit in autoroute_transit_records:
        edge_id = transit["edgeId"]
        vertex_id = transit["vertexId"]
        warn(
            "EDGE_AUTOROUTE_VERTEX_TRANSIT_RISK",
            edge_id,
            "simple-orthogonal-candidate-crosses-unrelated-vertex",
            dedupe_key=vertex_id,
            vertexId=vertex_id,
            candidatePaths=transit["candidatePaths"],
            allSimpleCandidatesBlocked=transit["allSimpleCandidatesBlocked"],
        )
        add_risk(
            "EDGE_AUTOROUTE_VERTEX_TRANSIT_RISK",
            rectangles.get(vertex_id),
            [edge_id, vertex_id],
            2,
        )

    for quality in bend_quality_records:
        clear_bend_counts = []
        for bend_count, candidate_segments in quality["candidates"]:
            if any(
                strict_segment_intersects_rectangle(
                    segment["start"], segment["end"], rectangle
                )
                for segment in candidate_segments
                for _, rectangle in quality["comparable"]
            ):
                continue
            clear_bend_counts.append(bend_count)
        if not clear_bend_counts:
            continue
        minimum_bends = min(clear_bend_counts)
        if quality["actualBends"] <= minimum_bends:
            continue
        edge_id = quality["edgeId"]
        warn(
            "EDGE_REDUNDANT_BEND_RISK",
            edge_id,
            "clearer-route-exists-with-fewer-bends",
            actualBends=quality["actualBends"],
            minimumFeasibleBends=minimum_bends,
        )
        path = quality["path"]
        add_risk(
            "EDGE_REDUNDANT_BEND_RISK",
            union_rectangles(
                {
                    "x": point[0] - 2.0,
                    "y": point[1] - 2.0,
                    "width": 4.0,
                    "height": 4.0,
                    "right": point[0] + 2.0,
                    "bottom": point[1] + 2.0,
                }
                for point in path
            ),
            [edge_id],
            2,
        )

    for record in route_records:
        edge_id = record["edgeId"]
        excluded = {record["sourceId"], record["targetId"], record["parentId"]}
        excluded.update(ancestor_map.get(record["sourceId"], set()))
        excluded.update(ancestor_map.get(record["targetId"], set()))
        for vertex_id, rectangle in rectangles.items():
            if vertex_id in excluded:
                continue
            if not any(
                strict_segment_intersects_rectangle(
                    segment["start"], segment["end"], rectangle
                )
                for segment in record["segments"]
            ):
                continue
            container_kind = visual_container_kind(cell_map[vertex_id])
            if container_kind is not None:
                header = (
                    swimlane_header_rectangle(cell_map[vertex_id], rectangle)
                    if container_kind == "swimlane"
                    else None
                )
                crosses_header = header is not None and any(
                    strict_segment_intersects_rectangle(
                        segment["start"], segment["end"], header
                    )
                    for segment in record["segments"]
                )
                if crosses_header and record["certainty"] == "exact":
                    reserve_finding()
                    collisions.append(
                        {
                            "type": "EDGE_CONTAINER_HEADER_INTERSECTION",
                            "page": page.id or page.name,
                            "edgeId": edge_id,
                            "cellId": vertex_id,
                            "certainty": record["certainty"],
                        }
                    )
                    add_risk("EDGE_CONTAINER_HEADER_INTERSECTION", header, [edge_id, vertex_id], 3)
                elif crosses_header:
                    warn(
                        "EDGE_CONTAINER_HEADER_INTERSECTION_RISK",
                        edge_id,
                        "approximate-route",
                        containerId=vertex_id,
                    )
                    add_risk("EDGE_CONTAINER_HEADER_INTERSECTION_RISK", header, [edge_id, vertex_id])
                else:
                    advise(
                        "EDGE_CONTAINER_TRANSIT",
                        edge_id,
                        "unrelated-container-body",
                        containerId=vertex_id,
                        certainty=record["certainty"],
                    )
            else:
                reserve_finding()
                collisions.append(
                    {
                        "type": "EDGE_VERTEX_INTERSECTION",
                        "page": page.id or page.name,
                        "edgeId": edge_id,
                        "cellId": vertex_id,
                        "certainty": record["certainty"],
                    }
                )
                add_risk("EDGE_VERTEX_INTERSECTION", rectangle, [edge_id, vertex_id], 3)

    def compact_point(point):
        return {"x": round(point[0], 3), "y": round(point[1], 3)}

    def event_bounds(event):
        if event.get("point") is not None:
            point = event["point"]
            return {
                "x": point[0] - 1.0,
                "y": point[1] - 1.0,
                "width": 2.0,
                "height": 2.0,
                "right": point[0] + 1.0,
                "bottom": point[1] + 1.0,
            }
        overlap = event.get("overlap")
        if overlap is not None:
            left = min(overlap[0][0], overlap[1][0])
            top = min(overlap[0][1], overlap[1][1])
            right = max(overlap[0][0], overlap[1][0])
            bottom = max(overlap[0][1], overlap[1][1])
            return {
                "x": left,
                "y": top,
                "width": max(1.0, right - left),
                "height": max(1.0, bottom - top),
                "right": max(left + 1.0, right),
                "bottom": max(top + 1.0, bottom),
            }
        return None

    def add_pair_finding(code, first, second, reason, events, priority, warning=True, **details):
        first_id, second_id = sorted((first["edgeId"], second["edgeId"]))
        reserve_finding()
        serialized_events = []
        for event in events[:MAX_EDGE_PAIR_EVENTS]:
            segment_indexes = event["segmentIndexes"]
            if first["edgeId"] != first_id:
                segment_indexes = list(reversed(segment_indexes))
            serialized = {
                "intersectionKind": event["kind"],
                "segmentIndexes": segment_indexes,
                "certainty": event["certainty"],
            }
            if event.get("point") is not None:
                serialized["point"] = compact_point(event["point"])
            if event.get("overlap") is not None:
                serialized["overlap"] = [compact_point(point) for point in event["overlap"]]
            if event.get("distance") is not None:
                serialized["distance"] = round(event["distance"], 3)
            serialized_events.append(serialized)
        item = {
            "code": code,
            "page": page.id or page.name,
            "cellId": first_id,
            "otherEdgeId": second_id,
            "edgeIds": [first_id, second_id],
            "reason": reason,
            "events": serialized_events,
            "omittedEventCount": max(0, len(events) - MAX_EDGE_PAIR_EVENTS),
        }
        item.update(details)
        (warnings if warning else advisories).append(item)
        bounds = union_rectangles(
            bound for bound in (event_bounds(event) for event in events) if bound is not None
        )
        add_risk(code, bounds, [first_id, second_id], priority)

    def shared_terminal_touch(first, second, point):
        shared = {
            first["sourceId"], first["targetId"]
        }.intersection({second["sourceId"], second["targetId"]})
        shared.discard(None)
        for terminal_id in shared:
            first_point = (
                first["pathPoints"][0]
                if terminal_id == first["sourceId"]
                else first["pathPoints"][-1]
            )
            second_point = (
                second["pathPoints"][0]
                if terminal_id == second["sourceId"]
                else second["pathPoints"][-1]
            )
            if point_equal(point, first_point) and point_equal(point, second_point):
                return True
        return False

    def jump_candidate(first, second, later_segment, point):
        if first["parentId"] != second["parentId"]:
            return False, "render-order-unverifiable"
        earlier, later = sorted((first, second), key=lambda record: record["siblingOrder"])
        if later["curved"]:
            return False, "later-edge-curved"
        if later["jumpStyle"] in (None, "", "none"):
            return False, "later-edge-without-jump"
        if earlier["noJump"]:
            return False, "earlier-edge-no-jump"
        try:
            jump_size = float(later["styles"].get("jumpSize", "6"))
            stroke_width = float(later["styles"].get("strokeWidth", "1"))
        except ValueError:
            return False, "invalid-jump-geometry"
        required = max(0.0, (jump_size - 2.0) / 2.0 + stroke_width)
        if (
            math.hypot(point[0] - later_segment["start"][0], point[1] - later_segment["start"][1]) <= required
            or math.hypot(point[0] - later_segment["end"][0], point[1] - later_segment["end"][1]) <= required
        ):
            return False, "insufficient-jump-clearance"
        return True, "eligible"

    def parallel_channel_event(first_segment, second_segment, certainty):
        a, b = first_segment["start"], first_segment["end"]
        c, d = second_segment["start"], second_segment["end"]
        first_vector = (b[0] - a[0], b[1] - a[1])
        second_vector = (d[0] - c[0], d[1] - c[1])
        first_length = math.hypot(*first_vector)
        second_length = math.hypot(*second_vector)
        cross = first_vector[0] * second_vector[1] - first_vector[1] * second_vector[0]
        if abs(cross) > geometry_epsilon * first_length * second_length:
            return None
        unit = (first_vector[0] / first_length, first_vector[1] / first_length)
        distance = abs((c[0] - a[0]) * unit[1] - (c[1] - a[1]) * unit[0])
        if distance <= geometry_epsilon or distance >= 24.0:
            return None
        first_projection = sorted((0.0, first_length))
        second_projection = sorted(
            (
                (c[0] - a[0]) * unit[0] + (c[1] - a[1]) * unit[1],
                (d[0] - a[0]) * unit[0] + (d[1] - a[1]) * unit[1],
            )
        )
        overlap_low = max(first_projection[0], second_projection[0])
        overlap_high = min(first_projection[1], second_projection[1])
        if overlap_high - overlap_low <= geometry_epsilon:
            return None
        midpoint = (overlap_low + overlap_high) / 2.0
        return {
            "kind": "parallel-channel",
            "segmentIndexes": [first_segment["index"], second_segment["index"]],
            "certainty": certainty,
            "distance": distance,
            "point": (a[0] + unit[0] * midpoint, a[1] + unit[1] * midpoint),
            "overlap": None,
        }

    for first_index, first in enumerate(route_records):
        for second in route_records[first_index + 1 :]:
            certainty = "approximate" if "approximate" in (first["certainty"], second["certainty"]) else "exact"
            grouped = {
                "EDGE_PATH_OVERLAP_RISK": [],
                "EDGE_CROSSING_RISK": [],
                "EDGE_CROSSING_WITH_JUMP": [],
                "EDGE_TOUCH_RISK": [],
                "EDGE_PARALLEL_CHANNEL_RISK": [],
            }
            jump_reasons = set()
            for first_segment in first["segments"]:
                for second_segment in second["segments"]:
                    relation = segment_relation(first_segment, second_segment)
                    if relation is None:
                        parallel = parallel_channel_event(first_segment, second_segment, certainty)
                        if parallel is not None:
                            grouped["EDGE_PARALLEL_CHANNEL_RISK"].append(parallel)
                        continue
                    event = {
                        "kind": relation["kind"],
                        "segmentIndexes": [first_segment["index"], second_segment["index"]],
                        "certainty": certainty,
                        "point": relation.get("point"),
                        "overlap": relation.get("overlap"),
                    }
                    if relation["kind"] == "collinear-overlap":
                        grouped["EDGE_PATH_OVERLAP_RISK"].append(event)
                    elif relation["kind"] == "touch":
                        if not shared_terminal_touch(first, second, relation["point"]):
                            grouped["EDGE_TOUCH_RISK"].append(event)
                    else:
                        later_record = max((first, second), key=lambda record: record["siblingOrder"])
                        later_segment = first_segment if later_record is first else second_segment
                        eligible, jump_reason = jump_candidate(
                            first, second, later_segment, relation["point"]
                        )
                        jump_reasons.add(jump_reason)
                        grouped[
                            "EDGE_CROSSING_WITH_JUMP" if eligible else "EDGE_CROSSING_RISK"
                        ].append(event)
            if grouped["EDGE_PATH_OVERLAP_RISK"]:
                add_pair_finding(
                    "EDGE_PATH_OVERLAP_RISK", first, second, "collinear-overlap",
                    grouped["EDGE_PATH_OVERLAP_RISK"], 3,
                )
            if grouped["EDGE_CROSSING_RISK"]:
                add_pair_finding(
                    "EDGE_CROSSING_RISK", first, second, "proper-crossing",
                    grouped["EDGE_CROSSING_RISK"], 2,
                    jumpEligibility="unverifiable",
                    jumpReasons=sorted(jump_reasons),
                )
            if grouped["EDGE_CROSSING_WITH_JUMP"]:
                add_pair_finding(
                    "EDGE_CROSSING_WITH_JUMP", first, second, "eligible-native-line-jump",
                    grouped["EDGE_CROSSING_WITH_JUMP"], 2,
                    jumpEligibility="eligible",
                )
            if grouped["EDGE_TOUCH_RISK"]:
                add_pair_finding(
                    "EDGE_TOUCH_RISK", first, second, "non-topological-touch",
                    grouped["EDGE_TOUCH_RISK"], 2,
                )
            if grouped["EDGE_PARALLEL_CHANNEL_RISK"]:
                add_pair_finding(
                    "EDGE_PARALLEL_CHANNEL_RISK", first, second, "parallel-channel-under-24px",
                    grouped["EDGE_PARALLEL_CHANNEL_RISK"], 1, warning=False,
                )

    port_groups = {}
    for entry in port_entries:
        port_groups.setdefault((entry["vertexId"], entry["side"]), []).append(entry)
    for (vertex_id, side), entries in port_groups.items():
        axis = 1 if side in ("left", "right") else 0
        entries.sort(key=lambda entry: (entry["point"][axis], entry["edgeId"], entry["role"]))
        duplicate_groups = []
        current = []
        current_coordinate = None
        for entry in entries:
            coordinate = entry["point"][axis]
            if current_coordinate is None or math.isclose(coordinate, current_coordinate, abs_tol=geometry_epsilon):
                current.append(entry)
            else:
                if len(current) > 1:
                    duplicate_groups.append(current)
                current = [entry]
            current_coordinate = coordinate
        if len(current) > 1:
            duplicate_groups.append(current)
        for duplicates in duplicate_groups:
            for index, first_entry in enumerate(duplicates):
                for second_entry in duplicates[index + 1 :]:
                    first_id, second_id = sorted((first_entry["edgeId"], second_entry["edgeId"]))
                    warn(
                        "EDGE_SHARED_PORT_RISK",
                        first_id,
                        "same-explicit-boundary-port",
                        dedupe_key=(first_id, second_id, vertex_id, side),
                        otherEdgeId=second_id,
                        edgeIds=[first_id, second_id],
                        vertexId=vertex_id,
                        side=side,
                        point=compact_point(first_entry["point"]),
                    )
                    add_risk("EDGE_SHARED_PORT_RISK", rectangles.get(vertex_id), [first_id, second_id, vertex_id], 3)
        distinct_entries = []
        for entry in entries:
            if not distinct_entries or not math.isclose(
                entry["point"][axis], distinct_entries[-1]["point"][axis], abs_tol=geometry_epsilon
            ):
                distinct_entries.append(entry)
        for first_entry, second_entry in zip(distinct_entries, distinct_entries[1:]):
            distance = abs(second_entry["point"][axis] - first_entry["point"][axis])
            if distance >= 12.0:
                continue
            first_id, second_id = sorted((first_entry["edgeId"], second_entry["edgeId"]))
            advise(
                "EDGE_PORT_SPACING_RISK",
                first_id,
                "adjacent-explicit-ports-under-12px",
                dedupe_key=(first_id, second_id, vertex_id, side),
                otherEdgeId=second_id,
                edgeIds=[first_id, second_id],
                vertexId=vertex_id,
                side=side,
                distance=round(distance, 3),
            )
            add_risk("EDGE_PORT_SPACING_RISK", rectangles.get(vertex_id), [first_id, second_id, vertex_id], 2)

    route_by_id = {record["edgeId"]: record for record in route_records}
    for label_record in label_records:
        if not label_record["explicitPlacement"]:
            continue
        record = route_by_id.get(label_record["edgeId"])
        if record is None:
            continue
        distance = min(
            segment_rectangle_distance(segment, label_record["bounds"])
            for segment in record["segments"]
        )
        if distance < 6.0:
            advise(
                "EDGE_LABEL_PATH_CLEARANCE_RISK",
                label_record["edgeId"],
                "explicit-label-under-6px-from-own-path",
                distance=round(distance, 3),
            )
            add_risk(
                "EDGE_LABEL_PATH_CLEARANCE_RISK",
                label_record["bounds"],
                [label_record["edgeId"]],
                2,
            )

    for label_record in label_records:
        label_rectangle = label_record["bounds"]
        edge_id = label_record["edgeId"]
        excluded = {
            label_record["sourceId"],
            label_record["targetId"],
        }
        for vertex_id, rectangle in rectangles.items():
            if visual_container_kind(cell_map[vertex_id]) != "swimlane":
                continue
            header = swimlane_header_rectangle(cell_map[vertex_id], rectangle)
            padded_header = expanded_rectangle(header, 4.0)
            if intersection(label_rectangle, padded_header) is None:
                continue
            warn(
                "EDGE_LABEL_CONTAINER_HEADER_RISK",
                edge_id,
                "estimated-label-bounds",
                containerId=vertex_id,
            )
            add_risk(
                "EDGE_LABEL_CONTAINER_HEADER_RISK",
                union_rectangles((label_rectangle, padded_header)),
                [edge_id, vertex_id],
                3,
            )
        for vertex_id, rectangle in rectangles.items():
            if vertex_id in excluded or visual_container_kind(cell_map[vertex_id]) is not None:
                continue
            if intersection(label_rectangle, expanded_rectangle(rectangle, 4.0)) is not None:
                warn(
                    "EDGE_LABEL_NEAR_VERTEX_RISK",
                    edge_id,
                    "estimated-label-bounds",
                    vertexId=vertex_id,
                )
                add_risk("EDGE_LABEL_NEAR_VERTEX_RISK", union_rectangles((label_rectangle, rectangle)), [edge_id, vertex_id])
                break
        if declared_page is not None and (
            label_rectangle["x"] < declared_page["x"]
            or label_rectangle["y"] < declared_page["y"]
            or label_rectangle["right"] > declared_page["right"]
            or label_rectangle["bottom"] > declared_page["bottom"]
        ):
            warn(
                "EDGE_LABEL_PAGE_RISK",
                edge_id,
                "estimated-label-bounds",
                bounds=compact_rectangle(label_rectangle),
            )
            add_risk("EDGE_LABEL_PAGE_RISK", label_rectangle, [edge_id])

    label_adjacency = {index: set() for index in range(len(label_records))}
    for index, first in enumerate(label_records):
        for second_index in range(index + 1, len(label_records)):
            second = label_records[second_index]
            if intersection(first["bounds"], second["bounds"]) is not None:
                warn(
                    "EDGE_LABEL_OVERLAP_RISK",
                    first["edgeId"],
                    "estimated-label-bounds",
                    otherEdgeId=second["edgeId"],
                )
                add_risk("EDGE_LABEL_OVERLAP_RISK", union_rectangles((first["bounds"], second["bounds"])), [first["edgeId"], second["edgeId"]])
            if intersection(expanded_rectangle(first["bounds"], 12.0), expanded_rectangle(second["bounds"], 12.0)) is not None:
                label_adjacency[index].add(second_index)
                label_adjacency[second_index].add(index)

    unseen = set(label_adjacency)
    while unseen:
        seed = unseen.pop()
        component = {seed}
        pending = [seed]
        while pending:
            current = pending.pop()
            for neighbor in label_adjacency[current]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    component.add(neighbor)
                    pending.append(neighbor)
        if len(component) >= 3:
            records = [label_records[index] for index in sorted(component)]
            edge_ids = [record["edgeId"] for record in records]
            bounds = union_rectangles(record["bounds"] for record in records)
            warn(
                "EDGE_LABEL_DENSITY_RISK",
                edge_ids[0],
                "three-or-more-nearby-labels",
                edgeIds=edge_ids,
                bounds=compact_rectangle(bounds),
            )
            add_risk("EDGE_LABEL_DENSITY_RISK", bounds, edge_ids)

    content_bounds = union_rectangles([*rectangles.values(), *(record["bounds"] for record in label_records)])
    occupied_page_tiles = None
    if declared_page is not None and content_bounds is not None:
        first_column = math.floor(content_bounds["x"] / declared_page["width"])
        last_column = math.ceil(content_bounds["right"] / declared_page["width"]) - 1
        first_row = math.floor(content_bounds["y"] / declared_page["height"])
        last_row = math.ceil(content_bounds["bottom"] / declared_page["height"]) - 1
        columns = max(1, last_column - first_column + 1)
        rows = max(1, last_row - first_row + 1)
        occupied_page_tiles = {"columns": columns, "rows": rows, "count": columns * rows}
        if content_bounds["x"] < 0 or content_bounds["y"] < 0:
            warn(
                "NEGATIVE_PAGE_COORDINATE_RISK",
                "__page__",
                "content-starts-before-page-origin",
                bounds=compact_rectangle(content_bounds),
            )
            add_risk("NEGATIVE_PAGE_COORDINATE_RISK", content_bounds, [], 2)
        if occupied_page_tiles["count"] > 1:
            details = {
                "bounds": compact_rectangle(content_bounds),
                "occupiedPageTiles": occupied_page_tiles,
            }
            if expect_single_page:
                warn(
                    "SINGLE_PAGE_BOUNDARY_EXCEEDED",
                    "__page__",
                    "content-occupies-multiple-page-tiles",
                    **details,
                )
                add_risk("SINGLE_PAGE_BOUNDARY_EXCEEDED", content_bounds, [], 2)
            else:
                advise(
                    "MULTI_PAGE_CONTENT",
                    "__page__",
                    "content-occupies-multiple-page-tiles",
                    **details,
                )

    merged_risks = []
    for risk in sorted(risk_items, key=lambda item: item["priority"], reverse=True):
        candidate = {
            "bounds": expanded_rectangle(risk["bounds"], 32.0),
            "cellIds": set(risk["cellIds"]),
            "reasons": {risk["reason"]},
            "priority": risk["priority"],
        }
        changed = True
        while changed:
            changed = False
            for existing in list(merged_risks):
                if intersection(candidate["bounds"], existing["bounds"]) is None:
                    continue
                candidate["bounds"] = union_rectangles((candidate["bounds"], existing["bounds"]))
                candidate["cellIds"].update(existing["cellIds"])
                candidate["reasons"].update(existing["reasons"])
                candidate["priority"] = max(candidate["priority"], existing["priority"])
                merged_risks.remove(existing)
                changed = True
        merged_risks.append(candidate)
    merged_risks.sort(
        key=lambda item: (
            -item["priority"],
            -(item["bounds"]["width"] * item["bounds"]["height"]),
        )
    )
    selected_risks = merged_risks[:8]
    omitted_risks = merged_risks[8:]
    omitted_high_priority_count = sum(risk["priority"] >= 2 for risk in omitted_risks)
    if omitted_risks:
        details = {
            "totalRiskRegionCount": len(merged_risks),
            "selectedRiskRegionCount": len(selected_risks),
            "omittedRiskRegionCount": len(omitted_risks),
            "omittedHighPriorityCount": omitted_high_priority_count,
        }
        if omitted_high_priority_count:
            warn(
                "QA_PLAN_TRUNCATED",
                "__page__",
                "high-priority-risk-regions-omitted",
                **details,
            )
        else:
            advise(
                "QA_PLAN_TRUNCATED",
                "__page__",
                "low-priority-risk-regions-omitted",
                **details,
            )
    full_page_bounds = declared_page or content_bounds or {
        "x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0,
        "right": 0.0, "bottom": 0.0,
    }
    review_targets = [
        {
            "type": "fullPage",
            "bounds": compact_rectangle(full_page_bounds),
            "checks": ["composition", "reading-order", "page-boundary", "edge-traceability"],
        }
    ]
    review_targets.extend(
        {
            "type": "riskRegion",
            "bounds": compact_rectangle(risk["bounds"]),
            "cellIds": sorted(risk["cellIds"]),
            "reasons": sorted(risk["reasons"]),
            "priority": risk["priority"],
        }
        for risk in selected_risks
    )

    status = "collision" if collisions else ("indeterminate" if warnings else "clear")
    return {
        "page": {"index": page.index, "id": page.id, "name": page.name},
        "status": status,
        "coverage": {
            "checkedVertices": len(rectangles),
            "totalVertices": len(vertex_ids),
            "checkedEdges": checked_edges,
            "totalEdges": edge_count,
            "checkedEdgePairs": checked_edge_pairs,
            "totalEdgePairs": total_edge_pairs,
            "exactEdges": exact_edges,
            "approximateEdges": approximate_edges,
            "unverifiableEdges": unverifiable_edges,
            "labeledEdges": labeled_edges,
            "unverifiableLabels": unverifiable_labels,
        },
        "collisions": collisions,
        "warnings": warnings,
        "advisories": advisories,
        "analysis": {
            "contentBounds": compact_rectangle(content_bounds),
            "declaredPageBounds": compact_rectangle(declared_page),
            "occupiedPageTiles": occupied_page_tiles,
            "estimatedEdgeLabels": len(label_records),
            "riskRegionCount": len(review_targets) - 1,
            "totalRiskRegionCount": len(merged_risks),
            "selectedRiskRegionCount": len(selected_risks),
            "omittedRiskRegionCount": len(omitted_risks),
            "omittedHighPriorityCount": omitted_high_priority_count,
        },
        "qaPlan": {
            "reviewTargets": review_targets,
            "totalRiskRegionCount": len(merged_risks),
            "selectedRiskRegionCount": len(selected_risks),
            "omittedRiskRegionCount": len(omitted_risks),
            "omittedHighPriorityCount": omitted_high_priority_count,
        },
    }


def count_codes(items):
    counts = {}
    for item in items:
        code = item["code"]
        counts[code] = counts.get(code, 0) + 1
    return dict(sorted(counts.items()))


def check_layout_command(args):
    document = load_document(args.input)
    pages = select_pages(document, page_selector_from_args(args))
    page_results = [
        layout_page(page, expect_single_page=args.expect_single_page)
        for page in pages
    ]
    collisions = [
        collision
        for page_result in page_results
        for collision in page_result["collisions"]
    ]
    warnings = [
        warning
        for page_result in page_results
        for warning in page_result["warnings"]
    ]
    advisories = [
        advisory
        for page_result in page_results
        for advisory in page_result["advisories"]
    ]
    coverage_keys = (
        "checkedVertices",
        "totalVertices",
        "checkedEdges",
        "totalEdges",
        "checkedEdgePairs",
        "totalEdgePairs",
        "exactEdges",
        "approximateEdges",
        "unverifiableEdges",
        "labeledEdges",
        "unverifiableLabels",
    )
    coverage = {
        key: sum(page_result["coverage"][key] for page_result in page_results)
        for key in coverage_keys
    }
    status = "collision" if collisions else ("indeterminate" if warnings else "clear")
    warning_counts = count_codes(warnings)
    advisory_counts = count_codes(advisories)
    if status == "collision":
        action = "Patch deterministic collisions, then rerun check-layout."
    elif status == "indeterminate":
        action = "Rendered visual QA is required for renderer-dependent routes or labels."
    else:
        action = "Static checks are clear; render once before claiming final visual quality."
    if args.verbose:
        output_pages = page_results
        output_warnings = warnings
        output_advisories = advisories
    else:
        output_pages = [
            {
                "page": page_result["page"],
                "status": page_result["status"],
                "collisionCount": len(page_result["collisions"]),
                "coverage": page_result["coverage"],
                "analysis": page_result["analysis"],
                "qaPlan": {
                    "fullPageCount": 1,
                    "riskRegionCount": page_result["analysis"]["riskRegionCount"],
                    "totalRiskRegionCount": page_result["qaPlan"]["totalRiskRegionCount"],
                    "selectedRiskRegionCount": page_result["qaPlan"]["selectedRiskRegionCount"],
                    "omittedRiskRegionCount": page_result["qaPlan"]["omittedRiskRegionCount"],
                    "omittedHighPriorityCount": page_result["qaPlan"]["omittedHighPriorityCount"],
                    "riskReasons": sorted(
                        {
                            reason
                            for target in page_result["qaPlan"]["reviewTargets"]
                            if target["type"] == "riskRegion"
                            for reason in target["reasons"]
                        }
                    ),
                },
            }
            for page_result in page_results
        ]
        output_warnings = (
            [
                {
                    "code": "RENDERED_QA_REQUIRED",
                    "count": len(warnings),
                    "byCode": warning_counts,
                    "message": action,
                }
            ]
            if warnings
            else []
        )
        output_advisories = [
            {"code": code, "count": count}
            for code, count in advisory_counts.items()
        ]
    if args.only_collisions:
        output_warnings = []
        output_advisories = []
    return {
        "file": str(document.path),
        "revision": document.revision,
        "result": {
            "status": status,
            "collisionCount": len(collisions),
            "coverage": coverage,
            "renderRequired": bool(warnings),
            "visualQaRecommended": True,
            "qaPlan": {
                "pages": [
                    {
                        "page": page_result["page"],
                        "reviewTargets": page_result["qaPlan"]["reviewTargets"],
                        "totalRiskRegionCount": page_result["qaPlan"]["totalRiskRegionCount"],
                        "selectedRiskRegionCount": page_result["qaPlan"]["selectedRiskRegionCount"],
                        "omittedRiskRegionCount": page_result["qaPlan"]["omittedRiskRegionCount"],
                        "omittedHighPriorityCount": page_result["qaPlan"]["omittedHighPriorityCount"],
                    }
                    for page_result in page_results
                ]
                if args.verbose
                else [
                    {
                        "page": page_result["page"],
                        "fullPageCount": 1,
                        "riskRegionCount": page_result["analysis"]["riskRegionCount"],
                        "totalRiskRegionCount": page_result["qaPlan"]["totalRiskRegionCount"],
                        "selectedRiskRegionCount": page_result["qaPlan"]["selectedRiskRegionCount"],
                        "omittedRiskRegionCount": page_result["qaPlan"]["omittedRiskRegionCount"],
                        "omittedHighPriorityCount": page_result["qaPlan"]["omittedHighPriorityCount"],
                    }
                    for page_result in page_results
                ],
            },
            "summary": {
                "vertices": {
                    "checked": coverage["checkedVertices"],
                    "total": coverage["totalVertices"],
                    "collisions": sum(
                        collision["type"] in ("VERTEX_OVERLAP", "CHILD_OUTSIDE_PARENT")
                        for collision in collisions
                    ),
                },
                "edges": {
                    "checked": coverage["checkedEdges"],
                    "total": coverage["totalEdges"],
                    "exact": coverage["exactEdges"],
                    "approximate": coverage["approximateEdges"],
                    "rendererDependent": coverage["unverifiableEdges"],
                    "checkedPairs": coverage["checkedEdgePairs"],
                    "totalPairs": coverage["totalEdgePairs"],
                },
                "labels": {
                    "total": coverage["labeledEdges"],
                    "requiringRenderedQa": coverage["unverifiableLabels"],
                },
                "warningCounts": warning_counts,
                "advisoryCounts": advisory_counts,
                "action": action,
            },
            "collisions": collisions,
            "pages": output_pages,
            "advisories": output_advisories,
        },
        "warnings": output_warnings,
    }


def parse_expected_edges(values):
    result = []
    for value in values or []:
        if len(value) == 2:
            source, target = value
        elif len(value) == 1 and ":" in value[0]:
            source, target = value[0].split(":", 1)
        else:
            raise CliError(
                "INVALID_TOPOLOGY_ARGUMENT",
                "--expect-edge requires SOURCE TARGET or SOURCE:TARGET.",
                {"value": value},
                exit_code=2,
            )
        if not source or not target:
            raise CliError(
                "INVALID_TOPOLOGY_ARGUMENT",
                "Expected edge endpoints must be non-empty cell IDs.",
                {"value": value},
                exit_code=2,
            )
        pair = (source, target)
        if pair not in result:
            result.append(pair)
    return result


def reachable_nodes(seeds, adjacency):
    visited = set()
    pending = list(seeds)
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        pending.extend(adjacency.get(current, ()))
    return visited


def topology_page(page, starts, terminals, expected_edges, require_connected=False):
    cell_map = logical_cell_map(page)
    vertices = {
        logical.id
        for logical in cell_map.values()
        if logical.cell.get("vertex") == "1"
    }
    for role, cell_ids in (("start", starts), ("terminal", terminals)):
        for cell_id in cell_ids:
            logical = cell_map.get(cell_id)
            if logical is None:
                raise CliError(
                    "TOPOLOGY_CELL_NOT_FOUND",
                    "Topology constraint references a missing cell.",
                    {"page": page.id or page.name, "role": role, "cellId": cell_id},
                )
            if logical.cell.get("vertex") != "1":
                raise CliError(
                    "TOPOLOGY_CELL_NOT_VERTEX",
                    "Topology start and terminal cells must be vertices.",
                    {"page": page.id or page.name, "role": role, "cellId": cell_id},
                )
    for source, target in expected_edges:
        for role, cell_id in (("source", source), ("target", target)):
            logical = cell_map.get(cell_id)
            if logical is None:
                raise CliError(
                    "TOPOLOGY_CELL_NOT_FOUND",
                    "Expected edge references a missing cell.",
                    {"page": page.id or page.name, "role": role, "cellId": cell_id},
                )
            if logical.cell.get("vertex") != "1":
                raise CliError(
                    "TOPOLOGY_CELL_NOT_VERTEX",
                    "Expected edge endpoints must be vertices.",
                    {"page": page.id or page.name, "role": role, "cellId": cell_id},
                )

    adjacency = {cell_id: set() for cell_id in vertices}
    reverse = {cell_id: set() for cell_id in vertices}
    undirected = {cell_id: set() for cell_id in vertices}
    edge_pairs = set()
    pair_counts = {}
    floating_edges = []
    edge_count = 0
    for logical in cell_map.values():
        if logical.cell.get("edge") != "1":
            continue
        edge_count += 1
        source = logical.cell.get("source")
        target = logical.cell.get("target")
        if source not in vertices or target not in vertices:
            floating_edges.append(logical.id)
            continue
        pair = (source, target)
        edge_pairs.add(pair)
        pair_counts[pair] = pair_counts.get(pair, 0) + 1
        adjacency[source].add(target)
        reverse[target].add(source)
        undirected[source].add(target)
        undirected[target].add(source)

    isolated = sorted(cell_id for cell_id in vertices if not undirected[cell_id])
    isolated_set = set(isolated)
    connected_vertices = vertices - isolated_set
    constrained_vertices = set(starts) | set(terminals)
    for source, target in expected_edges:
        constrained_vertices.update((source, target))
    topology_vertices = connected_vertices | constrained_vertices
    components = []
    remaining = set(topology_vertices)
    while remaining:
        seed = min(remaining)
        component = reachable_nodes((seed,), undirected)
        component &= topology_vertices
        components.append(sorted(component))
        remaining -= component
    components.sort(key=lambda component: (component[0] if component else "", len(component)))

    no_incoming = sorted(
        cell_id
        for cell_id in connected_vertices
        if not reverse[cell_id] and cell_id not in starts
    )
    no_outgoing = sorted(
        cell_id
        for cell_id in connected_vertices
        if not adjacency[cell_id] and cell_id not in terminals
    )
    missing_expected = [
        {"source": source, "target": target}
        for source, target in expected_edges
        if (source, target) not in edge_pairs
    ]
    duplicate_pairs = [
        {"source": source, "target": target, "count": count}
        for (source, target), count in sorted(pair_counts.items())
        if count > 1
    ]

    reachable_from_starts = reachable_nodes(starts, adjacency) if starts else set()
    unreachable = (
        sorted(topology_vertices - reachable_from_starts) if starts else []
    )
    can_reach_terminal = reachable_nodes(terminals, reverse) if terminals else set()
    terminal_scope = reachable_from_starts if starts else topology_vertices
    cannot_reach_terminal = (
        sorted(terminal_scope - can_reach_terminal) if terminals else []
    )
    isolated_constraints = sorted(
        (set(starts) | set(terminals)) & isolated_set
    )

    warnings = []
    advisories = []
    page_label = page.id or page.name
    if missing_expected:
        warnings.append(
            {
                "code": "MISSING_EXPECTED_EDGE",
                "page": page_label,
                "edges": missing_expected,
            }
        )
    if unreachable:
        warnings.append(
            {
                "code": "UNREACHABLE_FROM_START",
                "page": page_label,
                "cellIds": unreachable,
            }
        )
    if cannot_reach_terminal:
        warnings.append(
            {
                "code": "CANNOT_REACH_TERMINAL",
                "page": page_label,
                "cellIds": cannot_reach_terminal,
            }
        )
    if isolated_constraints:
        warnings.append(
            {
                "code": "ISOLATED_CONSTRAINT_VERTEX",
                "page": page_label,
                "cellIds": isolated_constraints,
            }
        )
    if len(components) > 1:
        disconnected = {
            "code": "DISCONNECTED_TOPOLOGY",
            "page": page_label,
            "componentCount": len(components),
            "components": components,
        }
        (warnings if require_connected else advisories).append(disconnected)
    if isolated:
        advisories.append(
            {"code": "ISOLATED_VERTEX", "page": page_label, "cellIds": isolated}
        )
    if no_incoming:
        advisories.append(
            {"code": "NO_INCOMING_EDGE", "page": page_label, "cellIds": no_incoming}
        )
    if no_outgoing:
        advisories.append(
            {"code": "NO_OUTGOING_EDGE", "page": page_label, "cellIds": no_outgoing}
        )
    if floating_edges:
        advisories.append(
            {"code": "FLOATING_OR_NON_VERTEX_EDGE", "page": page_label, "cellIds": sorted(floating_edges)}
        )
    if duplicate_pairs:
        advisories.append(
            {"code": "DUPLICATE_EDGE_PAIR", "page": page_label, "edges": duplicate_pairs}
        )
    return {
        "page": {"index": page.index, "id": page.id, "name": page.name},
        "status": "issues" if warnings else "clear",
        "counts": {
            "vertices": len(vertices),
            "topologyVertices": len(topology_vertices),
            "isolatedVertices": len(isolated),
            "edges": edge_count,
            "directedEdges": sum(pair_counts.values()),
            "components": len(components),
        },
        "constraints": {
            "starts": list(starts),
            "terminals": list(terminals),
            "expectedEdges": [
                {"source": source, "target": target}
                for source, target in expected_edges
            ],
        },
        "findings": {
            "missingExpectedEdges": missing_expected,
            "unreachableFromStarts": unreachable,
            "cannotReachTerminal": cannot_reach_terminal,
            "isolatedConstraintVertices": isolated_constraints,
            "isolatedVertices": isolated,
            "noIncoming": no_incoming,
            "noOutgoing": no_outgoing,
            "components": components,
            "floatingEdges": sorted(floating_edges),
            "duplicateEdgePairs": duplicate_pairs,
        },
        "warnings": warnings,
        "advisories": advisories,
    }


def compact_topology_page(page_result):
    findings = page_result["findings"]
    return {
        "page": page_result["page"],
        "status": page_result["status"],
        "counts": page_result["counts"],
        "constraints": page_result["constraints"],
        "findings": {
            "missingExpectedEdges": findings["missingExpectedEdges"],
            "unreachableFromStarts": findings["unreachableFromStarts"],
            "cannotReachTerminal": findings["cannotReachTerminal"],
            "isolatedConstraintVertices": findings["isolatedConstraintVertices"],
        },
        "warningCounts": count_codes(page_result["warnings"]),
        "advisoryCounts": count_codes(page_result["advisories"]),
    }


def compact_topology_warning(warning):
    if warning["code"] == "DISCONNECTED_TOPOLOGY":
        return {
            "code": warning["code"],
            "page": warning["page"],
            "componentCount": warning["componentCount"],
        }
    return warning


def check_topology_command(args):
    document = load_document(args.input)
    starts = tuple(dict.fromkeys(args.starts or []))
    terminals = tuple(dict.fromkeys(args.terminals or []))
    expected_edges = parse_expected_edges(args.expected_edges)
    has_constraints = bool(starts or terminals or expected_edges)
    pages = select_pages(
        document,
        page_selector_from_args(args),
        require_for_multiple=has_constraints,
    )
    page_results = [
        topology_page(
            page,
            starts,
            terminals,
            expected_edges,
            require_connected=args.require_connected,
        )
        for page in pages
    ]
    warnings = [item for result in page_results for item in result["warnings"]]
    advisories = [item for result in page_results for item in result["advisories"]]
    output_pages = page_results if args.verbose else [
        compact_topology_page(result) for result in page_results
    ]
    output_warnings = warnings if args.verbose else [
        compact_topology_warning(warning) for warning in warnings
    ]
    output_advisories = advisories if args.verbose else [
        {"code": code, "count": count}
        for code, count in count_codes(advisories).items()
    ]
    return {
        "file": str(document.path),
        "revision": document.revision,
        "result": {
            "status": "issues" if warnings else "clear",
            "pages": output_pages,
            "summary": {
                "pagesChecked": len(page_results),
                "warningCounts": count_codes(warnings),
                "advisoryCounts": count_codes(advisories),
            },
            "advisories": output_advisories,
        },
        "warnings": output_warnings,
    }


def page_selector_from_args(args):
    selector = {}
    for name in ("id", "name", "index"):
        value = getattr(args, "page_" + name, None)
        if value is not None:
            selector[name] = value
    return selector or None


def validate_selector(selector):
    if selector is None:
        return
    if not isinstance(selector, dict) or len(selector) != 1:
        raise CliError("INVALID_PAGE_SELECTOR", "Page must specify exactly one of id, name, or index.")
    key, value = next(iter(selector.items()))
    if key not in ("id", "name", "index"):
        raise CliError("INVALID_PAGE_SELECTOR", "Unknown page selector.", {"selector": key})
    if key == "index":
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise CliError("INVALID_PAGE_SELECTOR", "Page index must be a non-negative integer.")
    elif not isinstance(value, str) or not value:
        raise CliError("INVALID_PAGE_SELECTOR", "Page id/name must be a non-empty string.")


def select_pages(document, selector, require_for_multiple=False):
    validate_selector(selector)
    if selector is None:
        if require_for_multiple and len(document.pages) > 1:
            raise CliError("PAGE_REQUIRED", "A page selector is required for a multi-page operation.")
        return list(document.pages)
    key, value = next(iter(selector.items()))
    matches = [page for page in document.pages if getattr(page, key) == value]
    if len(matches) != 1:
        if not matches:
            code = "PAGE_NOT_FOUND"
        elif key == "name":
            code = "PAGE_NOT_UNIQUE"
        else:
            code = "AMBIGUOUS_PAGE"
        raise CliError(
            code,
            "Page selector must resolve to exactly one page.",
            {"selector": selector, "matches": len(matches)},
        )
    return matches


def geometry_projection(cell):
    geometry = next(
        (child for child in list(cell) if local_name(child.tag) == "mxGeometry"), None
    )
    if geometry is None:
        return None
    projection = {"attrs": dict(geometry.attrib)}
    children = []
    for child in list(geometry):
        if not isinstance(child.tag, str):
            continue
        item = {"tag": local_name(child.tag), "attrs": dict(child.attrib)}
        points = []
        for point in list(child):
            if local_name(point.tag) == "mxPoint":
                points.append(dict(point.attrib))
        if points:
            item["points"] = points
        children.append(item)
    if children:
        projection["children"] = children
    return projection


def cell_hash(logical):
    return revision_for(ET.tostring(logical.outer, encoding="utf-8", short_empty_elements=True))


def semantic_element(element, include_tail=True):
    """Return a formatting-independent representation of native Draw.io XML."""
    def meaningful_text(value):
        return value if value and value.strip() else None

    children = [
        semantic_element(child)
        for child in list(element)
        if isinstance(child.tag, str)
    ]
    return {
        "tag": element.tag,
        "attrs": sorted(element.attrib.items()),
        "text": meaningful_text(element.text),
        "tail": meaningful_text(element.tail) if include_tail else None,
        "children": children,
    }


def page_semantic_revision(page):
    canonical = json.dumps(
        semantic_element(page.model, include_tail=False),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return revision_for(canonical)


def web_export_semantic_element(element):
    """Normalize only the representation changes made by the official Web editor."""
    attrs = dict(element.attrib)
    tag = local_name(element.tag)
    if tag == "mxGraphModel":
        attrs.pop("dx", None)
        attrs.pop("dy", None)
    elif tag == "mxGeometry" and attrs.get("relative") == "1":
        for coordinate in ("x", "y"):
            if attrs.get(coordinate) in ("0", "0.0", "-0"):
                attrs.pop(coordinate)

    def meaningful_text(value):
        return value if value and value.strip() else None

    return {
        "tag": element.tag,
        "attrs": sorted(attrs.items()),
        "text": meaningful_text(element.text),
        "children": [
            web_export_semantic_element(child)
            for child in list(element)
            if isinstance(child.tag, str)
        ],
    }


def page_web_export_revision(page):
    """Identity projection tolerant of official Draw.io save/export normalization."""
    logical = logical_cell_map(page)
    root = direct_child(page.model, "root")
    cell_outer_ids = {id(item.outer): cell_id for cell_id, item in logical.items()}
    order_by_parent = {}
    unknown_root_children = []
    for child in list(root):
        if not isinstance(child.tag, str):
            continue
        cell_id = cell_outer_ids.get(id(child))
        if cell_id is None:
            unknown_root_children.append(web_export_semantic_element(child))
            continue
        parent = logical[cell_id].cell.get("parent") or ""
        order_by_parent.setdefault(parent, []).append(cell_id)

    model_attrs = dict(page.model.attrib)
    model_attrs.pop("dx", None)
    model_attrs.pop("dy", None)
    for name, default_value in DRAWIO_WEB_MODEL_DEFAULTS.items():
        if model_attrs.get(name) == default_value:
            model_attrs.pop(name)
    projection = {
        "modelAttrs": sorted(model_attrs.items()),
        "cells": {
            cell_id: web_export_semantic_element(item.outer)
            for cell_id, item in sorted(logical.items())
        },
        "orderByParent": {
            parent: cell_ids for parent, cell_ids in sorted(order_by_parent.items())
        },
        "unknownRootChildren": unknown_root_children,
    }
    canonical = json.dumps(
        projection, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return revision_for(canonical)


def cell_projection(page, logical, include_style=False, include_raw=False):
    wrapper = logical.wrapper
    label = logical_label(logical)
    result = {
        "page": {"index": page.index, "id": page.id, "name": page.name},
        "id": logical.id,
        "label": label,
        "cellType": "edge"
        if logical.cell.get("edge") == "1"
        else ("vertex" if logical.cell.get("vertex") == "1" else "cell"),
        "parent": logical.cell.get("parent"),
        "source": logical.cell.get("source"),
        "target": logical.cell.get("target"),
        "attrs": {
            key: value
            for key, value in logical.cell.attrib.items()
            if key not in ("id", "value", "style", "parent", "source", "target")
        },
        "geometry": geometry_projection(logical.cell),
        "wrapper": None,
        "cellHash": cell_hash(logical),
    }
    if wrapper is not None:
        result["wrapper"] = {
            "tag": local_name(wrapper.tag),
            "attrs": {key: value for key, value in wrapper.attrib.items() if key != "id"},
        }
    if include_style:
        result["style"] = logical.cell.get("style", "")
    if include_raw:
        result["rawXml"] = ET.tostring(logical.outer, encoding="unicode", short_empty_elements=True)
    return result


def inspect_command(args):
    document = load_document(args.input)
    validation = validate_document(document)
    selected = select_pages(document, page_selector_from_args(args))
    pages = []
    for page in selected:
        cells = logical_cells(page)
        pages.append(
            {
                "index": page.index,
                "id": page.id,
                "name": page.name,
                "encoding": page.encoding,
                "cells": len(cells),
                "wrappers": sum(1 for cell in cells if cell.wrapper is not None),
            }
        )
    return {
        "file": str(document.path),
        "revision": document.revision,
        "result": {"pages": pages, "totals": {"pages": validation["pages"], "cells": validation["cells"]}},
        "warnings": validation["warnings"],
    }


def query_command(args):
    if not args.ids and args.label is None and args.label_contains is None:
        raise CliError("QUERY_FILTER_REQUIRED", "Query requires --id, --label, or --label-contains.", exit_code=2)
    if args.limit < 1 or args.limit > MAX_QUERY_LIMIT:
        raise CliError(
            "INVALID_LIMIT",
            "Query limit is outside the supported range.",
            {"min": 1, "max": MAX_QUERY_LIMIT},
            exit_code=2,
        )
    document = load_document(args.input)
    pages = select_pages(document, page_selector_from_args(args))
    id_filter = set(args.ids or [])
    matches = []
    for page in pages:
        for logical in logical_cells(page):
            label = logical_label(logical)
            if id_filter and logical.id not in id_filter:
                continue
            if args.label is not None and label != args.label:
                continue
            if args.label_contains is not None and args.label_contains not in label:
                continue
            matches.append(cell_projection(page, logical, args.include_style, args.include_raw))
            if len(matches) > args.limit:
                raise CliError(
                    "RESULT_LIMIT_EXCEEDED",
                    "Query matched more cells than the configured limit; narrow the filters.",
                    {"limit": args.limit},
                )
    return {
        "file": str(document.path),
        "revision": document.revision,
        "result": {"matches": matches, "count": len(matches)},
        "warnings": [],
    }


def validate_attribute_name(name):
    if (
        not isinstance(name, str)
        or not SAFE_ATTR_NAME.fullmatch(name)
        or name == "xmlns"
        or name.startswith("xmlns:")
        or name.startswith("xml:")
    ):
        raise CliError("INVALID_ATTRIBUTE", "Unsafe XML attribute name.", {"attribute": name})


def require_keys(value, allowed, required, context):
    if not isinstance(value, dict):
        raise CliError("INVALID_PATCH", context + " must be an object.")
    unknown = sorted(set(value) - set(allowed))
    missing = sorted(set(required) - set(value))
    if unknown or missing:
        raise CliError(
            "INVALID_PATCH",
            context + " has invalid fields.",
            {"unknown": unknown, "missing": missing},
        )


def load_patch(path):
    patch_path = Path(path).expanduser().resolve()
    try:
        data = patch_path.read_bytes()
    except FileNotFoundError as exc:
        raise CliError("FILE_NOT_FOUND", "Patch file does not exist.", {"path": str(patch_path)}) from exc
    if len(data) > MAX_PATCH_BYTES:
        raise CliError("INPUT_SIZE_LIMIT", "Patch file exceeds the lightweight V1 limit.")

    def strict_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("non-finite JSON number: " + value)

    try:
        patch = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=strict_object,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CliError("INVALID_PATCH", "Patch file must be UTF-8 JSON.", {"error": str(exc)}) from exc
    require_keys(
        patch,
        {"version", "expectedRevision", "page", "operations"},
        {"version", "expectedRevision", "operations"},
        "Patch envelope",
    )
    if patch["version"] != VERSION:
        raise CliError("UNSUPPORTED_PATCH_VERSION", "Patch version must be 1.")
    if not isinstance(patch["expectedRevision"], str) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", patch["expectedRevision"]
    ):
        raise CliError("INVALID_PATCH", "expectedRevision must be a sha256 revision.")
    if not isinstance(patch["operations"], list) or not patch["operations"]:
        raise CliError("INVALID_PATCH", "operations must be a non-empty array.")
    validate_selector(patch.get("page"))
    return patch_path, patch


def find_logical(page, cell_id):
    if not isinstance(cell_id, str) or not cell_id:
        raise CliError("INVALID_PATCH", "cellId must be a non-empty string.")
    logical = logical_cell_map(page).get(cell_id)
    if logical is None:
        raise CliError("CELL_NOT_FOUND", "Cell does not exist on the selected page.", {"cellId": cell_id})
    return logical


def target_element(logical, target):
    if target == "cell":
        return logical.cell
    if target == "wrapper" and logical.wrapper is not None:
        return logical.wrapper
    if target not in ("cell", "wrapper"):
        raise CliError("INVALID_PATCH", "target must be cell or wrapper.")
    raise CliError("WRAPPER_REQUIRED", "The selected logical cell has no wrapper.", {"cellId": logical.id})


def string_attributes(attrs):
    if not isinstance(attrs, dict) or not attrs:
        raise CliError("INVALID_PATCH", "attrs must be a non-empty object.")
    result = {}
    for name, value in attrs.items():
        validate_attribute_name(name)
        if name == "id":
            raise CliError("IMMUTABLE_ID", "Cell and wrapper IDs cannot be changed.")
        if not isinstance(value, str):
            raise CliError("INVALID_PATCH", "XML attribute values must be strings.", {"attribute": name})
        result[name] = value
    return result


def attribute_list(attrs):
    if not isinstance(attrs, list) or not attrs or any(not isinstance(item, str) for item in attrs):
        raise CliError("INVALID_PATCH", "attrs must be a non-empty string array.")
    for name in attrs:
        validate_attribute_name(name)
        if name == "id":
            raise CliError("IMMUTABLE_ID", "Cell and wrapper IDs cannot be changed.")
    return attrs


def style_value(value, key):
    if isinstance(value, bool):
        text = "1" if value else "0"
    elif isinstance(value, (str, int, float)) and not isinstance(value, bool):
        text = str(value)
    else:
        raise CliError("INVALID_PATCH", "Style values must be strings, numbers, or booleans.", {"key": key})
    if ";" in text:
        raise CliError("INVALID_PATCH", "A style value cannot contain ';'.", {"key": key})
    return text


def style_key(token):
    return token.split("=", 1)[0]


def apply_style(logical, operation):
    require_keys(operation, {"op", "cellId", "set", "unset"}, {"op", "cellId"}, "set-style")
    set_values = operation.get("set", {})
    unset = operation.get("unset", [])
    if not isinstance(set_values, dict) or not isinstance(unset, list):
        raise CliError("INVALID_PATCH", "set-style set/unset have invalid types.")
    if not set_values and not unset:
        raise CliError("INVALID_PATCH", "set-style requires set or unset values.")
    if any(not isinstance(item, str) for item in unset):
        raise CliError("INVALID_PATCH", "set-style unset must be a string array.")
    changed_keys = set(unset) | set(set_values)
    for key in changed_keys:
        if not isinstance(key, str) or not key or ";" in key or "=" in key:
            raise CliError("INVALID_PATCH", "Invalid native style key.", {"key": key})
    tokens = [token for token in logical.cell.get("style", "").split(";") if token]
    kept = [token for token in tokens if style_key(token) not in changed_keys]
    for key, value in set_values.items():
        kept.append(key + "=" + style_value(value, key))
    logical.cell.set("style", ";".join(kept) + (";" if kept else ""))


def apply_label(logical, operation):
    require_keys(
        operation,
        {"op", "cellId", "value", "format"},
        {"op", "cellId", "value", "format"},
        "set-label",
    )
    value = validate_xml_text(operation["value"], "set-label value")
    label_format = operation["format"]
    if label_format not in ("plain", "html"):
        raise CliError("INVALID_PATCH", "set-label format must be plain or html.")
    if label_format == "html" and probable_double_escaped_markup(value):
        raise CliError(
            "DOUBLE_ESCAPED_LABEL",
            "HTML labels require decoded logical markup, not &lt;...&gt; text.",
            {"cellId": logical.id},
        )
    if logical.wrapper is not None:
        logical.wrapper.set("label", value)
    else:
        logical.cell.set("value", value)
    apply_style(
        logical,
        {
            "op": "set-style",
            "cellId": logical.id,
            "set": {"html": "1" if label_format == "html" else "0"},
            "unset": [],
        },
    )


def parse_fragment(xml, expected_root, context):
    if not isinstance(xml, str) or not xml.strip():
        raise CliError("INVALID_PATCH", context + " xml must be a non-empty string.")
    stripped = xml.strip()
    if stripped.startswith("<?xml"):
        raise CliError("INVALID_PATCH", "XML declarations are not allowed in fragments.")
    element = parse_xml_bytes(stripped.encode("utf-8"), context)
    if local_name(element.tag) not in expected_root:
        raise CliError(
            "INVALID_PATCH",
            context + " has an unsupported root element.",
            {"root": local_name(element.tag), "allowed": sorted(expected_root)},
        )
    return element


def replace_geometry(logical, geometry):
    children = list(logical.cell)
    existing = [child for child in children if local_name(child.tag) == "mxGeometry"]
    if len(existing) > 1:
        raise CliError("INVALID_GEOMETRY", "Cell contains multiple mxGeometry elements.")
    if existing:
        index = children.index(existing[0])
        logical.cell.remove(existing[0])
        logical.cell.insert(index, geometry)
    else:
        logical.cell.append(geometry)
    for child in list(logical.cell):
        if local_name(child.tag) == "Array" and child.get("as") == "points":
            logical.cell.remove(child)


def parse_cell_fragment(xml, page, expected_id):
    element = parse_fragment(xml, {"mxCell", "object", "UserObject"}, "cell fragment")
    logical = parse_logical_cell(element, page)
    if logical is None or logical.id != expected_id:
        raise CliError(
            "CELL_ID_MISMATCH",
            "Cell fragment logical ID must match cellId.",
            {"expected": expected_id, "actual": logical.id if logical else None},
        )
    if misplaced_waypoint_arrays(logical):
        raise CliError(
            "MISPLACED_WAYPOINT_ARRAY",
            "Waypoint arrays in cell fragments must be nested inside mxGeometry.",
            {"cellId": expected_id},
        )
    return element


def apply_operation(page, operation):
    if not isinstance(operation, dict) or not isinstance(operation.get("op"), str):
        raise CliError("INVALID_PATCH", "Every operation requires an op string.")
    op = operation["op"]
    cell_id = operation.get("cellId")
    if op == "set-attrs":
        require_keys(operation, {"op", "cellId", "target", "attrs"}, {"op", "cellId", "target", "attrs"}, op)
        logical = find_logical(page, cell_id)
        element = target_element(logical, operation["target"])
        for name, value in string_attributes(operation["attrs"]).items():
            element.set(name, value)
    elif op == "unset-attrs":
        require_keys(operation, {"op", "cellId", "target", "attrs"}, {"op", "cellId", "target", "attrs"}, op)
        logical = find_logical(page, cell_id)
        element = target_element(logical, operation["target"])
        for name in attribute_list(operation["attrs"]):
            element.attrib.pop(name, None)
    elif op == "set-style":
        logical = find_logical(page, cell_id)
        apply_style(logical, operation)
    elif op == "set-label":
        logical = find_logical(page, cell_id)
        apply_label(logical, operation)
    elif op == "set-geometry":
        require_keys(
            operation,
            {"op", "cellId", "set", "unset", "xml"},
            {"op", "cellId"},
            op,
        )
        logical = find_logical(page, cell_id)
        has_xml = "xml" in operation
        has_fields = "set" in operation or "unset" in operation
        if has_xml == has_fields:
            raise CliError("INVALID_PATCH", "set-geometry requires either xml or set/unset fields.")
        if has_xml:
            geometry = parse_fragment(operation["xml"], {"mxGeometry"}, "geometry fragment")
            replace_geometry(logical, geometry)
        else:
            set_values = operation.get("set", {})
            unset = operation.get("unset", [])
            if not set_values and not unset:
                raise CliError(
                    "INVALID_PATCH",
                    "set-geometry requires at least one set or unset value.",
                )
            geometry = next(
                (child for child in list(logical.cell) if local_name(child.tag) == "mxGeometry"),
                None,
            )
            if geometry is None:
                geometry = ET.Element("mxGeometry", {"as": "geometry"})
                logical.cell.append(geometry)
            if set_values:
                for name, value in string_attributes(set_values).items():
                    geometry.set(name, value)
            if unset:
                for name in attribute_list(unset):
                    geometry.attrib.pop(name, None)
    elif op == "add-cell-xml":
        require_keys(operation, {"op", "cellId", "xml"}, {"op", "cellId", "xml"}, op)
        if not isinstance(cell_id, str) or not cell_id:
            raise CliError("INVALID_PATCH", "cellId must be a non-empty string.")
        if cell_id in logical_cell_map(page):
            raise CliError("DUPLICATE_CELL_ID", "Cell ID already exists.", {"cellId": cell_id})
        model_root(page).append(parse_cell_fragment(operation["xml"], page, cell_id))
    elif op == "delete":
        require_keys(operation, {"op", "cellId"}, {"op", "cellId"}, op)
        if cell_id in ("0", "1"):
            raise CliError("PROTECTED_CELL", "Root cells 0 and 1 cannot be deleted.", {"cellId": cell_id})
        logical = find_logical(page, cell_id)
        model_root(page).remove(logical.outer)
    elif op == "replace-cell-xml":
        require_keys(
            operation,
            {"op", "cellId", "expectedCellHash", "xml"},
            {"op", "cellId", "expectedCellHash", "xml"},
            op,
        )
        logical = find_logical(page, cell_id)
        if not isinstance(operation["expectedCellHash"], str) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", operation["expectedCellHash"]
        ):
            raise CliError("INVALID_PATCH", "expectedCellHash must be a sha256 cell hash.")
        if operation["expectedCellHash"] != cell_hash(logical):
            raise CliError("CELL_HASH_CONFLICT", "Cell changed since query.", {"cellId": cell_id}, exit_code=4)
        replacement = parse_cell_fragment(operation["xml"], page, cell_id)
        root = model_root(page)
        children = list(root)
        index = children.index(logical.outer)
        root.remove(logical.outer)
        root.insert(index, replacement)
    else:
        raise CliError("UNSUPPORTED_OPERATION", "Patch operation is not supported.", {"op": op})
    page.changed = True


def serialize_model(model):
    return ET.tostring(model, encoding="utf-8", short_empty_elements=True)


def compress_model(model):
    xml_text = serialize_model(model).decode("utf-8")
    percent = urllib.parse.quote(xml_text, safe="-_.!~*'()")
    compressor = zlib.compressobj(level=9, wbits=-zlib.MAX_WBITS)
    compressed = compressor.compress(percent.encode("ascii")) + compressor.flush()
    return base64.b64encode(compressed).decode("ascii")


def serialize_document(document):
    if document.bare:
        return serialize_model(document.root)
    for page in document.pages:
        if not page.changed or page.encoding == "plain":
            continue
        for child in list(page.diagram):
            page.diagram.remove(child)
        page.diagram.text = compress_model(page.model)
    return ET.tostring(document.root, encoding="utf-8", short_empty_elements=True)


def validate_expected_revision(document, expected_revision):
    if not isinstance(expected_revision, str) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", expected_revision
    ):
        raise CliError("INVALID_REVISION", "expectedRevision must be a sha256 revision.")
    if document.revision != expected_revision:
        raise CliError(
            "REVISION_CONFLICT",
            "Source revision does not match the requested operation.",
            {"expected": expected_revision, "actual": document.revision},
            exit_code=4,
        )


def validate_page_text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise CliError("INVALID_PAGE_VALUE", field + " must be a non-empty string.")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise CliError("INVALID_PAGE_VALUE", field + " cannot contain control characters.")
    return value


def generate_page_id(document):
    existing = {page.id for page in document.pages if page.id}
    for _ in range(100):
        candidate = "page-" + secrets.token_hex(6)
        if candidate not in existing:
            return candidate
    raise CliError("PAGE_ID_GENERATION_FAILED", "Could not generate a unique page ID.", exit_code=6)


def normalize_bare_document(document, page_name="Page 1"):
    if not document.bare:
        return document.pages[0]
    page = document.pages[0]
    page_id = generate_page_id(document)
    mxfile = ET.Element("mxfile", {"host": "app.diagrams.net"})
    diagram = ET.SubElement(mxfile, "diagram", {"id": page_id, "name": page_name})
    diagram.append(page.model)
    document.root = mxfile
    document.bare = False
    page.id = page_id
    page.name = page_name
    page.diagram = diagram
    page.encoding = "plain"
    return page


def load_page_model(path):
    model_path = Path(path).expanduser().resolve()
    try:
        stat = model_path.stat()
    except FileNotFoundError as exc:
        raise CliError(
            "FILE_NOT_FOUND", "Page model file does not exist.", {"path": str(model_path)}
        ) from exc
    if not model_path.is_file():
        raise CliError("INVALID_PATH", "Page model input must be a file.", {"path": str(model_path)})
    if stat.st_size > MAX_INPUT_BYTES:
        raise CliError(
            "INPUT_SIZE_LIMIT",
            "Page model file exceeds the lightweight limit.",
            {"path": str(model_path), "limit": MAX_INPUT_BYTES, "size": stat.st_size},
        )
    data = model_path.read_bytes()
    if len(data) > MAX_INPUT_BYTES:
        raise CliError(
            "INPUT_SIZE_LIMIT",
            "Page model file exceeds the lightweight limit.",
            {"path": str(model_path), "limit": MAX_INPUT_BYTES, "size": len(data)},
        )
    model = parse_xml_bytes(data, str(model_path))
    if local_name(model.tag) != "mxGraphModel":
        raise CliError(
            "INVALID_PAGE_MODEL",
            "Page model file must contain one bare mxGraphModel.",
            {"path": str(model_path), "root": local_name(model.tag)},
        )
    synthetic = Document(
        model_path,
        data,
        model,
        True,
        [Page(0, None, "Page 1", "plain", None, model)],
    )
    validation = validate_document(synthetic)
    require_no_misplaced_waypoints(validation)
    return model_path, model


def commit_document_change(document, expected_revision, output, reserved_path=None):
    validate_expected_revision(document, expected_revision)
    validation = validate_document(document)
    output_data = serialize_document(document)
    output_path = ensure_output_path(
        document.path, reserved_path or document.path, output
    )
    safe_commit(
        document,
        reserved_path or document.path,
        output_path,
        output_data,
        expected_revision,
    )
    return output_path, output_data, validation


def page_add_command(args):
    document = load_document(args.input)
    validate_expected_revision(document, args.expected_revision)
    if len(document.pages) >= MAX_PAGES:
        raise CliError(
            "PAGE_COUNT_LIMIT",
            "Document has too many pages.",
            {"pages": len(document.pages), "limit": MAX_PAGES},
        )
    name = validate_page_text(args.name, "Page name")
    if document.bare:
        normalize_bare_document(document)
    page_id = validate_page_text(args.page_id, "Page ID") if args.page_id else generate_page_id(document)
    if any(page.id == page_id for page in document.pages):
        raise CliError("DUPLICATE_PAGE_ID", "Page ID already exists.", {"pageId": page_id})

    model_path = None
    if args.model_file:
        model_path, model = load_page_model(args.model_file)
    else:
        model = ET.fromstring(
            '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel>'
        )
    diagram = ET.SubElement(document.root, "diagram", {"id": page_id, "name": name})
    diagram.append(model)
    page = Page(len(document.pages), page_id, name, "plain", diagram, model)
    document.pages.append(page)
    output_path, output_data, validation = commit_document_change(
        document,
        args.expected_revision,
        args.output,
        reserved_path=model_path,
    )
    return {
        "file": str(output_path),
        "source": str(document.path),
        "revision": revision_for(output_data),
        "result": {
            "operation": "add",
            "page": {"index": page.index, "id": page.id, "name": page.name},
            "sourceModified": False,
        },
        "warnings": validation["warnings"],
    }


def page_rename_command(args):
    document = load_document(args.input)
    validate_expected_revision(document, args.expected_revision)
    page = select_pages(document, page_selector_from_args(args))[0]
    name = validate_page_text(args.name, "Page name")
    if document.bare:
        page = normalize_bare_document(document, page_name=name)
    else:
        page.diagram.set("name", name)
        page.name = name
    output_path, output_data, validation = commit_document_change(
        document, args.expected_revision, args.output
    )
    return {
        "file": str(output_path),
        "source": str(document.path),
        "revision": revision_for(output_data),
        "result": {
            "operation": "rename",
            "page": {"index": page.index, "id": page.id, "name": page.name},
            "sourceModified": False,
        },
        "warnings": validation["warnings"],
    }


def page_delete_command(args):
    document = load_document(args.input)
    validate_expected_revision(document, args.expected_revision)
    if len(document.pages) == 1:
        raise CliError("LAST_PAGE_DELETE", "A Draw.io document must retain at least one page.")
    page = select_pages(document, page_selector_from_args(args))[0]
    deleted = {"index": page.index, "id": page.id, "name": page.name}
    document.root.remove(page.diagram)
    document.pages.remove(page)
    for index, remaining in enumerate(document.pages):
        remaining.index = index
    output_path, output_data, validation = commit_document_change(
        document, args.expected_revision, args.output
    )
    return {
        "file": str(output_path),
        "source": str(document.path),
        "revision": revision_for(output_data),
        "result": {
            "operation": "delete",
            "page": deleted,
            "sourceModified": False,
        },
        "warnings": validation["warnings"],
    }


def version_series(path):
    match = VERSIONED_STEM.fullmatch(path.stem)
    if match:
        return match.group("base"), int(match.group("number"))
    return path.stem, None


def versions_command(args):
    document = load_document(args.input)
    base, current = version_series(document.path)
    matcher = re.compile(r"^" + re.escape(base) + r"-v([0-9]{3})\.drawio$")
    versions = []
    for candidate in document.path.parent.iterdir():
        try:
            if candidate.is_symlink() or not candidate.is_file():
                continue
        except FileNotFoundError:
            continue
        match = matcher.fullmatch(candidate.name)
        if match and int(match.group(1)) > 0:
            versions.append({"number": int(match.group(1)), "file": str(candidate.resolve())})
    if len(versions) > MAX_VERSIONS:
        raise CliError(
            "VERSION_COUNT_LIMIT",
            "Version series exceeds the lightweight listing limit.",
            {"count": len(versions), "limit": MAX_VERSIONS},
        )
    versions.sort(key=lambda item: (item["number"], item["file"]))
    origin = document.path.parent / (base + ".drawio")
    origin_path = None
    try:
        if not origin.is_symlink() and origin.is_file():
            origin_path = str(origin.resolve())
    except FileNotFoundError:
        pass
    return {
        "file": str(document.path),
        "revision": document.revision,
        "result": {
            "base": base,
            "origin": origin_path,
            "current": current,
            "versions": versions,
        },
        "warnings": [],
    }


def validated_copy_command(args, result_key, require_publishable=False):
    document = load_document(args.input)
    validate_expected_revision(document, args.expected_revision)
    validation = validate_document(document)
    if require_publishable:
        require_no_misplaced_waypoints(validation)
    output_path = ensure_output_path(document.path, document.path, args.output)
    safe_commit(
        document,
        document.path,
        output_path,
        document.source_bytes,
        args.expected_revision,
    )
    return {
        "file": str(output_path),
        "source": str(document.path),
        "revision": document.revision,
        "result": {
            result_key: str(document.path),
            "byteIdentical": True,
            "sourceModified": False,
        },
        "warnings": [],
    }


def restore_command(args):
    return validated_copy_command(args, "restoredFrom")


def publish_command(args):
    return validated_copy_command(args, "publishedFrom", require_publishable=True)


def ensure_output_path(source_path, patch_path, output):
    output_path = Path(output).expanduser()
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path
    # Check the user-facing path before resolving its parent so that an existing
    # dangling symlink cannot be mistaken for a free output name.
    if os.path.lexists(str(output_path)):
        raise CliError("OUTPUT_EXISTS", "Output path already exists.", {"path": str(output_path)}, exit_code=5)
    parent = output_path.parent.resolve()
    output_path = parent / output_path.name
    if os.path.lexists(str(output_path)):
        raise CliError("OUTPUT_EXISTS", "Output path already exists.", {"path": str(output_path)}, exit_code=5)
    if output_path == source_path or output_path == patch_path:
        raise CliError("OUTPUT_CONFLICT", "Output must differ from all inputs.", {"path": str(output_path)}, exit_code=5)
    if not output_path.parent.is_dir():
        raise CliError("INVALID_PATH", "Output parent directory does not exist.", {"path": str(output_path.parent)})
    return output_path


def safe_commit(
    source_document,
    patch_path,
    output_path,
    data,
    expected_revision,
    validate_drawio_output=True,
):
    if sys.platform not in ("darwin", "linux"):
        raise CliError(
            "UNSUPPORTED_PLATFORM",
            "Safe patch writes are supported on macOS and Linux in this V1.",
            {"platform": sys.platform},
            exit_code=5,
        )
    temp_name = ".drawio-file-" + secrets.token_hex(16) + ".tmp"
    temp_path = output_path.parent / temp_name
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = None
    committed = False
    try:
        fd = os.open(str(temp_path), flags, 0o600)
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise CliError("WRITE_FAILED", "Failed to write complete temporary output.", exit_code=6)
            view = view[written:]
        os.fsync(fd)
        os.close(fd)
        fd = None
        readback = temp_path.read_bytes()
        if readback != data:
            raise CliError("WRITE_FAILED", "Temporary output readback did not match.", exit_code=6)
        if validate_drawio_output:
            # Validate the exact bytes that will become the Draw.io output,
            # including compression, identities, references, and geometry.
            load_document(temp_path)
        current_revision = revision_for(source_document.path.read_bytes())
        if current_revision != expected_revision:
            raise CliError(
                "REVISION_CONFLICT",
                "Source changed before commit; query the current file and rebuild the patch.",
                {"expected": expected_revision, "actual": current_revision},
                exit_code=4,
            )
        try:
            os.link(str(temp_path), str(output_path), follow_symlinks=False)
        except FileExistsError as exc:
            raise CliError("OUTPUT_EXISTS", "Output path was created concurrently.", {"path": str(output_path)}, exit_code=5) from exc
        committed = True
    finally:
        if fd is not None:
            os.close(fd)
        if os.path.lexists(str(temp_path)):
            try:
                os.unlink(str(temp_path))
            except OSError:
                if not committed:
                    raise


def patch_command(args):
    patch_path, patch = load_patch(args.patch)
    document = load_document(args.input)
    before_validation = validate_document(document)
    before_misplaced = {
        (item["page"], item["cellId"])
        for item in misplaced_waypoint_warnings(before_validation)
    }
    expected = patch["expectedRevision"]
    if document.revision != expected:
        raise CliError(
            "REVISION_CONFLICT",
            "Source revision does not match the patch.",
            {"expected": expected, "actual": document.revision},
            exit_code=4,
        )
    page = select_pages(document, patch.get("page"), require_for_multiple=True)[0]
    for index, operation in enumerate(patch["operations"]):
        try:
            apply_operation(page, operation)
        except CliError as exc:
            exc.details.setdefault("operationIndex", index)
            raise
    validation = validate_document(document)
    introduced_misplaced = [
        item
        for item in misplaced_waypoint_warnings(validation)
        if (item["page"], item["cellId"]) not in before_misplaced
    ]
    if introduced_misplaced:
        raise CliError(
            "MISPLACED_WAYPOINT_ARRAY",
            "Patch introduced waypoint arrays outside mxGeometry.",
            {
                "cells": [
                    {"page": item["page"], "cellId": item["cellId"]}
                    for item in introduced_misplaced
                ]
            },
        )
    output_data = serialize_document(document)
    output_path = ensure_output_path(document.path, patch_path, args.output)
    safe_commit(document, patch_path, output_path, output_data, expected)
    return {
        "file": str(output_path),
        "source": str(document.path),
        "revision": revision_for(output_data),
        "result": {
            "page": {"index": page.index, "id": page.id, "name": page.name},
            "operationsApplied": len(patch["operations"]),
            "sourceModified": False,
        },
        "warnings": validation["warnings"],
    }


def validate_command(args):
    document = load_document(args.input)
    validation = validate_document(document)
    require_no_misplaced_waypoints(validation)
    return {
        "file": str(document.path),
        "revision": document.revision,
        "result": {"valid": True, "pages": validation["pages"], "cells": validation["cells"]},
        "warnings": validation["warnings"],
    }


def resolve_drawio_command(explicit):
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    else:
        on_path = shutil.which("drawio")
        if on_path:
            candidates.append(Path(on_path))
        if sys.platform == "darwin":
            candidates.append(Path("/Applications/draw.io.app/Contents/MacOS/draw.io"))
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_file() and os.access(str(resolved), os.X_OK):
            return resolved
    raise CliError(
        "DRAWIO_DESKTOP_NOT_FOUND",
        "Draw.io Desktop CLI was not found; use preview for remote Viewer QA or report structure_only.",
        {
            "requested": explicit,
            "fallback": "preview",
            "searched": [str(candidate) for candidate in candidates],
        },
    )


def validate_render_output(data, output_format):
    valid = False
    if output_format == "png":
        valid = data.startswith(b"\x89PNG\r\n\x1a\n")
    elif output_format == "pdf":
        valid = data.startswith(b"%PDF-")
    elif output_format == "svg":
        prefix = data[:8192].lstrip()
        valid = b"<svg" in prefix
    if not valid:
        raise CliError(
            "INVALID_RENDER_OUTPUT",
            "Draw.io Desktop did not create a recognizable render artifact.",
            {"format": output_format, "bytes": len(data)},
            exit_code=6,
        )


def render_command(args):
    document = load_document(args.input)
    output_path = ensure_output_path(document.path, document.path, args.output)
    if args.border < 0 or args.border > 1000:
        raise CliError(
            "INVALID_RENDER_BORDER",
            "Render border must be between 0 and 1000.",
            {"border": args.border},
            exit_code=2,
        )
    output_format = args.format or output_path.suffix.lower().lstrip(".")
    if output_format not in DRAWIO_FORMATS:
        raise CliError(
            "UNSUPPORTED_RENDER_FORMAT",
            "Render format must be png, svg, or pdf.",
            {"format": output_format or None},
            exit_code=2,
        )
    if output_path.suffix.lower() != "." + output_format:
        raise CliError(
            "RENDER_EXTENSION_MISMATCH",
            "Output extension must match the render format.",
            {"format": output_format, "output": str(output_path)},
            exit_code=2,
        )
    selector = page_selector_from_args(args)
    page = select_pages(
        document,
        selector,
        require_for_multiple=True,
    )[0]
    drawio_command = resolve_drawio_command(args.drawio_command)
    temp_path = output_path.parent / (
        ".drawio-render-" + secrets.token_hex(16) + "." + output_format
    )
    command = [
        str(drawio_command),
        "-x",
        "-f",
        output_format,
        "-e",
        "-b",
        str(args.border),
    ]
    if selector is not None or len(document.pages) > 1:
        command.extend(("-p", str(page.index + 1)))
    command.extend(("-o", str(temp_path), str(document.path)))
    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
            env={**os.environ, "DRAWIO_DISABLE_UPDATE": "true"},
        )
        if completed.returncode != 0:
            raise CliError(
                "DRAWIO_RENDER_FAILED",
                "Draw.io Desktop export failed.",
                {
                    "returnCode": completed.returncode,
                    "stderr": completed.stderr[-2000:],
                },
                exit_code=6,
            )
        if not temp_path.is_file():
            raise CliError(
                "DRAWIO_RENDER_FAILED",
                "Draw.io Desktop returned success without creating the requested output.",
                {"expected": str(temp_path)},
                exit_code=6,
            )
        data = temp_path.read_bytes()
        validate_render_output(data, output_format)
        connector_animation = None
        if output_format == "svg":
            try:
                svg_root, embedded_content = parse_editable_svg(data)
                mismatch = compare_embedded_svg_page(embedded_content, page)
            except CliError as exc:
                raise CliError(
                    "INVALID_RENDER_OUTPUT",
                    "Rendered SVG is not a safe editable Draw.io artifact.",
                    {"cause": exc.code, "message": exc.message},
                    exit_code=6,
                ) from exc
            if mismatch is not None:
                raise CliError(
                    "INVALID_RENDER_OUTPUT",
                    "Rendered SVG embedded content does not match the selected source page.",
                    mismatch,
                    exit_code=6,
                )
            connector_animation = connector_animation_summary(svg_root, page)
            if connector_animation["status"] == "missing":
                raise CliError(
                    "INVALID_RENDER_OUTPUT",
                    "Rendered SVG dropped a requested native connector animation.",
                    {
                        "cause": "SVG_CONNECTOR_ANIMATION_MISSING",
                        **connector_animation,
                    },
                    exit_code=6,
                )
        safe_commit(
            document,
            document.path,
            output_path,
            data,
            document.revision,
            validate_drawio_output=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CliError(
            "DRAWIO_RENDER_TIMEOUT",
            "Draw.io Desktop did not finish within 120 seconds.",
            exit_code=6,
        ) from exc
    finally:
        if os.path.lexists(str(temp_path)):
            os.unlink(str(temp_path))
    result = {
        "renderer": "drawio-desktop",
        "rendererCommand": str(drawio_command),
        "format": output_format,
        "page": {"index": page.index, "id": page.id, "name": page.name},
        "pageIndex": page.index,
        "editable": output_format == "svg",
        "renderArtifactReady": True,
        "visualReviewRequired": True,
        "sourceModified": False,
    }
    if connector_animation is not None:
        result["connectorAnimation"] = connector_animation
    return {
        "file": str(output_path),
        "source": str(document.path),
        "revision": document.revision,
        "result": result,
        "warnings": [
            {
                "code": "VISUAL_REVIEW_REQUIRED",
                "message": "Inspect the rendered artifact before marking the diagram ready.",
            }
        ],
    }


def single_page_projection(document, page):
    attributes = dict(document.root.attrib) if not document.bare else {}
    attributes.setdefault("host", "app.diagrams.net")
    root = ET.Element("mxfile", attributes)
    diagram_attributes = dict(page.diagram.attrib) if page.diagram is not None else {}
    diagram_attributes["id"] = page.id or "page-1"
    diagram_attributes["name"] = page.name or "Page 1"
    diagram = ET.SubElement(root, "diagram", diagram_attributes)
    diagram.append(copy.deepcopy(page.model))
    return ET.tostring(root, encoding="utf-8", short_empty_elements=True)


def expected_web_svg_name(document, page):
    if len(document.pages) == 1:
        return document.path.stem + ".svg"
    return f"{document.path.stem}-page-{page.index + 1:02d}.svg"


def web_svg_bridge_html(document, page):
    projection = single_page_projection(document, page)
    projection_base64 = base64.b64encode(projection).decode("ascii")
    page_name = html.escape(page.name or f"Page {page.index + 1}")
    source_name = html.escape(document.path.name)
    expected_name = expected_web_svg_name(document, page)
    expected_name_attribute = html.escape(expected_name, quote=True)
    revision = html.escape(document.revision)
    origin_json = json.dumps(DRAWIO_WEB_ORIGIN)
    projection_json = json.dumps(projection_base64)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        "frame-src https://embed.diagrams.net; script-src 'unsafe-inline'; "
        "style-src 'unsafe-inline'; img-src data: blob:; connect-src 'none'\">\n"
        f"<title>{source_name} · SVG export bridge</title>\n"
        "<style>"
        "html,body{height:100%;margin:0;background:#f6f7f9;color:#1f2937;"
        "font:14px/1.5 -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif}"
        "body{display:grid;grid-template-rows:auto 1fr}.bar{display:flex;gap:16px;"
        "align-items:center;justify-content:space-between;padding:10px 16px;background:#fff;"
        "border-bottom:1px solid #d9dde3}.meta{min-width:0}.meta strong,.meta span{display:block;"
        "overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.meta span{color:#667085;"
        "font-size:12px}.actions{display:flex;align-items:center;gap:12px}.status{color:#475467}"
        ".download{display:inline-flex;padding:8px 12px;border-radius:7px;background:#155eef;"
        "color:#fff;text-decoration:none;font-weight:700}.download[aria-disabled=true]{"
        "pointer-events:none;opacity:.45}iframe{width:100%;height:100%;border:0;background:#fff}"
        "main{position:relative}.offline-pages{position:absolute;inset:0;z-index:1;overflow:auto;background:#fff}"
        ".offline-pages figure{margin:12px}.offline-pages img{display:block;max-width:100%;height:auto}"
        ".offline-pages label{cursor:zoom-in}.offline-pages input:checked+label{cursor:zoom-out}"
        ".offline-pages input:checked+label img{max-width:none}.offline-pages input:focus-visible+label img{outline:2px solid #1769e0}"
        ".offline-pages~.viewer-notice{display:none}.offline-pages~.diagram-viewer{visibility:hidden}"
        "</style>\n</head>\n<body>\n"
        '<header class="bar"><div class="meta">'
        f"<strong>{source_name} · page {page.index + 1}: {page_name}</strong>"
        f"<span>Source revision: {revision}</span></div>"
        '<div class="actions"><span id="status" class="status">Connecting to official Draw.io…</span>'
        f'<a id="download" class="download" aria-disabled="true" download="{expected_name_attribute}">'
        "Download editable SVG</a></div></header>\n"
        '<iframe id="drawio" title="Official Draw.io SVG exporter" referrerpolicy="no-referrer"></iframe>\n'
        "<script>\n"
        f"const rendererOrigin={origin_json};\n"
        f"const projectionBase64={projection_json};\n"
        "const binary=atob(projectionBase64);"
        "const bytes=Uint8Array.from(binary,ch=>ch.charCodeAt(0));"
        "const projection=new TextDecoder().decode(bytes);\n"
        "const frame=document.getElementById('drawio');"
        "const status=document.getElementById('status');"
        "const download=document.getElementById('download');\n"
        "frame.src=rendererOrigin+'/?embed=1&proto=json&spin=1&libraries=1&noSaveBtn=1&noExitBtn=1&saveAndExit=0';\n"
        "let ready=false;let loadRequested=false;let exportRequested=false;let objectUrl=null;\n"
        "window.addEventListener('message',event=>{"
        "if(event.origin!==rendererOrigin||event.source!==frame.contentWindow)return;"
        "let message;try{message=typeof event.data==='string'?JSON.parse(event.data):event.data;}"
        "catch(error){return;}if(!message||typeof message!=='object')return;"
        "if(message.event==='init'&&!loadRequested){loadRequested=true;"
        "status.textContent='Loading selected page…';"
        "frame.contentWindow.postMessage(JSON.stringify({action:'load',xml:projection,autosave:0}),"
        "rendererOrigin);return;}"
        "if(message.event==='load'&&!exportRequested){exportRequested=true;"
        "status.textContent='Exporting selected page…';"
        "frame.contentWindow.postMessage(JSON.stringify({action:'export',format:'xmlsvg',"
        "embedImages:true}),rendererOrigin);return;}"
        "if(message.event==='export'&&typeof message.data==='string'){"
        "if(message.data.startsWith('data:image/svg+xml')){download.href=message.data;}"
        "else if(message.data.trimStart().startsWith('<svg')){"
        "objectUrl=URL.createObjectURL(new Blob([message.data],{type:'image/svg+xml'}));"
        "download.href=objectUrl;}else{status.textContent='Draw.io returned an unsupported SVG payload.';return;}"
        "ready=true;download.setAttribute('aria-disabled','false');"
        "status.textContent='Editable SVG ready. Download it, then run commit-web-svg.';return;}"
        "if(message.event==='error'){status.textContent='Draw.io export failed.';}"
        "});\n"
        "setTimeout(()=>{if(!ready)status.textContent='Export is not ready. Check network access to embed.diagrams.net.';},30000);\n"
        "window.addEventListener('beforeunload',()=>{if(objectUrl)URL.revokeObjectURL(objectUrl);});\n"
        "</script>\n</body>\n</html>\n"
    ).encode("utf-8")


def web_svg_bridge_command(args):
    document = load_document(args.input)
    page = select_pages(
        document, page_selector_from_args(args), require_for_multiple=True
    )[0]
    output_path = ensure_output_path(document.path, document.path, args.output)
    if output_path.suffix.lower() != ".html":
        raise CliError(
            "INVALID_OUTPUT_EXTENSION",
            "Web SVG bridge output must use the .html extension.",
            {"output": str(output_path)},
            exit_code=2,
        )
    output_data = web_svg_bridge_html(document, page)
    safe_commit(
        document,
        document.path,
        output_path,
        output_data,
        document.revision,
        validate_drawio_output=False,
    )
    return {
        "file": str(output_path),
        "source": str(document.path),
        "revision": document.revision,
        "result": {
            "renderer": "drawio-web-bridge",
            "rendererUrl": DRAWIO_WEB_ORIGIN,
            "page": {"index": page.index, "id": page.id, "name": page.name},
            "expectedSvgName": expected_web_svg_name(document, page),
            "networkRequired": True,
            "remotePageOnly": True,
            "sourceModified": False,
        },
        "warnings": [
            {
                "code": "REMOTE_DRAWIO_EDITOR_REQUIRED",
                "message": "The selected page is sent to the official Draw.io web editor for SVG export.",
            }
        ],
    }


def compact_svg_value(value):
    return re.sub(r"[\x00-\x20\x7f]+", "", value).lower()


def dangerous_svg_url(value):
    compact = compact_svg_value(value)
    if compact.startswith(("javascript:", "vbscript:")):
        return True
    if not compact.startswith("data:"):
        return False
    mime = compact[5:].split(";", 1)[0].split(",", 1)[0]
    return mime in SVG_ACTIVE_DATA_MIMES


def dangerous_svg_css(value):
    compact = compact_svg_value(value)
    if any(
        marker in compact
        for marker in (
            "javascript:",
            "vbscript:",
            "expression(",
            "@import",
            "-moz-binding",
            "behavior:",
        )
    ):
        return True
    if "\\" in value and ("url(" in compact or "@import" in compact):
        return True
    return any(
        "data:" + mime in compact
        for mime in SVG_ACTIVE_DATA_MIMES
    )


def validate_svg_active_content(root):
    for element in root.iter():
        tag = local_name(element.tag).lower()
        if tag in SVG_ACTIVE_ELEMENTS:
            raise CliError(
                "INVALID_WEB_SVG",
                "SVG contains an active element.",
                {"element": tag},
            )
        for name, value in element.attrib.items():
            attribute = local_name(name).lower()
            if attribute.startswith("on") or attribute == "srcdoc":
                raise CliError(
                    "INVALID_WEB_SVG",
                    "SVG contains an active attribute.",
                    {"attribute": attribute},
                )
            if attribute in ("href", "src") and dangerous_svg_url(value):
                raise CliError(
                    "INVALID_WEB_SVG",
                    "SVG contains an active URL.",
                    {"attribute": attribute},
                )
            if attribute == "style" and dangerous_svg_css(value):
                raise CliError(
                    "INVALID_WEB_SVG",
                    "SVG contains active CSS.",
                    {"attribute": attribute},
                )
        if tag == "style" and dangerous_svg_css(element.text or ""):
            raise CliError("INVALID_WEB_SVG", "SVG contains active CSS.")


def parse_editable_svg(data):
    try:
        data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CliError(
            "INVALID_WEB_SVG", "SVG must be UTF-8.", {"offset": exc.start}
        ) from exc
    upper = data.upper()
    if b"<!ENTITY" in upper:
        raise CliError("INVALID_WEB_SVG", "Entity declarations are not allowed in SVG.")
    parse_data = data
    if b"<!DOCTYPE" in upper:
        matches = list(SVG_DOCTYPE.finditer(data))
        if len(matches) != 1:
            raise CliError(
                "INVALID_WEB_SVG", "SVG contains an unsupported DOCTYPE."
            )
        match = matches[0]
        parse_data = data[: match.start()] + data[match.end() :]
        if b"<!DOCTYPE" in parse_data.upper():
            raise CliError(
                "INVALID_WEB_SVG", "SVG contains an unsupported DOCTYPE."
            )
    try:
        root = ET.fromstring(parse_data, parser=xml_parser())
    except ET.ParseError as exc:
        raise CliError(
            "INVALID_WEB_SVG", "Downloaded SVG XML parsing failed.", {"error": str(exc)}
        ) from exc
    if local_name(root.tag) != "svg":
        raise CliError(
            "INVALID_WEB_SVG", "Downloaded artifact root must be svg.", {"root": local_name(root.tag)}
        )
    validate_svg_active_content(root)
    content = root.get("content")
    if not content:
        raise CliError(
            "WEB_SVG_NOT_EDITABLE",
            "SVG does not contain embedded editable Draw.io content.",
        )
    return root, content


def connector_animation_summary(svg_root, page):
    expected = sorted(
        logical.id
        for logical in logical_cell_map(page).values()
        if logical.cell.get("edge") == "1"
        and native_style(logical.cell).get("flowAnimation") == "1"
    )
    if not expected:
        return {"status": "not-requested", "requested": 0, "preserved": 0}

    keyframes_present = any(
        local_name(element.tag).lower() == "style"
        and "@keyframes" in (element.text or "").lower()
        and "stroke-dashoffset" in (element.text or "").lower()
        for element in svg_root.iter()
    )
    expected_set = set(expected)
    preserved = set()
    for element in svg_root.iter():
        cell_id = element.get("data-cell-id")
        if cell_id not in expected_set:
            continue
        for rendered in element.iter():
            for declaration in rendered.get("style", "").split(";"):
                name, separator, value = declaration.partition(":")
                if (
                    separator
                    and name.strip().lower() == "animation"
                    and value.strip().lower() not in ("", "none", "initial", "unset")
                ):
                    preserved.add(cell_id)
                    break
            if cell_id in preserved:
                break

    missing = expected_set - preserved
    if not keyframes_present:
        missing = expected_set
    return {
        "status": "preserved" if not missing else "missing",
        "requested": len(expected),
        "preserved": len(expected) - len(missing),
        "missingCellIds": sorted(missing),
    }


def read_web_svg(path):
    user_path = Path(path).expanduser()
    if user_path.is_symlink():
        raise CliError(
            "INVALID_PATH", "Downloaded SVG input must not be a symlink.", {"path": str(user_path)}
        )
    try:
        svg_path = user_path.resolve(strict=True)
        stat = svg_path.stat()
    except FileNotFoundError as exc:
        raise CliError("FILE_NOT_FOUND", "Downloaded SVG does not exist.", {"path": str(user_path)}) from exc
    if not svg_path.is_file():
        raise CliError("INVALID_PATH", "Downloaded SVG input must be a file.", {"path": str(svg_path)})
    if stat.st_size > MAX_INPUT_BYTES:
        raise CliError(
            "WEB_SVG_SIZE_LIMIT",
            "Downloaded SVG exceeds the lightweight input limit.",
            {"path": str(svg_path), "limit": MAX_INPUT_BYTES, "size": stat.st_size},
        )
    data = svg_path.read_bytes()
    root, content = parse_editable_svg(data)
    return svg_path, data, root, content


def inspect_embedded_svg_pages(content):
    try:
        data = content.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CliError("INVALID_WEB_SVG", "Embedded Draw.io content is not valid UTF-8.") from exc
    if len(data) > MAX_EXPANDED_BYTES:
        raise CliError(
            "WEB_SVG_SIZE_LIMIT",
            "Embedded Draw.io content exceeds the expanded input limit.",
            {"limit": MAX_EXPANDED_BYTES, "size": len(data)},
        )
    try:
        with tempfile.NamedTemporaryFile(suffix=".drawio") as temporary:
            temporary.write(data)
            temporary.flush()
            embedded = load_document(temporary.name)
            return [
                {
                    "index": page.index,
                    "id": page.id or "page-1",
                    "name": page.name or "Page 1",
                    "cellIds": frozenset(logical_cell_map(page)),
                    "semanticRevision": page_semantic_revision(page),
                    "webExportRevision": page_web_export_revision(page),
                }
                for page in embedded.pages
            ]
    except CliError as exc:
        if exc.code.startswith("WEB_SVG") or exc.code == "INVALID_WEB_SVG":
            raise
        raise CliError(
            "INVALID_WEB_SVG",
            "Embedded Draw.io content is invalid.",
            {"cause": exc.code, "message": exc.message},
        ) from exc


def compare_embedded_svg_page(content, expected_page):
    embedded_pages = inspect_embedded_svg_pages(content)
    expected_id = expected_page.id or "page-1"
    if expected_page.id is not None:
        matches = [page for page in embedded_pages if page["id"] == expected_id]
    elif len(embedded_pages) == 1:
        matches = embedded_pages
    elif expected_page.index < len(embedded_pages):
        matches = [embedded_pages[expected_page.index]]
    else:
        matches = []
    if len(matches) != 1:
        return {
            "kind": "page",
            "expected": {"id": expected_id, "name": expected_page.name or "Page 1"},
            "matchingPages": len(matches),
        }
    actual = matches[0]
    expected_name = expected_page.name or "Page 1"
    if expected_page.diagram is not None and actual["name"] != expected_name:
        return {
            "kind": "page",
            "expected": {"id": expected_id, "name": expected_name},
            "actual": {"id": actual["id"], "name": actual["name"]},
        }
    expected_cells = frozenset(logical_cell_map(expected_page))
    if actual["cellIds"] != expected_cells:
        return {
            "kind": "cells",
            "missing": sorted(expected_cells - actual["cellIds"]),
            "unexpected": sorted(actual["cellIds"] - expected_cells),
        }
    expected_semantic_revision = page_web_export_revision(expected_page)
    if actual["webExportRevision"] != expected_semantic_revision:
        return {
            "kind": "content",
            "expectedRevision": expected_semantic_revision,
            "actualRevision": actual["webExportRevision"],
        }
    return None


def commit_web_svg_command(args):
    document = load_document(args.input)
    validate_expected_revision(document, args.expected_revision)
    page = select_pages(
        document, page_selector_from_args(args), require_for_multiple=True
    )[0]
    svg_path, svg_data, svg_root, embedded_content = read_web_svg(args.downloaded_svg)
    mismatch = compare_embedded_svg_page(embedded_content, page)
    if mismatch is not None and mismatch["kind"] == "page":
        raise CliError(
            "WEB_SVG_PAGE_MISMATCH",
            "Editable SVG page identity does not match the selected source page.",
            mismatch,
        )
    if mismatch is not None and mismatch["kind"] == "cells":
        raise CliError(
            "WEB_SVG_CELL_MISMATCH",
            "Editable SVG cell identities do not match the selected source page.",
            mismatch,
        )
    if mismatch is not None:
        raise CliError(
            "WEB_SVG_CONTENT_MISMATCH",
            "Editable SVG native content does not match the selected source page.",
            mismatch,
        )
    connector_animation = connector_animation_summary(svg_root, page)
    if connector_animation["status"] == "missing":
        raise CliError(
            "WEB_SVG_ANIMATION_MISSING",
            "Editable SVG dropped a requested native connector animation.",
            connector_animation,
        )
    output_path = ensure_output_path(document.path, svg_path, args.output)
    if output_path.suffix.lower() != ".svg":
        raise CliError(
            "INVALID_OUTPUT_EXTENSION",
            "Committed Web SVG output must use the .svg extension.",
            {"output": str(output_path)},
            exit_code=2,
        )
    safe_commit(
        document,
        svg_path,
        output_path,
        svg_data,
        args.expected_revision,
        validate_drawio_output=False,
    )
    return {
        "file": str(output_path),
        "source": str(document.path),
        "revision": document.revision,
        "result": {
            "renderer": "drawio-web",
            "format": "svg",
            "page": {"index": page.index, "id": page.id, "name": page.name},
            "editable": True,
            "connectorAnimation": connector_animation,
            "renderArtifactReady": True,
            "visualReviewRequired": True,
            "sourceModified": False,
            "downloadModified": False,
        },
        "warnings": [
            {
                "code": "VISUAL_REVIEW_REQUIRED",
                "message": "Inspect the committed SVG before marking the diagram ready.",
            }
        ],
    }


def offline_preview(document, paths):
    if not paths:
        return ""
    if len(paths) != len(document.pages):
        raise CliError("PREVIEW_PAGE_COUNT", "Provide one fallback PNG per page, in source order.")
    figures = []
    total = 0
    for page, path in zip(document.pages, paths):
        with Path(path).open("rb") as stream:
            data = stream.read(MAX_INPUT_BYTES - total + 1)
        total += len(data)
        if total > MAX_INPUT_BYTES:
            raise CliError("PREVIEW_SIZE_LIMIT", "Fallback PNGs exceed the combined input limit.")
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or data[12:16] != b"IHDR":
            raise CliError("INVALID_PREVIEW_PNG", "Expected a PNG page render.", {"path": str(path)})
        name = html.escape(page.name or f"Page {page.index + 1}", quote=True)
        encoded = base64.b64encode(data).decode("ascii")
        figures.append(
            f'<figure><figcaption>{page.index + 1}. {name}</figcaption>'
            f'<input type="checkbox" class="sr-only" id="zoom-{page.index}" aria-label="Actual size: {name}">'
            f'<label for="zoom-{page.index}"><img alt="{name}" src="data:image/png;base64,{encoded}"></label></figure>'
        )
    return '<section class="offline-pages" aria-label="Diagram preview">' + "".join(figures) + "</section>"


def preview_html(document, offline_pages=""):
    source_xml = document.source_bytes.decode("utf-8-sig")
    viewer_config = {
        "highlight": "#0000ff",
        "nav": True,
        "page": 0,
        "resize": False,
        "auto-fit": True,
        "center": True,
        "toolbar": "pages zoom layers lightbox",
        "tooltips": True,
        "xml": source_xml,
    }
    config_attribute = html.escape(
        json.dumps(viewer_config, ensure_ascii=False, separators=(",", ":")),
        quote=True,
    )
    title = html.escape(document.path.stem)
    source_name = html.escape(document.path.name)
    display_name = html.escape(document.path.stem)
    source_name_json = json.dumps(document.path.name)
    edited_name_json = json.dumps(f"{document.path.stem}-edited.drawio")
    editor_origin_json = json.dumps(DRAWIO_WEB_ORIGIN)
    page_count = len(document.pages)
    page_word = "page" if page_count == 1 else "pages"
    page_items = "".join(
        f'<li><button type="button" class="page-tab" data-page-index="{page.index}" '
        f'title="{html.escape(page.name or f"Page {page.index + 1}", quote=True)}" '
        'aria-controls="diagram-viewer" disabled>'
        f"{html.escape(page.name or f'Page {page.index + 1}')}</button></li>"
        for page in document.pages
    )
    # Rail bounds include 4px gaps and 4px padding on each side.
    page_tabs = (
        '<nav class="page-tabs" aria-label="Diagram pages" '
        f'style="--page-count:{page_count};--tabs-min:{page_count * 100 + 4}px;'
        f'--tabs-max:{page_count * 224 + 4}px">'
        f"<ol>{page_items}</ol>"
        '<span class="sr-only">Select a page here or use the viewer controls.</span>'
        '</nav>'
    )
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<title>{title} · Draw.io preview</title>\n"
        "<style>"
        "html,body{margin:0;min-height:100%;background:#f6f7f9;color:#1f2937;"
        "font:14px/1.5 -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif}"
        "body{height:100vh;height:100dvh;display:flex;flex-direction:column;overflow:hidden}"
        ".product-rail{flex-shrink:0;box-sizing:border-box;position:relative;z-index:2;display:flex;gap:18px;"
        "align-items:center;min-height:70px;padding:0 22px;background:#fff;"
        "border-bottom:1px solid #dbe2eb}"
        ".product-rail::before{content:'';position:absolute;left:0;top:16px;width:4px;height:38px;"
        "border-radius:0 4px 4px 0;background:#1769e0}"
        ".identity{display:flex;flex:0 1 420px;min-width:220px;flex-direction:column;gap:2px}"
        ".identity strong{overflow:hidden;color:#1f2937;font-size:16px;font-weight:700;"
        "line-height:1.3;text-overflow:ellipsis;white-space:nowrap}"
        ".preview-mode{color:#64748b;font-size:12px;line-height:1.35}"
        ".page-tabs{flex:1 1 0;min-width:0;max-width:var(--tabs-max);margin-left:auto;overflow-x:auto;scrollbar-width:thin}"
        ".page-tabs ol{box-sizing:border-box;display:grid;grid-template-columns:repeat(var(--page-count),minmax(0,1fr));"
        "gap:4px;width:100%;min-width:var(--tabs-min);list-style:none;margin:0;padding:4px;"
        "border-radius:10px;background:#f0f3f7}"
        ".page-tabs li{min-width:0}.page-tab{box-sizing:border-box;width:100%;overflow:hidden;text-overflow:ellipsis;appearance:none;border:0;background:transparent;cursor:pointer;font-family:inherit;display:block;padding:9px 13px;border-radius:7px;color:#4b5563;"
        "font-size:13px;font-weight:600;line-height:1.2;white-space:nowrap}"
        ".page-tab:hover{background:#e5ebf3}.page-tab:focus-visible{outline:3px solid #93c5fd;outline-offset:-3px}"
        ".page-tab:disabled{cursor:not-allowed;opacity:.6}"
        ".page-tab.active{background:#fff;color:#1559ba;box-shadow:0 1px 3px rgba(17,31,54,.12)}"
        ".actions{flex-shrink:0;display:flex;align-items:center;margin-left:8px}"
        ".actions button{display:inline-flex;align-items:center;gap:7px;appearance:none;border:0;"
        "border-radius:8px;background:#155eef;color:#fff;cursor:pointer;font:600 14px/1.2 "
        "-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;padding:10px 14px;white-space:nowrap}"
        ".actions button svg{width:14px;height:14px;fill:none;stroke:currentColor;stroke-linecap:round;"
        "stroke-linejoin:round;stroke-width:1.8}.actions button:hover{background:#124bc2}"
        ".actions button:focus-visible{outline:3px solid #93c5fd;outline-offset:2px}"
        ".edit-status{position:absolute;top:calc(100% + 8px);right:22px;z-index:20;max-width:min(520px,"
        "calc(100vw - 44px));overflow:hidden;padding:8px 11px;border:1px solid transparent;"
        "border-radius:8px;box-shadow:0 8px 24px rgba(17,31,54,.16);font-size:12px;"
        "text-overflow:ellipsis;white-space:nowrap}"
        ".edit-status[hidden]{display:none}.edit-status[data-level=info]{border-color:#bfdbfe;"
        "background:#eff6ff;color:#1d4ed8}.edit-status[data-level=success]{border-color:#a7f3d0;"
        "background:#ecfdf3;color:#067647}.edit-status[data-level=error]{border-color:#fecaca;"
        "background:#fef3f2;color:#b42318}"
        ".viewer-notice{margin-bottom:12px;padding:12px 16px;border:1px solid #dbe2eb;"
        "border-radius:8px;background:#fff}.viewer-notice[hidden]{display:none}"
        ".viewer-notice[data-level=error]{border-color:#fecaca;background:#fef3f2;color:#b42318}"
        ".viewer-notice button{margin-left:12px;padding:7px 10px;border:1px solid currentColor;"
        "border-radius:6px;background:#fff;color:inherit;cursor:pointer;font:inherit}"
        ".viewer-notice button:focus-visible{outline:3px solid #93c5fd;outline-offset:2px}"
        ".sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;"
        "clip:rect(0,0,0,0);white-space:nowrap;border:0}"
        "@media(max-width:900px){.product-rail{flex-wrap:wrap;gap:10px 14px;padding:12px 16px 12px 28px}"
        ".product-rail::before{left:0;top:15px}.identity{flex:1 1 280px}.actions{margin-left:auto}"
        ".page-tabs{order:3;flex:1 0 100%;max-width:none;margin-left:0}.page-tabs ol{max-width:var(--tabs-max)}.edit-status{right:16px;max-width:calc(100vw - 32px)}}"
        "@media(max-width:560px){.identity{min-width:0;flex-basis:calc(100% - 130px)}"
        ".preview-mode{white-space:nowrap}.actions button{padding:9px 11px}.page-tab{padding:8px 11px}}"
        "main{box-sizing:border-box;flex:1;min-height:0;display:flex;flex-direction:column;padding:16px}"
        ".viewer-notice{flex-shrink:0}.diagram-viewer{flex:1;min-height:0;overflow:auto!important;max-width:calc(100% - 2px);margin-inline:auto;border:1px solid transparent;"
        "background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.08)}"
        "main{position:relative}.offline-pages{position:absolute;inset:0;z-index:1;overflow:auto;background:#fff}"
        ".offline-pages figure{margin:12px}.offline-pages img{display:block;max-width:100%;height:auto}"
        ".offline-pages label{cursor:zoom-in}.offline-pages input:checked+label{cursor:zoom-out}"
        ".offline-pages input:checked+label img{max-width:none}.offline-pages input:focus-visible+label img{outline:2px solid #1769e0}"
        ".offline-pages~.viewer-notice{display:none}.offline-pages~.diagram-viewer{visibility:hidden}"
        "</style>\n</head>\n<body>\n"
        f'<header class="product-rail"><div class="identity"><strong title="{source_name}">{display_name}</strong>'
        f'<span class="preview-mode">Read-only companion preview · {page_count} {page_word}</span></div>'
        f'{page_tabs}'
        '<div class="actions"><button id="edit-diagram" type="button"><span>Edit a copy</span>'
        '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M6 3h7v7M13 3 5 11"/>'
        '<path d="M11 9v3a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h3"/></svg></button>'
        '<span id="edit-status" class="edit-status" role="status" aria-live="polite" hidden></span>'
        "</div></header>\n"
        f'<main>{offline_pages}<div id="viewer-notice" class="viewer-notice" data-level="info">'
        '<span id="viewer-status" role="status" aria-live="polite">Loading diagram preview…</span>'
        '<button id="retry-preview" type="button" hidden>Retry preview</button></div>'
        f'<div id="diagram-viewer" class="diagram-viewer" style="width:100%;height:100%" data-mxgraph="{config_attribute}"></div></main>\n'
        f'{"<noscript>The interactive viewer requires JavaScript and network access.</noscript>" if not offline_pages else ""}\n' 
        "<script>\n"
        "(()=>{\n"
        f"const editorOrigin={editor_origin_json};\n"
        "const editorUrl=editorOrigin+'/?embed=1&proto=json&spin=1&libraries=1&saveAndExit=1';\n"
        f"const sourceName={source_name_json};\n"
        f"const editedName={edited_name_json};\n"
        "const graph=document.querySelector('.diagram-viewer');\n"
        "const sourceXml=JSON.parse(graph.getAttribute('data-mxgraph')).xml;\n"
        "const button=document.getElementById('edit-diagram');\n"
        "const status=document.getElementById('edit-status');\n"
        "let editorWindow=null;let initTimer=null;let loadTimer=null;let loadRequested=false;let saved=false;\n"
        "let ignoredOriginMessages=0;let ignoredSourceMessages=0;\n"
        "const setStage=(stage,text,level='info')=>{status.dataset.stage=stage;status.dataset.level=level;"
        "status.textContent=text;status.hidden=!text;};\n"
        "const clearTimer=(name)=>{if(name==='init'&&initTimer!==null){clearTimeout(initTimer);initTimer=null;}"
        "if(name==='load'&&loadTimer!==null){clearTimeout(loadTimer);loadTimer=null;}};\n"
        "const clearTimers=()=>{clearTimer('init');clearTimer('load');};\n"
        "const ignoredSummary=()=>` Ignored messages: origin=${ignoredOriginMessages}, source=${ignoredSourceMessages}.`;\n"
        "const finishSession=()=>{clearTimers();editorWindow=null;loadRequested=false;};\n"
        "const downloadEdited=(xml)=>{\n"
        "if(typeof xml!=='string'||(!xml.includes('<mxfile')&&!xml.includes('<mxGraphModel'))){"
        "setStage('EDITOR_SAVE_INVALID','Draw.io returned an invalid diagram. Nothing was downloaded.','error');return false;}\n"
        "const url=URL.createObjectURL(new Blob([xml],{type:'application/xml'}));\n"
        "const link=document.createElement('a');link.href=url;link.download=editedName;\n"
        "document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);\n"
        "saved=true;setStage('EDITOR_DOWNLOAD_READY','Downloaded '+editedName+'. The original file was not modified.','success');return true;\n"
        "};\n"
        "button.addEventListener('click',()=>{\n"
        "if(editorWindow&&!editorWindow.closed){editorWindow.focus();return;}\n"
        "saved=false;loadRequested=false;ignoredOriginMessages=0;ignoredSourceMessages=0;"
        "editorWindow=window.open(editorUrl,'_blank');\n"
        "if(!editorWindow){setStage('EDITOR_POPUP_BLOCKED','Could not open the editor. Allow popups and try again.','error');return;}\n"
        "setStage('EDITOR_OPENING','Waiting for the official Draw.io editor to initialize.');\n"
        "clearTimers();initTimer=setTimeout(()=>{setStage('EDITOR_INIT_TIMEOUT',"
        "'The editor did not initialize. Check network access, popup policy, or extensions.'+ignoredSummary(),'error');},30000);\n"
        "});\n"
        "window.addEventListener('message',(event)=>{\n"
        "if(event.origin!==editorOrigin){ignoredOriginMessages+=1;return;}\n"
        "if(!editorWindow||event.source!==editorWindow){ignoredSourceMessages+=1;return;}\n"
        "let message;try{message=typeof event.data==='string'?JSON.parse(event.data):event.data;}catch{"
        "setStage('EDITOR_MESSAGE_INVALID','The editor returned an invalid response.','error');return;}\n"
        "if(!message||typeof message!=='object'){setStage('EDITOR_MESSAGE_INVALID','The editor returned an invalid response.','error');return;}\n"
        "if(message.event==='init'&&!loadRequested){\n"
        "loadRequested=true;clearTimer('init');setStage('EDITOR_INIT_RECEIVED','Sending the native diagram to Draw.io.');\n"
        "try{editorWindow.postMessage(JSON.stringify({action:'load',xml:sourceXml,"
        "autosave:0,title:sourceName,saveAndExit:1}),editorOrigin);}catch(error){"
        "setStage('EDITOR_LOAD_DISPATCH_FAILED','Could not send the diagram to the editor: '+error.name,'error');return;}\n"
        "setStage('EDITOR_LOAD_SENT','Waiting for Draw.io to confirm the diagram loaded.');"
        "loadTimer=setTimeout(()=>{setStage('EDITOR_LOAD_TIMEOUT',"
        "'Draw.io did not confirm loading the diagram.'+ignoredSummary(),'error');},30000);return;}\n"
        "if(message.event==='load'){clearTimer('load');setStage('EDITOR_LOADED','Editable copy ready. Saving downloads a new file.','success');return;}\n"
        "if(message.event==='save'){\n"
        "setStage('EDITOR_SAVE_RECEIVED','Preparing the edited native file download.');\n"
        "const downloaded=downloadEdited(message.xml);\n"
        "if(downloaded&&message.exit){try{editorWindow.close();}catch{}finishSession();}return;}\n"
        "if(message.event==='exit'){if(!saved){setStage('EDITOR_EXITED','Editor closed. The source file was not modified.','info');}finishSession();return;}\n"
        "if(message.event==='error'){clearTimers();setStage('EDITOR_REPORTED_ERROR',"
        "'Draw.io reported an editor error. The source file was not modified.','error');}\n"
        "});\n"
        "})();\n"
        "</script>\n"
        "<script>\n"
        "(()=>{\n"
        "const container=document.getElementById('diagram-viewer');\n"
        "const tabs=Array.from(document.querySelectorAll('.page-tab'));\n"
        "const notice=document.getElementById('viewer-notice');\n"
        "const status=document.getElementById('viewer-status');\n"
        "const retry=document.getElementById('retry-preview');\n"
        "let ready=false;let started=false;let timer=null;\n"
        "const fail=(message)=>{if(ready)return;clearTimeout(timer);\n"
        "notice.hidden=false;notice.dataset.level='error';status.textContent=message;retry.hidden=false;};\n"
        "retry.addEventListener('click',()=>window.location.reload());\n"
        "window.diagramViewerLoadFailed=()=>fail('Could not load the diagram viewer. Check your connection and retry.');\n"
        "timer=setTimeout(()=>fail('The diagram preview is taking too long to load. Check your connection and retry.'),30000);\n"
        "window.initializeDiagramViewer=()=>{if(started)return;started=true;\n"
        "try{GraphViewer.createViewerForElement(container,(viewer)=>{\n"
        "const tooltipGraph=viewer.graph;tooltipGraph.setTooltips(true);\n"
        "const nativeTooltip=tooltipGraph.getTooltipForCell;\n"
        "tooltipGraph.getTooltipForCell=function(cell){\n"
        "for(let current=cell;current;current=this.model.getParent(current)){\n"
        "const tooltip=nativeTooltip.call(this,current);if(tooltip)return tooltip;}return '';};\n"
        "let fittedPage=null;let fitFrame=null;\n"
        "const fitOverview=()=>{fitFrame=null;if(container.clientWidth<=0||container.clientHeight<=0)return;\n"
        "const graph=viewer.graph;const previousMax=graph.maxFitScale;graph.maxFitScale=1;\n"
        "try{container.scrollLeft=0;container.scrollTop=0;graph.fit(16);\n"
        "const bounds=graph.getGraphBounds();const view=graph.view;\n"
        "view.setTranslate(view.translate.x+((container.clientWidth-bounds.width)/2-bounds.x)/view.scale,\n"
        "view.translate.y+((container.clientHeight-bounds.height)/2-bounds.y)/view.scale);\n"
        "graph.initialViewState={scale:graph.view.scale,translate:graph.view.translate.clone()};\n"
        "}finally{graph.maxFitScale=previousMax;}\n"
        "};\n"
        "const scheduleOverview=()=>{if(fitFrame!==null)cancelAnimationFrame(fitFrame);fitFrame=requestAnimationFrame(fitOverview);};\n"
        "new ResizeObserver(scheduleOverview).observe(container,{box:'border-box'});\n"
        "const pageNav=document.querySelector('.page-tabs');\n"
        "const revealActiveTab=()=>{const active=pageNav.querySelector('.page-tab.active');if(!active)return;\n"
        "const bounds=pageNav.getBoundingClientRect();const tabBounds=active.getBoundingClientRect();\n"
        "if(tabBounds.left<bounds.left+4){pageNav.scrollLeft+=tabBounds.left-bounds.left-4;}\n"
        "else if(tabBounds.right>bounds.right-4){pageNav.scrollLeft+=tabBounds.right-bounds.right+4;}\n"
        "};\n"
        "const syncPage=()=>{if(fittedPage!==viewer.currentPage){fittedPage=viewer.currentPage;scheduleOverview();}\n"
        "tabs.forEach((tab)=>{\n"
        "const active=Number(tab.dataset.pageIndex)===viewer.currentPage;\n"
        "tab.classList.toggle('active',active);\n"
        "if(active){tab.setAttribute('aria-current','page');}else{tab.removeAttribute('aria-current');}\n"
        "});revealActiveTab();};\n"
        "window.addEventListener('resize',revealActiveTab);\n"
        "tabs.forEach((tab)=>{tab.disabled=false;tab.addEventListener('click',()=>{\n"
        "const index=Number(tab.dataset.pageIndex);\n"
        "if(index!==viewer.currentPage){viewer.selectPage(index);}\n"
        "});});\n"
        "viewer.addListener('graphChanged',syncPage);syncPage();\n"
        "document.querySelector('.offline-pages')?.remove();scheduleOverview();\n"
        "ready=true;clearTimeout(timer);notice.hidden=true;retry.hidden=true;\n"
        "});}catch(error){tabs.forEach((tab)=>{tab.disabled=true;});\n"
        "fail('Could not initialize the diagram preview. Retry, or open the native file in Draw.io.');}\n"
        "};})();\n"
        "</script>\n"
        '<script src="https://viewer.diagrams.net/js/viewer-static.min.js" '
        'onload="initializeDiagramViewer()" onerror="diagramViewerLoadFailed()"></script>\n'
        "</body>\n</html>\n"
    ).encode("utf-8")


def preview_command(args):
    document = load_document(args.input)
    output_path = ensure_output_path(document.path, document.path, args.output)
    offline_pages = offline_preview(document, args.fallback_png)
    output_data = preview_html(document, offline_pages)
    safe_commit(
        document,
        document.path,
        output_path,
        output_data,
        document.revision,
        validate_drawio_output=False,
    )
    return {
        "file": str(output_path),
        "source": str(document.path),
        "revision": document.revision,
        "result": {
            "previewRevision": revision_for(output_data),
            "networkRequired": not bool(offline_pages),
            "offlinePages": len(args.fallback_png),
            "viewer": "https://viewer.diagrams.net/js/viewer-static.min.js",
            "editor": DRAWIO_WEB_ORIGIN,
            "editorAutoLoad": True,
            "editorHandshakeDiagnostics": True,
            "browserSaveCreatesNewFile": True,
            "pageCount": len(document.pages),
            "pages": [
                {"index": page.index, "id": page.id, "name": page.name}
                for page in document.pages
            ],
            "initialPage": 0,
            "sourceModified": False,
        },
        "warnings": [
            {
                "code": "REMOTE_VIEWER_REQUIRED",
                "message": "Interactive viewing and web editing require network access to official Draw.io services.",
            }
        ],
    }


def add_page_args(parser, required=False):
    group = parser.add_mutually_exclusive_group(required=required)
    group.add_argument("--page-id", help="Select a page by stable native ID.")
    group.add_argument("--page-name", help="Select a uniquely named page.")
    group.add_argument("--page-index", type=int, help="Select a zero-based page index.")


def build_parser():
    parser = argparse.ArgumentParser(description="Safely inspect and modify native Draw.io files.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Summarize pages and cells.")
    inspect_parser.add_argument("input")
    add_page_args(inspect_parser)
    inspect_parser.set_defaults(handler=inspect_command)

    query_parser = subparsers.add_parser("query", help="Query cells by ID or label.")
    query_parser.add_argument("input")
    add_page_args(query_parser)
    query_parser.add_argument("--id", dest="ids", action="append")
    labels = query_parser.add_mutually_exclusive_group()
    labels.add_argument("--label")
    labels.add_argument("--label-contains")
    query_parser.add_argument("--include-style", action="store_true")
    query_parser.add_argument("--include-raw", action="store_true")
    query_parser.add_argument("--limit", type=int, default=DEFAULT_QUERY_LIMIT)
    query_parser.set_defaults(handler=query_command)

    patch_parser = subparsers.add_parser("patch", help="Apply a transactional native-cell patch.")
    patch_parser.add_argument("input")
    patch_parser.add_argument("patch")
    patch_parser.add_argument("--output", required=True)
    patch_parser.set_defaults(handler=patch_command)

    validate_parser = subparsers.add_parser("validate", help="Validate a supported Draw.io file.")
    validate_parser.add_argument("input")
    validate_parser.set_defaults(handler=validate_command)

    layout_parser = subparsers.add_parser(
        "check-layout", help="Report deterministic geometry collisions without changing the file."
    )
    layout_parser.add_argument("input")
    add_page_args(layout_parser)
    layout_detail = layout_parser.add_mutually_exclusive_group()
    layout_detail.add_argument(
        "--summary", action="store_true", help="Return compact aggregate findings (default)."
    )
    layout_detail.add_argument(
        "--verbose", action="store_true", help="Return per-cell warnings and advisories."
    )
    layout_parser.add_argument(
        "--only-collisions", action="store_true", help="Suppress warning/advisory payloads."
    )
    layout_parser.add_argument(
        "--expect-single-page",
        action="store_true",
        help="Report content spanning multiple declared page tiles as an unresolved risk.",
    )
    layout_parser.set_defaults(handler=check_layout_command)

    topology_parser = subparsers.add_parser(
        "check-topology", help="Lint native directed connectivity without changing the file."
    )
    topology_parser.add_argument("input")
    add_page_args(topology_parser)
    topology_parser.add_argument("--start", dest="starts", action="append")
    topology_parser.add_argument("--terminal", dest="terminals", action="append")
    topology_parser.add_argument(
        "--expect-edge",
        dest="expected_edges",
        action="append",
        nargs="+",
        metavar="CELL",
        help="Require SOURCE TARGET or SOURCE:TARGET; repeat for multiple edges.",
    )
    topology_parser.add_argument(
        "--require-connected",
        action="store_true",
        help="Treat multiple weak topology components as an issue.",
    )
    topology_detail = topology_parser.add_mutually_exclusive_group()
    topology_detail.add_argument(
        "--summary", action="store_true", help="Return compact aggregate findings (default)."
    )
    topology_detail.add_argument(
        "--verbose", action="store_true", help="Return complete cell and component details."
    )
    topology_parser.set_defaults(handler=check_topology_command)

    render_parser = subparsers.add_parser(
        "render", help="Export a real PNG, SVG, or PDF through Draw.io Desktop."
    )
    render_parser.add_argument("input")
    add_page_args(render_parser)
    render_parser.add_argument("--output", required=True)
    render_parser.add_argument("--format", choices=sorted(DRAWIO_FORMATS))
    render_parser.add_argument("--border", type=int, default=10)
    render_parser.add_argument("--drawio-command")
    render_parser.set_defaults(handler=render_command)

    bridge_parser = subparsers.add_parser(
        "web-svg-bridge",
        help="Create a single-page HTML bridge for editable SVG export through official Draw.io Web.",
    )
    bridge_parser.add_argument("input")
    add_page_args(bridge_parser)
    bridge_parser.add_argument("--output", required=True)
    bridge_parser.set_defaults(handler=web_svg_bridge_command)

    commit_svg_parser = subparsers.add_parser(
        "commit-web-svg", help="Validate and commit a downloaded editable Draw.io Web SVG."
    )
    commit_svg_parser.add_argument("input")
    commit_svg_parser.add_argument("downloaded_svg")
    add_page_args(commit_svg_parser)
    commit_svg_parser.add_argument("--expected-revision", required=True)
    commit_svg_parser.add_argument("--output", required=True)
    commit_svg_parser.set_defaults(handler=commit_web_svg_command)

    preview_parser = subparsers.add_parser(
        "preview", help="Create a companion HTML using the official remote Draw.io viewer."
    )
    preview_parser.add_argument("input")
    preview_parser.add_argument("--output", required=True)
    preview_parser.add_argument("--fallback-png", action="append", default=[],
                                help="Embed one official page render per page, in source order, for offline viewing.")
    preview_parser.set_defaults(handler=preview_command)

    page_parser = subparsers.add_parser("page", help="Safely add, rename, or delete a page.")
    page_subparsers = page_parser.add_subparsers(dest="page_command", required=True)

    page_add_parser = page_subparsers.add_parser("add", help="Append a page.")
    page_add_parser.add_argument("input")
    page_add_parser.add_argument("--name", required=True)
    page_add_parser.add_argument("--id", dest="page_id")
    page_add_parser.add_argument("--model-file")
    page_add_parser.add_argument("--expected-revision", required=True)
    page_add_parser.add_argument("--output", required=True)
    page_add_parser.set_defaults(handler=page_add_command)

    page_rename_parser = page_subparsers.add_parser("rename", help="Rename one page.")
    page_rename_parser.add_argument("input")
    add_page_args(page_rename_parser, required=True)
    page_rename_parser.add_argument("--name", required=True)
    page_rename_parser.add_argument("--expected-revision", required=True)
    page_rename_parser.add_argument("--output", required=True)
    page_rename_parser.set_defaults(handler=page_rename_command)

    page_delete_parser = page_subparsers.add_parser("delete", help="Delete one page.")
    page_delete_parser.add_argument("input")
    add_page_args(page_delete_parser, required=True)
    page_delete_parser.add_argument("--expected-revision", required=True)
    page_delete_parser.add_argument("--output", required=True)
    page_delete_parser.set_defaults(handler=page_delete_command)

    versions_parser = subparsers.add_parser("versions", help="List immutable sibling versions.")
    versions_parser.add_argument("input")
    versions_parser.set_defaults(handler=versions_command)

    restore_parser = subparsers.add_parser("restore", help="Copy an old version to a new output.")
    restore_parser.add_argument("input")
    restore_parser.add_argument("--expected-revision", required=True)
    restore_parser.add_argument("--output", required=True)
    restore_parser.set_defaults(handler=restore_command)

    publish_parser = subparsers.add_parser(
        "publish", help="Publish a validated working file to a no-clobber output."
    )
    publish_parser.add_argument("input")
    publish_parser.add_argument("--expected-revision", required=True)
    publish_parser.add_argument("--output", required=True)
    publish_parser.set_defaults(handler=publish_command)
    return parser


def success_payload(command, result):
    payload = {"version": VERSION, "ok": True, "command": command}
    payload.update(result)
    return payload


def error_payload(command, error):
    return {
        "version": VERSION,
        "ok": False,
        "command": command,
        "error": {"code": error.code, "message": error.message, "details": error.details},
        "warnings": [],
    }


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = success_payload(args.command, args.handler(args))
        exit_code = 0
    except CliError as exc:
        payload = error_payload(args.command, exc)
        exit_code = exc.exit_code
    except (OSError, ValueError) as exc:
        error = CliError("IO_ERROR", "File operation failed.", {"error": str(exc)}, exit_code=6)
        payload = error_payload(args.command, error)
        exit_code = error.exit_code
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

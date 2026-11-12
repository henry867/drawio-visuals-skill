#!/usr/bin/env python3
"""Loopback-only official Draw.io Web SVG export session."""

import argparse
import base64
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import urllib.parse


SCRIPT_DIR = Path(__file__).resolve().parent
CORE_PATH = SCRIPT_DIR / "drawio_file.py"
CORE_SPEC = importlib.util.spec_from_file_location("drawio_foundry_core", CORE_PATH)
core = importlib.util.module_from_spec(CORE_SPEC)
CORE_SPEC.loader.exec_module(core)

MAX_SESSION_SVG_BYTES = core.MAX_INPUT_BYTES


def page_projection(page, document):
    return base64.b64encode(core.single_page_projection(document, page)).decode("ascii")


def session_html(document, pages, token):
    page_payload = [
        {
            "index": page.index,
            "id": page.id,
            "name": page.name or f"Page {page.index + 1}",
            "projection": page_projection(page, document),
        }
        for page in pages
    ]
    pages_json = json.dumps(page_payload, ensure_ascii=False).replace("<", "\\u003c")
    token_json = json.dumps(token)
    renderer_json = json.dumps(core.DRAWIO_WEB_ORIGIN)
    source_name = html.escape(document.path.name)
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; "
        "frame-src https://embed.diagrams.net; script-src 'unsafe-inline'; "
        "style-src 'unsafe-inline'; connect-src 'self'\">"
        f"<title>{source_name} · Web SVG session</title>"
        "<style>html,body{height:100%;margin:0;background:#f6f7f9;color:#1f2937;"
        "font:14px/1.5 -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif}"
        "body{display:grid;grid-template-rows:auto 1fr}.bar{padding:12px 16px;background:#fff;"
        "border-bottom:1px solid #d9dde3}.bar strong,.bar span{display:block}.bar span{color:#667085}"
        "iframe{width:100%;height:100%;border:0;background:#fff}</style></head><body>"
        f"<header class=\"bar\"><strong>{source_name}</strong><span id=\"status\">Starting…</span></header>"
        "<iframe id=\"drawio\" title=\"Official Draw.io SVG exporter\" referrerpolicy=\"no-referrer\"></iframe>"
        "<script>"
        f"const rendererOrigin={renderer_json};const pages={pages_json};const token={token_json};"
        "const frame=document.getElementById('drawio');const status=document.getElementById('status');"
        "let current=0;let initialized=false;let exportRequested=false;let finished=false;"
        "function decodeBase64Utf8(value){const binary=atob(value);const bytes=Uint8Array.from(binary,c=>c.charCodeAt(0));"
        "return new TextDecoder().decode(bytes);}"
        "function loadCurrent(){exportRequested=false;const page=pages[current];"
        "status.textContent=`Loading page ${current+1}/${pages.length}: ${page.name}`;"
        "frame.contentWindow.postMessage(JSON.stringify({action:'load',xml:decodeBase64Utf8(page.projection),autosave:0}),rendererOrigin);}"
        "function svgText(data){if(data.trimStart().startsWith('<svg'))return data;"
        "if(!data.startsWith('data:image/svg+xml'))throw new Error('Unsupported SVG payload');"
        "const comma=data.indexOf(',');const header=data.slice(0,comma);const body=data.slice(comma+1);"
        "return header.includes(';base64')?decodeBase64Utf8(body):decodeURIComponent(body);}"
        "async function submit(data){const page=pages[current];status.textContent=`Validating page ${current+1}/${pages.length}…`;"
        "const response=await fetch(`/submit?token=${encodeURIComponent(token)}&page=${page.index}`,"
        "{method:'POST',headers:{'Content-Type':'image/svg+xml'},body:svgText(data)});"
        "const result=await response.json();if(!response.ok)throw new Error(result.error||'Commit failed');"
        "current+=1;if(current>=pages.length){finished=true;status.textContent='All editable SVG pages were validated and committed.';return;}loadCurrent();}"
        "frame.src=rendererOrigin+'/?embed=1&proto=json&spin=1&libraries=1&noSaveBtn=1&noExitBtn=1&saveAndExit=0';"
        "window.addEventListener('message',event=>{if(event.origin!==rendererOrigin||event.source!==frame.contentWindow)return;"
        "let message;try{message=typeof event.data==='string'?JSON.parse(event.data):event.data;}catch(error){return;}"
        "if(!message||typeof message!=='object'||finished)return;"
        "if(message.event==='init'&&!initialized){initialized=true;loadCurrent();return;}"
        "if(message.event==='load'&&!exportRequested){exportRequested=true;status.textContent=`Exporting page ${current+1}/${pages.length}…`;"
        "frame.contentWindow.postMessage(JSON.stringify({action:'export',format:'xmlsvg',embedImages:true}),rendererOrigin);return;}"
        "if(message.event==='export'&&typeof message.data==='string'){submit(message.data).catch(error=>{status.textContent=`Session failed: ${error.message}`;});return;}"
        "if(message.event==='error')status.textContent='Official Draw.io export failed.';});"
        "setTimeout(()=>{if(!finished)status.textContent='Session is still waiting for Draw.io Web; check network access.';},30000);"
        "</script></body></html>"
    ).encode("utf-8")


def validate_and_commit_svg(document, page, svg_data, output_dir):
    if len(svg_data) > MAX_SESSION_SVG_BYTES:
        raise core.CliError(
            "WEB_SVG_SESSION_PAYLOAD_LIMIT",
            "Web SVG session payload exceeds the configured limit.",
            {"bytes": len(svg_data), "limit": MAX_SESSION_SVG_BYTES},
        )
    svg_root, embedded_content = core.parse_editable_svg(svg_data)
    mismatch = core.compare_embedded_svg_page(embedded_content, page)
    if mismatch is not None and mismatch["kind"] == "page":
        raise core.CliError("WEB_SVG_PAGE_MISMATCH", "Editable SVG page identity does not match.", mismatch)
    if mismatch is not None and mismatch["kind"] == "cells":
        raise core.CliError("WEB_SVG_CELL_MISMATCH", "Editable SVG cell identities do not match.", mismatch)
    if mismatch is not None:
        raise core.CliError("WEB_SVG_CONTENT_MISMATCH", "Editable SVG native content does not match.", mismatch)
    animation = core.connector_animation_summary(svg_root, page)
    if animation["status"] == "missing":
        raise core.CliError(
            "WEB_SVG_ANIMATION_MISSING",
            "Editable SVG dropped a requested native connector animation.",
            animation,
        )
    output = Path(output_dir) / core.expected_web_svg_name(document, page)
    output_path = core.ensure_output_path(document.path, document.path, output)
    core.safe_commit(
        document,
        document.path,
        output_path,
        svg_data,
        document.revision,
        validate_drawio_output=False,
    )
    return output_path, animation


def selected_pages(document, args):
    selector = core.page_selector_from_args(args)
    if selector is None:
        return document.pages
    return core.select_pages(document, selector)


def run_session(args):
    document = core.load_document(args.input)
    pages = selected_pages(document, args)
    output_dir = Path(args.output_dir).expanduser().resolve()
    if not output_dir.is_dir():
        raise core.CliError("INVALID_PATH", "Output directory does not exist.", {"path": str(output_dir)})
    for page in pages:
        output = output_dir / core.expected_web_svg_name(document, page)
        if os.path.lexists(str(output)):
            raise core.CliError("OUTPUT_EXISTS", "Web SVG output already exists.", {"path": str(output)}, exit_code=5)
    if args.timeout < 1 or args.timeout > 3600:
        raise core.CliError("INVALID_TIMEOUT", "Session timeout must be between 1 and 3600 seconds.", exit_code=2)

    token = secrets.token_urlsafe(32)
    finished = threading.Event()
    state = {"committed": [], "error": None, "seen": set()}
    state_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format, *_args):
            return

        def json_response(self, status, payload):
            data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            if parsed.path != "/session" or query.get("token") != [token]:
                self.send_error(404)
                return
            data = session_html(document, pages, token)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            if parsed.path != "/submit" or query.get("token") != [token]:
                self.json_response(403, {"error": "Invalid session token."})
                return
            if self.headers.get("Origin") != session_origin:
                self.json_response(403, {"error": "Invalid request origin."})
                return
            if self.headers.get_content_type() != "image/svg+xml":
                self.json_response(415, {"error": "SVG submissions must use image/svg+xml."})
                return
            try:
                page_index = int(query.get("page", [""])[0])
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.json_response(400, {"error": "Invalid page or content length."})
                return
            page = next((candidate for candidate in pages if candidate.index == page_index), None)
            if page is None or content_length < 1 or content_length > MAX_SESSION_SVG_BYTES:
                self.json_response(400, {"error": "Page or payload is outside the session contract."})
                return
            with state_lock:
                if page_index in state["seen"]:
                    self.json_response(409, {"error": "Page was already submitted."})
                    return
                state["seen"].add(page_index)
            svg_data = self.rfile.read(content_length)
            try:
                output_path, animation = validate_and_commit_svg(document, page, svg_data, output_dir)
            except core.CliError as error:
                with state_lock:
                    state["error"] = error
                self.json_response(422, {"error": error.message, "code": error.code})
                finished.set()
                return
            with state_lock:
                state["committed"].append(
                    {
                        "page": {"index": page.index, "id": page.id, "name": page.name},
                        "file": str(output_path),
                        "connectorAnimation": animation,
                    }
                )
                complete = len(state["committed"]) == len(pages)
            self.json_response(200, {"ok": True, "complete": complete})
            if complete:
                finished.set()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    session_origin = f"http://127.0.0.1:{server.server_port}"
    session_url = f"{session_origin}/session?token={urllib.parse.quote(token)}"
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"WEB_SVG_SESSION_URL={session_url}", file=sys.stderr, flush=True)
    try:
        completed = finished.wait(args.timeout)
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)
    if not completed:
        raise core.CliError(
            "WEB_SVG_SESSION_TIMEOUT",
            "Web SVG session timed out before every selected page was committed.",
            {"timeout": args.timeout, "committed": state["committed"]},
            exit_code=6,
        )
    if state["error"] is not None:
        state["error"].details.setdefault("committed", state["committed"])
        raise state["error"]
    return {
        "file": str(document.path),
        "revision": document.revision,
        "result": {
            "renderer": "drawio-web-session",
            "rendererUrl": core.DRAWIO_WEB_ORIGIN,
            "pages": state["committed"],
            "sourceModified": False,
            "visualReviewRequired": True,
        },
        "warnings": [
            {
                "code": "VISUAL_REVIEW_REQUIRED",
                "message": "Inspect the committed SVG pages before marking the diagram ready.",
            }
        ],
    }


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("--output-dir", required=True)
    selectors = parser.add_mutually_exclusive_group()
    selectors.add_argument("--page-index", type=int)
    selectors.add_argument("--page-id")
    selectors.add_argument("--page-name")
    parser.add_argument("--timeout", type=int, default=300)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        payload = core.success_payload("web-svg-session", run_session(args))
        exit_code = 0
    except core.CliError as error:
        payload = core.error_payload("web-svg-session", error)
        exit_code = error.exit_code
    except (OSError, ValueError) as error:
        wrapped = core.CliError("IO_ERROR", "Web SVG session failed.", {"error": str(error)}, exit_code=6)
        payload = core.error_payload("web-svg-session", wrapped)
        exit_code = wrapped.exit_code
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

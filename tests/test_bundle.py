"""Offline checks for the distributed skill and native-file invariants."""

import base64
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "drawio_file.py"
EXAMPLE = ROOT / "examples" / "ecommerce-order.drawio"


class BundleTests(unittest.TestCase):
    def run_cli(self, *args, succeeds=True):
        process = subprocess.run(
            [sys.executable, "-I", "-B", str(CLI), *map(str, args)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        payload = json.loads(process.stdout)
        if succeeds:
            self.assertEqual(process.returncode, 0, payload)
            self.assertTrue(payload["ok"], payload)
        else:
            self.assertNotEqual(process.returncode, 0, payload)
            self.assertFalse(payload["ok"], payload)
        return payload

    def test_relative_documentation_links_resolve(self):
        documents = [ROOT / "SKILL.md", *ROOT.glob("README*.md")]
        documents.extend((ROOT / "references").glob("*.md"))
        for document in documents:
            for target in re.findall(r"\]\(([^)]+)\)", document.read_text()):
                if "://" in target or target.startswith("#"):
                    continue
                with self.subTest(document=document.name, target=target):
                    self.assertTrue(
                        (document.parent / target.split("#")[0]).exists()
                    )

    def test_native_assets_and_examples_validate(self):
        paths = sorted((ROOT / "assets" / "components").glob("*.drawio"))
        paths.extend(sorted((ROOT / "examples").glob("*.drawio")))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(path=path.name):
                self.run_cli("validate", path)
                layout = self.run_cli("check-layout", path, "--only-collisions")
                self.assertEqual(layout["result"]["collisionCount"], 0)

    def test_example_branch_outcomes_remain_reachable(self):
        views = {
            "checkout-flow": (
                "checkout",
                ["delivered", "notify_customer", "rejected", "cancelled", "refunded", "order_db"],
                [("event_queue", "fulfillment"), ("event_queue", "notify_customer"),
                 ("retry_gate", "fulfillment"), ("retry_gate", "dead_letter"),
                 ("manual_review", "refunded")],
            ),
            "order-lifecycle": (
                "initial",
                ["delivered_final", "rejected_final", "cancelled_final", "refunded_final"],
                [("fulfilling", "retry_scheduled"), ("retry_scheduled", "fulfilling"),
                 ("manual_review", "refund_pending")],
            ),
        }
        for page_id, (start, terminals, edges) in views.items():
            with self.subTest(page=page_id):
                args = ["check-topology", EXAMPLE, "--page-id", page_id, "--start", start]
                for terminal in terminals:
                    args.extend(["--terminal", terminal])
                for source, target in edges:
                    args.extend(["--expect-edge", source, target])
                result = self.run_cli(*args, "--require-connected")
                self.assertEqual(result["result"]["status"], "clear")

    def test_default_readme_and_examples_are_english(self):
        for path in [ROOT / "README.md", EXAMPLE, ROOT / "examples/components-en.drawio"]:
            with self.subTest(path=path.name):
                self.assertIsNone(re.search(r"[\u3400-\u9fff]", path.read_text()))

    def test_default_example_has_no_endpoint_label_risks(self):
        layout = self.run_cli("check-layout", EXAMPLE, "--verbose")
        risks = [item for item in layout["warnings"] if item["code"] == "EDGE_LABEL_ENDPOINT_OVERLAP_RISK"]
        self.assertEqual(risks, [])

    def test_patch_rejects_stale_revision_and_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "source.drawio"
            source.write_bytes((ROOT / "assets/components/document.drawio").read_bytes())
            before = source.read_bytes()
            revision = self.run_cli("inspect", source)["revision"]
            patch = {
                "version": 1,
                "expectedRevision": "sha256:" + "0" * 64,
                "operations": [{
                    "op": "set-label", "cellId": "caption",
                    "value": "Updated document", "format": "plain",
                }],
            }
            request = base / "patch.json"
            request.write_text(json.dumps(patch))
            output = base / "updated.drawio"
            rejected = self.run_cli("patch", source, request, "--output", output, succeeds=False)
            self.assertEqual(rejected["error"]["code"], "REVISION_CONFLICT")
            self.assertFalse(output.exists())

            patch["expectedRevision"] = revision
            request.write_text(json.dumps(patch))
            self.run_cli("patch", source, request, "--output", output)
            self.assertEqual(source.read_bytes(), before)
            output_before = output.read_bytes()
            self.assertEqual(
                ET.parse(output).find(".//mxCell[@id='caption']").get("value"),
                "Updated document",
            )
            rejected = self.run_cli("patch", source, request, "--output", output, succeeds=False)
            self.assertEqual(rejected["error"]["code"], "OUTPUT_EXISTS")
            self.assertEqual(output.read_bytes(), output_before)

    def test_preview_packages_png_without_changing_native_source(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "source.drawio"
            source.write_bytes(EXAMPLE.read_bytes())
            before = source.read_bytes()
            pngs = [ROOT / "docs/images/commerce-checkout.png", ROOT / "docs/images/commerce-lifecycle.png"]
            output = base / "preview.html"
            args = ["preview", source, "--output", output]
            for png in pngs:
                args.extend(["--fallback-png", png])
            response = self.run_cli(*args)
            self.assertFalse(response["result"]["networkRequired"])
            self.assertEqual(response["result"]["offlinePages"], 2)
            for png in pngs:
                self.assertIn(base64.b64encode(png.read_bytes()).decode(), output.read_text())
            self.assertEqual(source.read_bytes(), before)

    def test_unsafe_xml_and_page_limit_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            unsafe = base / "unsafe.drawio"
            unsafe.write_text(
                '<!DOCTYPE mxfile [<!ENTITY test "payload">]><mxfile/>'
            )
            self.run_cli("validate", unsafe, succeeds=False)

            root = ET.Element("mxfile")
            for index in range(16):
                page = ET.SubElement(root, "diagram", id=f"p{index}", name=f"Page {index}")
                model = ET.SubElement(page, "mxGraphModel")
                cells = ET.SubElement(model, "root")
                ET.SubElement(cells, "mxCell", id="0")
                ET.SubElement(cells, "mxCell", id="1", parent="0")
            oversized = base / "oversized.drawio"
            ET.ElementTree(root).write(oversized, encoding="utf-8")
            rejected = self.run_cli("validate", oversized, succeeds=False)
            self.assertEqual(rejected["error"]["code"], "PAGE_COUNT_LIMIT")


if __name__ == "__main__":
    unittest.main()

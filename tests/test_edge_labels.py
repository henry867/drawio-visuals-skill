"""Regression checks for edge labels running into their own endpoints."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


CLI = Path(__file__).resolve().parents[1] / "scripts" / "drawio_file.py"
RISK = "EDGE_LABEL_ENDPOINT_OVERLAP_RISK"


class EdgeLabelTests(unittest.TestCase):
    def layout(self, label, gap=105, offset=(0, -14), vertical=False):
        model = ET.Element("mxGraphModel")
        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", id="0")
        ET.SubElement(root, "mxCell", id="1", parent="0")
        for cell_id, x, y in (
            ("source", 20, 160),
            ("target", 20 if vertical else 240 + gap, 240 + gap if vertical else 160),
        ):
            cell = ET.SubElement(
                root, "mxCell", id=cell_id, value=cell_id,
                style="rounded=1;fillColor=#FFFFFF;strokeColor=#000000;",
                vertex="1", parent="1",
            )
            ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width="220", height="80", **{"as": "geometry"})
        ports = "exitX=0.5;exitY=1;entryX=0.5;entryY=0;" if vertical else "exitX=1;exitY=0.5;entryX=0;entryY=0.5;"
        edge = ET.SubElement(
            root, "mxCell", id="transition", value=label,
            style="edgeStyle=orthogonalEdgeStyle;fontSize=19;html=0;" + ports,
            edge="1", parent="1", source="source", target="target",
        )
        geometry = ET.SubElement(edge, "mxGeometry", relative="1", **{"as": "geometry"})
        ET.SubElement(geometry, "mxPoint", x=str(offset[0]), y=str(offset[1]), **{"as": "offset"})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "case.drawio"
            ET.ElementTree(model).write(path, encoding="utf-8")
            process = subprocess.run(
                [sys.executable, "-I", "-B", str(CLI), "check-layout", str(path), "--verbose"],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(process.returncode, 0, process.stdout)
            return json.loads(process.stdout)["result"]["pages"][0]

    def risks(self, result):
        return [item for item in result["warnings"] if item["code"] == RISK]

    def test_long_label_in_short_corridor_flags_both_endpoints(self):
        for label in ("job consumed", "delivery scan", "处理完成后提交订单"):
            with self.subTest(label=label):
                result = self.layout(label)
                risks = self.risks(result)
                self.assertEqual({item["endpoint"] for item in risks}, {"source", "target"})
                self.assertEqual(result["status"], "indeterminate")
                self.assertTrue(all(item["minimumClearance"] == 8 for item in risks))

    def test_wider_gap_or_explicit_wrapping_clears_endpoint_risk(self):
        self.assertFalse(self.risks(self.layout("job consumed", gap=190)))
        self.assertFalse(self.risks(self.layout("job\nconsumed", gap=130)))

    def test_position_and_vertical_label_height_are_respected(self):
        self.assertFalse(self.risks(self.layout("job consumed", offset=(0, -100))))
        multiline = "event\nguard\naction\nextra\ncontext\nmore"
        self.assertTrue(self.risks(self.layout(multiline, gap=80, offset=(0, 0), vertical=True)))
        self.assertFalse(self.risks(self.layout(multiline, gap=80, offset=(250, 0), vertical=True)))


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Tests: workflow JSON integrity + runs the profiler Code-node JS under Node."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

import generate_workflow as gw

HERE = Path(__file__).parent


class WorkflowTests(unittest.TestCase):
    def test_json_is_up_to_date(self):
        on_disk = json.loads((HERE / "Data_Analyst_Agent.json").read_text(encoding="utf-8"))
        self.assertEqual(on_disk, json.loads(json.dumps(gw.workflow)))

    def test_connections_reference_existing_nodes(self):
        names = {n["name"] for n in gw.workflow["nodes"]}
        for src, c in gw.workflow["connections"].items():
            self.assertIn(src, names)
            for branch in c["main"]:
                for link in branch:
                    self.assertIn(link["node"], names)

    def test_no_hardcoded_secrets(self):
        text = (HERE / "Data_Analyst_Agent.json").read_text(encoding="utf-8")
        self.assertNotIn("AIza", text)


@unittest.skipUnless(shutil.which("node"), "node not installed")
class ProfilerTests(unittest.TestCase):
    def run_js(self, payload):
        harness = (
            "const $input={first:()=>({json:%s})};"
            "const f=new Function('$input',%s);"
            "console.log(JSON.stringify(f($input)[0].json));"
        ) % (json.dumps(payload), json.dumps(gw.PROFILE_JS))
        out = subprocess.run(["node", "-e", harness], capture_output=True, text=True)
        return out

    def test_profile_numeric_and_text(self):
        out = self.run_js({"body": {"csv": 'a,b\n1,"x,y"\n3,x\n5,x', "question": "Q?"}})
        self.assertEqual(out.returncode, 0, out.stderr)
        res = json.loads(out.stdout)
        a, b = res["profile"]["columns"]
        self.assertEqual((a["type"], a["mean"], a["median"], a["max"]), ("numeric", 3, 3, 5))
        self.assertEqual(b["topValues"][0], {"value": "x", "count": 2})
        self.assertEqual(res["profile"]["rowCount"], 3)
        self.assertIn("Q?", res["requestBody"]["contents"][0]["parts"][0]["text"])

    def test_default_sample_used(self):
        out = self.run_js({})
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["profile"]["rowCount"], 8)

    def test_header_only_csv_errors(self):
        self.assertNotEqual(self.run_js({"csv": "a,b"}).returncode, 0)


if __name__ == "__main__":
    unittest.main()

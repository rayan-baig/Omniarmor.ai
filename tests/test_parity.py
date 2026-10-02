"""The dashboard's JavaScript evaluate() must give the same answer as the Python
engine for every rule. Runs with Node.js when it's installed (it is on CI)."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from omni_armor_rules import CATALOG, evaluate  # noqa: E402

RUNNER = """
const fs = require('fs');
const [jsFile, casesFile] = process.argv.slice(2);
eval(fs.readFileSync(jsFile, 'utf8') + '; globalThis.evaluate = evaluate;');
const cases = JSON.parse(fs.readFileSync(casesFile, 'utf8'));
process.stdout.write(JSON.stringify(cases.map(c => evaluate(c.rule, c.value))));
"""


@unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
class TestDashboardParity(unittest.TestCase):
    def test_js_matches_python_on_every_rule(self):
        with open(os.path.join(ROOT, "dashboard", "template.html"), encoding="utf-8") as f:
            page = f.read()
        script = page[page.index("<script>") + len("<script>"):page.rindex("</script>")]
        js = script[script.index("function fmt"):script.index("/* State:")]
        cases, expected = [], []
        for rules in CATALOG.values():
            for r in rules:
                values = [r.sample]
                if r.kind in ("max", "min"):
                    values += [r.limit, r.limit + 1, r.limit - 1, r.limit + 0.5, 0, 12345.678]
                    if r.warn is not None:
                        values.append(r.warn)
                else:
                    values += [True, False]
                for v in values:
                    fields = ("title", "kind", "unit", "limit", "warn", "policy", "action")
                    cases.append({"rule": {k: getattr(r, k) for k in fields}, "value": v})
                    expected.append(list(evaluate(r, v)))
        with tempfile.TemporaryDirectory() as tmp:
            paths = {name: os.path.join(tmp, name) for name in ("eval.js", "cases.json", "run.js")}
            with open(paths["eval.js"], "w", encoding="utf-8") as f:
                f.write(js)
            with open(paths["cases.json"], "w", encoding="utf-8") as f:
                json.dump(cases, f)
            with open(paths["run.js"], "w", encoding="utf-8") as f:
                f.write(RUNNER)
            out = subprocess.run(["node", paths["run.js"], paths["eval.js"], paths["cases.json"]],
                                 capture_output=True, text=True, check=True, timeout=60).stdout
        got = json.loads(out)
        mismatches = [(c["rule"]["title"], c["value"], g, e) for c, g, e in zip(cases, got, expected) if g != e]
        self.assertGreater(len(cases), 2500)
        self.assertEqual(mismatches[:5], [])


if __name__ == "__main__":
    unittest.main()

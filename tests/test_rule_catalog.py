import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omni_armor_platform import OmniArmorPortal  # noqa: E402
from omni_armor_rules import BLOCKED, CATALOG, CLEARED, WARNING, Rule, evaluate, get_rule  # noqa: E402
from omni_armor_rules.rule import validate_rules  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard"))
import build_dashboard  # noqa: E402


def make(kind, **kw):
    base = dict(key="k", title="T", cost="c", citation="x", kind=kind, input="i", action="Fix it.")
    base.update(kw)
    return Rule(**base)


class TestCatalogShape(unittest.TestCase):
    def test_ten_rules_for_each_of_50_industries(self):
        self.assertEqual(sorted(CATALOG), list(range(1, 51)))
        for module_id, rules in CATALOG.items():
            self.assertEqual(len(rules), 10, module_id)
        validate_rules(CATALOG, range(1, 51))

    def test_every_industry_has_theme_entry(self):
        self.assertEqual(sorted(OmniArmorPortal(verbose=False).theme.INDUSTRIES), sorted(CATALOG))

    def test_first_rule_links_to_the_detailed_check(self):
        portal = OmniArmorPortal(verbose=False)
        for module_id in range(1, 26):
            method = CATALOG[module_id][0].method
            self.assertTrue(method, f"industry {module_id} rule 1 has no method")
            self.assertTrue(callable(getattr(portal, method, None)), f"{module_id}: {method} missing")

    def test_every_sample_evaluates(self):
        for rules in CATALOG.values():
            for r in rules:
                level, _, message = evaluate(r, r.sample)
                self.assertIn(level, (CLEARED, WARNING, BLOCKED))
                self.assertTrue(message)

    def test_methods_only_on_known_checks(self):
        portal = OmniArmorPortal(verbose=False)
        for rules in CATALOG.values():
            for r in rules:
                if r.method:
                    self.assertTrue(callable(getattr(portal, r.method, None)), r.method)

    def test_keys_unique_across_catalog_per_industry(self):
        for module_id, rules in CATALOG.items():
            self.assertEqual(len({r.key for r in rules}), 10, module_id)

    def test_no_invented_dollar_figures_in_cost(self):
        for rules in CATALOG.values():
            for r in rules:
                self.assertNotRegex(r.cost, r"\$\s?\d[\d,.]*\s?(million|billion|[mbk]\b)", f"{r.key}: {r.cost}")


class TestEvaluate(unittest.TestCase):
    def test_max(self):
        r = make("max", unit="h", limit=11, warn=10)
        self.assertEqual(evaluate(r, 9)[0], CLEARED)
        self.assertEqual(evaluate(r, 10)[0], WARNING)
        self.assertEqual(evaluate(r, 11)[0], WARNING)
        level, status, message = evaluate(r, 11.5)
        self.assertEqual((level, status), (BLOCKED, "OVER LIMIT"))
        self.assertEqual(message, "11.5 h is over the 11 h limit. Fix it.")

    def test_min(self):
        r = make("min", unit="%", limit=90, warn=92)
        self.assertEqual(evaluate(r, 95)[0], CLEARED)
        self.assertEqual(evaluate(r, 92)[0], WARNING)
        self.assertEqual(evaluate(r, 89.5)[0], BLOCKED)
        self.assertEqual(evaluate(r, 89.5)[2], "89.5% is below the 90% minimum. Fix it.")

    def test_max_without_warn(self):
        r = make("max", unit="days", limit=30)
        self.assertEqual(evaluate(r, 30)[0], CLEARED)
        self.assertEqual(evaluate(r, 31)[0], BLOCKED)

    def test_required_and_forbidden(self):
        self.assertEqual(evaluate(make("required"), True)[0], CLEARED)
        self.assertEqual(evaluate(make("required"), False)[0], BLOCKED)
        self.assertEqual(evaluate(make("forbidden"), False)[0], CLEARED)
        self.assertEqual(evaluate(make("forbidden"), True)[0], BLOCKED)

    def test_wrong_input_type_rejected(self):
        with self.assertRaises(TypeError):
            evaluate(make("required"), 1)
        with self.assertRaises(TypeError):
            evaluate(make("max", limit=5), True)
        with self.assertRaises(TypeError):
            evaluate(make("max", limit=5), "4")

    def test_non_finite_rejected(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ValueError):
                evaluate(make("max", limit=5), bad)

    def test_formatting(self):
        self.assertIn("$10,000", evaluate(make("max", unit="$", limit=10000), 12500.5)[2])
        self.assertIn("$12,500.5", evaluate(make("max", unit="$", limit=10000), 12500.5)[2])
        self.assertIn("41°F", evaluate(make("max", unit="°F", limit=41), 45)[2])

    def test_policy_marker(self):
        r = make("max", unit="days", limit=30, policy=True)
        self.assertIn("(policy setting)", evaluate(r, 5)[2])

    def test_validator_catches_bad_rules(self):
        bad = {1: [make("max", limit=None, sample=1)] * 10}
        with self.assertRaises(ValueError):
            validate_rules(bad, [1])


class TestPortalCatalog(unittest.TestCase):
    def setUp(self):
        self.p = OmniArmorPortal(verbose=False)

    def test_check_rule_logs_result(self):
        rule = CATALOG[1][0]
        result = self.p.check_rule(1, rule.key, rule.sample)
        self.assertEqual(result.feature, rule.title)
        self.assertEqual(self.p.audit_log[-1], result)

    def test_run_industry_uses_readings(self):
        rule = next(r for r in CATALOG[18] if r.kind in ("required", "forbidden"))
        compliant = rule.kind == "required"
        results = self.p.run_industry(18, {rule.key: compliant})
        self.assertEqual(len(results), 10)
        match = next(r for r in results if r.feature == rule.title)
        self.assertEqual(match.level, CLEARED)

    def test_run_industry_rejects_unknown_key(self):
        with self.assertRaises(KeyError):
            self.p.run_industry(1, {"not_a_rule": 1})

    def test_get_rule_unknown(self):
        with self.assertRaises(KeyError):
            get_rule(1, "nope")

    def test_full_catalog(self):
        results = self.p.run_full_catalog()
        self.assertEqual(sum(len(v) for v in results.values()), 500)
        self.assertEqual(self.p.tracker.total_api_calls, 500)


class TestDashboard(unittest.TestCase):
    def test_built_file_is_current(self):
        with open(build_dashboard.OUTPUT, encoding="utf-8") as f:
            self.assertEqual(f.read(), build_dashboard.render(),
                             "dashboard/index.html is stale; run python3 dashboard/build_dashboard.py")

    def test_embedded_data_round_trips(self):
        html = build_dashboard.render()
        match = re.search(r"const INDUSTRIES = (\[.*?\]);\n", html, re.S)
        data = json.loads(match.group(1).replace("<\\/", "</"))
        self.assertEqual(len(data), 50)
        self.assertTrue(all(len(i["rules"]) == 10 for i in data))
        self.assertNotIn("</script", match.group(1).lower())


if __name__ == "__main__":
    unittest.main()

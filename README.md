# OmniArmor.ai

**Catch the fine before it catches you.**

Compliance checks for 50 regulated industries. Each industry has ten rules
covering the compliance failures that cost businesses in that industry the
most: common, expensive when missed, and cheap to prevent with a deadline,
a threshold or a checklist. That is 500 rules in all.

Every check answers **Cleared**, **Warning** or **Blocked** and names the
rule it applies. This is decision support, not legal advice: confirm each
rule with a compliance professional for your jurisdiction.

## Layout

| Path | What it is |
|---|---|
| `omni_armor_platform.py` | The engine: 25 detailed checks (industries 1–25), the audit log, and `check_rule` / `run_industry` / `run_full_catalog` for the rule catalog |
| `omni_armor_rules/rule.py` | The `Rule` format and the one `evaluate` function every rule uses |
| `omni_armor_rules/group_1.py` … `group_10.py` | The 500 rules, five industries per file |
| `dashboard/template.html` | The Risk Console page: live results, problems first, date pickers for day counts, rule search and a copyable report |
| `dashboard/build_dashboard.py` | Builds `dashboard/index.html` from the template and the catalog |
| `tests/` | Unit tests for the checks, the catalog and the dashboard build |

## Commands

```sh
python3 omni_armor_platform.py              # run the demo and the 500-rule summary
python3 -m unittest discover -s tests       # run the tests
python3 dashboard/build_dashboard.py        # rebuild the dashboard after changing a rule
```

The dashboard's JavaScript mirrors `evaluate` in `rule.py`; if you change one,
change the other. A test fails if `dashboard/index.html` is out of date.

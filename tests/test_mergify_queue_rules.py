from pathlib import Path

import yaml


def _mergify() -> dict:
    return yaml.safe_load(Path('.mergify.yml').read_text(encoding='utf-8'))


def _pull_rule_by_name(name: str) -> dict:
    return next(rule for rule in _mergify()['pull_request_rules'] if rule.get('name') == name)


def test_queue_rules_require_approval_and_real_diff() -> None:
    for name in ('queue development PRs', 'queue light (docs/CI-config-only) PRs'):
        rule = _pull_rule_by_name(name)

        assert '#approved-reviews-by>=1' in rule['conditions']
        assert '#files>=1' in rule['conditions']

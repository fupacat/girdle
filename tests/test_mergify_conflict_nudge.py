from pathlib import Path

import yaml


def _mergify() -> dict:
    return yaml.safe_load(Path('.mergify.yml').read_text(encoding='utf-8'))


def _rule_by_name(name: str) -> dict:
    return next(rule for rule in _mergify()['pull_request_rules'] if rule.get('name') == name)


def test_conflict_nudge_is_gated_per_head_marker_comment():
    rule = _rule_by_name('nudge Copilot when a PR goes into conflict')

    assert '-comments~=<!-- conflict-nudge:{{head}} -->' in rule['conditions']
    assert '-label=conflict-nudged' not in rule['conditions']

    message = rule['actions']['comment']['message']
    assert '<!-- conflict-nudge:{{head}} -->' in message


def test_conflict_nudge_does_not_depend_on_clear_label_rule():
    names = [rule.get('name') for rule in _mergify()['pull_request_rules']]

    assert 'clear conflict-nudged label once resolved' not in names

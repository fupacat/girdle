from pathlib import Path

import yaml


def _mergify() -> dict:
    return yaml.safe_load(Path('.mergify.yml').read_text(encoding='utf-8'))


def _rule_by_name(name: str) -> dict:
    return next(rule for rule in _mergify()['pull_request_rules'] if rule.get('name') == name)


def test_conflict_nudge_is_gated_by_label_and_marks_head_sha():
    rule = _rule_by_name('nudge Copilot when a PR goes into conflict')

    assert '-label=conflict-nudged' in rule['conditions']
    assert 'comments' not in ' '.join(rule['conditions'])
    assert rule['actions']['label']['add'] == ['conflict-nudged']

    message = rule['actions']['comment']['message']
    assert '<!-- conflict-nudge:{{head.sha}} -->' in message


def test_conflict_nudge_label_is_cleared_when_conflict_resolves():
    rule = _rule_by_name('clear conflict-nudged label once resolved')

    assert 'label=conflict-nudged' in rule['conditions']
    assert '-conflict' in rule['conditions']
    assert rule['actions']['label']['remove'] == ['conflict-nudged']

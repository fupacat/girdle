from pathlib import Path

import yaml


def _mergify() -> dict:
    return yaml.safe_load(Path('.mergify.yml').read_text(encoding='utf-8'))


def _rule_by_name(name: str) -> dict:
    return next(rule for rule in _mergify()['pull_request_rules'] if rule.get('name') == name)


def _queue_rule_by_name(name: str) -> dict:
    return next(rule for rule in _mergify()['queue_rules'] if rule.get('name') == name)


def test_light_queue_does_not_inject_master_ruleset_sonar_gate():
    queue = _queue_rule_by_name('light')

    assert queue['branch_protection_injection_mode'] == 'none'
    assert queue['merge_conditions'] == [
        'check-success=test',
        '#approved-reviews-by>=1',
    ]
    # Gitar skips draft PRs and merge_conditions are evaluated on Mergify's
    # speculative draft, so a `Gitar` check never appears there and the queue
    # would time out; Gitar's approval is covered by the approval count.
    assert all(
        'Gitar' not in condition and 'SonarCloud Code Analysis' not in condition
        for condition in queue['merge_conditions']
    )


def test_light_queue_sets_merge_bot_for_none_injection_mode():
    queue = _queue_rule_by_name('light')

    assert queue['branch_protection_injection_mode'] == 'none'
    assert queue['merge_bot_account'] == 'fupacat'


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

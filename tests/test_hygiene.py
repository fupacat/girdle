from pathlib import Path

from girdle.hygiene import build_hygiene
from girdle.tiers import Tier


def test_all_absent_on_empty_repo(tmp_path: Path):
    result = build_hygiene(tmp_path, languages=set())
    for check in result.checks.values():
        assert check.tier == Tier.ABSENT


def test_editorconfig_present(tmp_path: Path):
    (tmp_path / ".editorconfig").write_text("root = true\n")
    result = build_hygiene(tmp_path, languages=set())
    assert result.checks["editorconfig"].tier == Tier.CONFIGURED


def test_gitattributes_present(tmp_path: Path):
    (tmp_path / ".gitattributes").write_text("* text=auto\n")
    result = build_hygiene(tmp_path, languages=set())
    assert result.checks["gitattributes"].tier == Tier.CONFIGURED


def test_precommit_absent(tmp_path: Path):
    result = build_hygiene(tmp_path, languages=set())
    assert result.checks["precommit"].tier == Tier.ABSENT


def test_precommit_present(tmp_path: Path):
    # pre-commit exists with no CI configured → CONFIGURED (nothing to be missing from)
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    result = build_hygiene(tmp_path, languages=set())
    assert result.checks["precommit"].tier == Tier.CONFIGURED


def test_precommit_ci_parity_all_hooks_present(tmp_path: Path):
    # CI runs ruff + pytest, both present as pre-commit hooks → CONFIGURED
    pc = """
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
"""
    (tmp_path / ".pre-commit-config.yaml").write_text(pc)
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "ci.yml").write_text("- run: ruff check .\n- run: pytest\n")
    result = build_hygiene(tmp_path, languages=set())
    assert result.checks["precommit"].tier == Tier.CONFIGURED


def test_precommit_ci_parity_missing_hook(tmp_path: Path):
    # CI runs ruff + pytest, but pre-commit only has ruff → pytest is missing → ABSENT
    pc = """
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
"""
    (tmp_path / ".pre-commit-config.yaml").write_text(pc)
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "ci.yml").write_text("- run: ruff check .\n- run: pytest\n")
    result = build_hygiene(tmp_path, languages=set())
    cat = result.checks["precommit"]
    assert cat.tier == Tier.ABSENT
    assert "pytest" in (cat.reason or "")
    assert "pytest" in (cat.recommendation or "")


def test_precommit_ci_parity_hook_id_substring_match(tmp_path: Path):
    # hook id "ruff-format" still covers the tool "ruff" via substring
    pc = """
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff-format
"""
    (tmp_path / ".pre-commit-config.yaml").write_text(pc)
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / "ci.yml").write_text("- run: ruff check .\n")
    result = build_hygiene(tmp_path, languages=set())
    assert result.checks["precommit"].tier == Tier.CONFIGURED


def test_agent_sandbox_bootstrap_absent_without_precommit(tmp_path: Path):
    result = build_hygiene(tmp_path, languages=set())
    cat = result.checks["agent_sandbox_bootstrap"]
    assert cat.tier == Tier.ABSENT
    assert "no .pre-commit-config.yaml" in cat.reason


def test_agent_sandbox_bootstrap_absent_with_precommit_but_no_wiring(tmp_path: Path):
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    result = build_hygiene(tmp_path, languages=set())
    cat = result.checks["agent_sandbox_bootstrap"]
    assert cat.tier == Tier.ABSENT
    assert "not wired into any agent sandbox bootstrap" in cat.reason


def test_agent_sandbox_bootstrap_configured_via_copilot_setup_steps(tmp_path: Path):
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "copilot-setup-steps.yml").write_text(
        "jobs:\n  copilot-setup-steps:\n    runs-on: ubuntu-latest\n"
    )
    result = build_hygiene(tmp_path, languages=set())
    cat = result.checks["agent_sandbox_bootstrap"]
    assert cat.tier == Tier.CONFIGURED
    assert ".github/workflows/copilot-setup-steps.yml" in cat.evidence


def test_agent_sandbox_bootstrap_configured_via_claude_worktree_create(tmp_path: Path):
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(
        '{"hooks": {"WorktreeCreate": [{"hooks": [{"type": "command", "command": "true"}]}]}}\n'
    )
    result = build_hygiene(tmp_path, languages=set())
    cat = result.checks["agent_sandbox_bootstrap"]
    assert cat.tier == Tier.CONFIGURED
    assert ".claude/settings.json" in cat.evidence


def test_agent_sandbox_bootstrap_configured_via_claude_session_start(tmp_path: Path):
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(
        '{"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "true"}]}]}}\n'
    )
    result = build_hygiene(tmp_path, languages=set())
    cat = result.checks["agent_sandbox_bootstrap"]
    assert cat.tier == Tier.CONFIGURED
    assert ".claude/settings.json" in cat.evidence


def test_agent_sandbox_bootstrap_configured_via_codex_local_environment(tmp_path: Path):
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir()
    (codex_dir / "setup.sh").write_text("pre-commit install\n")
    result = build_hygiene(tmp_path, languages=set())
    cat = result.checks["agent_sandbox_bootstrap"]
    assert cat.tier == Tier.CONFIGURED
    assert ".codex" in cat.evidence


def test_agent_sandbox_bootstrap_empty_codex_dir_is_absent(tmp_path: Path):
    # An empty .codex/ (stale leftover, or an unrelated tool reusing the
    # name) must not count as configured - unlike the Copilot/Claude
    # sub-checks, there's no documented filename to verify content of, so
    # non-emptiness is the only signal this check can require.
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    (tmp_path / ".codex").mkdir()
    result = build_hygiene(tmp_path, languages=set())
    assert result.checks["agent_sandbox_bootstrap"].tier == Tier.ABSENT


def test_agent_sandbox_bootstrap_ignores_malformed_claude_settings(tmp_path: Path):
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text("not valid json{{{\n")
    result = build_hygiene(tmp_path, languages=set())
    assert result.checks["agent_sandbox_bootstrap"].tier == Tier.ABSENT


def test_agent_sandbox_bootstrap_tolerates_non_dict_hooks_value(tmp_path: Path):
    # Valid JSON, but "hooks" is the wrong shape (null/list/string) - must
    # not crash with AttributeError trying to .get() into it.
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text('{"hooks": null}\n')
    result = build_hygiene(tmp_path, languages=set())
    assert result.checks["agent_sandbox_bootstrap"].tier == Tier.ABSENT

    (claude_dir / "settings.json").write_text('{"hooks": ["not", "a", "dict"]}\n')
    result = build_hygiene(tmp_path, languages=set())
    assert result.checks["agent_sandbox_bootstrap"].tier == Tier.ABSENT


def test_agent_sandbox_bootstrap_copilot_mention_without_job_key_is_absent(tmp_path: Path):
    # A comment/doc referencing "copilot-setup-steps" must not count -
    # only an actual job key does.
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "copilot-setup-steps.yml").write_text(
        "# TODO: consider adding a copilot-setup-steps job later\njobs:\n  build:\n"
        "    runs-on: ubuntu-latest\n"
    )
    result = build_hygiene(tmp_path, languages=set())
    cat = result.checks["agent_sandbox_bootstrap"]
    assert cat.tier == Tier.ABSENT


def test_gitignore_missing_is_absent(tmp_path: Path):
    result = build_hygiene(tmp_path, languages={"python"})
    assert result.checks["gitignore"].tier == Tier.ABSENT
    assert "no .gitignore" in result.checks["gitignore"].reason


def test_gitignore_present_but_missing_stack_patterns(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("*.log\n")
    result = build_hygiene(tmp_path, languages={"python"})
    cat = result.checks["gitignore"]
    assert cat.tier == Tier.ABSENT
    assert "__pycache__" in cat.reason
    assert ".venv" in cat.reason
    assert "python" in cat.recommendation


def test_gitignore_covers_stack_is_configured(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("__pycache__/\n.venv/\n")
    result = build_hygiene(tmp_path, languages={"python"})
    assert result.checks["gitignore"].tier == Tier.CONFIGURED


def test_gitignore_multi_language_checks_all_stacks(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("__pycache__/\n.venv/\n")
    result = build_hygiene(tmp_path, languages={"python", "javascript"})
    cat = result.checks["gitignore"]
    assert cat.tier == Tier.ABSENT
    assert "node_modules" in cat.reason


def test_codeowners_found_in_github_dir(tmp_path: Path):
    github_dir = tmp_path / ".github"
    github_dir.mkdir()
    (github_dir / "CODEOWNERS").write_text("* @someone\n")
    result = build_hygiene(tmp_path, languages=set())
    cat = result.checks["codeowners"]
    assert cat.tier == Tier.CONFIGURED
    assert ".github" in cat.evidence[0]


def test_readme_empty_stub_is_absent(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Title\n")
    result = build_hygiene(tmp_path, languages=set())
    cat = result.checks["readme"]
    assert cat.tier == Tier.ABSENT
    assert "stub" in cat.reason


def test_readme_with_real_content_is_configured(tmp_path: Path):
    (tmp_path / "README.md").write_text(
        "# My Project\n\nThis project does something useful and has enough content.\n"
    )
    result = build_hygiene(tmp_path, languages=set())
    assert result.checks["readme"].tier == Tier.CONFIGURED


def test_agent_instructions_absent(tmp_path: Path):
    result = build_hygiene(tmp_path, languages=set())
    assert result.checks["agent_instructions"].tier == Tier.ABSENT


def test_agent_instructions_present_as_agents_md(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("# Agents\n")
    result = build_hygiene(tmp_path, languages=set())
    cat = result.checks["agent_instructions"]
    assert cat.tier == Tier.CONFIGURED
    assert cat.evidence[0] == "AGENTS.md"


def test_agent_instructions_present_as_claude_md(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("# Claude\n")
    result = build_hygiene(tmp_path, languages=set())
    cat = result.checks["agent_instructions"]
    assert cat.tier == Tier.CONFIGURED
    assert cat.evidence[0] == "CLAUDE.md"


def test_agent_instructions_present_as_copilot_instructions(tmp_path: Path):
    github_dir = tmp_path / ".github"
    github_dir.mkdir()
    (github_dir / "copilot-instructions.md").write_text("# Copilot\n")
    result = build_hygiene(tmp_path, languages=set())
    cat = result.checks["agent_instructions"]
    assert cat.tier == Tier.CONFIGURED
    assert cat.evidence[0] == ".github/copilot-instructions.md"


def test_contributing_absent(tmp_path: Path):
    result = build_hygiene(tmp_path, languages=set())
    assert result.checks["contributing"].tier == Tier.ABSENT


def test_contributing_present_in_docs(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "CONTRIBUTING.md").write_text("How to contribute...\n")
    result = build_hygiene(tmp_path, languages=set())
    assert result.checks["contributing"].tier == Tier.CONFIGURED


def test_dependency_monitoring_absent(tmp_path: Path):
    result = build_hygiene(tmp_path, languages=set())
    assert result.checks["dependency_monitoring"].tier == Tier.ABSENT


def test_dependency_monitoring_present_dependabot(tmp_path: Path):
    github_dir = tmp_path / ".github"
    github_dir.mkdir()
    (github_dir / "dependabot.yml").write_text("version: 2\n")
    result = build_hygiene(tmp_path, languages=set())
    cat = result.checks["dependency_monitoring"]
    assert cat.tier == Tier.CONFIGURED
    assert ".github/dependabot.yml" in cat.evidence


def test_dependency_monitoring_present_renovate(tmp_path: Path):
    (tmp_path / ".renovaterc").write_text("{}\n")
    result = build_hygiene(tmp_path, languages=set())
    cat = result.checks["dependency_monitoring"]
    assert cat.tier == Tier.CONFIGURED
    assert ".renovaterc" in cat.evidence


def test_to_dict_shape(tmp_path: Path):
    result = build_hygiene(tmp_path, languages=set())
    d = result.to_dict()
    assert set(d.keys()) == {
        "editorconfig", "gitattributes", "precommit", "agent_sandbox_bootstrap", "gitignore",
        "codeowners", "agent_instructions", "readme", "contributing", "dependency_monitoring",
    }
    assert "tier" in d["editorconfig"]

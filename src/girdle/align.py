"""Opt-in, append-only alignment of .editorconfig / .gitattributes /
.gitignore, derived from formatter config that's already present in the
repo - never invented from scratch. This changes girdle's trust model
(read-only scanner -> file writer), so it's a separate command from `scan`,
dry-run by default, and deliberately conservative:

- .editorconfig: only ADDS a new [glob] section when that glob isn't
  already present anywhere in the file. Never edits an existing section's
  keys, even to fill a gap - that needs a real INI-aware editor to do
  safely without risking a user's own customization or comments; this
  tool doesn't attempt it.
- .gitattributes: only adds a `* text=auto eol=<lf|crlf>` line when no
  `text=auto` rule exists yet, and only when every detected formatter that
  expresses an opinion on line endings agrees - if they disagree, this is
  reported as a conflict and left alone rather than guessed.
- .gitignore: only appends patterns proven absent (substring check against
  the existing file), for the ecosystems actually detected in this repo.

Source of truth for "what formatter is configured": an actual config file
found on disk (pyproject.toml's [tool.black]/[tool.ruff.format], a Prettier
config, rustfmt.toml) - not a guess based on which language is present. Go
is deliberately excluded: gofmt has no config file to detect, so there's
no "formatter is configured" evidence to key off, even though gofmt's
tab convention is a near-certainty in practice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from girdle.detectors._util import read_json, read_text, read_toml

EDITORCONFIG = ".editorconfig"
GITATTRIBUTES = ".gitattributes"
GITIGNORE = ".gitignore"

LANGUAGE_GLOBS = {
    "python": "*.py",
    "javascript": "*.{js,jsx,mjs,cjs}",
    "typescript": "*.{ts,tsx}",
    "rust": "*.rs",
}

# Superset of hygiene.py's scoring-oriented EXPECTED_IGNORE_PATTERNS -
# intentionally kept separate so this tool's richer suggestions don't
# retroactively change what the hygiene score requires.
ALIGN_IGNORE_PATTERNS = {
    "python": [
        "__pycache__", ".venv", "*.pyc", ".pytest_cache/", ".mypy_cache/",
        ".ruff_cache/", "*.egg-info/",
    ],
    "javascript": ["node_modules", "dist/", "build/", "coverage/"],
    "typescript": ["node_modules", "dist/", "build/", "coverage/"],
    "rust": ["target"],
    "java": ["target", "build", ".gradle"],
    "dotnet": ["bin", "obj"],
}


@dataclass
class AlignPlan:
    file: str
    exists: bool
    additions: list[str] = field(default_factory=list)
    new_content: str | None = None


def _python_formatter(root: Path) -> tuple[dict, str] | None:
    pyproject = read_toml(root / "pyproject.toml")
    if not pyproject:
        return None
    tools = pyproject.get("tool", {})
    if "black" in tools:
        black = tools["black"] or {}
        settings = {
            "indent_style": "space",
            "indent_size": 4,
            "max_line_length": black.get("line-length", 88),
        }
        return settings, "pyproject.toml#tool.black"
    ruff = tools.get("ruff")
    if isinstance(ruff, dict) and "format" in ruff:
        fmt = ruff["format"] or {}
        settings = {
            "indent_style": "tab" if fmt.get("indent-style") == "tab" else "space",
            "indent_size": fmt.get("indent-width", 4),
            "max_line_length": ruff.get("line-length", 88),
        }
        return settings, "pyproject.toml#tool.ruff.format"
    return None


_PRETTIER_JSON_LOCATIONS = (".prettierrc", ".prettierrc.json")
_PRETTIER_UNPARSEABLE = (
    ".prettierrc.js", ".prettierrc.cjs", ".prettierrc.yml", ".prettierrc.yaml",
    "prettier.config.js", "prettier.config.cjs",
)


def _js_formatter(root: Path) -> tuple[dict, str] | None:
    pkg = read_json(root / "package.json")
    if pkg and isinstance(pkg.get("prettier"), dict):
        return _prettier_settings(pkg["prettier"]), "package.json#prettier"
    for name in _PRETTIER_JSON_LOCATIONS:
        data = read_json(root / name)
        if data is not None:
            return _prettier_settings(data), name
    return None


def _js_formatter_skip_note(root: Path) -> str | None:
    for name in _PRETTIER_UNPARSEABLE:
        if (root / name).exists():
            return f"found {name} but it's not machine-parseable (JS/YAML); skipping JS/TS"
    return None


def _prettier_settings(cfg: dict) -> dict:
    use_tabs = cfg.get("useTabs", False)
    settings = {
        "indent_style": "tab" if use_tabs else "space",
        "indent_size": cfg.get("tabWidth", 2),
        "max_line_length": cfg.get("printWidth", 80),
    }
    eol = {"lf": "lf", "crlf": "crlf"}.get(cfg.get("endOfLine", "lf"))
    if eol:
        settings["end_of_line"] = eol
    return settings


def _rust_formatter(root: Path) -> tuple[dict, str] | None:
    for name in ("rustfmt.toml", ".rustfmt.toml"):
        path = root / name
        if not path.exists():
            continue
        data = read_toml(path) or {}
        settings = {
            "indent_style": "tab" if data.get("hard_tabs", False) else "space",
            "indent_size": data.get("tab_spaces", 4),
            "max_line_length": data.get("max_width", 100),
        }
        eol = {"Unix": "lf", "Windows": "crlf"}.get(data.get("newline_style", "Auto"))
        if eol:
            settings["end_of_line"] = eol
        return settings, name
    return None


def _detect_python(root: Path, languages: set[str], detections: dict) -> None:
    if "python" not in languages:
        return
    result = _python_formatter(root)
    if result:
        detections[LANGUAGE_GLOBS["python"]] = result


def _detect_js(root: Path, languages: set[str], detections: dict, skip_notes: list[str]) -> None:
    if "javascript" not in languages and "typescript" not in languages:
        return
    result = _js_formatter(root)
    if not result:
        note = _js_formatter_skip_note(root)
        if note:
            skip_notes.append(note)
        return
    settings, source = result
    for lang in ("javascript", "typescript"):
        if lang in languages:
            detections[LANGUAGE_GLOBS[lang]] = (settings, source)


def _detect_rust(root: Path, languages: set[str], detections: dict) -> None:
    if "rust" not in languages:
        return
    result = _rust_formatter(root)
    if result:
        detections[LANGUAGE_GLOBS["rust"]] = result


def detect_formatters(
    root: Path, languages: set[str]
) -> tuple[dict[str, tuple[dict, str]], list[str]]:
    """Returns {glob: (settings, source)} for every language with an actual
    detected formatter config, plus a list of human-readable skip notes for
    configs found but not machine-parseable.
    """
    detections: dict[str, tuple[dict, str]] = {}
    skip_notes: list[str] = []

    _detect_python(root, languages, detections)
    _detect_js(root, languages, detections, skip_notes)
    _detect_rust(root, languages, detections)

    return detections, skip_notes


def _parse_editorconfig_sections(text: str) -> set[str]:
    sections = set()
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            sections.add(line[1:-1])
    return sections


def _render_section(glob: str, settings: dict) -> str:
    lines = [f"[{glob}]"]
    for key in ("indent_style", "indent_size", "end_of_line", "max_line_length"):
        if key in settings:
            lines.append(f"{key} = {settings[key]}")
    return "\n".join(lines)


def plan_editorconfig(root: Path, languages: set[str]) -> AlignPlan:
    path = root / EDITORCONFIG
    existing_text = read_text(path) or ""
    existing_sections = _parse_editorconfig_sections(existing_text) if path.exists() else set()
    detections, skip_notes = detect_formatters(root, languages)

    additions: list[str] = []
    new_blocks: list[str] = []
    for glob, (settings, source) in detections.items():
        if glob in existing_sections:
            additions.append(f"[{glob}] already present - left as-is (source: {source})")
            continue
        new_blocks.append(_render_section(glob, settings))
        summary = ", ".join(f"{k}={v}" for k, v in settings.items())
        additions.append(f"add [{glob}] from {source}: {summary}")

    for note in skip_notes:
        additions.append(f"(skipped) {note}")

    if not new_blocks:
        return AlignPlan(EDITORCONFIG, path.exists(), additions, None)

    if path.exists():
        base = existing_text.rstrip("\n")
        new_content = base + "\n\n" + "\n\n".join(new_blocks) + "\n"
    else:
        new_content = "root = true\n\n" + "\n\n".join(new_blocks) + "\n"
        additions.insert(0, "create new file with root = true")

    return AlignPlan(EDITORCONFIG, path.exists(), additions, new_content)


def plan_gitattributes(root: Path, languages: set[str]) -> AlignPlan:
    path = root / GITATTRIBUTES
    existing_text = read_text(path) or ""
    detections, _ = detect_formatters(root, languages)

    eols = {}
    for glob, (settings, source) in detections.items():
        eol = settings.get("end_of_line")
        if eol:
            eols[glob] = (eol, source)

    if not eols:
        return AlignPlan(
            GITATTRIBUTES, path.exists(),
            ["no detected formatter expresses an EOL preference - nothing to propagate"],
        )

    distinct = {eol for eol, _ in eols.values()}
    if len(distinct) > 1:
        detail = ", ".join(f"{g}={eol} ({src})" for g, (eol, src) in eols.items())
        return AlignPlan(
            GITATTRIBUTES, path.exists(),
            [f"conflict: detected formatters disagree on line endings ({detail}) - skipped"],
        )

    eol = next(iter(distinct))
    if "text=auto" in existing_text:
        return AlignPlan(
            GITATTRIBUTES, path.exists(),
            [f"'* text=auto' rule already present - left as-is (would have set eol={eol})"],
        )

    line = f"* text=auto eol={eol}"
    if path.exists():
        base = existing_text.rstrip("\n")
        new_content = f"{base}\n{line}\n" if base else f"{line}\n"
    else:
        new_content = f"{line}\n"

    return AlignPlan(GITATTRIBUTES, path.exists(), [f"add `{line}`"], new_content)


def plan_gitignore(root: Path, languages: set[str]) -> AlignPlan:
    path = root / GITIGNORE
    existing_text = read_text(path) or ""

    missing: list[str] = []
    for language in sorted(languages):
        for pattern in ALIGN_IGNORE_PATTERNS.get(language, []):
            if pattern not in existing_text and pattern not in missing:
                missing.append(pattern)

    if not missing:
        return AlignPlan(GITIGNORE, path.exists(), ["already covers the detected stack"])

    block = "\n".join(missing)
    if path.exists():
        base = existing_text.rstrip("\n")
        new_content = f"{base}\n{block}\n" if base else f"{block}\n"
    else:
        new_content = f"{block}\n"

    additions = [f"add `{p}`" for p in missing]
    return AlignPlan(GITIGNORE, path.exists(), additions, new_content)


def build_align_plans(root: Path, languages: set[str]) -> list[AlignPlan]:
    return [
        plan_editorconfig(root, languages),
        plan_gitattributes(root, languages),
        plan_gitignore(root, languages),
    ]


def apply_plan(root: Path, plan: AlignPlan) -> bool:
    if plan.new_content is None:
        return False
    (root / plan.file).write_text(plan.new_content, encoding="utf-8")
    return True

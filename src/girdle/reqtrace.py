from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

REQ_PATTERN = re.compile(r"^\s*-\s*\*\*(REQ-\d+)\*\*")
SPEC_SLUG_PATTERN = re.compile(r"spec-(.*)\.md$")


@dataclass
class TraceabilityResult:
    """Result of a traceability check."""

    untraced: list[str] = field(default_factory=list)
    orphaned: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def has_failures(self) -> bool:
        """Return True if there are any untraced, orphaned, or problem entries."""
        return bool(self.untraced or self.orphaned or self.problems)


def _extract_defined_reqs(spec_path: Path) -> set[str]:
    """Parse a spec file for REQ-NNN definitions."""
    defined_reqs = set()
    if not spec_path.is_file():
        return defined_reqs
    content = spec_path.read_text("utf-8")
    for line in content.splitlines():
        match = REQ_PATTERN.match(line)
        if match:
            defined_reqs.add(match.group(1))
    return defined_reqs


def _extract_traced_reqs(
    tests_dir: Path, spec_slug: str, repo_root: Path
) -> tuple[set[str], list[str]]:
    """Parse test files for @pytest.mark.req markers."""
    traced_reqs = set()
    problems = []

    for test_file in tests_dir.rglob("test_*.py"):
        try:
            tree = ast.parse(test_file.read_text("utf-8"), filename=str(test_file))
        except SyntaxError as e:
            problems.append(f"{test_file}:{e.lineno}: could not parse file: {e}")
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            for decorator in node.decorator_list:
                is_req_marker = False
                if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                    # Could be <something>.req
                    if decorator.func.attr == "req":
                        # Could be mark.req
                        if (
                            isinstance(decorator.func.value, ast.Attribute)
                            and decorator.func.value.attr == "mark"
                        ):
                            # Could be pytest.mark.req
                            if (
                                isinstance(decorator.func.value.value, ast.Name)
                                and decorator.func.value.value.id == "pytest"
                            ):
                                is_req_marker = True

                if not is_req_marker:
                    continue

                rel_path = test_file.relative_to(repo_root)
                if len(decorator.args) != 2:
                    problems.append(
                        f"{rel_path}:{decorator.lineno}: "
                        "@pytest.mark.req must have 2 arguments"
                    )
                    continue

                slug_arg, req_id_arg = decorator.args

                if isinstance(slug_arg, ast.Constant) and isinstance(slug_arg.value, str):
                    slug = slug_arg.value
                else:
                    problems.append(
                        f"{rel_path}:{slug_arg.lineno}: "
                        "slug argument of @pytest.mark.req must be a string literal"
                    )
                    continue

                if slug != spec_slug:
                    continue

                if isinstance(req_id_arg, ast.Constant) and isinstance(req_id_arg.value, str):
                    req_id = req_id_arg.value
                    traced_reqs.add(req_id)
                else:
                    problems.append(
                        f"{rel_path}:{req_id_arg.lineno}: "
                        "req_id argument of @pytest.mark.req must be a string literal"
                    )

    return traced_reqs, problems


def check_traceability(spec_path: Path, tests_dir: Path) -> TraceabilityResult:
    """Check for traceability between a spec and tests."""
    slug_match = SPEC_SLUG_PATTERN.search(spec_path.name)
    if not slug_match:
        return TraceabilityResult(
            problems=[f"Spec file name '{spec_path.name}' does not match 'spec-*.md' pattern."]
        )
    spec_slug = slug_match.group(1)

    repo_root = tests_dir.parent
    defined_reqs = _extract_defined_reqs(spec_path)
    traced_reqs, problems = _extract_traced_reqs(tests_dir, spec_slug, repo_root)

    untraced = sorted(list(defined_reqs - traced_reqs))
    orphaned = sorted(list(traced_reqs - defined_reqs))

    return TraceabilityResult(untraced=untraced, orphaned=orphaned, problems=problems)

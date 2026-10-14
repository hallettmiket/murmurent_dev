"""
Purpose: Keep this machine's repositories folder a setting, not an assumption (#166).
Author: Mike Hallett (with Claude Code)
Date: 2026-10-14
Input: every Python file under src/murmurent
Output: pytest assertions

People keep repositories in ~/repos, ~/repo, ~/repositories or elsewhere, and
`murmurent config repos-root` records which. About 40 places once ignored that
and wrote ``~/repos`` directly; they came back one at a time, so this test
fails on any new one. Build a path to this machine's repositories from
core.repo.repos_root() or core.repo_paths.find(); a remote machine's folder
comes from its host record (hosts.DEFAULT_REMOTE_PROJECT_ROOT when it has none).

Comments and docstrings are not checked: they may describe the convention.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "murmurent"

#: The only files that may spell the folder out, and why.
ALLOWED = {
    "core/repo.py": "the setting itself: repos_root()'s fallback and legacy constants",
    "core/hosts.py": "DEFAULT_REMOTE_PROJECT_ROOT, a remote machine's folder when its record has none",
}
LITERALS = ("~/repos", "$HOME/repos")


def _docstring_nodes(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                ids.add(id(body[0].value))
    return ids


def _offences(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = _docstring_nodes(tree)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            if any(lit in node.value for lit in LITERALS):
                found.append(f"line {node.lineno}: {node.value[:60]!r}")
        # Path.home() / "repos"
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) \
                and isinstance(node.right, ast.Constant) and node.right.value == "repos" \
                and isinstance(node.left, ast.Call) and getattr(node.left.func, "attr", "") == "home":
            found.append(f"line {node.lineno}: Path.home() / 'repos'")
    return found


def test_no_hard_coded_repositories_folder() -> None:
    bad = {}
    for path in sorted(SRC.rglob("*.py")):
        rel = str(path.relative_to(SRC))
        if rel in ALLOWED:
            continue
        hits = _offences(path)
        if hits:
            bad[rel] = hits
    assert not bad, (
        "hard-coded ~/repos (use core.repo.repos_root() or core.repo_paths.find(); "
        f"a remote folder comes from its host record): {bad}"
    )


def test_the_guard_catches_what_it_should(tmp_path: Path) -> None:
    sample = tmp_path / "x.py"
    sample.write_text('"""~/repos is fine in a docstring"""\nfrom pathlib import Path\n'
                      'a = Path.home() / "repos"\nb = "~/repos/x"\n', encoding="utf-8")
    assert len(_offences(sample)) == 2

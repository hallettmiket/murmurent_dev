"""
Purpose: classify every tracked file against release/allowlist.yaml and fail if
         anything is unclassified or unresolved. The gate the export script runs.
Author: Mike Hallett (with Claude Code)
Date: 2026-09-01
Input: the git index of the repo this lives in, plus release/allowlist.yaml
Output: a per-bucket report; exit 1 if any file is unclassified or in `decide`

A file matching no rule is an error rather than a default. A release allowlist
that silently drops an unrecognised path is as broken as one that ships it:
both decide on the author's behalf, and neither says so.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
SPEC = REPO / "release" / "allowlist.yaml"


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files"], capture_output=True, text=True, check=True
    )
    return sorted(out.stdout.splitlines())


def _matches(path: str, rule: str) -> bool:
    return path.startswith(rule) if rule.endswith("/") else path == rule


def _best(path: str, rules: list[str]) -> str | None:
    """Longest matching rule wins, so a file rule beats its parent subtree."""
    hits = [r for r in rules if _matches(path, r)]
    return max(hits, key=len) if hits else None


def classify(paths: list[str], spec: dict) -> dict[str, list[str]]:
    ship = [r for r in spec.get("ship") or []]
    hold = [r for r in spec.get("withhold") or []]
    undecided = [d["path"] for d in spec.get("decide") or []]
    buckets: dict[str, list[str]] = {
        "ship": [], "withhold": [], "decide": [], "unclassified": []
    }
    for p in paths:
        candidates = {
            "ship": _best(p, ship),
            "withhold": _best(p, hold),
            "decide": _best(p, undecided),
        }
        # Longest rule wins, but `decide` wins any tie: an unresolved
        # judgement must never be silently settled by a rule of equal
        # specificity sitting in ship.
        best = max((len(v) for v in candidates.values() if v), default=0)
        winner = next(
            (k for k in ("decide", "withhold", "ship")
             if candidates[k] and len(candidates[k]) == best),
            None,
        )
        buckets[winner or "unclassified"].append(p)
    return buckets


def main() -> int:
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    buckets = classify(tracked_files(), spec)

    for name in ("ship", "withhold", "decide", "unclassified"):
        print(f"{name:14s} {len(buckets[name]):5d}")

    problems = 0
    if buckets["decide"]:
        ids = {
            d["id"]: d["path"] for d in spec.get("decide") or []
        }
        print("\nUNRESOLVED — a person must move these into ship or withhold:")
        for did, path in sorted(ids.items()):
            n = sum(1 for p in buckets["decide"] if _matches(p, path))
            print(f"  {did}  {path}  ({n} file{'s' if n != 1 else ''})")
        problems += 1

    if buckets["unclassified"]:
        print("\nUNCLASSIFIED — matched no rule, so the release cannot proceed:")
        for p in buckets["unclassified"]:
            print(f"  {p}")
        problems += 1

    if problems:
        print("\nFAIL — classify the paths above in release/allowlist.yaml.")
        return 1
    print("\nOK — every tracked file is classified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

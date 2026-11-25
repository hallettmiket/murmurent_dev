#!/usr/bin/env python3
"""
Purpose: Print which agent runs on which system, from each agent's ``harnesses:``
         front matter, and count the real runs the agent-event hook recorded.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-22
Input: agents/*.md (front matter), ~/.murmurent/agent_runs.tsv when present
       (date, system, model, agent, verdict; MURMURENT_AGENT_RUNS overrides).
Output: a markdown table on stdout; --json for the same as JSON.
Usage: python3 scripts/harness_matrix.py [--json] [--agents DIR] [--runs FILE]
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import pathlib
import sys

import yaml

HARNESSES = ("claude_code", "antigravity", "faraday")
STATUSES = ("verified", "degraded", "untested")


def front_matter(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.index("\n---", 4)
    return yaml.safe_load(text[4:end]) or {}


def load(agents_dir: pathlib.Path) -> dict[str, dict]:
    out = {}
    for p in sorted(agents_dir.glob("*.md")):
        fm = front_matter(p)
        out[fm.get("name", p.stem)] = fm.get("harnesses") or {}
    return out


def runs(path: pathlib.Path) -> dict[tuple[str, str], collections.Counter]:
    """(agent, harness) -> Counter of verdict words, from the hook's record."""
    out: dict[tuple[str, str], collections.Counter] = collections.defaultdict(collections.Counter)
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 5:
            _date, harness, _model, agent, verdict = parts[:5]
            out[(agent, harness)][verdict] += 1
    return out


def table(matrix: dict[str, dict], recorded) -> str:
    head = "| Agent | " + " | ".join(h.replace("_", " ") for h in HARNESSES) + " |"
    rows = [head, "|---|" + "---|" * len(HARNESSES)]
    for agent, block in matrix.items():
        cells = []
        for h in HARNESSES:
            e = block.get(h) or {}
            status = e.get("status", "untested")
            cell = status
            if e.get("checked"):
                cell += f" ({e['checked']})"
            if e.get("note"):
                cell += f": {e['note']}"
            n = sum(recorded.get((agent, h), {}).values())
            if n:
                cell += f", {n} run{'s' if n != 1 else ''} recorded"
            cells.append(cell)
        rows.append(f"| {agent} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("Purpose:")[1].split("Author")[0].strip())
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--agents", type=pathlib.Path,
                    default=pathlib.Path(__file__).resolve().parents[1] / "agents")
    ap.add_argument("--runs", type=pathlib.Path,
                    default=pathlib.Path(os.environ.get(
                        "MURMURENT_AGENT_RUNS", pathlib.Path.home() / ".murmurent" / "agent_runs.tsv")))
    a = ap.parse_args(argv)
    matrix = load(a.agents)
    recorded = runs(a.runs)
    if a.json:
        print(json.dumps({"harnesses": matrix,
                          "runs": {f"{k[0]}/{k[1]}": dict(v) for k, v in recorded.items()}},
                         indent=2, default=str))
    else:
        print(table(matrix, recorded))
    return 0


if __name__ == "__main__":
    sys.exit(main())

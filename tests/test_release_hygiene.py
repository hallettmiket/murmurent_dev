"""Nothing tied to one deployment reaches the public release (#133).

The public repo is seeded from the paths `release/allowlist.yaml` marks `ship`.
This asserts that none of those paths names another centre's business: a
private repo, a grant document, or a Slack channel, workspace or bot ID.

Why a test and not a review. Two of these were live defects rather than
untidiness. `dashboard/slack_notify.py` hardcoded one lab's dev channel as the
LAST-RESORT default for every notification, so any installation anywhere would
have defaulted to posting into that lab's Slack; `commands/reconcile_cmd.py`
did the same. Neither was wrong on the machine it was written on, which is
exactly why nobody noticed. Only a comparison against the shipping set catches
it.

`rules/local/` is the sanctioned home for these facts and is withheld, so it is
excluded here by construction rather than by a special case.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "release"))

# Substrings that must not appear in a shipped file. Each is a fact about one
# deployment, not about murmurent.
FORBIDDEN = {
    "murmurent_manuscript": "a private repo the public cannot clone",
    "chair_renewal": "a grant document that is not published",
    "C0B3D9DS6SE": "a Slack channel ID (#claude-test)",
    "C0ANNQ1U5EZ": "a Slack channel ID (#claude-code)",
    "CDWPTRQ86": "a Slack channel ID (lab infra)",
    "comp-bio-westernu": "a Slack workspace slug",
    "U0BHESELBAL": "a Slack bot user ID",
}

TEXT_SUFFIXES = {
    ".py", ".sh", ".md", ".yml", ".yaml", ".toml", ".json", ".txt", ".command",
}


def _shipping_paths() -> list[str]:
    from check_allowlist import classify  # noqa: PLC0415

    spec = yaml.safe_load((REPO / "release" / "allowlist.yaml").read_text())
    tracked = subprocess.run(
        ["git", "-C", str(REPO), "ls-files"], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    return classify(sorted(tracked), spec)["ship"]


@pytest.mark.parametrize("needle,why", sorted(FORBIDDEN.items()))
def test_no_shipped_file_names_a_deployment_fact(needle: str, why: str):
    offenders = []
    for rel in _shipping_paths():
        if Path(rel).suffix not in TEXT_SUFFIXES:
            continue
        try:
            text = (REPO / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if needle in line:
                offenders.append(f"{rel}:{i}")
    assert not offenders, (
        f"{needle!r} is {why} and must not ship. Found in: {offenders[:10]}. "
        "Move it to rules/local/, or resolve it from env/config at runtime."
    )


def test_the_allowlist_leaves_nothing_unclassified():
    """A path matching no rule must stop the release, not pick a default."""
    from check_allowlist import classify  # noqa: PLC0415

    spec = yaml.safe_load((REPO / "release" / "allowlist.yaml").read_text())
    tracked = subprocess.run(
        ["git", "-C", str(REPO), "ls-files"], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    buckets = classify(sorted(tracked), spec)
    assert not buckets["unclassified"], (
        "classify these in release/allowlist.yaml: "
        f"{buckets['unclassified'][:10]}"
    )


def test_slack_channel_defaults_are_not_literals():
    """The regression that motivated this file: no ID baked into source."""
    for rel in ("src/murmurent/dashboard/slack_notify.py",
                "src/murmurent/commands/reconcile_cmd.py"):
        text = (REPO / rel).read_text(encoding="utf-8")
        bad = re.findall(r'=\s*"C[A-Z0-9]{8,}"', text)
        assert not bad, f"{rel} assigns a literal Slack ID: {bad}"

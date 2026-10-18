"""
Purpose: Tests for core/sensitivity.py, the single source of the three
         sensitivity tiers, and for the places that must read the former name
         ``clinical`` as ``protected`` (issue #205).
Author: Mike Hallett (with Claude Code)
Date: 2026-10-18
Input: None (pure functions, plus small files under pytest's tmp_path).
Output: Test results.
"""

from __future__ import annotations

import click
import pytest
from click.testing import CliRunner

from murmurent.cli import SensitivityChoice, cli
from murmurent.core import cert_projects as CP
from murmurent.core import charter as CH
from murmurent.core import sensitivity as S
from murmurent.core import vault_provision as VP

# ---------------------------------------------------------------------------
# The module itself
# ---------------------------------------------------------------------------


def test_tiers_are_the_manuscript_three():
    assert S.TIERS == ("standard", "restricted", "protected")
    assert S.LEGACY == {"clinical": "protected"}


@pytest.mark.parametrize("raw, want", [
    ("standard", "standard"),
    ("restricted", "restricted"),
    ("protected", "protected"),
    ("clinical", "protected"),
    ("  Clinical ", "protected"),
    ("PROTECTED", "protected"),
    (None, ""),
    ("", ""),
    ("   ", ""),
    ("secret", "secret"),          # unknown: kept, so a validator can name it
])
def test_normalize(raw, want):
    assert S.normalize(raw) == want


@pytest.mark.parametrize("raw", ["protected", "clinical", " Clinical", "PROTECTED"])
def test_is_protected_true(raw):
    assert S.is_protected(raw) is True


@pytest.mark.parametrize("raw", ["standard", "restricted", "", None, "secret"])
def test_is_protected_false(raw):
    assert S.is_protected(raw) is False


def test_is_valid_accepts_legacy_name_only_as_its_new_tier():
    assert all(S.is_valid(t) for t in S.TIERS)
    assert S.is_valid("clinical")
    assert not S.is_valid("secret")
    assert not S.is_valid("")


def test_other_modules_take_their_tiers_from_here():
    assert CP.VALID_SENSITIVITY_TIERS == S.TIERS
    assert CH.VALID_SENSITIVITY_TIERS == S.TIERS


# ---------------------------------------------------------------------------
# Command line: offers three names, still accepts the old one
# ---------------------------------------------------------------------------


def test_choice_normalizes_clinical_to_protected():
    choice = SensitivityChoice()
    assert choice.convert("clinical", None, None) == "protected"
    assert choice.convert("Protected", None, None) == "protected"
    assert choice.convert("standard", None, None) == "standard"
    with pytest.raises(click.BadParameter):
        choice.convert("secret", None, None)


@pytest.mark.parametrize("argv", [
    ["project", "new", "--help"],
    ["project", "sensitivity", "--help"],
])
def test_help_text_shows_only_the_three_names(argv):
    out = CliRunner().invoke(cli, argv).output
    assert "protected" in out
    assert "clinical" not in out


# ---------------------------------------------------------------------------
# Readers treat a legacy ``clinical`` record exactly like ``protected``
# ---------------------------------------------------------------------------


def test_cert_project_built_with_legacy_name_holds_protected():
    cp = CP.CertProject(name="p", lab="mh", sensitivity="clinical")
    assert cp.sensitivity == "protected"
    with pytest.raises(CP.CertProjectValidationError, match="reb_number"):
        CP.validate_project(cp)


def test_legacy_charter_still_validates_and_render_writes_protected():
    meta = {"project": "p", "lead": "@a", "members": ["@a"], "sensitivity": "clinical",
            "reb_number": "R1", "reb_expires": "2027-01-01", "data_residency": "ca"}
    CH.validate_charter(meta)                       # old charter: still valid
    text = CH.render_charter(project="p", lead="@a", members=["@a"],
                             sensitivity="clinical", description="x",
                             reb_number="R1", reb_expires="2027-01-01",
                             data_residency="ca")
    assert "sensitivity: protected" in text
    assert "sensitivity: clinical" not in text


def test_vault_scan_excludes_protected_and_legacy_clinical(tmp_path):
    for name, tag in (("a", "protected"), ("b", "clinical"), ("c", "standard")):
        (tmp_path / f"{name}.md").write_text(f"---\nsensitivity: {tag}\n---\nx\n",
                                             encoding="utf-8")
    assert VP.scan_sensitive(tmp_path) == ["a.md", "b.md"]

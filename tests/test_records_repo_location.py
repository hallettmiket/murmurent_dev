"""Tests for where a machine looks for a group's lab records repo.

There is exactly one place per group: ``<repos>/murmurent_lab_mgmt_<group>``.
The machine owner's identity card says which groups they belong to, and that
is the whole lookup. There is no pin file, no scan of the repositories folder,
and no placeholder roster. A clone at any other path is reported with the
command that moves it, never used.

These pin that contract:
  * a card for group ``mh`` resolves to the canonical path, present or not
  * a clone under another name is ignored; the hint says how to move it
  * ``MURMURENT_LAB_MGMT_REPO`` still wins over the card
  * a led group wins over a plain membership
  * a stale pin file from an older murmurent is ignored
  * no card and no registry → the group-less default that never exists
"""

from __future__ import annotations

from pathlib import Path

import pytest

from murmurent.core import identity_card as IC
from murmurent.core import repo as _repo


def _make_clone(root: Path, name: str, *, lab: str, members: list[str]) -> Path:
    """A records repo clone (lab.md + members/<h>.md) under root."""
    clone = root / name
    (clone / "members").mkdir(parents=True)
    (clone / "lab.md").write_text(
        f"---\nlab: {lab}\nname: {lab.title()} Lab\npi: '@the_pi'\n---\n",
        encoding="utf-8")
    for h in members:
        (clone / "members" / f"{h}.md").write_text(
            f"---\nhandle: '@{h}'\nfull_name: '{h.title()}'\n"
            "role: postdoc\nstatus: active\n---\n",
            encoding="utf-8")
    return clone


def _card(netname: str, roles: list[dict]) -> dict:
    return {"version": 1, "netname": netname, "centre": "qa", "roles": roles,
            "issued_by": "the_pi", "issued_at": "2026-10-01"}


MEMBER_OF_MH = {"kind": "member", "group": "mh", "pi": "@the_pi", "group_kind": "lab"}
LEADS_SEQ = {"kind": "core_leader", "group": "seq", "pi": "@bob"}


@pytest.fixture
def member_machine(monkeypatch, tmp_path):
    """A member machine: isolated repos root + MURMURENT_HOME, no env var."""
    repos = tmp_path / "repos"
    repos.mkdir()
    monkeypatch.setenv("MURMURENT_REPOS_ROOT", str(repos))
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("MURMURENT_LAB_INFO_ROOT", str(tmp_path / "home" / "lab_info"))
    monkeypatch.delenv("MURMURENT_LAB_MGMT_REPO", raising=False)
    monkeypatch.setenv("MURMURENT_USER", "bob")
    monkeypatch.setattr(_repo, "DEFAULT_LAB_MGMT_REPO", tmp_path / "no_default")
    return repos


def test_card_resolves_to_the_canonical_path_even_before_cloning(member_machine):
    IC.import_card(_card("bob", [MEMBER_OF_MH]))
    want = member_machine / "murmurent_lab_mgmt_mh"
    assert _repo.lab_mgmt_repo_root() == want
    assert not want.exists()           # nothing invented on disk


def test_card_resolves_to_the_clone_once_present(member_machine):
    IC.import_card(_card("bob", [MEMBER_OF_MH]))
    clone = _make_clone(member_machine, "murmurent_lab_mgmt_mh", lab="mh",
                        members=["the_pi", "bob"])
    assert _repo.lab_mgmt_repo_root() == clone


def test_clone_under_another_name_is_not_used_but_is_pointed_at(member_machine):
    IC.import_card(_card("bob", [MEMBER_OF_MH]))
    stray = _make_clone(member_machine, "lab_mgmt", lab="mh", members=["the_pi", "bob"])
    want = member_machine / "murmurent_lab_mgmt_mh"
    assert _repo.lab_mgmt_repo_root() == want
    assert _repo.find_misplaced_records_clone("mh") == stray
    hint = _repo.records_clone_hint("mh")
    assert f"mv {stray} {want}" in hint


def test_clone_hint_names_the_remote_when_known(member_machine):
    IC.import_card(_card("bob", [MEMBER_OF_MH]))
    want = member_machine / "murmurent_lab_mgmt_mh"
    hint = _repo.records_clone_hint("mh", remote="git@github.com:owner/murmurent_lab_mgmt_mh.git")
    assert hint.endswith(f"git clone git@github.com:owner/murmurent_lab_mgmt_mh.git {want}")


def test_env_var_wins_over_the_card(member_machine, monkeypatch, tmp_path):
    IC.import_card(_card("bob", [MEMBER_OF_MH]))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(tmp_path / "explicit"))
    assert _repo.lab_mgmt_repo_root() == tmp_path / "explicit"


def test_a_led_group_wins_over_a_membership(member_machine):
    IC.import_card(_card("bob", [MEMBER_OF_MH, LEADS_SEQ]))
    assert _repo.lab_mgmt_repo_root() == member_machine / "murmurent_lab_mgmt_seq"
    groups = _repo.owner_groups()
    assert [(g.group, g.role, g.kind) for g in groups] == [
        ("seq", "leader", "core"), ("mh", "member", "lab")]
    assert groups[1].pi == "the_pi"


def test_stale_pin_file_is_ignored(member_machine, tmp_path):
    IC.import_card(_card("bob", [MEMBER_OF_MH]))
    old = _make_clone(member_machine, "murmurent_lab_mgmt_bioinformatics",
                      lab="bioinformatics", members=["bob"])
    (tmp_path / "home" / "lab_mgmt_path").write_text(str(old) + "\n", encoding="utf-8")
    assert _repo.lab_mgmt_repo_root() == member_machine / "murmurent_lab_mgmt_mh"


def test_no_card_and_no_registry_gives_the_default_that_never_exists(member_machine, tmp_path):
    assert _repo.owner_groups() == []
    assert _repo.lab_mgmt_repo_root() == tmp_path / "no_default"

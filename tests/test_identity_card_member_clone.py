"""
Tests for the member-machine half of identity-card import.

A member's machine has one place for their group's records repo,
``<repos>/murmurent_lab_mgmt_<group>``, and the registry entry that
``import_card`` writes points there whether or not the clone exists yet. No
placeholder roster is written: the card itself proves the membership, so the
dashboard opens, and the import says where to clone.

Regression context (2026-07, 2026-10): a member imported her card and her
dashboard listed only herself, because ``import_card`` had invented a
one-person roster under ``lab_info/`` and pointed the registry at it. Later a
member's terminal followed one lab (an old pin file) while the dashboard
followed another (the registry). Both mechanisms are gone.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from murmurent.core import centre_init as CI
from murmurent.core import identity_card as IC
from murmurent.core import registrar as R
from murmurent.core import repo as _repo


ROSTER = ("yxia266", "vick", "noorish")


@pytest.fixture
def mayor_world(monkeypatch, tmp_path):
    """The MAYOR's machine: a centre registry with a lab whose roster has 3 people."""
    monkeypatch.setenv("MURMURENT_LAB_INFO_ROOT", str(tmp_path / "mayor_lab_info"))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(tmp_path / "mayor_lab_mgmt"))
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "mayor_home"))
    monkeypatch.setattr(R, "REGISTRAR_SENTINEL", tmp_path / "sentinel")
    CI.init_centre(name="Western QA", institution="U", founding_mayor="@tbrowne5",
                   unique_name="western-qa", write_sentinel=False)
    R.create_lab(name="yxia_lab", display_name="Xia Lab",
                 pi_handle="@yxia266", pi_email="y@x.edu")
    # The PI's lab_mgmt (mayor side) carries the whole roster, so build_card's
    # member probe finds @noorish.
    _write_roster(R.read_registry().labs[0].lab_mgmt_path, "yxia_lab")
    return tmp_path


def _write_roster(lab_mgmt_dir, group: str, handles=ROSTER) -> None:
    d = Path(lab_mgmt_dir)
    (d / "members").mkdir(parents=True, exist_ok=True)
    for h in handles:
        (d / "members" / f"{h}.md").write_text(
            f"---\nhandle: '@{h}'\nstatus: active\nlab: {group}\n---\n\n# @{h}\n",
            encoding="utf-8")


def _make_real_clone(repos_root, group: str, handles=ROSTER, name: str | None = None):
    """A member's read-only lab_mgmt clone: lab.md + full members/ + .git."""
    root = Path(repos_root)
    clone = root / (name or f"murmurent_lab_mgmt_{group}")
    (clone / ".git").mkdir(parents=True, exist_ok=True)
    clone.joinpath("lab.md").write_text(
        f"---\nlab: {group}\nname: Xia Lab\npi: '@yxia266'\nkind: lab\n---\n\n# Xia Lab\n",
        encoding="utf-8")
    _write_roster(clone, group, handles)
    return clone


def _become_member(monkeypatch, tmp_path, netname: str):
    """Move to a FRESH member machine: own home, own lab_info, own repos root,
    and no ``MURMURENT_LAB_MGMT_REPO`` (a member never exports it)."""
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / f"{netname}_home"))
    monkeypatch.setenv("MURMURENT_LAB_INFO_ROOT", str(tmp_path / f"{netname}_lab_info"))
    monkeypatch.setenv("MURMURENT_REPOS_ROOT", str(tmp_path / f"{netname}_repos"))
    monkeypatch.delenv("MURMURENT_LAB_MGMT_REPO", raising=False)
    repos = tmp_path / f"{netname}_repos"
    repos.mkdir(parents=True, exist_ok=True)
    return repos


def test_import_card_points_at_the_canonical_clone(mayor_world, monkeypatch, tmp_path):
    card = IC.build_card("noorish", issued_by="@tbrowne5")
    assert any(r["kind"] == "member" and r["group"] == "yxia_lab" for r in card["roles"])

    repos = _become_member(monkeypatch, tmp_path, "noorish")
    clone = _make_real_clone(repos, "yxia_lab")
    actions = IC.import_card(card)

    match = R.lab_mgmt_path_for_handle("noorish")
    assert match is not None and match[0] == "yxia_lab"
    assert Path(match[1]).resolve() == clone.resolve()
    assert _repo.lab_mgmt_repo_root().resolve() == clone.resolve()
    assert any("your copy of the lab records" in a for a in actions)


def test_import_card_without_a_clone_invents_nothing(mayor_world, monkeypatch, tmp_path):
    """No clone yet: the registry still names the canonical path, no roster is
    written under lab_info, the import says how to clone, and the member is
    still recognised (their card proves the membership)."""
    card = IC.build_card("noorish", issued_by="@tbrowne5")
    repos = _become_member(monkeypatch, tmp_path, "noorish")
    actions = IC.import_card(card, remotes={"yxia_lab": "git@github.com:o/murmurent_lab_mgmt_yxia_lab.git"})

    want = repos / "murmurent_lab_mgmt_yxia_lab"
    match = R.lab_mgmt_path_for_handle("noorish")
    assert match == ("yxia_lab", str(want))
    assert not want.exists()
    assert not (tmp_path / "noorish_lab_info" / "labs" / "yxia_lab" / "lab-mgmt").exists()
    hint = next(a for a in actions if "not on this machine yet" in a)
    assert f"gh repo clone o/murmurent_lab_mgmt_yxia_lab {want}" in hint


def test_clone_under_another_name_is_ignored(mayor_world, monkeypatch, tmp_path):
    card = IC.build_card("noorish", issued_by="@tbrowne5")
    repos = _become_member(monkeypatch, tmp_path, "noorish")
    stray = _make_real_clone(repos, "yxia_lab", name="lab_mgmt")
    actions = IC.import_card(card)

    want = repos / "murmurent_lab_mgmt_yxia_lab"
    assert R.lab_mgmt_path_for_handle("noorish") == ("yxia_lab", str(want))
    hint = next(a for a in actions if "not on this machine yet" in a)
    assert f"mv {stray} {want}" in hint


def test_other_peoples_handles_are_not_settled_by_my_card(mayor_world, monkeypatch, tmp_path):
    """The card on this machine only vouches for its own netname."""
    card = IC.build_card("noorish", issued_by="@tbrowne5")
    _become_member(monkeypatch, tmp_path, "noorish")
    IC.import_card(card)
    assert R.lab_mgmt_path_for_handle("vick") is None


def test_a_pi_entry_points_at_the_canonical_path(mayor_world, monkeypatch, tmp_path):
    card = IC.build_card("yxia266", issued_by="@tbrowne5")
    repos = _become_member(monkeypatch, tmp_path, "yxia266")
    IC.import_card(card)
    assert R.lab_mgmt_path_for_handle("yxia266") == (
        "yxia_lab", str(repos / "murmurent_lab_mgmt_yxia_lab"))


# ---- through the real HTTP surface -------------------------------------

def test_member_dashboard_serves_the_full_roster(mayor_world, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from murmurent.dashboard.server import create_app

    card = IC.build_card("noorish", issued_by="@tbrowne5")
    repos = _become_member(monkeypatch, tmp_path, "noorish")
    IC.import_card(card)
    _make_real_clone(repos, "yxia_lab")

    client = TestClient(create_app())
    res = client.get("/api/dashboard?user=noorish")
    assert res.status_code == 200, res.text
    handles = {h.lstrip("@") for h in (res.json().get("group_members") or [])}
    assert handles == set(ROSTER)


def test_member_dashboard_opens_before_the_clone_exists(mayor_world, monkeypatch, tmp_path):
    """A member who has not cloned yet is not refused: the card proves the
    membership, and the page carries the clone command."""
    from fastapi.testclient import TestClient
    from murmurent.dashboard.server import create_app

    card = IC.build_card("noorish", issued_by="@tbrowne5")
    repos = _become_member(monkeypatch, tmp_path, "noorish")
    IC.import_card(card)

    client = TestClient(create_app())
    res = client.get("/api/dashboard?user=noorish")
    assert res.status_code == 200, res.text
    body = res.json()
    records = body.get("lab_records") or {}
    assert records.get("present") is False
    assert str(repos / "murmurent_lab_mgmt_yxia_lab") in (records.get("hint") or "")

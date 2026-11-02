"""
Purpose: Issue #255. Membership of a project means access to every repository
         it lists, granted on add and revoked on removal; a lead who is not the
         PI can remove a member (the revocation waits for the PI's machine);
         the removed person is told; leaving the lab means leaving its projects.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-02
Input:   temporary folders; keys made on the fly; Slack and GitHub seams.
Output:  pass or fail.
"""
from __future__ import annotations

import pytest
from click.testing import CliRunner
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from murmurent.cli import cli
from murmurent.core import cert_projects as CP
from murmurent.core import cert_provision as CPROV
from murmurent.core import idcert as C
from murmurent.core import idkeys as K
from murmurent.core import issuance as ISS
from murmurent.core import membership as MEM
from murmurent.core import project_members as PM
from murmurent.core import revocation as REV


@pytest.fixture
def lab(monkeypatch, tmp_path):
    """A self-rooted PI (@pi, lab mh), two carded members with GitHub logins,
    and a project 'atlas' with two GitHub repositories listed."""
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "pi_home"))
    monkeypatch.setenv("MURMURENT_LAB_INFO_ROOT", str(tmp_path / "pi_li"))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(tmp_path / "lab_mgmt"))
    monkeypatch.setenv("MURMURENT_GROUP_SLACK_TOKEN", "xoxb-test")
    monkeypatch.setenv("MURMURENT_USER", "pi")
    K.generate_keypair()
    out = ISS.self_issue_pi_card("@pi", "mh")
    for h, gh in (("@allie", "allie-gh"), ("@bob", "bob-gh")):
        priv = Ed25519PrivateKey.generate()
        req = C.make_enrollment_request(h, priv=priv, nonce="n", group="mh",
                                        email=f"{h[1:]}@x.edu", slack=f"{h[1:]}slack",
                                        github=gh)
        ISS.issue_member_card(h, enrollment=req, group="mh")
        MEM.upsert_member(h, github=gh)
    ISS.issue_project_lead_card("@pi", project="atlas")
    CP.upsert("atlas", lab="mh", slack_channel_id="CATLAS",
              repos=[CP.RepoRef(name="atlas", remote_url="git@github.com:org/atlas.git"),
                     CP.RepoRef(name="atlas_manuscript", role="manuscript",
                                remote_url="https://github.com/org/atlas_manuscript")])
    return {"tmp": tmp_path, "trust": out["trust_root"]}


def _gh_world():
    acted = {"added": [], "removed": []}
    seams = dict(
        collaborators_fetcher=lambda org, name: set(),
        adder=lambda org, name, login: acted["added"].append((f"{org}/{name}", login)) or (True, "ok"),
        remover=lambda org, name, login: acted["removed"].append((f"{org}/{name}", login)) or (True, "ok"),
    )
    return acted, seams


# ---------------------------------------------------------------------------
# every repository the project lists
# ---------------------------------------------------------------------------


def test_project_github_repos_from_remote_urls_and_legacy(lab):
    cp = CP.get("atlas")
    assert CPROV.project_github_repos(cp) == ["org/atlas", "org/atlas_manuscript"]
    CP.upsert("atlas", lab="mh", github_repo="org/atlas_old")
    assert CPROV.project_github_repos(CP.get("atlas"))[-1] == "org/atlas_old"


def test_reconcile_github_covers_every_repository_and_reports_problems(lab):
    CP.upsert("atlas", lab="mh", member="@allie")
    CP.upsert("atlas", lab="mh", member="@noghost")       # no GitHub login
    acted, seams = _gh_world()
    out = CPROV.reconcile_github("atlas", **seams)
    assert out["ok"] and out["repos"] == ["org/atlas", "org/atlas_manuscript"]
    assert sorted(acted["added"]) == [("org/atlas", "allie-gh"), ("org/atlas_manuscript", "allie-gh")]
    assert out["added"] == ["allie-gh"] and not out["in_sync"]
    assert any("@noghost has no GitHub login" in p for p in out["problems"])
    assert len(out["per_repo"]) == 2


def test_reconcile_github_never_removes_the_repository_owner(lab):
    CP.upsert("atlas", lab="mh", member="@allie")
    acted, seams = _gh_world()
    seams["collaborators_fetcher"] = lambda org, name: {"org", "allie-gh", "stale"}
    out = CPROV.reconcile_github("atlas", **seams)
    assert out["to_remove"] == ["stale"]
    assert ("org/atlas", "org") not in acted["removed"]


def test_provision_github_grants_on_the_list_and_creates_nothing(lab):
    CP.upsert("atlas", lab="mh", member="@allie")
    granted = []
    out = CPROV.provision_github("atlas", repo_creator=lambda o, n: pytest.fail("created"),
                                 collaborator=lambda o, n, l: granted.append(f"{o}/{n}:{l}") or (True, "ok"))
    assert out["ok"] and out["repos"] == ["org/atlas", "org/atlas_manuscript"]
    assert granted == ["org/atlas:allie-gh", "org/atlas_manuscript:allie-gh"]
    assert CP.get("atlas").github_repo == ""


def test_provision_github_without_repositories_says_so(lab):
    CP.upsert("solo", lab="mh")
    out = CPROV.provision_github("solo")
    assert not out["ok"] and out["error"] == "no_repos" and "add-repo" in out["detail"]


def test_add_member_grants_access_everywhere(lab, monkeypatch):
    acted, seams = _gh_world()
    monkeypatch.setattr(CPROV, "_default_collaborators_fetcher", seams["collaborators_fetcher"])
    monkeypatch.setattr(CPROV, "_default_collaborator", seams["adder"])
    out = PM.add_member("atlas", "@allie", dm=False)
    assert out["ok"] and out["github"]["ok"]
    assert sorted(r for r, _l in acted["added"]) == ["org/atlas", "org/atlas_manuscript"]


# ---------------------------------------------------------------------------
# removal
# ---------------------------------------------------------------------------


def test_remove_member_revokes_everywhere_and_tells_them(lab):
    PM.add_member("atlas", "@allie", dm=False)
    kicked, removed, sent = [], [], []
    out = PM.remove_member(
        "atlas", "@allie", actor="@pi",
        uid_resolver=lambda hs, em: {h: "UALLIE" for h in hs},
        kicker=lambda cid, uid: kicked.append((cid, uid)) or (True, "ok"),
        collab_remover=lambda o, n, l: removed.append((f"{o}/{n}", l)) or (True, "ok"),
        dm_sender=lambda ws, **kw: sent.append(kw) or (True, "sent"))
    assert out["ok"] and out["revoked"] and not out["revocation_pending"]
    assert kicked == [("CATLAS", "UALLIE")]
    assert removed == [("org/atlas", "allie-gh"), ("org/atlas_manuscript", "allie-gh")]
    assert sent and "removed from the murmurent project 'atlas' by @pi" in sent[0]["text"]
    assert out["dm"]["sent"] and out["problems"] == []
    assert "@allie" not in CP.get("atlas").members


def test_kick_is_not_blocked_by_an_unresolved_third_party(lab):
    PM.add_member("atlas", "@allie", dm=False)
    CP.upsert("atlas", lab="mh", member="@mystery")       # nobody can resolve them
    kicked = []
    out = PM.remove_member(
        "atlas", "@allie", dm=False,
        uid_resolver=lambda hs, em: {h: ("UALLIE" if h == "allie" else None) for h in hs},
        kicker=lambda cid, uid: kicked.append(uid) or (True, "ok"),
        collab_remover=lambda o, n, l: (True, "ok"))
    assert out["slack"]["ok"] and kicked == ["UALLIE"]


def test_removal_problems_are_listed_not_hidden(lab):
    PM.add_member("atlas", "@allie", dm=False)
    out = PM.remove_member(
        "atlas", "@allie",
        uid_resolver=lambda hs, em: {h: None for h in hs},
        collab_remover=lambda o, n, l: (False, "gh CLI not installed"),
        dm_sender=lambda ws, **kw: (False, "no Slack token"))
    assert out["ok"]
    joined = " ".join(out["problems"])
    assert "could not be matched to a Slack account" in joined
    assert "could not remove allie-gh from org/atlas" in joined
    assert "was not told by direct message" in joined


def test_a_lead_who_is_not_the_pi_removes_and_the_pi_finishes(lab, monkeypatch, tmp_path):
    """The lead's machine cannot sign the lab's revocation list: the removal
    still happens, the card id is recorded, and the PI's reconcile revokes it."""
    PM.add_member("atlas", "@bob", dm=False)
    bob_card = next(c["card_id"] for c in CP.get("atlas").certs if c["handle"] == "@bob")
    CP.upsert("atlas", lab="mh", lead="@allie", member="@allie")
    # Allie's machine: her own key, her member card imported, the lab root pinned.
    allie_bundle = ISS.issue_member_card(
        "@allie", group="mh",
        enrollment=C.make_enrollment_request("@allie", priv=Ed25519PrivateKey.generate(),
                                             nonce="n2", group="mh"))
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "allie_home"))
    monkeypatch.setenv("MURMURENT_LAB_INFO_ROOT", str(tmp_path / "allie_li"))
    monkeypatch.setenv("MURMURENT_USER", "allie")
    K.generate_keypair()
    ISS.verify_and_import_member_card(allie_bundle, trust_root=lab["trust"])
    assert not PM.can_sign_revocations("pi-mh")

    out = PM.remove_member("atlas", "@bob", actor="@allie", dm=False,
                           uid_resolver=lambda hs, em: {h: "UBOB" for h in hs},
                           kicker=lambda cid, uid: (True, "ok"),
                           collab_remover=lambda o, n, l: (True, "ok"))
    assert out["ok"] and not out["revoked"] and out["revocation_pending"]
    assert "@bob" not in CP.get("atlas").members
    rows = CP.get("atlas").pending_revocations
    assert len(rows) == 1 and rows[0]["card_id"] == bob_card and rows[0]["by"] == "@allie"
    assert any("murmurent project reconcile atlas --apply" in p for p in out["problems"])

    # Back on the PI's machine: reconcile finishes the revocation.
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "pi_home"))
    monkeypatch.setenv("MURMURENT_LAB_INFO_ROOT", str(tmp_path / "pi_li"))
    monkeypatch.setenv("MURMURENT_USER", "pi")
    assert PM.can_sign_revocations("pi-mh")
    res = PM.apply_pending_revocations("atlas")
    assert [r["card_id"] for r in res["applied"]] == [bob_card]
    assert not CP.get("atlas").pending_revocations
    assert bob_card in set(REV.current_crl("pi-mh")["payload"]["revoked"])


def test_reconcile_cli_reports_and_applies_pending_revocations(lab, monkeypatch):
    PM.add_member("atlas", "@bob", dm=False)
    card = next(c["card_id"] for c in CP.get("atlas").certs if c["handle"] == "@bob")
    CP.remove_member("atlas", "@bob")
    CP.upsert("atlas", lab="mh", pending_revocations=[{"handle": "@bob", "card_id": card,
                                                         "by": "@allie", "at": "2026-11-02"}])
    monkeypatch.setattr(CPROV, "reconcile_slack",
                        lambda *a, **k: {"ok": False, "error": "not_provisioned", "invited": [],
                                         "kicked": [], "unresolved": []})
    monkeypatch.setattr(CPROV, "reconcile_github",
                        lambda *a, **k: {"ok": False, "error": "not_provisioned", "repos": [],
                                         "to_add": [], "to_remove": [], "in_sync": True,
                                         "problems": []})
    out = CliRunner().invoke(cli, ["project", "reconcile", "atlas"])
    assert out.exit_code == 0, out.output
    assert "1 card(s) removed by a lead await revocation" in out.output
    out = CliRunner().invoke(cli, ["project", "reconcile", "atlas", "--apply"])
    assert out.exit_code == 0, out.output
    assert "revoked 1 card(s) a lead removed: @bob" in out.output
    assert card in set(REV.current_crl("pi-mh")["payload"]["revoked"])


def test_remove_member_cli_prints_the_report(lab, monkeypatch):
    PM.add_member("atlas", "@allie", dm=False)
    monkeypatch.setattr(CPROV, "_default_collab_remover", lambda o, n, l: (True, "ok"))
    monkeypatch.setattr(CPROV, "_default_uid_resolver",
                        lambda hs, em, token=None, slack_map=None: {h: "UALLIE" for h in hs})
    monkeypatch.setattr(CPROV, "_default_kicker", lambda cid, uid, token=None: (True, "ok"))
    monkeypatch.setattr(PM, "_default_dm_sender", lambda ws, **kw: (True, "sent"))
    out = CliRunner().invoke(cli, ["project-remove-member", "@allie", "--project", "atlas"])
    assert out.exit_code == 0, out.output
    assert "removed from atlas (card revoked)" in out.output
    assert "GitHub: access removed on org/atlas, org/atlas_manuscript" in out.output
    assert "Slack: removed from the project channel" in out.output
    assert "told by direct message" in out.output


# ---------------------------------------------------------------------------
# leaving the lab
# ---------------------------------------------------------------------------


def test_remove_from_all_projects_skips_what_they_lead(lab):
    PM.add_member("atlas", "@allie", dm=False)
    CP.upsert("side", lab="mh", lead="@allie", member="@allie")
    CP.upsert("other", lab="mh", member="@allie")
    results = PM.remove_from_all_projects(
        "@allie", dm=False, uid_resolver=lambda hs, em: {h: "U" for h in hs},
        kicker=lambda c, u: (True, "ok"), collab_remover=lambda o, n, l: (True, "ok"))
    by = {r["project"]: r for r in results}
    assert by["atlas"]["ok"] and by["atlas"]["revoked"]
    assert by["other"]["ok"] and not by["other"]["revoked"]
    assert not by["side"]["ok"] and "leads side" in by["side"]["error"]
    assert "@allie" not in CP.get("atlas").members
    assert "@allie" in CP.get("side").members

"""Tests for project-join requests (Phase 8).

Three layers:
  - core.requests   — file/approve/decline + persistence + member add
  - request_actions — auth wrapper + audit logging
  - HTTP endpoint   — POST /api/request/join + /{id}/{action}
"""

from __future__ import annotations

import datetime as _dt

import pytest

from murmurent.commands import project_cmd
from murmurent.core import requests as req_core
from murmurent.dashboard import audit_log, request_actions, snapshot


@pytest.fixture
def world(monkeypatch, tmp_path):
    monkeypatch.setenv("MURMURENT_PROJECTS_ROOT", str(tmp_path / "repos"))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(tmp_path / "lab-mgmt"))
    monkeypatch.setenv("MURMURENT_LAB_VM_ROOT", str(tmp_path / "lab_vm"))
    monkeypatch.setenv("MURMURENT_USER", "diego")
    (tmp_path / "lab-mgmt" / "members").mkdir(parents=True)
    (tmp_path / "lab-mgmt" / "projects").mkdir(parents=True)
    # Set the PI via lab.md (so request_actions can authorise approve/decline).
    (tmp_path / "lab-mgmt" / "lab.md").write_text(
        "---\nlab: hallett\nname: 'Hallett Lab'\npi: '@the_pi'\n---\n", encoding="utf-8"
    )

    project_cmd.cmd_new(
        "p_request",
        charter_path=None,
        members_csv="@the_pi,@allie",  # diego is NOT a member
        description="x", sensitivity="standard", lead="@allie",
        skip_github=True,
    )
    return tmp_path


# ---------------------------------------------------------------------------
# core.requests
# ---------------------------------------------------------------------------


def test_file_request_creates_pending(world):
    req = req_core.file_request(
        requester="diego", project="p_request",
        justification="want to help with imaging",
    )
    assert req.id == 1
    assert req.state == "pending"
    assert req.requester == "@diego"
    assert req.project == "p_request"
    assert req.created_at  # ISO date


def test_file_request_refuses_existing_member(world):
    with pytest.raises(req_core.RequestError) as ei:
        req_core.file_request(requester="allie", project="p_request")
    assert "already a member" in str(ei.value).lower()


def test_file_request_refuses_duplicate_pending(world):
    req_core.file_request(requester="diego", project="p_request")
    with pytest.raises(req_core.RequestError) as ei:
        req_core.file_request(requester="diego", project="p_request")
    assert "pending" in str(ei.value).lower()


def test_file_request_unknown_project(world):
    with pytest.raises(req_core.RequestError) as ei:
        req_core.file_request(requester="diego", project="nope")
    assert "not found" in str(ei.value).lower()


def test_approve_adds_to_members(world):
    req = req_core.file_request(requester="diego", project="p_request")
    req_core.approve(req, approver="the_pi")
    req_core.write_request(req)

    assert req.state == "approved"
    assert req.resolved_by == "@the_pi"

    # Check the project's MEMBERS file got updated.
    members_path = world / "repos" / "p_request" / "MEMBERS"
    text = members_path.read_text()
    assert "@diego" in text


def test_approve_is_idempotent_for_member_add(world):
    """Approving twice would fail at the state machine, but the underlying
    membership-add helper should be safe even if called repeatedly."""
    req_core._add_to_project_members("p_request", "@diego")
    req_core._add_to_project_members("p_request", "@diego")
    members_path = world / "repos" / "p_request" / "MEMBERS"
    occurrences = members_path.read_text().count("@diego")
    assert occurrences == 1


def test_decline_requires_reason(world):
    req = req_core.file_request(requester="diego", project="p_request")
    with pytest.raises(req_core.RequestError):
        req_core.decline(req, decliner="the_pi", reason="")


def test_decline_persists_reason(world):
    req = req_core.file_request(requester="diego", project="p_request")
    req_core.decline(req, decliner="the_pi", reason="not a clinical project member")
    req_core.write_request(req)
    reloaded = req_core.parse_request(req.path)
    assert reloaded.state == "declined"
    assert reloaded.decline_reason == "not a clinical project member"


def test_cannot_re_approve_terminal(world):
    req = req_core.file_request(requester="diego", project="p_request")
    req_core.approve(req, approver="the_pi")
    req_core.write_request(req)
    with pytest.raises(req_core.RequestStateError):
        req_core.approve(req, approver="the_pi")


# ---------------------------------------------------------------------------
# request_actions (auth + audit)
# ---------------------------------------------------------------------------


def test_action_layer_only_pi_can_approve(world):
    req = req_core.file_request(requester="diego", project="p_request")
    with pytest.raises(request_actions.RequestForbidden):
        request_actions.apply_action(
            request_id=req.id, action="approve", actor="diego"
        )


def test_action_layer_pi_approve_works_and_audits(world):
    req = req_core.file_request(requester="diego", project="p_request")
    request_actions.apply_action(
        request_id=req.id, action="approve", actor="the_pi"
    )
    events = audit_log.read_recent()
    kinds = {e.kind for e in events}
    # File event was logged via the file_join_request path; approve here.
    # We only ran apply_action (not file_join_request), so just check approve.
    assert "request.approve" in kinds


def test_action_layer_unknown_action_is_bad_request(world):
    req = req_core.file_request(requester="diego", project="p_request")
    with pytest.raises(request_actions.RequestBadRequest):
        request_actions.apply_action(
            request_id=req.id, action="haxxor", actor="the_pi"
        )


def test_action_layer_decline_requires_reason(world):
    req = req_core.file_request(requester="diego", project="p_request")
    with pytest.raises(request_actions.RequestBadRequest):
        request_actions.apply_action(
            request_id=req.id, action="decline", actor="the_pi"
        )


# ---------------------------------------------------------------------------
# Snapshot integration
# ---------------------------------------------------------------------------


def test_snapshot_member_sees_only_own_pending(world):
    """A member's dashboard shows only THEIR pending requests."""
    req_core.file_request(requester="diego", project="p_request", justification="hi")
    resp = snapshot.build_response("diego", today=_dt.date(2026, 5, 8))
    assert len(resp.requests_pending) == 1
    assert resp.requests_pending[0].requester == "@diego"


def test_snapshot_pi_sees_all_pending(world):
    req_core.file_request(requester="diego", project="p_request", justification="hi")
    resp = snapshot.build_response(
        "the_pi", persona="pi", today=_dt.date(2026, 5, 8)
    )
    assert len(resp.requests_pending) == 1


def test_snapshot_member_does_not_see_others_pending(world):
    """A non-PI member should not see requests from other people."""
    req_core.file_request(requester="diego", project="p_request", justification="hi")
    resp = snapshot.build_response("allie", today=_dt.date(2026, 5, 8))
    # Allie didn't file anything, so requests_pending is empty for her.
    assert resp.requests_pending == []


def test_requests_mine_shows_resolved_too(world):
    req = req_core.file_request(requester="diego", project="p_request", justification="hi")
    request_actions.apply_action(
        request_id=req.id, action="decline", actor="the_pi",
        reason="clinical compliance gap",
    )
    resp = snapshot.build_response("diego", today=_dt.date(2026, 5, 8))
    states = {r.state for r in resp.requests_mine}
    assert "declined" in states


# ---------------------------------------------------------------------------
# HTTP endpoint
# ---------------------------------------------------------------------------


def _client():
    from fastapi.testclient import TestClient
    from murmurent.dashboard.server import create_app
    return TestClient(create_app())


def test_endpoint_file_join_happy_path(world):
    client = _client()
    res = client.post(
        "/api/request/join?user=diego",
        json={"project": "p_request", "justification": "imaging help"},
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["ok"] is True
    assert payload["request"]["state"] == "pending"


def test_endpoint_file_join_409_for_existing_member(world):
    client = _client()
    res = client.post(
        "/api/request/join?user=allie", json={"project": "p_request"}
    )
    assert res.status_code == 409


def test_endpoint_file_join_404_for_unknown_project(world):
    client = _client()
    res = client.post(
        "/api/request/join?user=diego", json={"project": "nonsense"}
    )
    assert res.status_code == 404


def test_endpoint_approve_pi_only(world):
    client = _client()
    client.post("/api/request/join?user=diego", json={"project": "p_request"})
    res_diego = client.post("/api/request/1/approve?user=diego", json={})
    assert res_diego.status_code == 403
    res_pi = client.post("/api/request/1/approve?user=the_pi", json={})
    assert res_pi.status_code == 200
    assert res_pi.json()["request"]["state"] == "approved"


def test_endpoint_decline_requires_reason(world):
    client = _client()
    client.post("/api/request/join?user=diego", json={"project": "p_request"})
    res = client.post("/api/request/1/decline?user=the_pi", json={})
    assert res.status_code == 422


def test_endpoint_decline_persists(world):
    client = _client()
    client.post("/api/request/join?user=diego", json={"project": "p_request"})
    res = client.post(
        "/api/request/1/decline?user=the_pi",
        json={"reason": "wait until next quarter"},
    )
    assert res.status_code == 200
    assert res.json()["request"]["decline_reason"] == "wait until next quarter"


def test_endpoint_unknown_action_is_422(world):
    client = _client()
    client.post("/api/request/join?user=diego", json={"project": "p_request"})
    res = client.post("/api/request/1/explode?user=the_pi", json={})
    assert res.status_code == 422


def test_endpoint_404_for_missing_request(world):
    client = _client()
    res = client.post("/api/request/999/approve?user=the_pi", json={})
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# project = a set of EXISTING repos — approval registers, never scaffolds
# ---------------------------------------------------------------------------


def test_approve_with_attach_repos_registers_without_scaffolding(world, tmp_path):
    """A create request that names its repo set is registered over the clones
    the user already has: the cert-project record carries the repos + members
    and NO new ~/repos/<project> directory is created."""
    from murmurent.core import cert_projects as CP

    # two pre-existing clones in the projects root (the "Repo location" dirs)
    for rname in ("dcis_code", "dcis_manuscript"):
        (world / "repos" / rname).mkdir(parents=True, exist_ok=True)

    req = req_core.file_create_request(
        requester="@allie", project="dcis_17",
        proposed_members=["@allie", "@the_pi"],
        attach_repos=["dcis_code", "dcis_manuscript"],
    )
    req_core.approve(req, approver="@the_pi")

    # no new repo scaffolded for the project itself
    assert not (world / "repos" / "dcis_17").exists()

    cp = CP.get("dcis_17")
    assert cp is not None and cp.status == "active"
    assert cp.lead == "@allie"
    assert {r.name for r in cp.repos} == {"dcis_code", "dcis_manuscript"}
    # role heuristic: manuscript repos are recognised by name
    roles = {r.name: r.role for r in cp.repos}
    assert roles["dcis_manuscript"] == "manuscript"
    assert roles["dcis_code"] == "code"
    assert {m.lstrip("@") for m in cp.members} == {"allie", "the_pi"}


def test_approve_without_attach_repos_keeps_legacy_scaffold(world):
    """The CLI/legacy path (no repo set named) still scaffolds a fresh repo."""
    req = req_core.file_create_request(
        requester="@allie", project="fresh_proj",
        proposed_members=["@allie"],
    )
    req_core.approve(req, approver="@the_pi")
    assert (world / "repos" / "fresh_proj" / "CHARTER.md").is_file()


def _attach_world(world, monkeypatch, names=("dcis_code",), *, ready=()):
    """Clones under the projects root, with git, some already murmurent-ready.
    Records adopt_clone calls instead of running the real bootstrap."""
    from murmurent.core import adopt as _adopt
    from murmurent.core.repo import repos_root
    for rname in names:
        clone = repos_root() / rname
        (clone / ".git").mkdir(parents=True, exist_ok=True)
        if rname in ready:
            (clone / ".murmurent.yaml").write_text("lab: hallett\n", encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setattr(_adopt, "adopt_clone",
                        lambda **kw: calls.append(kw["clone_path"]))
    return calls


def test_approve_makes_attached_repos_ready(world, monkeypatch):
    """#185 item 9: choosing repos for a project makes each one ready; one that
    is already ready is left alone."""
    calls = _attach_world(world, monkeypatch, ("dcis_code", "dcis_ready"),
                          ready=("dcis_ready",))
    req = req_core.file_create_request(
        requester="@allie", project="dcis_18", proposed_members=["@allie"],
        attach_repos=["dcis_code", "dcis_ready"],
    )
    req_core.approve(req, approver="@the_pi")
    assert [p.rsplit("/", 1)[-1] for p in calls] == ["dcis_code"]


def test_approve_survives_a_failed_make_ready(world, monkeypatch):
    from murmurent.core import adopt as _adopt
    from murmurent.core import cert_projects as CP
    _attach_world(world, monkeypatch, ("dcis_code",))

    def boom(**kw):
        raise _adopt.AdoptError("bootstrap failed")
    monkeypatch.setattr(_adopt, "adopt_clone", boom)
    req = req_core.file_create_request(
        requester="@allie", project="dcis_19", proposed_members=["@allie"],
        attach_repos=["dcis_code"],
    )
    req_core.approve(req, approver="@the_pi")
    assert CP.get("dcis_19") is not None


def test_endpoint_approve_attach_repos_skips_remote_provisioning(world, monkeypatch):
    """#185: a project built from existing repos has no project-named working
    tree, so approval must not report a failed git-remote step."""
    _attach_world(world, monkeypatch, ("dcis_code",))
    client = _client()
    res = client.post("/api/request/create-project?user=the_pi", json={
        "project": "dcis_20", "proposed_members": ["@the_pi"],
        "attach_repos": ["dcis_code"],
    })
    assert res.status_code == 200, res.text
    rid = res.json()["request"]["id"]
    res = client.post(f"/api/request/{rid}/approve?user=the_pi")
    assert res.status_code == 200, res.text
    probes = {p["name"]: p for p in res.json().get("probes", [])}
    assert probes["git remote"]["status"] == "ok"
    assert "local clone" not in probes and "remote provisioning" not in probes


def test_approve_copies_a_github_only_repo(world, monkeypatch):
    """#185 item 8: a repo picked from the lab's GitHub organisation is copied
    to this machine on approval, then registered and made ready."""
    import subprocess as _sp
    from murmurent.core import cert_projects as CP
    from murmurent.core.repo import repos_root
    calls = _attach_world(world, monkeypatch, ())          # nothing local yet
    monkeypatch.setattr(req_core, "_github_full_name", lambda name: f"lab-org/{name}")
    real_run = _sp.run

    def fake_run(argv, *a, **kw):
        if list(argv[:3]) == ["gh", "repo", "clone"]:
            dest = argv[4]
            (__import__("pathlib").Path(dest) / ".git").mkdir(parents=True)
            return _sp.CompletedProcess(argv, 0, "", "")
        return real_run(argv, *a, **kw)

    monkeypatch.setattr(_sp, "run", fake_run)
    req = req_core.file_create_request(
        requester="@allie", project="dcis_21", proposed_members=["@allie"],
        attach_repos=["gh_only"],
    )
    req_core.approve(req, approver="@the_pi")
    dest = repos_root() / "gh_only"
    assert (dest / ".git").exists()
    repo = next(r for r in CP.get("dcis_21").repos if r.name == "gh_only")
    assert repo.path == str(dest)
    assert [c.rsplit("/", 1)[-1] for c in calls] == ["gh_only"]

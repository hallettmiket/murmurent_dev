"""Starting a choreography from nothing, and keeping its declaration once made.

Two things are pinned here.

1. **The declaration survives readiness.** ``repo upgrade`` (and
   ``adopt --all-agents`` on a ready repo) used to rewrite ``.murmurent.yaml``
   with the readiness fields only, silently erasing ``kind: choreography``;
   ``choreography install`` then refused the repo as not being one.

2. **``choreography init`` does every step it can, in order, and says what is
   left.** It reuses the existing paths (adopt, the question file, the
   project-create request) rather than re-implementing them.
"""

from __future__ import annotations

import subprocess

import pytest
import yaml
from click.testing import CliRunner

from murmurent.core import choreography as _ch
from murmurent.core import choreography_init as ci
from murmurent.core import choreography_registry as cr
from murmurent.core import repo_ready

DECLARATION = {
    "kind": "choreography",
    "name": "inhibition",
    "title": "Dance with Inhibition",
    "summary": "Four approaches, one judge.",
    "mode": "compositional",
    "approaches": ["t1", "t2"],
}


@pytest.fixture
def env(monkeypatch, tmp_path):
    """A fake commons, an isolated repos root, data root and question folder,
    and a git identity so commits work on any machine."""
    commons = tmp_path / "commons"
    for d in ("agents", "rules", "skills"):
        (commons / d).mkdir(parents=True)
    for a in ("oracle", "blacksmith", "judge"):
        (commons / "agents" / f"{a}.md").write_text(f"# {a}\n", encoding="utf-8")
    monkeypatch.setenv("MURMURENT_COMMONS_ROOT", str(commons))
    repos = tmp_path / "repos"
    repos.mkdir()
    monkeypatch.setenv("MURMURENT_REPOS_ROOT", str(repos))
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("MURMURENT_DATA_ROOT", str(data))
    questions = tmp_path / "group" / "choreographies"
    monkeypatch.setenv(_ch.ENV_CHOREOGRAPHY_DIR, str(questions))
    for k, v in (("GIT_AUTHOR_NAME", "t"), ("GIT_AUTHOR_EMAIL", "t@e"),
                 ("GIT_COMMITTER_NAME", "t"), ("GIT_COMMITTER_EMAIL", "t@e")):
        monkeypatch.setenv(k, v)
    return {"repos": repos, "data": data, "questions": questions}


def _plan(**over) -> ci.ChoreographyPlan:
    base = dict(name="pin1_x", title="Pin1 binders", summary="Dock and assay, then judge.",
                approaches=["t1_dock", "t2_assay"], agents=["blacksmith", "judge"],
                candidate_key="inchikey", criteria="rank by affinity",
                request_project=False)
    base.update(over)
    return ci.ChoreographyPlan(**base)


# ---------------------------------------------------------------------------
# 1. the bug
# ---------------------------------------------------------------------------


def _ready_choreography(tmp_path):
    repo = tmp_path / "repos" / "inhibition"
    repo.mkdir(parents=True)
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    repo_ready.make_ready(repo, lab="mh", agents=["oracle"])
    repo_ready.update_marker(repo, DECLARATION)
    return repo


def test_upgrade_keeps_the_choreography_declaration(env, tmp_path):
    repo = _ready_choreography(tmp_path)
    repo_ready.upgrade(repo, all_agents=True)
    marker = repo_ready.read_marker(repo)
    assert marker["kind"] == "choreography"
    assert marker["approaches"] == ["t1", "t2"]
    assert marker["agents"] == ["blacksmith", "judge", "oracle"], "upgrade still ran"
    assert cr.read_marker(repo).name == "inhibition", "install still accepts it"


def test_readopting_with_new_agents_keeps_the_declaration(env, tmp_path):
    repo = _ready_choreography(tmp_path)
    repo_ready.make_ready(repo, lab="mh", agents=["oracle", "judge"])
    assert repo_ready.read_marker(repo)["kind"] == "choreography"


def test_update_marker_will_not_touch_readiness_fields(env, tmp_path):
    repo = _ready_choreography(tmp_path)
    with pytest.raises(ValueError):
        repo_ready.update_marker(repo, {"agents": []})


def test_update_marker_will_not_make_a_repo_ready(tmp_path):
    with pytest.raises(FileNotFoundError):
        repo_ready.update_marker(tmp_path, DECLARATION)


# ---------------------------------------------------------------------------
# 2. init
# ---------------------------------------------------------------------------


def test_init_does_every_step(env):
    result = ci.init_choreography(_plan(), actor="alice")
    assert result.ok, [p.to_dict() for p in result.probes]
    repo = env["repos"] / "pin1_x"

    for d in ci.LAYOUT_DIRS:
        assert (repo / d).is_dir()
    assert (repo / "how_this_project_breaks.md").is_file()
    assert (repo / "src" / "ready_to_delete.md").is_file()

    marker = repo_ready.read_marker(repo)
    assert marker["murmurent"] == repo_ready.MARKER_SCHEMA, "it is ready"
    info = cr.read_marker(repo)
    assert (info.name, info.mode, info.approaches) == (
        "pin1_x", "compositional", ["t1_dock", "t2_assay"])
    assert marker["question"] == "pin1_x"

    q = _ch.Choreography.from_file(result.question_path)
    assert result.question_path.parent == env["questions"]
    assert (q.poser, q.candidate_key, q.repo) == ("@alice", "inchikey", "pin1_x")

    assert (env["data"] / "append_only" / "pin1_x").is_dir()
    log = subprocess.run(["git", "-C", str(repo), "log", "--oneline"],
                         capture_output=True, text=True, check=True).stdout
    assert "Start the choreography" in log
    status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                            capture_output=True, text=True, check=True).stdout
    assert ".murmurent.yaml" not in status, "the declaration is committed"
    assert any("prepare-run" in s for s in result.next_steps)


def test_an_agent_this_machine_lacks_is_reported(env):
    result = ci.init_choreography(_plan(agents=["judge", "medchem"]), actor="alice")
    ready = next(p for p in result.probes if p.name == "murmurent-ready")
    assert result.ok and ready.status == "warn" and "medchem" in ready.detail


def test_an_invalid_plan_writes_nothing(env):
    with pytest.raises(ci.InitError) as exc:
        ci.init_choreography(_plan(name="Bad Name", criteria=""), actor="alice")
    assert len(exc.value.problems) == 2
    assert not any(env["repos"].iterdir())


def test_criteria_without_a_candidate_key_is_refused(env):
    with pytest.raises(ci.InitError):
        ci.init_choreography(_plan(candidate_key=""), actor="alice")


def test_it_will_not_start_the_same_choreography_twice(env):
    ci.init_choreography(_plan(), actor="alice")
    with pytest.raises(ci.InitError, match="already a choreography"):
        ci.init_choreography(_plan(), actor="alice")


def test_the_question_can_wait(env):
    result = ci.init_choreography(_plan(candidate_key="", criteria=""), actor="alice")
    assert result.ok and result.question_path is None
    assert "question" not in repo_ready.read_marker(result.repo_path)
    assert any("choreography new" in s for s in result.next_steps)


def test_without_a_group_folder_the_repository_keeps_the_question(env, monkeypatch):
    monkeypatch.setattr(_ch, "default_choreography_dir", lambda: None)
    result = ci.init_choreography(_plan(), actor="alice")
    assert result.question_path.parent == result.repo_path / ci.IN_REPO_QUESTION_DIR
    tracked = subprocess.run(["git", "-C", str(result.repo_path), "ls-files"],
                             capture_output=True, text=True, check=True).stdout
    assert "choreography/pin1_x.md" in tracked


def test_the_project_request_names_this_repository(env, monkeypatch):
    from murmurent.dashboard import request_actions as ra

    seen = {}

    class _Req:
        id = 7

    class _Filed:
        request = _Req()

    def fake(**kw):
        seen.update(kw)
        return _Filed()

    monkeypatch.setattr(ra, "file_create_request", fake)
    result = ci.init_choreography(
        _plan(request_project=True, members=["@bob"]), actor="alice")
    assert result.request_id == 7
    assert seen["attach_repos"] == ["pin1_x"], "approval must not scaffold a second repo"
    assert seen["proposed_members"] == ["@bob"]
    assert "request #7" in result.next_steps[0]


def test_a_refused_request_does_not_undo_the_repository(env, monkeypatch):
    from murmurent.dashboard import request_actions as ra

    def refuse(**kw):
        raise ra.RequestBadRequest("project already exists: pin1_x")

    monkeypatch.setattr(ra, "file_create_request", refuse)
    result = ci.init_choreography(_plan(request_project=True), actor="alice")
    assert result.ok and result.request_id is None
    assert result.probes[-1].status == "warn"


# ---------------------------------------------------------------------------
# the two front doors
# ---------------------------------------------------------------------------


def test_cli_with_every_flag(env):
    from murmurent.cli import cli

    r = CliRunner().invoke(cli, [
        "choreography", "init", "pin1_x", "--title", "Pin1 binders",
        "--summary", "Dock and assay.", "--candidate-key", "inchikey",
        "--criteria", "rank by affinity", "--no-project", "--yes"])
    assert r.exit_code == 0, r.output
    assert "What is left" in r.output
    assert cr.read_marker(env["repos"] / "pin1_x").title == "Pin1 binders"


def test_cli_asks_for_what_is_missing(env, monkeypatch):
    from murmurent.cli import cli
    from murmurent.commands import choreography_cmd

    monkeypatch.setattr(choreography_cmd, "_interactive", lambda: True)
    answers = ["Pin1 binders", "Dock and assay, judged together.", "",
               "t1_dock, t2_assay", "y", "inchikey", "rank by affinity", "y"]
    r = CliRunner().invoke(cli, ["choreography", "init", "pin1_x", "--no-project"],
                           input="\n".join(answers) + "\n")
    assert r.exit_code == 0, r.output
    assert "This will:" in r.output, "the plan is shown before anything is made"
    info = cr.read_marker(env["repos"] / "pin1_x")
    assert (info.mode, info.approaches) == ("compositional", ["t1_dock", "t2_assay"])


def test_cli_does_nothing_when_the_plan_is_declined(env, monkeypatch):
    from murmurent.cli import cli
    from murmurent.commands import choreography_cmd

    monkeypatch.setattr(choreography_cmd, "_interactive", lambda: True)
    r = CliRunner().invoke(cli, [
        "choreography", "init", "pin1_x", "--title", "T", "--summary", "S",
        "--mode", "coordination", "--no-project"], input="\nn\n")
    assert "Nothing was created" in r.output
    assert not (env["repos"] / "pin1_x").exists()


def test_cli_says_what_is_missing_instead_of_guessing(env):
    from murmurent.cli import cli

    r = CliRunner().invoke(cli, ["choreography", "init", "pin1_x", "--yes"])
    assert r.exit_code != 0
    assert "title is required" in r.output
    assert not (env["repos"] / "pin1_x").exists()


def test_dashboard_endpoint(env, monkeypatch):
    from fastapi.testclient import TestClient

    from murmurent.dashboard.server import create_app

    monkeypatch.setenv("MURMURENT_USER", "alice")
    client = TestClient(create_app())
    r = client.post("/api/choreography/init", json={
        "name": "pin1_x", "title": "Pin1 binders", "summary": "Dock and assay.",
        "candidate_key": "inchikey", "criteria": "rank", "request_project": False})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] and body["next_steps"]
    bad = client.post("/api/choreography/init", json={
        "name": "pin1_y", "title": "", "summary": "x"})
    assert bad.status_code == 422 and "title" in bad.json()["detail"]

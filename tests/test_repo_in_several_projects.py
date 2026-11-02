"""
Purpose: Issue #253. A repository may be listed by several projects: its data
         stays with its home project and the others read that project's
         folders; ``--home`` moves it; the placeholder project adopt makes is
         retired whatever its name; ``murmurent project add-repo`` and
         ``release-repo`` are for the PI or the lead.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-02
Input:   temporary folders only.
Output:  pass or fail.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from murmurent.cli import cli
from murmurent.core import cert_projects as cp
from murmurent.core import slack_routing as sr


@pytest.fixture
def world(monkeypatch, tmp_path):
    repos = tmp_path / "repos"
    lab_mgmt = tmp_path / "lab_mgmt"
    for d in (repos, lab_mgmt, tmp_path / "mm_home"):
        d.mkdir(parents=True)
    monkeypatch.setenv("MURMURENT_REPOS_ROOT", str(repos))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(lab_mgmt))
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "mm_home"))
    monkeypatch.setenv("MURMURENT_USER", "tester")
    monkeypatch.setenv("MURMURENT_HOSTS_FILE", str(tmp_path / "hosts.yaml"))
    monkeypatch.setattr(sr, "_lab_channel", lambda lab, env=None: "")
    return {"repos": repos, "lab_mgmt": lab_mgmt}


def marked_repo(root: Path, name: str) -> Path:
    p = root / name
    (p / ".git").mkdir(parents=True, exist_ok=True)
    (p / ".murmurent.yaml").write_text(yaml.safe_dump({"murmurent": 1, "lab": "mh"}))
    return p


def _entry(project: str, repo: str) -> cp.RepoRef:
    return next(r for r in cp.get(project).repos if r.name == repo)


# ---------------------------------------------------------------------------
# the home project and reads_from
# ---------------------------------------------------------------------------


def test_second_project_reads_the_home_projects_folders(world):
    repo = marked_repo(world["repos"], "brca_manuscript")
    cp.upsert("brca", lab="mh", slack_channel_id="CBRCA",
              repos=[cp.RepoRef(name="brca_manuscript", role="manuscript", path=str(repo))])
    cp.upsert("brca_paper", lab="mh", slack_channel_id="CPAPER")
    cp.add_repo("brca_paper", role="manuscript", repo_name="brca_manuscript", path=str(repo))

    assert _entry("brca", "brca_manuscript").home == ""            # brca is the home
    assert _entry("brca_paper", "brca_manuscript").home == "brca"
    assert list(cp.get("brca_paper").reads_from) == ["immutable/brca", "append_only/brca"]
    assert cp.home_project_of("brca_manuscript") == "brca"
    assert sorted(p.name for p in cp.owning_projects("brca_manuscript")) == ["brca", "brca_paper"]
    # both projects stay active: neither is a placeholder
    assert cp.get("brca").status == "active"


def test_home_moves_only_when_asked(world):
    repo = marked_repo(world["repos"], "pipeline")
    cp.upsert("study_a", lab="mh", slack_channel_id="CA",
              repos=[cp.RepoRef(name="pipeline", path=str(repo))])
    cp.upsert("study_b", lab="mh", slack_channel_id="CB")
    cp.add_repo("study_b", repo_name="pipeline", path=str(repo))
    assert cp.home_project_of("pipeline") == "study_a"

    cp.add_repo("study_b", repo_name="pipeline", path=str(repo), home=True)
    assert cp.home_project_of("pipeline") == "study_b"
    assert _entry("study_b", "pipeline").home == ""
    assert _entry("study_a", "pipeline").home == "study_b"
    assert list(cp.get("study_a").reads_from) == ["immutable/study_b", "append_only/study_b"]
    assert "immutable/study_a" not in cp.get("study_b").reads_from


def test_home_move_across_three_projects(world):
    repo = marked_repo(world["repos"], "pipeline")
    cp.upsert("a", lab="mh", slack_channel_id="CA", repos=[cp.RepoRef(name="pipeline", path=str(repo))])
    cp.upsert("b", lab="mh", slack_channel_id="CB")
    cp.upsert("c", lab="mh", slack_channel_id="CC")
    cp.add_repo("b", repo_name="pipeline", path=str(repo))
    cp.add_repo("c", repo_name="pipeline", path=str(repo))
    assert list(cp.get("b").reads_from) == list(cp.get("c").reads_from) == cp.home_folders("a")

    cp.add_repo("c", repo_name="pipeline", path=str(repo), home=True)
    assert cp.home_project_of("pipeline") == "c"
    for other in ("a", "b"):
        assert _entry(other, "pipeline").home == "c"
        assert list(cp.get(other).reads_from) == cp.home_folders("c")
    assert not cp.get("c").reads_from


def test_a_repository_in_one_project_has_no_home_field(world):
    repo = marked_repo(world["repos"], "solo")
    cp.upsert("solo_proj", lab="mh")
    cp.add_repo("solo_proj", repo_name="solo", path=str(repo))
    assert _entry("solo_proj", "solo").home == "" and not cp.get("solo_proj").reads_from
    assert cp.home_project_of("solo") == "solo_proj"
    assert cp.home_project_of("nothing") == ""


def test_home_is_written_and_read_back(world):
    ref = cp.RepoRef(name="x", home="other")
    assert cp.RepoRef.from_dict(ref.to_dict()).home == "other"
    assert "home" not in cp.RepoRef(name="x").to_dict()


# ---------------------------------------------------------------------------
# the placeholder adopt made
# ---------------------------------------------------------------------------


def test_placeholder_with_another_name_is_retired(world):
    """adopt names the one-repository project after the project folder, so a
    placeholder ``x`` may hold only ``x_manuscript``; it is retired all the same."""
    repo = marked_repo(world["repos"], "x_manuscript")
    cp.upsert("x", lab="mh", lead="@tester", member="@tester",
              repos=[cp.RepoRef(name="x_manuscript", role="manuscript", path=str(repo))])
    cp.upsert("big_study", lab="mh", slack_channel_id="CBIG")
    cp.add_repo("big_study", role="manuscript", repo_name="x_manuscript", path=str(repo))
    assert cp.get("x").status == "archived"
    assert cp.home_project_of("x_manuscript") == "big_study"
    assert not cp.get("big_study").reads_from        # nothing to read from a placeholder


def test_a_project_with_members_is_not_a_placeholder(world):
    repo = marked_repo(world["repos"], "shared")
    cp.upsert("small", lab="mh", lead="@tester", member="@tester",
              repos=[cp.RepoRef(name="shared", path=str(repo))])
    cp.upsert("small", lab="mh", member="@allie")
    cp.upsert("other", lab="mh")
    cp.add_repo("other", repo_name="shared", path=str(repo))
    assert cp.get("small").status == "active"
    assert _entry("other", "shared").home == "small"


# ---------------------------------------------------------------------------
# the commands
# ---------------------------------------------------------------------------


def test_cli_add_repo_from_a_folder(world):
    repo = marked_repo(world["repos"], "brca_manuscript")
    cp.upsert("brca", lab="mh", slack_channel_id="CBRCA",
              repos=[cp.RepoRef(name="brca_manuscript", role="manuscript", path=str(repo))])
    cp.upsert("brca_paper", lab="mh", slack_channel_id="CPAPER")
    out = CliRunner().invoke(cli, ["project", "add-repo", "brca_paper", str(repo),
                                   "--role", "manuscript"])
    assert out.exit_code == 0, out.output
    assert "brca_paper now lists the repository brca_manuscript (manuscript)" in out.output
    assert "also in: brca" in out.output
    assert "stays in brca's folders" in out.output and "--home" in out.output
    assert sorted(x.channel_id for x in sr.resolve_route(repo).all) == ["CBRCA", "CPAPER"]


def test_cli_add_repo_by_name_and_home(world):
    repo = marked_repo(world["repos"], "pipeline")
    cp.upsert("study_a", lab="mh", slack_channel_id="CA",
              repos=[cp.RepoRef(name="pipeline", path=str(repo))])
    cp.upsert("study_b", lab="mh")
    out = CliRunner().invoke(cli, ["project", "add-repo", "study_b", "pipeline", "--home"])
    assert out.exit_code == 0, out.output
    assert "Its data folders moved" in out.output
    assert cp.home_project_of("pipeline") == "study_b"


def test_cli_add_repo_refuses_a_bad_role_and_an_unknown_project(world):
    cp.upsert("p", lab="mh")
    out = CliRunner().invoke(cli, ["project", "add-repo", "p", "x", "--role", "poem"])
    assert out.exit_code != 0 and "role must be one of" in out.output
    out = CliRunner().invoke(cli, ["project", "add-repo", "nope", "x"])
    assert out.exit_code != 0 and "no project named" in out.output


def test_only_the_lead_or_pi_changes_the_repositories(world):
    cp.upsert("p", lab="mh", lead="@allie", repos=[cp.RepoRef(name="x")])
    out = CliRunner().invoke(cli, ["project", "add-repo", "p", "y"])
    assert out.exit_code != 0 and "only the project lead or the lab PI (@allie)" in out.output
    out = CliRunner().invoke(cli, ["project", "release-repo", "p", "x"])
    assert out.exit_code != 0 and "@allie" in out.output
    assert [r.name for r in cp.get("p").repos] == ["x"]


def test_the_lead_may_change_them(world, monkeypatch):
    monkeypatch.setenv("MURMURENT_USER", "allie")
    cp.upsert("p", lab="mh", lead="@allie", repos=[cp.RepoRef(name="x")])
    out = CliRunner().invoke(cli, ["project", "add-repo", "p", "y", "--role", "data"])
    assert out.exit_code == 0, out.output
    assert sorted(r.name for r in cp.get("p").repos) == ["x", "y"]


def test_release_repo_from_the_home_says_where_the_data_is(world):
    repo = marked_repo(world["repos"], "pipeline")
    cp.upsert("study_a", lab="mh", slack_channel_id="CA",
              repos=[cp.RepoRef(name="pipeline", path=str(repo))])
    cp.upsert("study_b", lab="mh")
    cp.add_repo("study_b", repo_name="pipeline", path=str(repo))
    out = CliRunner().invoke(cli, ["project", "release-repo", "study_a", "pipeline"])
    assert out.exit_code == 0, out.output
    assert "still in study_a's folders, which study_b read" in out.output
    assert "add-repo <project> pipeline --home" in out.output


def test_channels_audit_lists_shared_repositories_without_calling_them_a_fault(world):
    repo = marked_repo(world["repos"], "bioinfo")
    for name in ("bioinfo", "teaching"):
        cp.upsert(name, lab="mh", repos=[cp.RepoRef(name="bioinfo", path=str(repo))])
    out = CliRunner().invoke(cli, ["project", "channels"])
    assert out.exit_code == 0, out.output
    assert "Repositories in more than one active project" in out.output
    assert "bioinfo: bioinfo, teaching" in out.output
    assert "cannot be routed" not in out.output


def test_channel_command_prints_every_channel(world, monkeypatch):
    repo = marked_repo(world["repos"], "bioinfo")
    cp.upsert("bioinfo", lab="mh", slack_channel_id="CBIO",
              repos=[cp.RepoRef(name="bioinfo", path=str(repo))])
    cp.upsert("teaching", lab="mh", slack_channel_id="CTEACH",
              repos=[cp.RepoRef(name="bioinfo", path=str(repo))])
    monkeypatch.chdir(repo)
    out = CliRunner().invoke(cli, ["project", "channel"])
    assert out.exit_code == 0, out.output
    assert sorted(out.output.split()) == ["CBIO", "CTEACH"]

"""
Purpose: Guard issue #166: your repositories folder is a setting, each machine
         finds its own copies, and a project's repositories can sit together.
Author: Mike Hallett (with Claude Code)
Date: 2026-10-14
Input: temporary home folders and git repositories under tmp_path
Output: pytest assertions
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from murmurent.cli import cli
from murmurent.core import project_gather as PG
from murmurent.core import repo as R
from murmurent.core import repo_paths as RP


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    h = tmp_path / "home" / "me"
    h.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: h)
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.delenv("MURMURENT_REPOS_ROOT", raising=False)
    monkeypatch.setattr(R, "MACHINE_SETTINGS_FILE", h / ".murmurent" / "machine.yaml")
    monkeypatch.setenv("MURMURENT_HOME", str(h / ".murmurent"))
    return h


def _git(path: Path, origin: str = "") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    if origin:
        subprocess.run(["git", "-C", str(path), "remote", "add", "origin", origin], check=True)
    return path


# --- the setting ---------------------------------------------------------------

def test_lookup_order_env_then_machine_file_then_default(home: Path, monkeypatch) -> None:
    assert R.repos_root_and_source() == (home / "repos", "the default (nothing set)")
    R.set_repos_root("~/repositories")
    root, source = R.repos_root_and_source()
    assert root == home / "repositories" and "machine.yaml" in source
    monkeypatch.setenv("MURMURENT_REPOS_ROOT", str(home / "elsewhere"))
    assert R.repos_root() == home / "elsewhere"


def test_setting_keeps_the_rest_of_machine_yaml(home: Path) -> None:
    R.MACHINE_SETTINGS_FILE.parent.mkdir(parents=True)
    R.MACHINE_SETTINGS_FILE.write_text("machine_name: laptop\n", encoding="utf-8")
    R.set_repos_root(home / "repo")
    data = yaml.safe_load(R.MACHINE_SETTINGS_FILE.read_text(encoding="utf-8"))
    assert data == {"machine_name": "laptop", "repos_root": "~/repo"}


def test_suggestion_prefers_a_folder_that_exists(home: Path) -> None:
    assert R.suggest_repos_root() == home / "repos"
    (home / "repositories").mkdir()
    assert R.suggest_repos_root() == home / "repositories"


def test_dashboard_save_keeps_both_settings(home: Path, monkeypatch) -> None:
    from murmurent.dashboard import contract as C
    from murmurent.dashboard import machine_settings as MS
    monkeypatch.setattr(MS, "MACHINE_FILE", R.MACHINE_SETTINGS_FILE)
    R.set_repos_root("~/repositories")
    CliRunner().invoke(cli, ["config", "project-layout", "flat"])
    MS.write(C.MachineSettings(machine_name="laptop"))       # an older page sends neither
    data = yaml.safe_load(R.MACHINE_SETTINGS_FILE.read_text(encoding="utf-8"))
    assert data["repos_root"] == "~/repositories" and data["project_layout"] == "flat"


def test_local_host_follows_the_setting(home: Path, monkeypatch) -> None:
    from murmurent.core import hosts
    monkeypatch.setenv("MURMURENT_HOSTS_FILE", str(home / "hosts.yaml"))
    R.set_repos_root("~/repositories")
    assert hosts.read()["local"].project_root == "~/repositories"


# --- finding a repository on this machine --------------------------------------

def test_found_flat_nested_by_record_and_by_origin(home: Path) -> None:
    root = home / "repos"
    flat = _git(root / "alpha")
    nested = _git(root / "proj" / "proj_manuscript")
    assert RP.find("alpha") == flat
    assert RP.find("proj_manuscript") == nested
    odd = _git(home / "odd_place" / "renamed", origin="git@github.com:lab/beta.git")
    assert RP.find("beta") is None
    RP.record("beta", odd)
    assert RP.find("beta") == odd
    _git(root / "gamma_clone", origin="https://github.com/lab/gamma")
    assert RP.find("gamma", remote_url="git@github.com:lab/gamma.git") == root / "gamma_clone"


def test_another_members_folder_is_never_used(home: Path) -> None:
    theirs = _git(home.parent / "them" / "repos" / "delta")
    assert RP.find("delta", hint=str(theirs)) is None
    assert RP.is_mine(home / "x") and RP.is_mine("/data/shared/x") and not RP.is_mine(theirs)


# --- new projects ----------------------------------------------------------------

def test_new_projects_get_a_folder_unless_flat(home: Path) -> None:
    assert RP.new_project_repo("x_y") == home / "repos" / "x_y" / "x_y"
    assert RP.new_project_repo("x_y", "x_y_seminar") == home / "repos" / "x_y" / "x_y_seminar"
    CliRunner().invoke(cli, ["config", "project-layout", "flat"])
    assert RP.new_project_repo("x_y") == home / "repos" / "x_y"


def test_seminar_is_a_repository_role() -> None:
    from murmurent.core import cert_projects as CP
    assert "seminar" in CP.VALID_REPO_ROLES


# --- gather ------------------------------------------------------------------------

def test_gather_shows_its_plan_and_moves_only_with_yes(home: Path) -> None:
    root = home / "repos"
    _git(root / "x_y")
    (root / "x_y" / "notes.txt").write_text("kept\n", encoding="utf-8")
    _git(root / "x_y_manuscript")
    out = CliRunner().invoke(cli, ["project", "gather", "x_y"]).output
    assert "Nothing was moved" in out and (root / "x_y" / ".git").is_dir()

    out = CliRunner().invoke(cli, ["project", "gather", "x_y", "--yes"]).output
    assert "Done." in out, out
    assert (root / "x_y" / "x_y" / ".git").is_dir()
    assert (root / "x_y" / "x_y" / "notes.txt").read_text(encoding="utf-8") == "kept\n"
    assert (root / "x_y" / "x_y_manuscript" / ".git").is_dir()
    assert not (root / "x_y_manuscript").exists() and not (root / "x_y" / ".git").exists()
    assert RP.find("x_y") == root / "x_y" / "x_y"

    again = PG.plan("x_y")                                  # running it twice is harmless
    assert again.moves == [] and set(again.already_inside) == {"x_y", "x_y_manuscript"}


def test_gather_refuses_to_overwrite(home: Path) -> None:
    root = home / "repos"
    (root / "p").mkdir(parents=True)                        # a project folder already exists...
    _git(root / "p" / "p")
    _git(root / "p_manuscript")
    (root / "p" / "p_manuscript").mkdir()                   # ...and something sits at the target
    with pytest.raises(PG.GatherError, match="already exists"):
        PG.plan("p")
    assert (root / "p_manuscript" / ".git").is_dir()        # nothing moved


# --- other servers ----------------------------------------------------------------

def test_remote_folder_is_expanded_by_the_server_and_checked() -> None:
    from murmurent.core import remote_install as RI
    assert RI.shell_dir("~/repositories") == "$HOME/repositories"
    assert RI.shell_dir("/srv/repos/") == "/srv/repos"
    for bad in ("~/x; rm -rf /", "$(id)", "~/../etc"):
        with pytest.raises(ValueError):
            RI.shell_dir(bad)
    lines = RI.commons_lines("~/code")
    assert lines[0] == 'REPOS="$HOME/code"' and "wigamig" in lines[2]

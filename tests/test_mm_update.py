"""Tests for core.mm_update — the "murmurent update available" check (issue #41 pt 1).

Notification-only: it fetches + counts, never pulls. These pin the contract:
behind + fast-forwardable, up to date, no upstream, an offline remote, a diverged
local, and a non-git checkout — all degrade to a benign status, never raise.
"""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from murmurent.core import mm_update as MM


def _cp(returncode=0, stdout=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr="")


@pytest.fixture
def repo(monkeypatch, tmp_path):
    """A murmurent repo root that looks like a git checkout."""
    root = tmp_path / "murmurent"
    (root / ".git").mkdir(parents=True)
    monkeypatch.setattr(MM, "install_root", lambda: root)
    return root


def _wire(monkeypatch, *, upstream_rc=0, upstream="origin/main", fetch_rc=0,
          behind=0, is_ancestor_rc=0, pull_rc=0, pull_out=""):
    """Install a fake _run_git dispatching on the git subcommand."""
    def fake(root, *args):
        if args[:1] == ("rev-parse",) and args[-1] == "@{u}":
            return _cp(upstream_rc, upstream)
        if args[:1] == ("fetch",):
            return _cp(fetch_rc)
        if args[:2] == ("rev-parse", "--short"):
            return _cp(0, "abc1234" if args[-1] == "HEAD" else "def5678")
        if args[:1] == ("rev-list",):
            return _cp(0, str(behind))
        if args[:1] == ("merge-base",):
            return _cp(is_ancestor_rc)
        if args[:1] == ("pull",):
            return _cp(pull_rc, pull_out)
        return _cp(0, "")
    monkeypatch.setattr(MM, "_run_git", fake)


def test_behind_and_fast_forwardable(repo, monkeypatch):
    _wire(monkeypatch, behind=3, is_ancestor_rc=0)
    s = MM.check_update()
    assert s.is_git and s.ok
    assert s.behind == 3 and s.can_ff is True
    assert s.current == "abc1234" and s.latest == "def5678"
    assert "3 new commit" in s.detail


def test_up_to_date(repo, monkeypatch):
    _wire(monkeypatch, behind=0, is_ancestor_rc=0)
    s = MM.check_update()
    assert s.ok and s.behind == 0
    assert s.detail == "up to date"


def test_no_upstream(repo, monkeypatch):
    _wire(monkeypatch, upstream_rc=1)
    s = MM.check_update()
    assert s.is_git and s.ok is False and s.behind == 0
    assert "no upstream" in s.detail


def test_offline_fetch_fails(repo, monkeypatch):
    _wire(monkeypatch, fetch_rc=1)
    s = MM.check_update()
    assert s.ok is False and "offline" in s.detail


def test_offline_skipped_when_fetch_false(repo, monkeypatch):
    # fetch=False must not consult the network at all — a failing fetch is irrelevant.
    _wire(monkeypatch, fetch_rc=1, behind=2, is_ancestor_rc=0)
    s = MM.check_update(fetch=False)
    assert s.ok and s.behind == 2


def test_diverged_local(repo, monkeypatch):
    # behind, but local HEAD is NOT an ancestor of upstream → not a safe ff.
    _wire(monkeypatch, behind=1, is_ancestor_rc=1)
    s = MM.check_update()
    assert s.behind == 1 and s.can_ff is False
    assert "diverged" in s.detail


def test_not_a_git_checkout(monkeypatch, tmp_path):
    monkeypatch.setattr(MM, "install_root", lambda: tmp_path / "plain")
    s = MM.check_update()
    assert s.is_git is False and s.behind == 0


# ---- apply_update (git pull --ff-only, no restart here) ----------------------

def test_apply_update_fast_forwards_and_signals_restart(repo, monkeypatch):
    _wire(monkeypatch, behind=2, is_ancestor_rc=0, pull_rc=0)
    out = MM.apply_update()
    assert out["ok"] and out["pulled"] and out["restart"] is True
    assert out["from"] == "abc1234" and out["to"] == "def5678"


def test_apply_update_refuses_when_diverged(repo, monkeypatch):
    # behind, but local is NOT an ancestor of upstream → never force.
    _wire(monkeypatch, behind=1, is_ancestor_rc=1)
    out = MM.apply_update()
    assert out["ok"] is False and out["pulled"] is False and out["restart"] is False
    assert "diverged" in out["detail"]


def test_apply_update_already_current(repo, monkeypatch):
    _wire(monkeypatch, behind=0)
    out = MM.apply_update()
    assert out["ok"] and out["restart"] is False
    assert out["detail"] == "already up to date"


def test_apply_update_pull_refused_surfaces_error(repo, monkeypatch):
    # ff-able at check time, but git pull refuses (e.g. uncommitted changes).
    _wire(monkeypatch, behind=1, is_ancestor_rc=0, pull_rc=1,
          pull_out="error: Your local changes would be overwritten")
    out = MM.apply_update()
    assert out["ok"] is False and out["restart"] is False
    assert "local changes" in out["detail"]


def test_apply_update_not_a_git_checkout(monkeypatch, tmp_path):
    monkeypatch.setattr(MM, "install_root", lambda: tmp_path / "plain")
    out = MM.apply_update()
    assert out["ok"] is False and out["restart"] is False


def test_install_root_is_the_running_checkout(monkeypatch):
    """Without an override, the checked repo is the one this code runs from,
    not the default ~/repos/murmurent (#185)."""
    monkeypatch.delenv("MURMURENT_REPO_ROOT", raising=False)
    root = MM.install_root()
    assert (root / "src" / "murmurent" / "core" / "mm_update.py").is_file()


def test_install_root_honours_override(monkeypatch, tmp_path):
    monkeypatch.setenv("MURMURENT_REPO_ROOT", str(tmp_path))
    assert MM.install_root() == tmp_path


def test_status_names_the_checked_root(repo, monkeypatch):
    _wire(monkeypatch, behind=1)
    assert MM.check_update().root == str(repo)


def test_reexec_reruns_the_interpreter_with_original_args(monkeypatch):
    calls = []
    monkeypatch.setattr(MM.os, "execv", lambda exe, args: calls.append((exe, args)))
    monkeypatch.setattr(MM.sys, "orig_argv", ["python3", "-m", "murmurent.cli", "dashboard"])
    MM.reexec()
    assert calls == [(MM.sys.executable,
                      [MM.sys.executable, "-m", "murmurent.cli", "dashboard"])]


def test_reexec_failure_is_logged_not_raised(monkeypatch, caplog):
    def boom(exe, args):
        raise OSError("nope")
    monkeypatch.setattr(MM.os, "execv", boom)
    MM.reexec()
    assert "restart failed" in caplog.text


def test_describe_running_code_for_a_checkout(monkeypatch, tmp_path):
    root = tmp_path / "murmurent_dev"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.email=a@b", "-c", "user.name=a",
                    "commit", "-q", "--allow-empty", "-m", "x"], check=True)
    monkeypatch.setattr(MM, "install_root", lambda: root)
    info = MM.describe_running_code()
    assert info["kind"] == "dev" and info["branch"] == "main"
    assert info["label"].startswith("murmurent_dev · main @ ")


def test_describe_running_code_for_a_release(monkeypatch, tmp_path):
    monkeypatch.setattr(MM, "install_root", lambda: tmp_path)
    from murmurent import __version__
    info = MM.describe_running_code()
    assert info == {**info, "kind": "release", "label": f"release v{__version__}"}


def _git(*args, cwd=None):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={**__import__("os").environ, "GIT_AUTHOR_NAME": "a", "GIT_AUTHOR_EMAIL": "a@b",
                        "GIT_COMMITTER_NAME": "a", "GIT_COMMITTER_EMAIL": "a@b"})


def _commit_version(repo, version, msg):
    f = repo / "src" / "murmurent" / "__init__.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f'__version__ = "{version}"\n# {msg}\n')
    _git("add", "-A", cwd=repo)
    _git("commit", "-q", "-m", msg, cwd=repo)


@pytest.fixture
def dev_pair(monkeypatch, tmp_path):
    """A local murmurent_dev clone one or more commits behind its origin."""
    origin = tmp_path / "origin.git"
    _git("init", "-q", "--bare", "-b", "main", str(origin))
    seed = tmp_path / "seed"
    _git("clone", "-q", str(origin), str(seed))
    _commit_version(seed, "2026.10.0", "first")
    _git("push", "-q", "origin", "HEAD:main", cwd=seed)
    local = tmp_path / "murmurent_dev"
    _git("clone", "-q", str(origin), str(local))
    monkeypatch.setattr(MM, "install_root", lambda: local)
    return seed, local


def test_banner_words_between_releases(dev_pair):
    """#185 follow-up: name the copy and the changes, not just commit codes."""
    seed, _ = dev_pair
    _commit_version(seed, "2026.10.0", "Fix the Space page")
    _git("push", "-q", "origin", "HEAD:main", cwd=seed)
    s = MM.check_update(fetch=True)
    assert s.name == "murmurent_dev" and s.behind == 1
    assert s.current_version == s.latest_version == "2026.10.0"
    assert s.changes == ["Fix the Space page"]


def test_banner_words_for_a_new_release(dev_pair):
    seed, _ = dev_pair
    _commit_version(seed, "2026.10.1", "Release 2026.10.1")
    _git("push", "-q", "origin", "HEAD:main", cwd=seed)
    s = MM.check_update(fetch=True)
    assert (s.current_version, s.latest_version) == ("2026.10.0", "2026.10.1")

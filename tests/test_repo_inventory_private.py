"""Tests for private-repo exclusions in :mod:`murmurent.core.repo_inventory`.

``~/repos`` is where everything lives, personal work included, and the
scan takes every git repo it finds there. Marking a repo **private**
keeps it out of the inventory entirely — not hidden in the UI, but never
recorded: the point is that a private clone's path and origin URL stop
being written to disk at all.

Covered here:
  - pattern matching on basename and on full path (including ``~``),
  - the scan dropping excluded clones before a row is built,
  - the cache purge scrubbing rows from reports already written,
  - fail-open-but-loud on a malformed exclude file — a typo must not
    take the Repos panel down, but it must not silently un-hide a
    private repo either.

``EXCLUDE_FILE``/``INVENTORY_DIR`` are module-level Paths, so each test
redirects them at a tmp_path rather than touching the real
``~/.murmurent``.
"""

from __future__ import annotations

import pytest
import yaml

from murmurent.core import repo_inventory as inv


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Point the module's inventory dir + exclude file at a tmp dir."""
    d = tmp_path / "inventory"
    d.mkdir()
    monkeypatch.setattr(inv, "INVENTORY_DIR", d)
    monkeypatch.setattr(inv, "EXCLUDE_FILE", d / "exclude.yaml")
    return d


# --- matching --------------------------------------------------------------

@pytest.mark.parametrize("path,expected", [
    ("/home/u/repos/cmwim_website", True),    # basename match
    ("cmwim_website", True),                  # bare name match
    ("/home/u/repos/cmwim_website_v2", False),  # not a prefix match
    ("/home/u/repos/dcis_calculator", False),
    ("/home/u/repos/scratch_foo", True),      # glob on basename
])
def test_is_excluded_matches_basename(path, expected):
    pats = ("cmwim_website", "scratch_*")
    assert inv.is_excluded(path, pats) is expected


def test_is_excluded_matches_full_path_with_home_expansion(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert inv.is_excluded(str(tmp_path / "personal" / "diary"), ("~/personal/*",))
    assert not inv.is_excluded(str(tmp_path / "repos" / "diary"), ("~/personal/*",))


def test_no_patterns_excludes_nothing():
    assert inv.is_excluded("/anything/at/all", ()) is False


# --- load / add / remove ---------------------------------------------------

def test_load_exclusions_missing_file_is_empty(sandbox):
    assert inv.load_exclusions() == ()
    assert inv.exclusions_error() is None


def test_add_then_remove_round_trip(sandbox):
    inv.add_exclusion("cmwim_website")
    assert "cmwim_website" in inv.load_exclusions()
    inv.remove_exclusion("cmwim_website")
    assert inv.load_exclusions() == ()


def test_add_is_idempotent(sandbox):
    inv.add_exclusion("x")
    inv.add_exclusion("x")
    assert list(inv.load_exclusions()).count("x") == 1


def test_add_rejects_empty_pattern(sandbox):
    with pytest.raises(ValueError):
        inv.add_exclusion("   ")


def test_bare_list_format_is_accepted(sandbox):
    """Hand-edited files may be a bare list rather than a patterns: map."""
    inv.EXCLUDE_FILE.write_text("- one\n- two\n", encoding="utf-8")
    assert set(inv.load_exclusions()) == {"one", "two"}


# --- fail open, but loudly -------------------------------------------------

def test_malformed_file_fails_open_but_reports(sandbox):
    inv.EXCLUDE_FILE.write_text("patterns: [unclosed\n  - :: bad\n", encoding="utf-8")
    assert inv.load_exclusions() == ()          # open: scan still works
    err = inv.exclusions_error()
    assert err and "NOT being hidden" in err    # loud: user is told


def test_wrong_shape_file_reports(sandbox):
    inv.EXCLUDE_FILE.write_text("patterns: 42\n", encoding="utf-8")
    assert inv.load_exclusions() == ()
    assert "expected a list" in (inv.exclusions_error() or "")


# --- the scan drops excluded clones ---------------------------------------

def test_scan_drops_excluded_clone(sandbox, monkeypatch):
    """An excluded clone never becomes a RepoOnHost, so its path and
    origin URL never reach the report."""
    inv.add_exclusion("cmwim_website")

    scan_output = (
        "/home/u/repos/cmwim_website|https://github.com/cmwim/website.git|0|0|1\n"
        "/home/u/repos/dcis_calculator|https://github.com/x/dcis.git|1|1|1\n"
    )

    class _Res:
        ok, stdout, stderr, returncode = True, scan_output, "", 0

    monkeypatch.setattr(inv._hosts, "resolve",
                        lambda n: inv._hosts.Host(name="local", kind="local"))
    monkeypatch.setattr(inv._remote, "Remote",
                        lambda host: type("R", (), {"run": lambda *a, **k: _Res()})())

    repos, err = inv.list_machine_repos("local")
    assert err is None
    paths = [r.path for r in repos]
    assert paths == ["/home/u/repos/dcis_calculator"]


# --- the purge scrubs reports already on disk ------------------------------

def _write_report(path, rows):
    path.write_text(yaml.safe_dump({"rows": rows}, sort_keys=False), encoding="utf-8")


def test_purge_drops_row_whose_clones_are_all_private(sandbox):
    rpt = sandbox / "inventory_2026-01-01T000000.yaml"
    _write_report(rpt, [
        {"name": "cmwim_website",
         "clones": [{"host": "local", "path": "/home/u/repos/cmwim_website"}]},
        {"name": "dcis_calculator",
         "clones": [{"host": "local", "path": "/home/u/repos/dcis_calculator"}]},
    ])
    inv.add_exclusion("cmwim_website")
    assert inv.purge_excluded_from_cache() == 1
    data = yaml.safe_load(rpt.read_text(encoding="utf-8"))
    assert [r["name"] for r in data["rows"]] == ["dcis_calculator"]
    assert "cmwim" not in rpt.read_text(encoding="utf-8")


def test_purge_keeps_row_but_drops_the_private_clone(sandbox):
    """A repo cloned twice — one copy under a private tree — keeps the row
    and loses only the private path."""
    rpt = sandbox / "inventory_2026-01-01T000000.yaml"
    _write_report(rpt, [
        {"name": "shared", "clones": [
            {"host": "local", "path": "/home/u/repos/shared"},
            {"host": "local", "path": "/home/u/private/shared"},
        ]},
    ])
    inv.add_exclusion("/home/u/private/*")
    assert inv.purge_excluded_from_cache() == 0     # row survives
    data = yaml.safe_load(rpt.read_text(encoding="utf-8"))
    assert [c["path"] for c in data["rows"][0]["clones"]] == ["/home/u/repos/shared"]


def test_purge_is_a_noop_without_patterns(sandbox):
    rpt = sandbox / "inventory_2026-01-01T000000.yaml"
    _write_report(rpt, [{"name": "a", "clones": []}])
    before = rpt.read_text(encoding="utf-8")
    assert inv.purge_excluded_from_cache() == 0
    assert rpt.read_text(encoding="utf-8") == before


# --- permissions -----------------------------------------------------------

def _mode(path):
    return path.stat().st_mode & 0o777


def test_exclude_file_is_owner_only(sandbox):
    """The exclude file NAMES the repos being hidden — it must not sit at
    the umask default, which on a shared server is readable by every
    account on the box."""
    inv.add_exclusion("cmwim_website")
    assert _mode(inv.EXCLUDE_FILE) == 0o600


def test_reports_are_owner_only(sandbox):
    """A report lists every repo path on the machine."""
    rep = inv.InventoryReport(
        generated_at="2026-01-01T00:00:00+00:00",
        github_org="", hosts_scanned=[], rows=[], errors=[],
    )
    path = inv.write_report(rep)
    assert _mode(path) == 0o600
    assert _mode(inv.INVENTORY_DIR) == 0o700


def test_pre_existing_loose_files_are_tightened(sandbox):
    """A data root created before this hardening stops being world-readable
    on the next write, rather than staying 0644 forever."""
    stale = sandbox / "inventory_2026-01-01T000000.yaml"
    stale.write_text("rows: []\n", encoding="utf-8")
    stale.chmod(0o644)
    sandbox.chmod(0o755)
    inv.add_exclusion("anything")           # any write triggers the sweep
    assert _mode(stale) == 0o600
    assert _mode(sandbox) == 0o700


def test_purge_rewrite_keeps_owner_only(sandbox):
    rpt = sandbox / "inventory_2026-01-01T000000.yaml"
    _write_report(rpt, [
        {"name": "priv", "clones": [{"host": "local", "path": "/h/repos/priv"}]},
        {"name": "keep", "clones": [{"host": "local", "path": "/h/repos/keep"}]},
    ])
    rpt.chmod(0o644)
    inv.add_exclusion("priv")
    inv.purge_excluded_from_cache()
    assert _mode(rpt) == 0o600

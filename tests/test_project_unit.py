"""
Purpose: tests for issue #151, step 0, "everything is a project": the new
         project-record fields, last_used and activity, adopt making a
         one-repository project, `murmurent project migrate` and
         `murmurent project status`.
Author: Mike Hallett (with Claude Code)
Date: 2026-10-16
Input: temporary folders and fake git repositories only. No network, no real
       data root, no real lab records repository.
Output: pass or fail.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from murmurent.cli import cli
from murmurent.core import cert_projects as cp
from murmurent.core import project_migrate as pm
from murmurent.core import project_unit as pu
from murmurent.core import repo_inventory as inv

UTC = dt.timezone.utc


@pytest.fixture
def world(monkeypatch, tmp_path):
    """A repositories folder, a data root, a lab records folder and a commons,
    all under tmp_path. The conftest already isolates MURMURENT_HOME,
    MURMURENT_REPOS_ROOT and MURMURENT_LAB_MGMT_REPO; this pins them here."""
    repos = tmp_path / "repos"
    data = tmp_path / "data"
    lab_mgmt = tmp_path / "lab_mgmt"
    home = tmp_path / "mm_home"
    commons = tmp_path / "commons"
    for d in (repos, data / "immutable", data / "append_only", lab_mgmt, home,
              commons / "agents"):
        d.mkdir(parents=True)
    monkeypatch.setenv("MURMURENT_REPOS_ROOT", str(repos))
    monkeypatch.setenv("MURMURENT_DATA_ROOT", str(data))
    monkeypatch.delenv("MURMURENT_LAB_VM_ROOT", raising=False)
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(lab_mgmt))
    monkeypatch.setenv("MURMURENT_HOME", str(home))
    monkeypatch.setenv("MURMURENT_USER", "tester")
    monkeypatch.setenv("MURMURENT_COMMONS_ROOT", str(commons))
    monkeypatch.setenv("MURMURENT_HOSTS_FILE", str(tmp_path / "hosts.yaml"))
    monkeypatch.setattr(inv, "EXCLUDE_FILE", tmp_path / "exclude.yaml")
    return {"repos": repos, "data": data, "lab_mgmt": lab_mgmt, "home": home,
            "tmp": tmp_path}


def git_repo(path: Path, *, when: str | None = None) -> Path:
    """A git repository at ``path``, with one commit dated ``when`` if given."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    if when:
        (path / "README.md").write_text("hello\n")
        env = {**os.environ, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
        subprocess.run(["git", "-C", str(path), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@x",
                        "commit", "-q", "-m", "first"], check=True, env=env)
    return path


def record_text(world, name: str) -> str:
    return (world["lab_mgmt"] / "cert_projects" / f"{name}.md").read_text()


def snapshot(folder: Path) -> dict[str, bytes]:
    """Every file under ``folder`` and its contents, to show nothing moved."""
    return {str(p.relative_to(folder)): p.read_bytes()
            for p in sorted(folder.rglob("*")) if p.is_file() and ".git" not in p.parts}


# ---------------------------------------------------------------------------
# 1. The new record fields
# ---------------------------------------------------------------------------


def test_new_fields_round_trip(world):
    cp.upsert("brca", lab="mh", data_folders=["append_only/brca", "/elsewhere/brca"],
              reads_from=["append_only/shared_cohort", "dcis_calculator"],
              retain_until="2031-06-30")
    got = cp.get("brca")
    assert got.data_folders == ("append_only/brca", "/elsewhere/brca")
    assert got.reads_from == ("append_only/shared_cohort", "dcis_calculator")
    assert got.retain_until == "2031-06-30"
    d = got.to_dict()
    assert d["data_folders"] == ["append_only/brca", "/elsewhere/brca"]
    assert d["reads_from"] == ["append_only/shared_cohort", "dcis_calculator"]
    assert d["retain_until"] == "2031-06-30"
    meta = yaml.safe_load(record_text(world, "brca").split("---")[1])
    assert meta["retain_until"] == "2031-06-30"


def test_upsert_keeps_new_fields_unless_given_and_can_clear_them(world):
    cp.upsert("brca", lab="mh", data_folders=["append_only/brca"],
              reads_from=["dcis_calculator"], retain_until="2031-06-30")
    cp.upsert("brca", lab="mh", member="@ann")          # a membership-only upsert
    got = cp.get("brca")
    assert got.data_folders == ("append_only/brca",)
    assert got.reads_from == ("dcis_calculator",)
    assert got.retain_until == "2031-06-30"
    cp.upsert("brca", lab="mh", data_folders=[], reads_from=[], retain_until="")
    got = cp.get("brca")
    assert (got.data_folders, got.reads_from, got.retain_until) == ((), (), "")


def test_old_record_without_new_fields_loads_and_rewrites_unchanged(world):
    reg = world["lab_mgmt"] / "cert_projects"
    reg.mkdir()
    old = ("---\nproject: oldie\nlab: mh\nstatus: active\ncreated: '2026-01-01'\n"
           "lead: '@ann'\nsensitivity: standard\nmembers:\n- '@ann'\ncerts: []\n---\n\n# oldie\n")
    (reg / "oldie.md").write_text(old)
    got = cp.get("oldie")
    assert (got.data_folders, got.reads_from, got.retain_until) == ((), (), "")
    cp.set_status("oldie", "active")                   # rewrites the file
    text = record_text(world, "oldie")
    for key in ("data_folders", "reads_from", "retain_until"):
        assert key not in text


def test_hand_written_values_are_read_sensibly(world):
    reg = world["lab_mgmt"] / "cert_projects"
    reg.mkdir()
    (reg / "hand.md").write_text(
        "---\nproject: hand\nlab: mh\nretain_until: 2030-01-01\n"
        "data_folders: append_only/hand\nreads_from: [dcis_calculator, dcis_calculator]\n"
        "members: []\n---\n")
    got = cp.get("hand")
    assert got.retain_until == "2030-01-01"            # an unquoted YAML date
    assert got.data_folders == ("append_only/hand",)   # one string is a list of one
    assert got.reads_from == ("dcis_calculator",)       # repeats dropped


def test_validate_rejects_a_retain_until_that_is_not_a_date(world):
    good = cp.CertProject(name="a", lab="mh", retain_until="2030-01-01")
    cp.validate_project(good)
    with pytest.raises(cp.CertProjectValidationError, match="retain_until"):
        cp.validate_project(cp.CertProject(name="a", lab="mh", retain_until="next spring"))


def test_status_field_is_untouched_and_members_keep_access(world):
    """Activity is separate from status: a dormant project keeps status
    'active', so membership lookups (which filter on it) still find it."""
    old = git_repo(world["repos"] / "ancient", when="2020-01-01T12:00:00+00:00")
    cp.upsert("ancient", lab="mh", member="@ann",
              repos=[cp.RepoRef(name="ancient", path=str(old))])
    got = cp.get("ancient")
    assert pu.activity(got) == pu.DORMANT
    assert got.status == "active"
    assert [p.name for p in cp.projects_for_member("@ann")] == ["ancient"]
    assert "dormant" not in record_text(world, "ancient")


# ---------------------------------------------------------------------------
# 2. Data folders, reads_from, retain_until
# ---------------------------------------------------------------------------


def test_effective_data_folders_default_and_named(world):
    data = world["data"]
    plain = cp.CertProject(name="x_y", lab="mh")
    assert pu.effective_data_folders(plain) == [data / "immutable" / "x_y",
                                                data / "append_only" / "x_y"]
    named = cp.CertProject(name="x_y", lab="mh",
                           data_folders=("append_only/x_y/run_2", "/srv/other/x"))
    assert pu.effective_data_folders(named) == [data / "append_only" / "x_y" / "run_2",
                                                Path("/srv/other/x")]


def test_reads_from_splits_folders_and_repositories(world):
    p = cp.CertProject(name="x", lab="mh",
                       reads_from=("append_only/bc_dcis", "/srv/shared", "dcis_calculator"))
    reads = pu.resolve_reads_from(p)
    assert reads.folders == (world["data"] / "append_only" / "bc_dcis", Path("/srv/shared"))
    assert reads.repos == ("dcis_calculator",)


@pytest.mark.parametrize("value, today, blocked", [
    ("", dt.date(2026, 1, 1), False),
    ("2030-01-01", dt.date(2029, 12, 31), True),
    ("2030-01-01", dt.date(2030, 1, 1), False),
    ("not a date", dt.date(2026, 1, 1), True),       # a typing mistake keeps data
])
def test_retention_blocks_deletion(value, today, blocked):
    p = cp.CertProject(name="x", lab="mh", retain_until=value)
    assert pu.retention_blocks_deletion(p, today) is blocked


# ---------------------------------------------------------------------------
# 3. last_used and activity
# ---------------------------------------------------------------------------


def _project_with_repo(world, name: str, when: str) -> cp.CertProject:
    path = git_repo(world["repos"] / name, when=when)
    cp.upsert(name, lab="mh", repos=[cp.RepoRef(name=name, path=str(path))])
    return cp.get(name)


def test_last_used_from_the_newest_commit(world):
    p = _project_with_repo(world, "brca", "2026-03-04T10:00:00+00:00")
    last = pu.last_used(p)
    assert last.source == "commit"
    assert last.when == dt.datetime(2026, 3, 4, 10, tzinfo=UTC)
    assert "brca" in last.detail


def test_last_used_takes_the_newest_repository(world):
    a = git_repo(world["repos"] / "brca", when="2025-01-01T00:00:00+00:00")
    b = git_repo(world["repos"] / "brca_manuscript", when="2026-02-01T00:00:00+00:00")
    git_repo(world["repos"] / "missing_here")           # no commits: no evidence
    cp.upsert("brca", lab="mh", repos=[
        cp.RepoRef(name="brca", path=str(a)),
        cp.RepoRef(name="brca_manuscript", role="manuscript", path=str(b)),
        cp.RepoRef(name="elsewhere", host="lab-server", remote_path="/srv/elsewhere")])
    last = pu.last_used(cp.get("brca"))
    assert last.when.date() == dt.date(2026, 2, 1)
    assert "brca_manuscript" in last.detail


def test_job_records_count_and_bad_ones_are_ignored(world):
    p = _project_with_repo(world, "brca", "2025-01-01T00:00:00+00:00")
    runs = world["home"] / "runs"
    runs.mkdir()
    (runs / "a.json").write_text(json.dumps(
        {"project": "brca", "started_at": "2026-05-01T08:00:00Z",
         "ended_at": "2026-05-02T09:30:00Z"}))
    (runs / "b.json").write_text(json.dumps(
        {"project": "other", "ended_at": "2026-09-01T00:00:00Z"}))   # another project
    (runs / "c.json").write_text("{not json")
    (runs / "d.json").write_text(json.dumps(["a", "list"]))
    (runs / "e.json").write_text(json.dumps({"project": "brca", "ended_at": "soon"}))
    last = pu.last_used(p)
    assert last.source == "job"
    assert last.when == dt.datetime(2026, 5, 2, 9, 30, tzinfo=UTC)


def test_a_running_job_counts_from_its_start(world):
    runs = world["home"] / "runs"
    runs.mkdir()
    (runs / "live.json").write_text(json.dumps({"project": "brca", "started_at": 1767225600}))
    found = pu.job_card_evidence("brca")
    assert found and found[0].when == dt.datetime(2026, 1, 1, tzinfo=UTC)


def test_no_job_folder_means_no_job_evidence(world):
    assert pu.job_card_evidence("brca") == []


def test_data_scan_record_is_read_and_folders_are_never_walked(world):
    p = _project_with_repo(world, "brca", "2025-01-01T00:00:00+00:00")
    folder = world["data"] / "append_only" / "brca" / "exp_01"
    folder.mkdir(parents=True)
    (folder / "new_today.csv").write_text("1\n")        # a fresh file, but no record
    assert pu.data_change_evidence(p) == []             # so nothing is found
    cache = world["home"] / "space" / "data_dates.json"
    cache.parent.mkdir()
    cache.write_text(json.dumps({"schema": 1, "folders": {
        str(folder): {"newest_change": "2026-07-01T00:00:00+00:00",
                      "scanned_at": "2026-07-02T00:00:00+00:00"},
        str(world["data"] / "append_only" / "other"): {"newest_change": "2026-10-01T00:00:00Z"},
    }}))
    last = pu.last_used(p)
    assert last.source == "data"
    assert last.when.date() == dt.date(2026, 7, 1)


def test_activity_thresholds(world):
    now = dt.datetime(2026, 10, 16, tzinfo=UTC)

    def ev(y, m, d):
        return pu.UsageEvidence(when=dt.datetime(y, m, d, tzinfo=UTC), source="commit", detail="")
    assert pu.activity_for(ev(2026, 9, 1), now=now) == pu.ACTIVE
    assert pu.activity_for(ev(2025, 10, 17), now=now) == pu.ACTIVE    # not quite 12 months
    assert pu.activity_for(ev(2025, 10, 16), now=now) == pu.QUIET
    assert pu.activity_for(ev(2024, 10, 17), now=now) == pu.QUIET
    assert pu.activity_for(ev(2024, 10, 16), now=now) == pu.DORMANT
    assert pu.activity_for(None, now=now) == pu.UNKNOWN


def test_activity_unknown_without_any_evidence(world):
    p = cp.CertProject(name="nowhere", lab="mh",
                       repos=(cp.RepoRef(name="nowhere", path=str(world["repos"] / "nowhere")),))
    assert pu.last_used(p) is None
    assert pu.activity(p) == pu.UNKNOWN


def test_policy_file_sets_thresholds_and_nonsense_falls_back(world):
    # The thresholds come from the millwright's policy file (one file for the
    # lab's numbers), policy/millwright.yaml in the lab records repository.
    from murmurent.core import millwright_policy as mp
    policy = world["lab_mgmt"] / mp.POLICY_RELATIVE_PATH
    policy.parent.mkdir(parents=True, exist_ok=True)
    assert pu.load_activity_policy() == pu.ActivityPolicy(12, 24)
    policy.write_text("project_quiet_months: 6\nproject_dormant_months: 18\n")
    assert pu.load_activity_policy() == pu.ActivityPolicy(6, 18)
    policy.write_text("project_quiet_months: 30\nproject_dormant_months: 18\n")
    assert pu.load_activity_policy() == pu.ActivityPolicy(12, 24)
    policy.write_text(": not yaml : [")
    assert pu.load_activity_policy() == pu.ActivityPolicy(12, 24)


def test_months_between():
    assert pu.months_between(dt.date(2026, 1, 31), dt.date(2026, 2, 28)) == 0
    assert pu.months_between(dt.date(2026, 1, 15), dt.date(2026, 2, 15)) == 1
    assert pu.months_between(dt.date(2027, 1, 1), dt.date(2026, 1, 1)) == 0


# ---------------------------------------------------------------------------
# 4. Every repository becomes a project: `repo adopt`
# ---------------------------------------------------------------------------


def _adopt(path: Path):
    return CliRunner().invoke(cli, ["repo", "adopt", str(path), "--lab", "mh"])


def test_adopt_makes_a_one_repository_project(world):
    repo = git_repo(world["repos"] / "brca_wgs")
    res = _adopt(repo)
    assert res.exit_code == 0, res.output
    assert "made project brca_wgs" in res.output
    got = cp.get("brca_wgs")
    assert [(r.name, r.role) for r in got.repos] == [("brca_wgs", "code")]
    assert got.lead == "@tester" and got.members == ("@tester",)
    assert got.lab == "mh" and got.status == "active"
    assert not (repo / "CHARTER.md").exists()           # a record, not a charter


def test_readopting_changes_nothing(world):
    repo = git_repo(world["repos"] / "brca_wgs")
    assert _adopt(repo).exit_code == 0
    before = record_text(world, "brca_wgs")
    res = _adopt(repo)
    assert res.exit_code == 0, res.output
    assert "already part of project brca_wgs" in res.output
    assert record_text(world, "brca_wgs") == before


def test_adopt_never_changes_an_existing_project(world):
    cp.upsert("brca", lab="mh", lead="@pi", member="@ann", sensitivity="restricted",
              repos=[cp.RepoRef(name="brca_code", path="")])
    before = record_text(world, "brca")
    repo = git_repo(world["repos"] / "brca")
    res = _adopt(repo)
    assert res.exit_code == 0, res.output              # the repository is still made ready
    assert (repo / ".murmurent.yaml").is_file()
    assert "project brca exists and does not list brca" in res.output
    assert "murmurent project migrate" in res.output
    assert record_text(world, "brca") == before


def test_adopt_sibling_of_an_existing_project_is_not_split_off(world):
    cp.upsert("brca", lab="mh", repos=[cp.RepoRef(name="brca", path="")])
    before = record_text(world, "brca")
    res = _adopt(git_repo(world["repos"] / "brca_manuscript"))
    assert res.exit_code == 0, res.output
    assert cp.get("brca_manuscript") is None             # no project of its own
    assert record_text(world, "brca") == before          # and brca unchanged
    assert "murmurent project migrate" in res.output


def test_adopt_groups_a_sibling_with_its_code_repository(world):
    git_repo(world["repos"] / "brca")                   # here, not yet adopted
    res = _adopt(git_repo(world["repos"] / "brca_seminar"))
    assert res.exit_code == 0, res.output
    got = cp.get("brca")
    assert [(r.name, r.role) for r in got.repos] == [("brca_seminar", "seminar")]


def test_adopt_unrelated_suffix_is_its_own_project(world):
    """`cell_data` is not split into project `cell` when nothing called cell exists."""
    res = _adopt(git_repo(world["repos"] / "cell_data"))
    assert res.exit_code == 0, res.output
    assert cp.get("cell") is None
    assert [(r.name, r.role) for r in cp.get("cell_data").repos] == [("cell_data", "code")]


def test_adopt_records_a_clinical_marker(world):
    repo = git_repo(world["repos"] / "cohort")
    (repo / ".murmurent.yaml").write_text("murmurent: 1\nlab: mh\nsensitivity: clinical\n")
    assert _adopt(repo).exit_code == 0
    assert cp.get("cohort").sensitivity == "clinical"


def test_adopt_in_a_project_folder_joins_that_project(world):
    git_repo(world["repos"] / "dcis" / "dcis")
    res = _adopt(git_repo(world["repos"] / "dcis" / "dcis_manuscript"))
    assert res.exit_code == 0, res.output
    assert [(r.name, r.role) for r in cp.get("dcis").repos] == [("dcis_manuscript", "manuscript")]


def test_adopt_in_a_project_folder_through_a_linked_repositories_folder(world, monkeypatch):
    """The repositories folder is often a link to a bigger drive, and adopt
    hands over the resolved path; the project folder must still be found."""
    real = world["tmp"] / "big_drive" / "repos"
    real.mkdir(parents=True)
    link = world["tmp"] / "linked_repos"
    link.symlink_to(real)
    monkeypatch.setenv("MURMURENT_REPOS_ROOT", str(link))
    res = _adopt(git_repo(link / "dcis" / "pathology_notes"))
    assert res.exit_code == 0, res.output
    assert cp.get("pathology_notes") is None
    assert [(r.name, r.role) for r in cp.get("dcis").repos] == [("pathology_notes", "code")]


def test_joining_a_bigger_project_archives_the_placeholder(world):
    """One owning project per repository: when an adopted repository is added
    to another project, its one-repository project is archived, not deleted."""
    repo = git_repo(world["repos"] / "brca_code")
    assert _adopt(repo).exit_code == 0
    cp.upsert("brca_17", lab="mh", lead="@pi")
    cp.add_repo("brca_17", repo_name="brca_code", path=str(repo))
    placeholder = cp.get("brca_code")
    assert placeholder is not None and placeholder.status == "archived"
    assert pu.owning_project("brca_code").name == "brca_17"


def test_a_real_project_is_not_archived_when_its_repository_is_shared(world):
    cp.upsert("brca_code", lab="mh", slack_channel_id="C123",
              repos=[cp.RepoRef(name="brca_code", path="")])
    cp.upsert("brca_17", lab="mh")
    cp.add_repo("brca_17", repo_name="brca_code", path="")
    assert cp.get("brca_code").status == "active"


def test_owning_project_prefers_an_active_record(world):
    cp.upsert("a_old", lab="mh", status="archived", repos=[cp.RepoRef(name="shared")])
    cp.upsert("b_new", lab="mh", repos=[cp.RepoRef(name="shared")])
    assert pu.owning_project("SHARED").name == "b_new"
    assert pu.owning_project("nothing_lists_this") is None


def test_project_name_for_cwd_uses_the_owning_project(world):
    repo = git_repo(world["repos"] / "brca_manuscript")
    (repo / ".murmurent.yaml").write_text("murmurent: 1\n")
    cp.upsert("brca", lab="mh",
              repos=[cp.RepoRef(name="brca_manuscript", role="manuscript", path=str(repo))])
    assert cp.project_name_for_cwd(repo) == "brca"


# ---------------------------------------------------------------------------
# 5. `murmurent project migrate`
# ---------------------------------------------------------------------------


@pytest.fixture
def machine(world):
    """A machine with a mix of claimed and unclaimed repositories and data."""
    r = world["repos"]
    git_repo(r / "brca", when="2026-01-01T00:00:00+00:00")
    git_repo(r / "brca_manuscript")
    git_repo(r / "brca_seminar")
    git_repo(r / "atlas")
    git_repo(r / "atlas_seminar")
    git_repo(r / "cell_data")
    git_repo(r / "dcis" / "dcis")
    git_repo(r / "dcis" / "dcis_manuscript")
    git_repo(r / "murmurent_dev")
    git_repo(r / "personal_notes")
    labrec = git_repo(r / "lab_records")
    (labrec / "lab.md").write_text("---\nlab: mh\n---\n")
    (labrec / "members").mkdir()
    (r / "plain_folder").mkdir()                         # not git: not a repository
    inv.EXCLUDE_FILE.write_text("patterns: [personal_notes]\n")
    cp.upsert("atlas", lab="mh", lead="@pi", member="@ann", sensitivity="clinical",
              reb_number="1", reb_expires="2030-01-01", data_residency="ca",
              repos=[cp.RepoRef(name="atlas", path=str(r / "atlas"))])
    d = world["data"]
    for folder in ("immutable/brca", "append_only/brca", "append_only/atlas",
                   "immutable/old_cohort", "append_only/cell_data"):
        (d / folder).mkdir(parents=True)
        (d / folder / "keep.txt").write_text(folder)
    return world


def test_migrate_dry_run_lists_and_writes_nothing(machine):
    before_records = snapshot(machine["lab_mgmt"])
    before_repos = snapshot(machine["repos"])
    before_data = snapshot(machine["data"])
    res = CliRunner().invoke(cli, ["project", "migrate"])
    assert res.exit_code == 0, res.output
    out = res.output
    assert "Nothing was written" in out
    for name in ("brca_manuscript", "brca_seminar", "atlas_seminar", "cell_data",
                 "dcis_manuscript"):
        assert name in out
    assert "added to the existing project" in out
    assert "immutable/old_cohort" in out and "stays listed as unclaimed" in out
    assert "append_only/brca" in out and "claimed by the new project brca" in out
    assert "append_only/atlas" not in out             # already claimed by default
    assert "murmurent's own repository" in out
    assert "marked private" in out
    assert "lab records repository" in out
    assert "plain_folder" not in out
    assert snapshot(machine["lab_mgmt"]) == before_records
    assert snapshot(machine["repos"]) == before_repos
    assert snapshot(machine["data"]) == before_data


def test_migrate_plan_groups_by_name_and_folder(machine):
    plan = pm.plan()
    got = {p.name: (p.action, sorted((r.name, r.role) for r in p.repos))
           for p in plan.proposals}
    assert got == {
        "brca": ("new", [("brca", "code"), ("brca_manuscript", "manuscript"),
                         ("brca_seminar", "seminar")]),
        "cell_data": ("new", [("cell_data", "code")]),
        "dcis": ("new", [("dcis", "code"), ("dcis_manuscript", "manuscript")]),
        "atlas": ("add", [("atlas_seminar", "seminar")]),
    }
    assert all(p.lead == "tester" for p in plan.new_projects)
    unclaimed = {str(f.path.relative_to(machine["data"])): f.project for f in plan.folders}
    assert unclaimed == {"immutable/brca": "brca", "append_only/brca": "brca",
                         "immutable/old_cohort": "", "append_only/cell_data": "cell_data"}


def test_migrate_apply_asks_first_and_no_means_nothing(machine):
    before = snapshot(machine["lab_mgmt"])
    res = CliRunner().invoke(cli, ["project", "migrate", "--apply"], input="n\n")
    assert res.exit_code == 0, res.output
    assert "Write these project records now?" in res.output
    assert "Nothing was written" in res.output
    assert snapshot(machine["lab_mgmt"]) == before


def test_migrate_apply_writes_records_and_moves_nothing(machine):
    atlas_before = cp.get("atlas")
    before_repos = snapshot(machine["repos"])
    before_data = snapshot(machine["data"])
    res = CliRunner().invoke(cli, ["project", "migrate", "--apply"], input="y\n")
    assert res.exit_code == 0, res.output
    assert "wrote project brca" in res.output
    brca = cp.get("brca")
    assert sorted((r.name, r.role) for r in brca.repos) == [
        ("brca", "code"), ("brca_manuscript", "manuscript"), ("brca_seminar", "seminar")]
    assert brca.lead == "@tester" and brca.members == ("@tester",)
    atlas = cp.get("atlas")
    assert sorted(r.name for r in atlas.repos) == ["atlas", "atlas_seminar"]
    # Everything else about the existing project is exactly as it was.
    for key in ("lead", "members", "sensitivity", "reb_number", "lab", "status", "created"):
        assert getattr(atlas, key) == getattr(atlas_before, key)
    assert snapshot(machine["repos"]) == before_repos
    assert snapshot(machine["data"]) == before_data
    # A second run finds only what is still unclaimed: the folder no one owns.
    plan = pm.plan()
    assert not plan.has_writes()
    assert [str(f.path.relative_to(machine["data"])) for f in plan.folders] == [
        "immutable/old_cohort"]


def test_migrate_yes_skips_the_question(machine):
    res = CliRunner().invoke(cli, ["project", "migrate", "--apply", "--yes"])
    assert res.exit_code == 0, res.output
    assert "Write these project records now?" not in res.output
    assert cp.get("dcis") is not None


def test_migrate_apply_leaves_a_project_that_appeared_meanwhile(machine):
    plan = pm.plan()
    cp.upsert("brca", lab="other", lead="@someone_else")   # appears before apply
    before = record_text(machine, "brca")
    lines = pm.apply(plan)
    assert any("skipped brca" in line for line in lines)
    assert record_text(machine, "brca") == before


def test_migrate_with_no_data_root(world, monkeypatch):
    monkeypatch.setenv("MURMURENT_DATA_ROOT", str(world["tmp"] / "no_such_data"))
    git_repo(world["repos"] / "solo")
    res = CliRunner().invoke(cli, ["project", "migrate"])
    assert res.exit_code == 0, res.output
    assert "only repositories were checked" in res.output


# ---------------------------------------------------------------------------
# 6. `murmurent project status`
# ---------------------------------------------------------------------------


def test_status_shows_the_project_as_a_unit(world):
    repo = git_repo(world["repos"] / "brca", when="2026-09-30T12:00:00+00:00")
    (world["data"] / "append_only" / "brca").mkdir()
    cp.upsert("brca", lab="mh", lead="@pi",
              repos=[cp.RepoRef(name="brca", path=str(repo)),
                     cp.RepoRef(name="brca_manuscript", role="manuscript", path="")],
              reads_from=["append_only/shared_cohort", "dcis_calculator"],
              retain_until="2099-01-01")
    res = CliRunner().invoke(cli, ["project", "status", "brca"])
    assert res.exit_code == 0, res.output
    out = res.output
    assert "Project brca" in out
    assert "last used 2026-09-30" in out and "newest commit in brca" in out
    assert "quiet after 12 months" in out
    assert "brca_manuscript" in out and "not on this computer" in out
    assert "immutable/brca" in out and "not found" in out
    assert "append_only/brca" in out and "here" in out
    assert "append_only/shared_cohort" in out and "dcis_calculator" in out
    assert "2099-01-01: nothing in this project may be suggested for deletion" in out
    assert "does not record when a file is read" in out


def test_status_from_inside_a_repository(world, monkeypatch):
    repo = git_repo(world["repos"] / "brca_seminar")
    (repo / ".murmurent.yaml").write_text("murmurent: 1\n")
    cp.upsert("brca", lab="mh",
              repos=[cp.RepoRef(name="brca_seminar", role="seminar", path=str(repo))])
    monkeypatch.chdir(repo)
    res = CliRunner().invoke(cli, ["project", "status"])
    assert res.exit_code == 0, res.output
    assert "Project brca" in res.output


def test_status_accepts_a_repository_name(world):
    cp.upsert("brca", lab="mh", repos=[cp.RepoRef(name="brca_seminar", role="seminar")])
    res = CliRunner().invoke(cli, ["project", "status", "brca_seminar"])
    assert res.exit_code == 0, res.output
    assert "Project brca" in res.output
    assert "nothing on this computer shows it being used" in res.output


def test_status_unknown_project(world):
    res = CliRunner().invoke(cli, ["project", "status", "nope"])
    assert res.exit_code != 0
    assert "no project named 'nope'" in res.output

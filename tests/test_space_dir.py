"""
Purpose: The shared space folder (``space_dir``) that lets the weekly scan run
         under a lab service account while the PI reads the table under their
         own login (docs/service_account.md); and the lab-records refresh the
         timers do before a run.
Author:  Mike Hallett (with Claude Code)
Date:    2026-10-31
"""

from __future__ import annotations

from pathlib import Path

import yaml

from murmurent.core import millwright_policy as mp
from murmurent.core import project_unit as pu
from murmurent.core import roster_sync as rs
from murmurent.core import space_lab as sl
from murmurent.core import space_schedule as sch
from murmurent.core import space_table as st


def _lab_policy(tmp_path, monkeypatch, **values) -> Path:
    lab_mgmt = tmp_path / "lab_mgmt"
    (lab_mgmt / "policy").mkdir(parents=True)
    path = lab_mgmt / "policy" / "millwright.yaml"
    path.write_text(yaml.safe_dump(values))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(lab_mgmt))
    monkeypatch.delenv(mp.POLICY_ENV, raising=False)
    return path


def test_default_is_the_accounts_own_space_folder(monkeypatch, tmp_path):
    monkeypatch.delenv(pu.SPACE_DIR_ENV, raising=False)
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "home"))
    assert pu.space_dir() == tmp_path / "home" / "space"
    assert sl.report_path() == tmp_path / "home" / "space" / sl.REPORT_FILENAME
    assert st.table_path() == tmp_path / "home" / "space" / st.TABLE_FILENAME
    assert pu.data_dates_path() == tmp_path / "home" / "space" / pu.DATA_DATES_FILENAME


def test_policy_names_a_shared_folder(monkeypatch, tmp_path):
    monkeypatch.delenv(pu.SPACE_DIR_ENV, raising=False)
    _lab_policy(tmp_path, monkeypatch, space_dir="/var/lib/murmurent/space")
    assert mp.load_policy().space_dir == "/var/lib/murmurent/space"
    assert pu.space_dir() == Path("/var/lib/murmurent/space")
    assert st.table_path() == Path("/var/lib/murmurent/space") / st.TABLE_FILENAME


def test_environment_wins_over_policy(monkeypatch, tmp_path):
    _lab_policy(tmp_path, monkeypatch, space_dir="/var/lib/murmurent/space")
    monkeypatch.setenv(pu.SPACE_DIR_ENV, str(tmp_path / "elsewhere"))
    assert pu.space_dir() == tmp_path / "elsewhere"


def test_the_timer_carries_the_folder_and_records_it(monkeypatch, tmp_path):
    monkeypatch.setenv(pu.SPACE_DIR_ENV, str(tmp_path / "shared"))
    service = sch.service_text()
    assert f"Environment=MURMURENT_SPACE_DIR={tmp_path / 'shared'}" in service
    _lab_policy(tmp_path, monkeypatch)
    recorded = sch.record("Sun *-*-* 02:00:00")
    text = recorded.read_text()
    assert str(tmp_path / "shared") in text
    assert "~/.murmurent/space" not in text


def test_record_writes_the_home_folder_with_a_tilde(monkeypatch, tmp_path):
    monkeypatch.delenv(pu.SPACE_DIR_ENV, raising=False)
    monkeypatch.setenv("MURMURENT_HOME", str(Path.home() / ".murmurent"))
    _lab_policy(tmp_path, monkeypatch)
    assert "`~/.murmurent/space`" in sch.record("Sun *-*-* 02:00:00").read_text()


def test_refresh_note_is_silent_without_a_clone(monkeypatch, tmp_path):
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(tmp_path / "plain_folder"))
    (tmp_path / "plain_folder").mkdir()
    assert rs.refresh_note() == ""


def test_refresh_note_reports_a_failed_pull_without_raising(monkeypatch):
    def failing():
        return rs.RosterSyncResult(path="x", is_git=True, ok=False, detail="diverged")
    monkeypatch.setattr(rs, "pull_lab_mgmt", failing)
    assert rs.refresh_note() == "lab records not refreshed: diverged"

    def exploding():
        raise OSError("no git")
    monkeypatch.setattr(rs, "pull_lab_mgmt", exploding)
    assert rs.refresh_note() == "lab records not refreshed: no git"


def test_tests_never_touch_the_real_systemd_units():
    """The autouse fixture in conftest: a timer installed by a test lands in a
    temp folder, not in ``~/.config/systemd/user``."""
    assert str(Path.home() / ".config") not in str(sch.unit_dir())

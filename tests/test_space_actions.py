"""Tests for carrying out space-table decisions (#151, step 6)."""

from __future__ import annotations

import gzip
import json

import pytest
import yaml
from click.testing import CliRunner

from murmurent.cli import cli
from murmurent.core import cert_projects as cp
from murmurent.core import space_actions as sa
from murmurent.core import space_table as st
from murmurent.core.millwright_policy import POLICY_ENV, load_policy


@pytest.fixture
def lab(monkeypatch, tmp_path):
    data, backup, home = tmp_path / "data", tmp_path / "backup", tmp_path / "home"
    for d in (data / "append_only" / "brca", data / "immutable" / "brca", backup, home,
              tmp_path / "lab_mgmt"):
        d.mkdir(parents=True)
    policy = tmp_path / "policy.yaml"
    policy.write_text(yaml.safe_dump({"mothball_target": str(backup),
                                      "mothball_target_fill_limit": 0.999}))
    monkeypatch.setenv("MURMURENT_DATA_ROOT", str(data))
    monkeypatch.setenv("MURMURENT_LAB_MGMT_REPO", str(tmp_path / "lab_mgmt"))
    monkeypatch.setenv("MURMURENT_HOME", str(home))
    monkeypatch.setenv("MURMURENT_USER", "tester")
    monkeypatch.setenv(POLICY_ENV, str(policy))
    cp.upsert("brca", lab="mh", lead="@tester", member="tester")
    conn = st.connect()

    def row(rel: str, decision: str, text: str = "ACGT\n" * 1000) -> int:
        path = data / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        item = st.Item(path=str(path), category=st.COMPRESSIBLE, suggestion=decision,
                       reason="r", size=path.stat().st_size)
        st.record_scan(conn, st.ScanSummary(project="brca", started_at=st.now_iso(),
                                            items=[item]), roots=[str(data)])
        rid = next(r["id"] for r in st.rows(conn, "brca", include_settled=True)
                   if r["path"] == str(path))
        st.decide(conn, rid, decision, by="tester")
        return rid

    return {"data": data, "backup": backup, "conn": conn, "row": row, "policy": policy}


def test_mothball_copies_checks_logs_and_keeps_the_original(lab):
    rid = lab["row"]("append_only/brca/01_x/reads.fastq", st.MOTHBALL)
    [p] = sa.plan(lab["conn"])
    assert not p.blocked and p.destination == lab["backup"] / "brca" / "append_only/brca/01_x/reads.fastq"
    result = sa.carry_out(lab["conn"], p, by="tester")
    assert result.status == sa.VERIFIED
    assert p.destination.read_text() == p.source.read_text()
    assert p.source.exists()                                   # never removed
    log = (st.table_path().parent / sa.ACTIONS_LOG).read_text().splitlines()
    assert json.loads(log[-1])["row"] == rid
    may, held = sa.removable(lab["conn"])
    assert [r.row for r in may] == [rid] and not held
    [again] = sa.plan(lab["conn"])
    assert again.blocked == "Already copied and checked."


def test_mothball_needs_a_backup_drive(lab):
    lab["policy"].write_text(yaml.safe_dump({}))
    lab["row"]("append_only/brca/a.csv", st.MOTHBALL)
    [p] = sa.plan(lab["conn"])
    assert "No backup drive" in p.blocked


def test_compress_writes_a_checked_gzip_beside_the_original(lab):
    lab["row"]("append_only/brca/table.csv", st.COMPRESS)
    [p] = sa.plan(lab["conn"])
    result = sa.carry_out(lab["conn"], p, by="tester")
    assert result.status == sa.VERIFIED
    with gzip.open(p.destination, "rt") as fh:
        assert fh.read() == p.source.read_text()
    assert p.source.exists()


def test_nothing_is_written_inside_immutable_and_nothing_is_overwritten(lab):
    lab["row"]("immutable/brca/raw.csv", st.COMPRESS)
    rid = lab["row"]("append_only/brca/b.csv", st.COMPRESS)
    (lab["data"] / "append_only/brca/b.csv.gz").write_bytes(b"x")
    by_row = {p.row: p for p in sa.plan(lab["conn"])}
    assert any("immutable/" in p.blocked for p in by_row.values())
    assert "already exists" in by_row[rid].blocked


def test_a_mismatch_fails_and_the_original_is_not_removable(lab, monkeypatch):
    lab["row"]("append_only/brca/c.fastq", st.MOTHBALL)
    [p] = sa.plan(lab["conn"])
    real = sa.manifest
    monkeypatch.setattr(sa, "manifest", lambda root: (
        {k: (s, "bad") for k, (s, _) in real(root).items()} if root == p.destination else real(root)))
    result = sa.carry_out(lab["conn"], p, by="tester")
    assert result.status == sa.FAILED and result.mismatches
    assert sa.removable(lab["conn"]) == ([], [])


def test_a_keep_until_date_holds_removal(lab):
    lab["row"]("append_only/brca/d.fastq", st.MOTHBALL)
    from dataclasses import replace
    cp._write(replace(cp.get("brca"), retain_until="2999-01-01"))
    [p] = sa.plan(lab["conn"])
    sa.carry_out(lab["conn"], p, by="tester")
    may, held = sa.removable(lab["conn"])
    assert not may and held and "keeps everything until 2999-01-01" in held[0].reason


def test_the_command_shows_a_plan_unless_told_to_apply(lab):
    lab["row"]("append_only/brca/e.fastq", st.MOTHBALL)
    runner = CliRunner()
    out = runner.invoke(cli, ["space", "carry-out"]).output
    assert "Nothing was changed" in out and not any(lab["backup"].rglob("e.fastq"))
    out = runner.invoke(cli, ["space", "carry-out", "--apply"]).output
    assert "1 of 1 copied and checked" in out and any(lab["backup"].rglob("e.fastq"))
    out = runner.invoke(cli, ["space", "removable"]).output
    assert "e.fastq" in out and "does not remove files" in out


def test_the_policy_reads_the_backup_settings(lab):
    assert load_policy().mothball_target == str(lab["backup"])

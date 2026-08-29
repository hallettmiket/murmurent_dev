"""
Purpose: Tests for the conscience gap-harvest hook — parsing a report's
         ``## Gap register``, appending to the append-only ledger, regenerating
         the ranked register, and staying silent-but-safe on malformed input.
Author:  Mike Hallett (with Claude Code)
Date:    2026-08-29
Input:   Temp directories standing in for docs/ and a project's outputs/.
Output:  Assertions.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

from murmurent.hooks import conscience_gaps as cg

REPORT = """# Review

Flagged — two issues.

## Gap register

| Needed | Domain | Why it blocked you | Kind |
|---|---|---|---|
| intersectionality (Crenshaw) | 2+3 | could not flag, reported as observation | `no-source` |
| OCAP® | 3 | entry on backlog, unfetched | `blocked` |
"""


def _dirs(tmp_path: Path) -> tuple[Path, Path]:
    """Local store + a reports dir. The repo's docs/ is separate and read-only."""
    store = tmp_path / "store"
    reports = tmp_path / "proj" / "outputs" / "conscience"
    reports.mkdir(parents=True)
    return store, reports


def _repo_docs(tmp_path: Path, decisions: str = "") -> Path:
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "edid_resources.md").write_text(
        "- [Western's Guide](https://edi.uwo.ca/g.pdf) `[binds UWO]`\n"
        "- [General thing](https://example.org/g)\n"
    )
    if decisions:
        (docs / "edid_gap_decisions.md").write_text(decisions)
    return docs


def _write_call(path: Path) -> dict[str, object]:
    return {"tool_name": "Write", "tool_input": {"file_path": str(path)}}


def test_ignores_paths_outside_outputs_conscience(tmp_path: Path) -> None:
    store, _ = _dirs(tmp_path)
    other = tmp_path / "notes.md"
    other.write_text(REPORT)
    assert cg.evaluate(_write_call(other), store, repo_docs=_repo_docs(tmp_path), scopes=set())["status"] == "skip"


def test_ignores_non_write_tools(tmp_path: Path) -> None:
    store, reports = _dirs(tmp_path)
    report = reports / "report_1.md"
    report.write_text(REPORT)
    call = {"tool_name": "Read", "tool_input": {"file_path": str(report)}}
    assert cg.evaluate(call, store)["status"] == "skip"


def test_harvest_writes_log_and_register(tmp_path: Path) -> None:
    store, reports = _dirs(tmp_path)
    report = reports / "report_1.md"
    report.write_text(REPORT)
    assert cg.evaluate(_write_call(report), store, "2026-08-29", repo_docs=_repo_docs(tmp_path), scopes=set()) == {
        "status": "harvested",
        "rows": 2,
    }
    register = (store / cg.REGISTER_NAME).read_text()
    assert "intersectionality (Crenshaw)" in register
    assert "`blocked`" in register


def test_repeated_gap_raises_hit_count_and_ranks_first(tmp_path: Path) -> None:
    store, reports = _dirs(tmp_path)
    (reports / "report_1.md").write_text(REPORT)
    cg.evaluate(_write_call(reports / "report_1.md"), store, "2026-08-29", repo_docs=_repo_docs(tmp_path), scopes=set())
    second = REPORT.replace("| OCAP® | 3 | entry on backlog, unfetched | `blocked` |", "")
    (reports / "report_2.md").write_text(second)
    cg.evaluate(_write_call(reports / "report_2.md"), store, "2026-08-30", repo_docs=_repo_docs(tmp_path), scopes=set())

    rows = [
        line
        for line in (store / cg.REGISTER_NAME).read_text().splitlines()
        if line.startswith("| 1 ") or line.startswith("| 2 ")
    ]
    assert rows[0].startswith("| 2 | intersectionality")
    assert any(row.startswith("| 1 | OCAP") for row in rows)


def test_log_is_append_only(tmp_path: Path) -> None:
    store, reports = _dirs(tmp_path)
    (reports / "report_1.md").write_text(REPORT)
    cg.evaluate(_write_call(reports / "report_1.md"), store, "2026-08-29", repo_docs=_repo_docs(tmp_path), scopes=set())
    (reports / "report_2.md").write_text(REPORT)
    cg.evaluate(_write_call(reports / "report_2.md"), store, "2026-08-30", repo_docs=_repo_docs(tmp_path), scopes=set())
    data = [
        line
        for line in (store / cg.LOG_NAME).read_text().splitlines()
        if line.startswith("| 2026-")
    ]
    assert len(data) == 4


def test_missing_section_is_reported_not_silent(tmp_path: Path) -> None:
    store, reports = _dirs(tmp_path)
    report = reports / "report_3.md"
    report.write_text("# Review\n\nOK — nothing found.\n")
    assert cg.evaluate(_write_call(report), store, repo_docs=_repo_docs(tmp_path), scopes=set())["status"] == "missing-section"


def test_main_emits_warning_for_missing_section(tmp_path: Path) -> None:
    store, reports = _dirs(tmp_path)
    report = reports / "report_3.md"
    report.write_text("# Review\n\nOK — nothing found.\n")
    out = io.StringIO()
    cg.main(io.StringIO(json.dumps(_write_call(report))), out)
    assert "Gap register" in out.getvalue()


def test_declared_but_empty_register_is_not_a_warning(tmp_path: Path) -> None:
    store, reports = _dirs(tmp_path)
    report = reports / "report_5.md"
    report.write_text("## Gap register\n\n| Needed | Domain | Why | Kind |\n|---|---|---|---|\n")
    assert cg.evaluate(_write_call(report), store, repo_docs=_repo_docs(tmp_path), scopes=set())["status"] == "harvested"


def test_malformed_table_does_not_raise(tmp_path: Path) -> None:
    store, reports = _dirs(tmp_path)
    report = reports / "report_4.md"
    report.write_text("## Gap register\n\n| broken\n")
    assert cg.evaluate(_write_call(report), store, repo_docs=_repo_docs(tmp_path), scopes=set())["status"] == "harvested"


def test_main_never_raises_on_garbage_stdin() -> None:
    assert cg.main(io.StringIO("not json at all"), io.StringIO()) == 0
    assert cg.main(io.StringIO(""), io.StringIO()) == 0


def test_nothing_is_written_into_the_repo(tmp_path: Path) -> None:
    """Gap text describes someone's document and the repo is public."""
    store, reports = _dirs(tmp_path)
    docs = _repo_docs(tmp_path)
    (reports / "report_1.md").write_text(REPORT)
    cg.evaluate(_write_call(reports / "report_1.md"), store, "2026-08-29",
                repo_docs=docs, scopes=set())
    assert {p.name for p in docs.iterdir()} == {"edid_resources.md"}
    assert (store / cg.LOG_NAME).exists()


def test_nudge_stays_silent_below_threshold_and_fires_at_it(tmp_path: Path) -> None:
    store, reports = _dirs(tmp_path)
    docs = _repo_docs(tmp_path)
    for i, day in enumerate(["2026-08-29", "2026-08-30", "2026-08-31"], start=1):
        report = reports / f"report_{i}.md"
        report.write_text(REPORT)
        result = cg.evaluate(_write_call(report), store, day, repo_docs=docs, scopes=set())
        if i < cg.NUDGE_THRESHOLD:
            assert result["crossed"] == []
    assert dict(result["crossed"])["intersectionality (Crenshaw)"] == 3


def test_declined_gap_never_nudges(tmp_path: Path) -> None:
    store, reports = _dirs(tmp_path)
    docs = _repo_docs(tmp_path, decisions=(
        "| Gap | State | Reason |\n|---|---|---|\n"
        "| intersectionality (Crenshaw) | `declined` | out of scope by decision |\n"
    ))
    for i, day in enumerate(["2026-08-29", "2026-08-30", "2026-08-31"], start=1):
        report = reports / f"report_{i}.md"
        report.write_text(REPORT)
        result = cg.evaluate(_write_call(report), store, day, repo_docs=docs, scopes=set())
    assert result["crossed"] == []
    register = (store / cg.REGISTER_NAME).read_text()
    assert "`declined` — out of scope by decision" in register


def test_scope_mismatch_warns_only_for_tagged_entries_outside_scope(tmp_path: Path) -> None:
    store, reports = _dirs(tmp_path)
    docs = _repo_docs(tmp_path)
    report = reports / "report_1.md"
    report.write_text(
        REPORT + "\nCites [Western's Guide](https://edi.uwo.ca/g.pdf) and "
        "[General thing](https://example.org/g).\n"
    )
    result = cg.evaluate(_write_call(report), store, "2026-08-29",
                         repo_docs=docs, scopes={"CA"})
    assert ("https://edi.uwo.ca/g.pdf", "UWO") in result["mismatched"]
    assert not any("example.org" in url for url, _ in result["mismatched"])


def test_scope_check_silent_when_deployment_scope_unset(tmp_path: Path) -> None:
    """Warning on every citation would train the reader to ignore it."""
    store, reports = _dirs(tmp_path)
    docs = _repo_docs(tmp_path)
    report = reports / "report_1.md"
    report.write_text(REPORT + "\n[Western's Guide](https://edi.uwo.ca/g.pdf)\n")
    result = cg.evaluate(_write_call(report), store, "2026-08-29",
                         repo_docs=docs, scopes=set())
    assert result["mismatched"] == []

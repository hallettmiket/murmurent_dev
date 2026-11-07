"""
Purpose: Tests for `murmurent notebook report` (#294): the audience field,
         whole-entry collection by reader and date, refusal of restricted and
         protected entries, the material and source files, the self-contained
         page with embedded thumbnails and server links (never a movie), the
         scribe's narrative slot, and that nothing is sent.
Author:  Mike Hallett (with Claude Code)
Date:    2026-11-07
Input:   A temp vault.
Output:  Assertions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from murmurent.commands import notebook_cmd
from murmurent.core import lab_notebook as nb
from murmurent.core import notebook_report as rep


def _entry(vault: Path, name: str, *, audience: str | None, sensitivity: str = "standard",
           body: str = "Notes.\n", date: str | None = None) -> Path:
    date = date or name[:10]
    aud = f"audience: {audience}\n" if audience is not None else ""
    p = vault / "lab-notebook" / f"{name}.md"
    p.write_text(f"---\ntitle: {name}\ndate: {date}\nproject: p_demo\nsensitivity: {sensitivity}\n"
                 f"{aud}tags: []\n---\n\n{body}", encoding="utf-8")
    return p


@pytest.fixture
def vault(tmp_path, monkeypatch):
    v = tmp_path / "vault"
    (v / "lab-notebook").mkdir(parents=True)
    monkeypatch.setenv("MURMURENT_VAULT_ROOT", str(v))
    monkeypatch.delenv("MURMURENT_NOTEBOOK_DIR", raising=False)
    return v


def test_audience_helpers():
    assert nb.audiences_of({}) == ["me"]
    assert nb.audiences_of({"audience": "Supervisor"}) == ["supervisor"]
    assert nb.audiences_of({"audience": ["lab", "project:x"]}) == ["lab", "project:x"]
    assert nb.is_valid_audience("project:dcis") and not nb.is_valid_audience("project:")
    assert not nb.is_valid_audience("everyone")
    assert nb.audience_admits(["supervisor"], "supervisor")
    assert nb.audience_admits(["lab"], "supervisor")      # the lab includes the supervisor
    assert not nb.audience_admits(["supervisor"], "lab")
    assert nb.audience_admits(["project:x"], "project:x")
    assert not nb.audience_admits(["project:x"], "lab")
    assert not nb.audience_admits(["me"], "supervisor")
    assert not nb.audience_admits(["supervisor"], "me")  # me is never a reader


def test_collect_takes_whole_entries_by_audience_and_date_and_refuses_tiers(vault):
    _entry(vault, "2026-11-01", audience="supervisor", body="Day one for Mike.\n")
    _entry(vault, "2026-11-02", audience=None, body="Private thought.\n")
    _entry(vault, "2026-11-03", audience="lab", body="For everyone.\n")
    _entry(vault, "2026-11-04", audience="supervisor", sensitivity="restricted", body="Patent idea.\n")
    _entry(vault, "2026-11-05", audience="supervisor", sensitivity="protected", body="PHI.\n")
    _entry(vault, "2026-10-20", audience="supervisor", body="Too early.\n")
    _entry(vault, "2026-11-06", audience="project:dcis", body="Project only.\n")
    paths = nb.resolve_paths()
    b = rep.collect(paths, reader="supervisor", since="2026-11-01", until="2026-11-07")
    assert [e.date for e in b.included] == ["2026-11-01", "2026-11-03"]
    assert b.considered == 6
    assert {r for r, _ in b.refused} == {"lab-notebook/2026-11-04.md", "lab-notebook/2026-11-05.md"}
    assert all("never leaves the vault" in why for _, why in b.refused)
    lab = rep.collect(paths, reader="lab", since="2026-11-01", until="2026-11-07")
    assert [e.date for e in lab.included] == ["2026-11-03"]
    proj = rep.collect(paths, reader="project:dcis", since="2026-11-01", until="2026-11-07")
    assert [e.date for e in proj.included] == ["2026-11-06"]
    with pytest.raises(rep.ReportError):
        rep.collect(paths, reader="me", since="2026-11-01", until="2026-11-07")


def test_report_writes_material_sources_and_a_self_contained_page(vault, capsys):
    thumb = vault / "attachments" / "2026-11-02" / "gel_thumb.jpg"
    thumb.parent.mkdir(parents=True)
    thumb.write_bytes(b"\xff\xd8\xff\xdb fake jpeg")
    _entry(vault, "2026-11-02", audience="supervisor", body=(
        "# Gel day\n\n## 14:05 image: gel.png\n![[attachments/2026-11-02/gel_thumb.jpg]]\n"
        "- original: `lab-server:/data/lab_vm/append_only/p_demo/notebook/2026-11-02/gel.png` (3.1 MB)\n"
        "> Machine reading (image description by Claude Code, not the record): a clean band at 40 kDa\n\n"
        "## 16:00 video: talk.mov\n- original: `lab-server:/data/lab_vm/append_only/p_demo/notebook/2026-11-02/talk.mov`\n"
        "\nSessions: [[sessions/2026-11-02]]\n"))
    _entry(vault, "2026-11-03", audience="supervisor", sensitivity="protected", body="secret\n")
    out = vault / "reports" / "weekly"
    rc = notebook_cmd.cmd_report("supervisor", since="2026-11-01", until="2026-11-07", out_dir=str(out))
    assert rc == 0
    printed = capsys.readouterr().out
    assert "lab-notebook/2026-11-02.md" in printed
    assert "attachments/2026-11-02/gel_thumb.jpg (from the vault, embedded)" in printed
    assert "notebook/2026-11-02/gel.png (on the server, linked)" in printed
    assert "lab-notebook/2026-11-03.md: sensitivity: protected" in printed
    assert "Nothing has been sent" in printed
    assert "artifact" in printed and "murmurent project note" in printed

    page = (out / "report.html").read_text(encoding="utf-8")
    assert page.startswith("<!doctype html>")
    assert "data:image/jpeg;base64," in page           # the thumbnail is embedded
    assert "talk.mov" in page and "<video" not in page   # the movie is linked, never embedded
    assert "a reader with an account opens it there" in page
    assert "<blockquote>" in page and "not the record" in page
    assert "secret" not in page
    assert "<!-- scribe: narrative -->" in page and "to be drafted by the scribe" in page
    assert "sessions/2026-11-02" not in printed.split("Files drawn on")[1].split("Written")[0]

    material = (out / "material.md").read_text(encoding="utf-8")
    assert "## 2026-11-02: 2026-11-02  (lab-notebook/2026-11-02.md)" in material
    assert "a clean band at 40 kDa" in material and "secret" not in material
    sources = (out / "sources.md").read_text(encoding="utf-8")
    assert "lab-notebook/2026-11-02.md" in sources and "Refused" in sources

    # the scribe writes narrative.md; the next run puts it in the page
    (out / "narrative.md").write_text("This week the gel **worked**. [CITE]\n", encoding="utf-8")
    assert notebook_cmd.cmd_report("supervisor", since="2026-11-01", until="2026-11-07", out_dir=str(out)) == 0
    page = (out / "report.html").read_text(encoding="utf-8")
    assert "<strong>worked</strong>" in page and "to be drafted by the scribe" not in page


def test_lab_exposition_uses_the_same_page(vault):
    _entry(vault, "2026-11-02", audience="lab", body="Shown to all.\n")
    paths = nb.resolve_paths()
    b = rep.collect(paths, reader="lab", since="2026-11-01", until="2026-11-07")
    page = rep.render_page(paths, b)
    assert "<title>Exposition for the lab, 2026-11-01 to 2026-11-07</title>" in page
    assert rep.default_out_dir(paths, b) == vault / "reports" / "2026-11-07_lab"


def test_bad_reader_and_bad_dates_are_errors(vault, capsys):
    assert notebook_cmd.cmd_report("me", since="2026-11-01", until="2026-11-07") == 1
    assert "me is never a reader" in capsys.readouterr().out
    assert notebook_cmd.cmd_report("lab", since="yesterday", until="2026-11-07") == 1
    assert notebook_cmd.cmd_report("everyone", since="2026-11-01", until="2026-11-07") == 1


def test_empty_range_still_writes_a_page_with_no_entries(vault, capsys):
    out = vault / "r"
    assert notebook_cmd.cmd_report("lab", since="2026-11-01", until="2026-11-07", out_dir=str(out)) == 0
    assert "No entry in this range is marked for this audience" in (out / "report.html").read_text()

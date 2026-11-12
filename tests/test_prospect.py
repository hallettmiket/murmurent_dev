"""The prospector's deterministic half: profiles, the registry read as data,
the internal deadline from the pack's rule, the registry check, the feed
poll and the report files."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from murmurent.cli import cli
from murmurent.core import institution as _inst
from murmurent.core import prospect as _p

REGISTRY = """# The funder registry

## How each page loads

| Loads | Meaning | What the prospector does |
|---|---|---|
| plain | the listing comes through | read it |

## Canada

| Agency | Listing page | What it gave on the date checked | Loads | Feed | Funds | Checked |
|---|---|---|---|---|---|---|
| CIHR | <https://www.researchnet-recherchenet.ca/rnr16/search.do?view=currentOpps> | the list | plain, with a catch | one RSS feed per category | health | 2026-11-12 |
| NSERC | <https://nserc.example/funding-opportunity> | programs | plain | none found | science | 2026-11-12 |

## United States

| Agency | Listing page | What it gave on the date checked | Loads | Feed | Funds | Checked |
|---|---|---|---|---|---|---|
| NSF | <https://nsf.example/opportunities> | script app | script | <https://nsf.example/rss/upcoming.xml> (due dates) | science | 2026-11-12 |
| NIH | <https://nih.example/guide> | 403 | refused | none | biomedical | 2026-11-12 |

## Closed or renamed, found on the date checked

| Asked for | What the page said on 2026-11-12 | Page |
|---|---|---|
| Banting | closed | <https://banting.example/> |
"""

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>NSF Upcoming Due Dates</title>
<item><title>Program A</title><link>https://nsf.example/a</link><pubDate>Mon, 10 Nov 2026 00:00:00 GMT</pubDate></item>
<item><title>Program B</title><link>https://nsf.example/b</link></item>
</channel></rss>"""

RESEARCHNET = """<table><tr><td><a href="vwOpprtntyDtls.do?prog=4074&amp;view=currentOpps">Project Grant: Fall 2026</a></td>
<td>2027-02-03</td><td>2027-03-03</td></tr>
<tr><td><a href="vwOpprtntyDtls.do?prog=4076&amp;view=currentOpps">Doctoral Research Award</a></td><td>N/A</td><td>2026-11-23</td></tr></table>"""


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("MURMURENT_HOME", str(tmp_path / "home"))
    reg = tmp_path / "funders.md"
    reg.write_text(REGISTRY)
    monkeypatch.setenv(_p.FUNDERS_ENV, str(reg))
    return tmp_path


def test_profile_round_trip_and_validation(world):
    prof = _p.Profile(name="cf_phd", who="student", field="cystic fibrosis genomics",
                      terms=["cystic fibrosis", "genomics"], citizenship="Canadian citizen")
    path = _p.save_profile(prof)
    assert path.is_file() and _p.list_profiles() == ["cf_phd"]
    back = _p.load_profile("cf_phd")
    assert back.terms == ["cystic fibrosis", "genomics"] and back.horizon_months == 12
    with pytest.raises(ValueError, match="who"):
        _p.save_profile(_p.Profile(name="x", who="dean", field="y"))
    with pytest.raises(ValueError, match="name"):
        _p.save_profile(_p.Profile(name="Bad Name", who="pi", field="y"))


def test_registry_reads_only_the_agency_tables(world):
    entries = _p.load_registry()
    assert [e.agency for e in entries] == ["CIHR", "NSERC", "NSF", "NIH"]
    assert entries[0].tier == "Canada" and entries[2].tier == "United States"
    assert entries[2].feeds == ["https://nsf.example/rss/upcoming.xml"]
    assert entries[1].loads_plain and not entries[2].loads_plain
    assert _p.is_researchnet(entries[0].listing)
    sources = _p.feed_sources(entries)
    assert [u for _, u in sources] == [entries[0].listing, "https://nsf.example/rss/upcoming.xml"]


def _pack(tmp_path, rule: dict | None) -> _inst.Pack:
    root = tmp_path / "institution" / "example"
    root.mkdir(parents=True)
    (root / "institution.yaml").write_text(yaml.safe_dump({
        "name": "Example University", "unique_name": "example", "domains": ["example.edu"], "keeper": "bookworm"}))
    (root / "calendar.yaml").write_text(yaml.safe_dump({"holidays": [
        {"name": "Family Day", "date": "2027-02-15", "source": "https://www.example.edu/hr/holidays.html", "date_read": "2026-11-12"}]}))
    if rule is not None:
        (root / "funding.yaml").write_text(yaml.safe_dump({"internal_deadline": rule}))
    return _inst.load_pack(root)


def test_internal_deadline_counts_working_days_over_holidays(tmp_path):
    pack = _pack(tmp_path, {"rule": "five business days before", "working_days": -5,
                            "by": {"tri_agency": -10}, "source": "https://www.example.edu/research/signatures.html",
                            "date_read": "2026-11-12"})
    plain = _p.internal_deadline(pack, date(2027, 2, 22))
    assert plain.known and plain.internal == date(2027, 2, 12)      # Family Day on the 15th is skipped
    assert "skipped 2027-02-15 Family Day" in plain.explanation
    tri = _p.internal_deadline(pack, date(2027, 2, 22), "tri_agency")
    assert tri.internal == date(2027, 2, 5) and "tri_agency variant" in tri.explanation
    assert tri.source.endswith("signatures.html")


def test_internal_deadline_is_unknown_without_a_rule(tmp_path):
    pack = _pack(tmp_path, None)
    got = _p.internal_deadline(pack, date(2027, 2, 22))
    assert not got.known and got.explanation.startswith("Unknown") and "funding.yaml" in got.explanation
    assert not _p.internal_deadline(None, date(2027, 2, 22)).known


def test_check_flags_a_registry_that_disagrees_with_the_page(world):
    entries = _p.load_registry()

    def fetcher(url: str) -> _p.FetchResult:
        if "nih" in url:
            return _p.FetchResult(url, 200, True, "ok", title="NIH Guide")
        if "nserc" in url:
            return _p.FetchResult(url, 403, False, "refused", note="answered 403")
        return _p.FetchResult(url, 200, True, "ok", title="Page")

    lines = [r.line() for r in _p.check_registry(entries, fetcher)]
    assert any(l.startswith("NIH:") and "says refused; update it" in l for l in lines)
    assert any(l.startswith("NSERC:") and "says plain; update it" in l for l in lines)
    assert any(l.startswith("NSF:") and "<-" not in l for l in lines)


def test_feed_poll_reports_only_what_is_new_after_the_first_run(world):
    entries = _p.load_registry()
    state = world / "seen.json"
    pages = {"https://nsf.example/rss/upcoming.xml": RSS, entries[0].listing: RESEARCHNET}

    def fetcher(url: str) -> _p.FetchResult:
        return _p.FetchResult(url, 200, True, "ok", text=pages[url]) if url in pages else \
            _p.FetchResult(url, 404, False, "error", note="answered 404")

    first = _p.poll_feeds(entries, fetcher=fetcher, state=state)
    assert first.first_run and not first.new and first.seen_total == 4 and len(first.polled) == 2
    assert "first poll" in _p.format_poll_note(first, entries)

    pages["https://nsf.example/rss/upcoming.xml"] = RSS.replace("</channel>",
        "<item><title>Program C</title><link>https://nsf.example/c</link></item></channel>")
    second = _p.poll_feeds(entries, fetcher=fetcher, state=state)
    assert not second.first_run and [i.title for i in second.new] == ["Program C"]
    note = _p.format_poll_note(second, entries)
    assert note.startswith("Funding feeds: 1 new item.") and "NSF: Program C https://nsf.example/c" in note

    rn = _p.parse_researchnet(RESEARCHNET, entries[0].listing)
    assert rn[0].title == "Project Grant: Fall 2026" and rn[0].loi == "2027-02-03" and rn[0].deadline == "2027-03-03"
    assert rn[0].link.startswith("https://www.researchnet-recherchenet.ca/rnr16/vwOpprtntyDtls.do?prog=4074&view=")


def test_feed_parser_reads_atom_too():
    atom = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Call X</title>'
            '<link href="https://eu.example/x"/><updated>2026-11-01T00:00:00Z</updated></entry></feed>')
    items = _p.parse_feed(atom, "https://eu.example/feed")
    assert items[0].title == "Call X" and items[0].link == "https://eu.example/x" and items[0].published.startswith("2026")
    assert _p.parse_feed("not xml", "u") == []


def test_report_renders_html_and_calendar(world):
    rows = world / "rows.yaml"
    rows.write_text(yaml.safe_dump({
        "profile": {"name": "cf_phd", "who": "student", "field": "cystic fibrosis genomics", "horizon_months": 12},
        "rows": [
            {"opportunity": "Research Fellowship Awards", "funder": "Cystic Fibrosis Canada", "tier": "disease",
             "who_may_apply": "postdoctoral fellows", "pays": "not stated", "registration": "none",
             "full_deadline": "2027-10-01", "internal_deadline": "2027-09-24 (computed)",
             "link": "https://www.cysticfibrosis.ca/our-programs/research/funding-opportunities",
             "read": "2026-11-12", "status": "READ"},
            {"opportunity": "Something behind a login", "funder": "Pivot", "status": "nonsense"},
        ],
        "searched": ["cystic fibrosis fellowship international: nothing open to Canadians"],
        "for_the_bookworm": ["Cystic Fibrosis Foundation (US): funds Canadians, not in the registry"],
    }))
    head, parsed = _p.load_rows(rows)
    assert parsed[1]["status"] == "UNRESOLVED" and parsed[1]["link"] == ""
    html_path, ics_path = _p.write_report(head, parsed, world / "out", "cf", today=date(2026, 11, 12))
    html = html_path.read_text()
    assert html_path.name == "2026-11-12_cf.html" and "Research Fellowship Awards" in html
    assert 'href="https://www.cysticfibrosis.ca/our-programs/research/funding-opportunities"' in html
    assert "What was searched and did not find" in html and "For the bookworm" in html
    assert "<script" not in html
    ics = ics_path.read_text()
    assert ics.count("BEGIN:VEVENT") == 2 and "DTSTART;VALUE=DATE:20271001" in ics and "DTSTART;VALUE=DATE:20270924" in ics


def test_cli_profile_registry_and_report(world):
    runner = CliRunner()
    r = runner.invoke(cli, ["prospect", "profile", "new", "cf_phd", "--who", "student", "--field", "cf genomics",
                            "--terms", "cystic fibrosis, genomics"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(cli, ["prospect", "profile", "show", "cf_phd"])
    assert "terms: cystic fibrosis, genomics" in r.output
    r = runner.invoke(cli, ["prospect", "registry", "--tier", "united"])
    assert r.exit_code == 0 and "NSF" in r.output and "CIHR" not in r.output and "Institution tier" in r.output
    r = runner.invoke(cli, ["prospect", "internal-deadline", "2027-03-03"])
    assert r.exit_code == 0 and r.output.startswith("Unknown")
    r = runner.invoke(cli, ["prospect", "internal-deadline", "bad"])
    assert r.exit_code != 0

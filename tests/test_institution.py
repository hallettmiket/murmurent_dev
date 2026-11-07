"""The institution pack and the clerk's three jobs (issue #291).

A pack under ``tmp_path`` is built from the shipped ``institution/example``
pack, so the tests never touch a deployment's own pack, and every fetch is a
fake: the only network rule tested is the one that refuses it.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from murmurent.core import institution as inst
from murmurent.core import paper_package as pp

_REPO = Path(__file__).resolve().parent.parent
_EXAMPLE = _REPO / "institution" / "example"

TODAY = date(2026, 11, 7)


@pytest.fixture
def pack_dir(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "institution"
    shutil.copytree(_EXAMPLE, root / "example")
    monkeypatch.setenv("MURMURENT_INSTITUTION_ROOT", str(root))
    monkeypatch.setenv("MURMURENT_INSTITUTION_PACK", str(root / "example"))
    return root / "example"


@pytest.fixture
def pack(pack_dir) -> inst.Pack:
    return inst.load_pack(pack_dir)


def _edit(path: Path, fn) -> None:
    doc = yaml.safe_load(path.read_text())
    fn(doc)
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


# --------------------------------------------------------------------------- #
# Finding, loading, validating
# --------------------------------------------------------------------------- #


def test_shipped_example_pack_validates():
    pack = inst.load_pack(_EXAMPLE)
    assert inst.validate_pack(pack) == []
    assert pack.unique_name == "example"
    assert "thesis_examination" in pack.procedures


def test_find_pack_order(pack_dir, monkeypatch):
    assert inst.find_pack() == pack_dir
    assert inst.find_pack("example") == pack_dir
    assert inst.find_pack(str(pack_dir)) == pack_dir
    assert inst.find_pack("nowhere") is None
    monkeypatch.delenv("MURMURENT_INSTITUTION_PACK")
    # No centre on this machine, so no default pack: the example is never picked by itself.
    assert inst.find_pack() is None
    assert [p.name for p in inst.list_packs()] == ["example"]


def test_validate_refuses_unsourced_offdomain_and_private_fields(pack_dir):
    def spoil(d):
        d["offices"][0].pop("date_read")
        d["offices"][1]["source"] = "https://www.linkedin.com/in/someone"
        d["offices"][2]["home_address"] = "12 Private Lane"
    _edit(pack_dir / "directory.yaml", spoil)
    problems = inst.validate_pack(inst.load_pack(pack_dir))
    text = "\n".join(problems)
    assert "`date_read:` is required" in text
    assert "outside the pack's domains" in text
    assert "`home_address:` is not a directory field" in text


def test_host_allowed_is_strict():
    assert inst.host_allowed("https://grad.uwo.ca/x", ["uwo.ca"])
    assert inst.host_allowed("https://uwo.ca/", ["uwo.ca"])
    assert not inst.host_allowed("https://uwo.ca.example.com/", ["uwo.ca"])
    assert not inst.host_allowed("http://grad.uwo.ca/x", ["uwo.ca"])
    assert inst.host_allowed("http://grad.uwo.ca/x", ["uwo.ca"], require_https=False)
    assert not inst.host_allowed("https://evil.com/?uwo.ca", ["uwo.ca"])


def test_fetch_text_refuses_off_domain_before_any_network(pack):
    with pytest.raises(inst.PackError, match="outside the pack's domains"):
        inst.fetch_text("https://www.linkedin.com/", domains=pack.domains)


def test_staleness_is_stated(pack):
    office = pack.offices[0]
    assert inst.age_note(office, pack, TODAY) == ""
    note = inst.age_note(office, pack, date(2027, 11, 7))
    assert "365 days ago" in note and "180-day limit" in note
    assert len(inst.stale_facts(pack, date(2027, 11, 7))) == len(pack.facts())
    assert inst.stale_facts(pack, TODAY) == []


# --------------------------------------------------------------------------- #
# Job 1: check a document
# --------------------------------------------------------------------------- #


def test_check_confirms_fixes_and_says_unknown(pack):
    text = (
        "Dear Dr. Example,\n"
        "As Vice-President (Research), Ada Example (vpr@example.edu) will reply.\n"
        "The Dean of Science, Robert Wrong, has agreed; write to deanoffice@example.edu.\n"
        "Copy to unknown.person@example.edu.\n"
        "Heading colour #003366; body colour #FF0000; font-family: Arial\n"
    )
    findings = inst.check_document(pack, text, TODAY)
    by = {(f.verdict, f.what): f for f in findings}
    assert ("Correct", "Vice-President (Research)") in by
    assert ("Correct", "email for Vice-President (Research)") in by
    dean = by[("Fix", "Dean of Science")]
    assert "Charles Example" in dean.detail and "Robert Wrong" in dean.detail
    assert dean.source.startswith("https://www.example.edu/") and dean.date_read == "2026-11-07"
    assert "sciencedean@example.edu" in by[("Fix", "email for Dean of Science")].detail
    assert ("Unknown", "email unknown.person@example.edu") in by
    assert ("Correct", "colour #003366") in by
    assert ("Fix", "colour #FF0000") in by
    assert ("Fix", "font Arial") in by
    assert inst.check_verdict(findings) == "Fix"


def test_check_is_unknown_when_the_pack_holds_nothing_named(pack):
    findings = inst.check_document(pack, "A memo about nothing in particular.", TODAY)
    assert findings == [] and inst.check_verdict(findings) == "Unknown"


def test_check_flags_a_wrong_postal_code(pack):
    text = "Charles Example, Dean of Science, Science Building, Exampleton ON Z9Z 9Z9\n"
    findings = inst.check_document(pack, text, TODAY)
    fix = [f for f in findings if f.verdict == "Fix" and f.what == "address for Dean of Science"]
    assert fix and "Z9Z 9Z9" in fix[0].detail and "A1A 1A2" in fix[0].detail


# --------------------------------------------------------------------------- #
# Job 2: compute a date
# --------------------------------------------------------------------------- #


def test_working_days_skip_weekends_and_holidays_and_never_land_on_one(pack):
    # 2027-04-16 is a Friday; Good Friday 2027-03-26 and Founders' Day 04-12 are holidays.
    assert inst.working_days_from(pack, date(2027, 4, 16), -5) == date(2027, 4, 8)   # skips 04-12
    assert inst.working_days_from(pack, date(2027, 4, 16), -25) == date(2027, 3, 10)  # skips both
    assert inst.working_days_from(pack, date(2027, 4, 9), 1) == date(2027, 4, 13)     # Mon 04-12 is a holiday
    assert inst.working_days_from(pack, date(2027, 4, 12), 0) == date(2027, 4, 13)
    assert inst.working_days_from(pack, date(2027, 4, 10), 0) == date(2027, 4, 13)    # Saturday
    assert inst.is_holiday(pack, date(2027, 3, 26)) == "Good Friday"
    s = inst.explain_date(pack, date(2027, 4, 16), -25)
    assert "2027-03-10" in s and "Good Friday" in s and "Founders' Day" in s


# --------------------------------------------------------------------------- #
# Job 3: walk a procedure
# --------------------------------------------------------------------------- #


def test_walk_resolves_deadlines_from_the_anchor_by_variant(pack):
    steps = inst.walk_procedure(pack, "thesis_examination", date(2027, 4, 16), variant="doctoral")
    by_title = {s.title[:30]: s for s in steps}
    req = by_title["Thesis Examination Request For"]
    assert req.form == "Thesis Examination Request Form"
    assert req.due == date(2027, 3, 10)                      # 25 working days, two holidays skipped
    reports = by_title["Examiners' preliminary reports"]
    assert reports.due == date(2027, 4, 8)
    masters = inst.walk_procedure(pack, "thesis_examination", date(2027, 4, 16), variant="masters")
    assert {s.title[:30]: s for s in masters}["Thesis Examination Request For"].due == date(2027, 3, 24)
    undated = inst.walk_procedure(pack, "thesis_examination")
    assert all(s.due is None for s in undated)
    assert any("needs the defence date" in s.note for s in undated)
    nxt = inst.next_steps(inst.walk_procedure(pack, "thesis_examination", date(2027, 4, 16),
                                              done=[1, 2, 3], variant="doctoral"))
    assert [s.number for s in nxt] == [4, 5, 8]
    with pytest.raises(inst.PackError, match="no procedure `annual_report`"):
        inst.walk_procedure(pack, "annual_report")
    text = inst.format_walk(pack, "thesis_examination", steps, TODAY)
    assert "by **2027-03-10**" in text and "Sources:" in text


# --------------------------------------------------------------------------- #
# Courses: fetch rule plus cache; refresh
# --------------------------------------------------------------------------- #

_TIMETABLE = """
<html><body><h4>BIOCHEM 3380G - BIOCHEMISTRY LABORATORY</h4>
<table><tr><th>Section</th><th>Component</th><th>Class Nbr</th><th>Status</th><th>Campus</th><th>Delivery Type</th></tr>
<tr><td>001</td><td>LEC</td><td>9313</td><td>Full</td><td>Main</td><td>In Person</td></tr>
<tr><td>003</td><td>LAB</td><td>9511</td><td>Full</td><td>Main</td><td>In Person</td></tr>
<tr><td>005</td><td>LAB</td><td>9599</td><td>Not Full</td><td>Main</td><td>In Person</td></tr>
</table></body></html>
"""


def test_fetch_course_uses_the_rule_and_parses_the_table(pack):
    calls = []

    def fake(url, data):
        calls.append((url, data))
        return _TIMETABLE

    entry = inst.fetch_course(pack, "BIOCHEM", "3380", fetcher=fake, today=TODAY)
    assert calls == [("https://timetable.example.edu/search.cfm",
                      {"subject": "BIOCHEM", "catalognbr": "3380", "command": "search"})]
    assert entry["found"] and entry["code"] == "BIOCHEM 3380G"
    assert [s["section"] for s in entry["sections"]] == ["001", "003", "005"]
    assert entry["sections"][2]["status"] == "Not Full"
    assert "room" not in entry["sections"][0]          # the page does not show it, so neither does the cache
    assert entry["source"].startswith("https://timetable.example.edu") and entry["date_read"] == "2026-11-07"
    missing = inst.fetch_course(pack, "COMPSCI", "9999", fetcher=fake, today=TODAY)
    assert not missing["found"] and missing["sections"] == []


def test_refresh_reports_confirmed_changed_unreachable_and_applies_dates(pack_dir):
    pack = inst.load_pack(pack_dir)
    pages = {
        "https://www.example.edu/research/leadership.html": "<p>Ada Example, Vice-President (Research), vpr@example.edu</p>",
        "https://www.example.edu/science/people.html": "<p>Dean of Science: Someone New, sciencedean@example.edu</p>",
        "https://www.example.edu/hr/holidays.html": "<ul><li>January 1</li><li>February 15</li><li>March 26</li><li>April 12</li><li>May 24</li></ul>",
        "https://www.example.edu/registrar/sessional_dates.html": "2027-01-04 classes; 2027-04-13 exams",
        "https://www.example.edu/science/annual_report.html": "Reports are due June 30.",
        "https://timetable.example.edu/search.cfm": _TIMETABLE,
        "https://www.example.edu/brand/colours.html": "#003366 #FFFFFF #FFCC00",
        "https://grad.example.edu/thesis/index.html": "thesis", "https://grad.example.edu/thesis/timelines.html": "timelines",
    }

    def fake(url, data):
        if url not in pages:
            raise inst.PackError(f"could not read {url}: 404")
        return pages[url]

    later = date(2027, 1, 15)
    changes = inst.refresh(pack, fetcher=fake, today=later)
    status = {(c.fact.kind, c.fact.key): c.status for c in changes}
    assert status[("office", "Vice-President (Research)")] == "confirmed"
    assert status[("office", "Dean of Science")] == "changed"
    assert status[("office", "Graduate Program Chair, Biochemistry")] == "unreachable"
    assert status[("holiday", "Good Friday")] == "confirmed"
    assert status[("course", "BIOCHEM 3380G")] == "changed"       # a third section appeared
    assert status[("template", "letterhead")] == "confirmed"
    report = inst.format_changes(changes, later)
    assert "CHANGED: office `Dean of Science`" in report and "Someone New" not in report
    # Dry run wrote nothing.
    assert yaml.safe_load((pack_dir / "directory.yaml").read_text())["offices"][0]["date_read"] == "2026-11-07"

    inst.refresh(pack, fetcher=fake, today=later, apply=True)
    d = yaml.safe_load((pack_dir / "directory.yaml").read_text())["offices"]
    assert d[0]["date_read"] == "2027-01-15"            # confirmed: restamped
    assert d[1]["date_read"] == "2026-11-07" and d[1]["person"] == "Charles Example"   # changed: left for a person
    c = yaml.safe_load((pack_dir / "courses.yaml").read_text())["cache"][0]
    assert len(c["sections"]) == 3 and c["date_read"] == "2027-01-15"


def test_refresh_refuses_off_domain_sources_without_fetching(pack_dir):
    _edit(pack_dir / "directory.yaml", lambda d: d["offices"][0].update(source="https://www.linkedin.com/x"))
    pack = inst.load_pack(pack_dir)
    seen = []
    changes = inst.refresh(pack, fetcher=lambda u, d: seen.append(u) or "<p></p>", today=TODAY, kinds=("office",))
    assert changes[0].status == "off_domain" and "linkedin" not in " ".join(seen)


# --------------------------------------------------------------------------- #
# The thesis paperwork reads the pack
# --------------------------------------------------------------------------- #


def test_init_pack_seeds_the_thesis_procedure_from_the_code(tmp_path):
    written = inst.init_pack(tmp_path / "acme", name="Acme", unique_name="acme", domains=["acme.com"],
                             keeper="bookworm", thesis_procedure=pp.seed_thesis_procedure())
    assert {p.name for p in written} >= {"institution.yaml", "directory.yaml", "calendar.yaml", "thesis_examination.yaml"}
    proc = yaml.safe_load((tmp_path / "acme/procedures/thesis_examination.yaml").read_text())
    assert proc["constants"]["lead_working_days"] == {"doctoral": pp.PHD_LEAD_WORKING_DAYS,
                                                      "masters": pp.MASTERS_LEAD_WORKING_DAYS}
    assert proc["sources"][0]["date_read"] == pp.PAPERWORK_READ_ON
    assert inst.init_pack(tmp_path / "acme", name="Acme", unique_name="acme", domains=[], keeper="x") == []


def test_paperwork_uses_the_pack_and_falls_back_to_the_seed(tmp_path, monkeypatch, pack_dir):
    monkeypatch.delenv("MURMURENT_DATA_ROOT", raising=False)
    monkeypatch.delenv("MURMURENT_LAB_VM_ROOT", raising=False)
    root = tmp_path / "examples"
    shutil.copytree(_REPO / "examples", root, ignore=shutil.ignore_patterns("build"))
    thesis = root / "thesis_example"
    # With the example pack: Good Friday and Founders' Day are skipped and the file says which pack.
    text = pp.paperwork(thesis)
    assert "institution pack" in text and "**2027-03-10**" in text
    assert "the pack's holidays are skipped" in text
    assert "murmurent institution walk thesis_examination" in text
    # Without a pack: the seed, weekends only, and the file says so.
    monkeypatch.delenv("MURMURENT_INSTITUTION_PACK")
    text = pp.paperwork(thesis)
    assert "no institution pack found" in text and "**2027-03-12**" in text


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def test_cli_validate_show_date_walk_check(pack_dir, tmp_path):
    from murmurent.cli import cli

    r = CliRunner()
    out = r.invoke(cli, ["institution", "validate"])
    assert out.exit_code == 0 and "0 error(s)" in out.output
    out = r.invoke(cli, ["institution", "show", "office", "dean of science"])
    assert out.exit_code == 0 and "Charles Example" in out.output and "date_read" in out.output
    out = r.invoke(cli, ["institution", "show", "office", "Chancellor"])
    assert out.exit_code == 1 and out.output.startswith("Unknown") and "Nearest" in out.output
    out = r.invoke(cli, ["institution", "show", "holiday", "2027"])
    assert "Good Friday" in out.output
    out = r.invoke(cli, ["institution", "date", "2027-04-16", "--days", "-25"])
    assert "2027-03-10" in out.output and "Good Friday" in out.output
    out = r.invoke(cli, ["institution", "date", "2027-04-12", "--days", "0"])
    assert "Founders' Day" in out.output and "2027-04-13" in out.output
    out = r.invoke(cli, ["institution", "walk", "thesis_examination", "--anchor", "2027-04-16",
                         "--variant", "doctoral", "--done", "1,2", "--next"])
    assert out.exit_code == 0 and "2027-03-10" in out.output
    out = r.invoke(cli, ["institution", "show", "course", "BIOCHEM 3380"])
    assert "9313" in out.output
    letter = tmp_path / "letter.txt"
    letter.write_text("To the Dean of Science, Robert Wrong.\n")
    out = r.invoke(cli, ["institution", "check", str(letter)])
    assert out.exit_code == 1 and out.output.startswith("Fix") and "Charles Example" in out.output
    letter.write_text("To Charles Example, Dean of Science.\n")
    out = r.invoke(cli, ["institution", "check", str(letter)])
    assert out.exit_code == 0 and out.output.startswith("Correct")


def test_cli_without_a_pack_says_so(monkeypatch, tmp_path):
    from murmurent.cli import cli

    monkeypatch.setenv("MURMURENT_INSTITUTION_ROOT", str(tmp_path / "none"))
    monkeypatch.delenv("MURMURENT_INSTITUTION_PACK", raising=False)
    out = CliRunner().invoke(cli, ["institution", "validate"])
    assert out.exit_code == 2 and "No institution pack found" in out.output


def test_cli_init_scaffolds_a_pack(tmp_path):
    from murmurent.cli import cli

    out = CliRunner().invoke(cli, ["institution", "init", "acme", "--name", "Acme", "--domain", "acme.com",
                                   "--seed-thesis", "--root", str(tmp_path)])
    assert out.exit_code == 0 and (tmp_path / "acme/procedures/thesis_examination.yaml").is_file()
    pack = inst.load_pack(tmp_path / "acme")
    problems = inst.validate_pack(pack)
    # The seed's sources are Western's; a new centre's domains do not admit them, and validate says so.
    assert problems and all("outside the pack's domains" in p for p in problems)


# --------------------------------------------------------------------------- #
# The pack as memory: learn, recall, verify on read, crawl lookup (issue #291, Mike's review)
# --------------------------------------------------------------------------- #

RULE_PAGE = "<html><title>Exams</title><body>If a department prints its own papers they must reach the Registrar at least seven days prior to the scheduled examination.</body></html>"


def _fetcher(pages: dict[str, str]):
    def f(url, data):
        if url not in pages:
            raise inst.PackError(f"could not read {url}: 404")
        return pages[url]
    return f


def test_learn_fact_needs_the_page_to_state_it_and_recall_finds_it(pack):
    src = "https://www.example.edu/exams.html"
    fetcher = _fetcher({src: RULE_PAGE})
    with pytest.raises(inst.PackError):
        inst.learn_fact(pack, question="exam printing deadline", answer="ten days before",
                        source=src, fetcher=fetcher, today=date(2026, 11, 7))
    entry = inst.learn_fact(pack, question="When must printed exams reach the Registrar?",
                            answer="At least seven days before the exam.",
                            evidence="at least seven days prior to the scheduled examination",
                            source=src, fetcher=fetcher, today=date(2026, 11, 7))
    assert entry["date_read"] == "2026-11-07"
    again = inst.load_pack(pack.root)
    assert len(again.learned) == 1 and (pack.root / inst.FACTS_FILE).exists()
    found = inst.recall(again, "printed exams registrar")
    assert found and found[0]["kind"] == "fact"
    assert any(f.kind == "fact" for f in again.facts())
    with pytest.raises(inst.PackError):
        inst.learn_fact(pack, question="q", answer="a", source="https://elsewhere.org/p", fetcher=fetcher)


def test_learn_office_replaces_and_refuses_an_unstated_person(pack):
    src = "https://www.example.edu/edi/team.html"
    fetcher = _fetcher({src: "<html><body>Associate Vice-President (EDI): Dr. A. Person, edi@example.edu</body></html>"})
    with pytest.raises(inst.PackError):
        inst.learn_office(pack, office="EDI office", person="Someone Else", source=src, fetcher=fetcher)
    e = inst.learn_office(pack, office="EDI office", person="A. Person", title="Associate Vice-President (EDI)",
                          email="edi@example.edu", source=src, fetcher=fetcher, today=date(2026, 11, 7))
    assert e["email"] == "edi@example.edu"
    e2 = inst.learn_office(pack, office="EDI office", person="A. Person", source=src, fetcher=fetcher)
    again = inst.load_pack(pack.root)
    assert sum(1 for o in again.offices if o["office"] == "EDI office") == 1


def test_verify_on_read_restamps_or_reports_change(pack):
    src = "https://www.example.edu/exams.html"
    fetcher = _fetcher({src: RULE_PAGE})
    inst.learn_fact(pack, question="q1", answer="seven days", evidence="seven days prior", source=src,
                    fetcher=fetcher, today=date(2026, 1, 1))
    fact = next(f for f in pack.facts() if f.kind == "fact")
    assert inst.needs_verify(pack, fact, today=date(2026, 11, 7))
    ch = inst.verify_fact(pack, fact, fetcher=fetcher, today=date(2026, 11, 7))
    assert ch.status == "confirmed" and fact.data["date_read"] == "2026-11-07"
    assert inst.needs_verify(pack, fact, today=date(2026, 11, 7))        # default: re-read every time
    pack.meta["verify_after_days"] = 30
    assert not inst.needs_verify(pack, fact, today=date(2026, 11, 7))    # unless the pack allows an age
    changed = _fetcher({src: "<html><body>Papers must reach the Registrar ten days before.</body></html>"})
    ch2 = inst.verify_fact(pack, fact, fetcher=changed, today=date(2026, 12, 1))
    assert ch2.status == "changed" and fact.data["date_read"] == "2026-11-07"


def test_lookup_crawls_from_the_hub_inside_the_domains(pack):
    pack.meta["lookup"] = {"pages": ["https://www.example.edu/a-z.html"]}
    pages = {
        "https://www.example.edu/a-z.html": '<a href="https://www.example.edu/edi/">Equity, Diversity and Inclusion</a>'
                                            '<a href="https://other.org/edi">Elsewhere</a>',
        "https://www.example.edu/edi/": '<title>EDI office</title><a href="team.html">Our team</a>',
        "https://www.example.edu/edi/team.html": "<title>Our team</title><body>The Director of the EDI office is Dr. B.</body>",
    }
    hits = inst.lookup(pack, "who is the head of the EDI office", fetcher=_fetcher(pages))
    assert hits and hits[0].url == "https://www.example.edu/edi/team.html"
    assert "Director" in hits[0].snippet
    assert all("other.org" not in h.url for h in hits)


def test_cli_recall_learn_verify_and_show_fact(pack_dir, tmp_path, monkeypatch):
    from murmurent.cli import cli
    src = "https://www.example.edu/exams.html"
    monkeypatch.setattr(inst, "fetch_text", lambda u, d=None, **k: RULE_PAGE if u == src else (_ for _ in ()).throw(inst.PackError("404")))
    r = CliRunner()
    out = r.invoke(cli, ["institution", "recall", "exam printing", "--pack", str(pack_dir)])
    assert out.exit_code == 1 and "nothing remembered" in out.output
    out = r.invoke(cli, ["institution", "learn", "When must printed exams reach the Registrar?", "--answer",
                         "Seven days before.", "--evidence", "seven days prior", "--source", src, "--pack", str(pack_dir)])
    assert out.exit_code == 0, out.output
    out = r.invoke(cli, ["institution", "recall", "printed exams", "--pack", str(pack_dir)])
    assert out.exit_code == 0 and "Seven days before." in out.output
    out = r.invoke(cli, ["institution", "verify", "printed exams", "--pack", str(pack_dir)])
    assert out.exit_code == 0 and "CONFIRMED" in out.output
    out = r.invoke(cli, ["institution", "show", "fact", "registrar", "--pack", str(pack_dir)])
    assert out.exit_code == 0 and "exams.html" in out.output


# --------------------------------------------------------------------------- #
# Policies: a syllabus against the institution's rules (Mike's review, 2026-11-07)
# --------------------------------------------------------------------------- #

SYLLABUS = """# A course, Fall 2026
Term: 10 September to 9 December 2026.
| Assessment | Date | Weight |
| Quiz 1 | 1 October 2026 | 5% |
| Quiz 2 | 3 December 2026 | 15% |
| Lab report 2 (new, announced 20 November 2026) | 8 December 2026 | 15% |
| Final examination | December examination period | 30% |
"""
POLICY_PAGE = "<html><body><h3>Scheduling Tests</h3>Tests for one-term courses may not be scheduled during the last 3 weeks of classes in the term.</body></html>"


def test_parse_assessments_reads_names_dates_weights_and_announcements():
    items = inst.parse_assessments(SYLLABUS)
    names = [a.name for a in items]
    assert names[:2] == ["Quiz 1", "Quiz 2"]
    q2 = items[1]
    assert q2.when == date(2026, 12, 3) and q2.weight == 15 and q2.is_test
    lab = items[2]
    assert lab.announced == date(2026, 11, 20) and lab.when == date(2026, 12, 8) and not lab.is_test
    assert items[3].is_final and items[3].when is None


def test_announcement_date_without_a_year_takes_the_assessment_year():
    items = inst.parse_assessments("| Lab report 2 (new, announced 20 November) | 8 December 2026 | 15% |")
    assert items[0].announced == date(2026, 11, 20) and items[0].when == date(2026, 12, 8)


def test_learn_rule_needs_the_page_and_check_syllabus_reports_fix_correct_unknown(pack):
    src = "https://www.example.edu/calendar/exams.html"
    fetcher = _fetcher({src: POLICY_PAGE})
    with pytest.raises(inst.PackError):
        inst.learn_rule(pack, policy="course_outlines", rule_id="x", says="no quiz over 5% in the last two weeks",
                        source=src, fetcher=fetcher)
    inst.learn_rule(pack, policy="course_outlines", rule_id="tests_last_3_weeks",
                    says="Tests for one-term courses may not be scheduled during the last 3 weeks of classes in the term.",
                    source=src, heading="Scheduling Tests", check={"kind": "no_tests_in_last_weeks", "weeks": 3},
                    fetcher=fetcher, today=date(2026, 11, 7))
    inst.learn_rule(pack, policy="course_outlines", rule_id="no_new_6_weeks", says="no new assignments in the last six weeks",
                    source=src, check={"kind": "no_new_assignments_in_last_weeks", "weeks": 6}, confirm=False)
    again = inst.load_pack(pack.root)
    assert "course_outlines" in again.policies and (pack.root / "policies" / "course_outlines.yaml").exists()
    assert any(f.kind == "rule" for f in again.facts())
    findings = inst.check_syllabus(again, SYLLABUS, "course_outlines")
    by = {(f.verdict, f.what): f.detail for f in findings}
    assert ("Correct", "Quiz 1") in by
    assert ("Fix", "Quiz 2") in by and "last 3 weeks" in by[("Fix", "Quiz 2")] and "read 2026-11-07" in by[("Fix", "Quiz 2")]
    assert ("Fix", "Lab report 2") in by and "announced 2026-11-20" in by[("Fix", "Lab report 2")]
    assert inst.check_verdict(findings) == "Fix"
    no_term = inst.check_syllabus(again, SYLLABUS.replace("Term: 10 September to 9 December 2026.", ""), "course_outlines")
    assert all(f.verdict == "Unknown" for f in no_term)


def test_cli_check_with_policy(pack_dir, tmp_path):
    from murmurent.cli import cli
    r = CliRunner()
    out = r.invoke(cli, ["institution", "learn-rule", "course_outlines", "--id", "t3", "--says",
                         "Tests for one-term courses may not be scheduled during the last 3 weeks of classes in the term.",
                         "--source", "https://www.example.edu/calendar/exams.html", "--check-kind", "no_tests_in_last_weeks",
                         "--weeks", "3", "--no-confirm", "--pack", str(pack_dir)])
    assert out.exit_code == 0, out.output
    syl = tmp_path / "syllabus.md"; syl.write_text(SYLLABUS)
    out = r.invoke(cli, ["institution", "check", str(syl), "--policy", "course_outlines", "--pack", str(pack_dir)])
    assert out.exit_code == 1 and "Fix: Quiz 2" in out.output and "Correct: Quiz 1" in out.output

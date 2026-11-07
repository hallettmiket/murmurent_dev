"""
Purpose: Tests for the queryable paper package and the thesis composed from
         paper packages (issue #284): manifests, checks, builds, the defence
         talk, the Western paperwork checklist, and the CLI.
Author: Mike Hallett (with Claude Code)
Date: 2026-11-06
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from murmurent.core import paper_package as pp

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
PAPER_EX = EXAMPLES / "paper_example"
THESIS_EX = EXAMPLES / "thesis_example"


@pytest.fixture()
def examples(tmp_path, monkeypatch):
    """A writable copy of both example packages, side by side (the thesis
    points at ``../paper_example``)."""
    monkeypatch.delenv("MURMURENT_DATA_ROOT", raising=False)
    monkeypatch.delenv("MURMURENT_LAB_VM_ROOT", raising=False)
    root = tmp_path / "examples"
    shutil.copytree(EXAMPLES, root, ignore=shutil.ignore_patterns("build"))
    return root / "paper_example", root / "thesis_example"


def _edit(manifest: Path, fn) -> None:
    data = yaml.safe_load(manifest.read_text())
    fn(data)
    manifest.write_text(yaml.safe_dump(data))


# --------------------------------------------------------------------------- #
# The examples are clean
# --------------------------------------------------------------------------- #


def test_example_paper_has_no_findings(examples):
    paper, _ = examples
    rep = pp.check_paper(paper)
    assert rep.findings == [], rep.format()


def test_example_thesis_has_no_findings(examples):
    _, thesis = examples
    rep = pp.check_thesis(thesis)
    assert rep.findings == [], rep.format()


def test_example_evidence_scripts_run(examples):
    paper, thesis = examples
    for script in (paper / "exp/1_signal/run_all.py", thesis / "exp/3_metadata/run_all.py"):
        proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
    assert (paper / "build/results.tsv").read_text().startswith("measure\tvalue")
    assert "country" in (thesis / "build/country_means.tsv").read_text()


# --------------------------------------------------------------------------- #
# Paper checks
# --------------------------------------------------------------------------- #


def test_paper_check_catches_missing_source_code_and_figure(examples):
    paper, _ = examples
    (paper / "exp/1_signal/run_all.py").unlink()
    _edit(paper / "paper.yaml", lambda d: d["claims"][0].update(figure="fig:nope"))
    rep = pp.check_paper(paper)
    msgs = [f.message for f in rep.errors]
    assert any("code path exp/1_signal/run_all.py does not exist" in m for m in msgs)
    assert any("figure label `fig:nope` is not defined" in m for m in msgs)
    (paper / "main.tex").unlink()
    rep = pp.check_paper(paper)
    assert any("main.tex does not exist" in f.message for f in rep.errors)


def test_paper_check_missing_data_and_duplicate_ids(examples):
    paper, _ = examples

    def dup(d):
        d["claims"].append(dict(d["claims"][0], data=["data/missing.csv"]))

    _edit(paper / "paper.yaml", dup)
    rep = pp.check_paper(paper)
    msgs = [f.message for f in rep.errors]
    assert "duplicate claim id" in msgs
    assert any("data/missing.csv does not exist" in m for m in msgs)


def test_paper_no_claims_is_a_warning_not_an_error(examples):
    paper, _ = examples
    _edit(paper / "paper.yaml", lambda d: d.update(claims=[]))
    rep = pp.check_paper(paper)
    assert rep.errors == []
    assert any("not re-runnable" in f.message for f in rep.warnings)


def test_protected_paper_may_not_bundle_data(examples):
    paper, _ = examples
    _edit(paper / "paper.yaml", lambda d: d.update(sensitivity="protected"))
    rep = pp.check_paper(paper)
    assert any("protected data must not be bundled" in f.message for f in rep.errors)
    # `clinical` is the old name and means the same thing.
    _edit(paper / "paper.yaml", lambda d: d.update(sensitivity="clinical"))
    assert any("protected data must not be bundled" in f.message for f in pp.check_paper(paper).errors)


def test_data_root_references_warn_when_root_unset_and_check_when_set(examples, monkeypatch, tmp_path):
    paper, _ = examples
    _edit(paper / "paper.yaml", lambda d: d["claims"][0].update(data=["append_only/proj/1_signal/x.csv"]))
    rep = pp.check_paper(paper)
    assert rep.errors == []
    assert any("data root, which is not set" in f.message for f in rep.warnings)
    root = tmp_path / "root"
    monkeypatch.setenv("MURMURENT_DATA_ROOT", str(root))
    rep = pp.check_paper(paper)
    assert any("does not exist under the data root" in f.message for f in rep.warnings)
    (root / "append_only/proj/1_signal").mkdir(parents=True)
    (root / "append_only/proj/1_signal/x.csv").write_text("a\n")
    assert pp.check_paper(paper).findings == []


def test_published_without_doi_warns(examples):
    paper, _ = examples
    _edit(paper / "paper.yaml", lambda d: d.update(status="published"))
    assert any("no `doi:`" in f.message for f in pp.check_paper(paper).warnings)


def test_paper_init_scaffolds_and_fails_check_until_filled(tmp_path):
    target = tmp_path / "my_paper"
    written = pp.init_paper(target, title="A title", author="A. Author", lab="mh")
    names = {p.relative_to(target).as_posix() for p in written}
    assert {"paper.yaml", "main.tex", "CLAUDE.md", "queries/README.md", ".murmurent.yaml"} <= names
    assert "lab: mh" in (target / ".murmurent.yaml").read_text()
    rep = pp.check_paper(target)
    assert any("missing `text:`" in f.message for f in rep.errors)
    # Running init again never overwrites.
    (target / "main.tex").write_text("kept")
    assert pp.init_paper(target, title="x") == []
    assert (target / "main.tex").read_text() == "kept"


# --------------------------------------------------------------------------- #
# Thesis checks
# --------------------------------------------------------------------------- #


def test_thesis_needs_one_intro_one_conclusion_and_a_middle(examples):
    _, thesis = examples
    _edit(thesis / "thesis.yaml", lambda d: d.update(chapters=[d["chapters"][1]]))
    msgs = [f.message for f in pp.check_thesis(thesis).errors]
    assert any("exactly one chapter of kind `introduction`" in m for m in msgs)
    assert any("exactly one chapter of kind `conclusion`" in m for m in msgs)


def test_thesis_reports_its_papers_findings_with_a_prefix(examples):
    paper, thesis = examples
    (paper / "exp/1_signal/run_all.py").unlink()
    rep = pp.check_thesis(thesis)
    assert any(f.where.startswith("chapter 2 (../paper_example) >") for f in rep.errors)


def test_published_paper_needs_permission(examples):
    paper, thesis = examples
    _edit(paper / "paper.yaml", lambda d: d.update(status="published", doi="10.1/x"))
    rep = pp.check_thesis(thesis)
    assert any("copyright release" in f.message for f in rep.errors)
    (thesis / "permissions/paper_example.pdf").write_bytes(b"%PDF")
    _edit(thesis / "thesis.yaml", lambda d: d["chapters"][1].update(permission="permissions/paper_example.pdf"))
    assert not any("copyright release" in f.message for f in pp.check_thesis(thesis).errors)


def test_lay_summary_and_abstract_word_limits(examples):
    _, thesis = examples
    (thesis / "front/lay_summary.tex").write_text("word " * 351)
    rep = pp.check_thesis(thesis)
    assert any("lay summary is 351 words" in f.message for f in rep.errors)
    (thesis / "front/lay_summary.tex").write_text("\\textbf{bold} " + "word " * 349)
    assert not any("lay summary" in f.message for f in pp.check_thesis(thesis).errors)


def test_genai_statement_is_required(examples):
    _, thesis = examples
    _edit(thesis / "thesis.yaml", lambda d: d["front"].pop("genai_statement"))
    assert any("front.genai_statement" in f.message for f in pp.check_thesis(thesis).errors)


def test_coauthored_paper_needs_coauthorship_statement(examples):
    _, thesis = examples
    _edit(thesis / "thesis.yaml", lambda d: d["front"].pop("coauthorship"))
    assert any("front.coauthorship" in f.message for f in pp.check_thesis(thesis).errors)


def test_protected_paper_raises_thesis_sensitivity(examples):
    paper, thesis = examples
    _edit(paper / "paper.yaml", lambda d: d.update(sensitivity="protected", claims=[]))
    rep = pp.check_thesis(thesis)
    assert any("raise the thesis sensitivity" in f.message for f in rep.errors)


def test_monograph_chapter_claims_are_checked(examples):
    _, thesis = examples
    _edit(thesis / "thesis.yaml", lambda d: d["chapters"][2]["claims"][0].update(code="exp/none.py"))
    rep = pp.check_thesis(thesis)
    assert any(f.where == "chapter 3 claim c3.1" and "exp/none.py does not exist" in f.message
               for f in rep.errors)


def test_thesis_init_scaffolds(tmp_path):
    target = tmp_path / "my_thesis"
    written = pp.init_thesis(target, title="T", candidate="C. Andidate")
    names = {p.relative_to(target).as_posix() for p in written}
    assert {"thesis.yaml", "front/lay_summary.tex", "chapters/01_introduction.tex", "CLAUDE.md"} <= names
    rep = pp.check_thesis(target)
    # A fresh scaffold has an introduction and a conclusion but nothing between.
    assert any("at least one `paper` or `chapter`" in f.message for f in rep.errors)


# --------------------------------------------------------------------------- #
# Builds
# --------------------------------------------------------------------------- #


def test_build_paper_writes_claim_map_and_skips_pdf_without_latexmk(examples, monkeypatch):
    paper, _ = examples
    monkeypatch.setattr(pp.shutil, "which", lambda name: None)
    done = pp.build_paper(paper, pdf=True)
    assert "wrote build/claim_map.md" in done
    assert any(d.startswith("PDF skipped") for d in done)
    text = (paper / "build/claim_map.md").read_text()
    assert "**c1**" in text and "exp/1_signal/run_all.py" in text and "fig:signal" in text


def test_paper_body_for_thesis_strips_title_abstract_and_bibliography(tmp_path):
    src = tmp_path / "p.tex"
    src.write_text(
        "\\documentclass{article}\\title{T}\\author{A}\n\\begin{document}\\maketitle\n"
        "\\begin{abstract}gone\\end{abstract}\n\\section{Intro}kept\n"
        "\\bibliography{refs}\n\\end{document}\n"
    )
    body = pp.paper_body_for_thesis(src)
    assert "kept" in body
    for gone in ("gone", "\\maketitle", "\\bibliography", "\\title", "documentclass"):
        assert gone not in body
    frag = tmp_path / "f.tex"
    frag.write_text("\\section{A}\nfragment\n")
    assert pp.paper_body_for_thesis(frag).strip() == "\\section{A}\nfragment"


def test_build_thesis_assembles_main_tex_and_combined_claim_map(examples, monkeypatch):
    _, thesis = examples
    monkeypatch.setattr(pp.shutil, "which", lambda name: None)
    done = pp.build_thesis(thesis, pdf=False)
    assert "wrote build/main.tex" in done
    tex = (thesis / "build/main.tex").read_text()
    for chapter in ("Introduction", "Serum enlarges colonies", "Colony size and country of origin", "Conclusion"):
        assert f"\\chapter{{{chapter}" in tex
    assert "Summary for Lay Audience" in tex and "Generative Artificial Intelligence" in tex and "Co-Authorship" in tex
    chapter2 = (thesis / "build/chapters/02_paper_example.tex").read_text()
    assert "\\begin{abstract}" not in chapter2 and "\\section{Results}" in chapter2
    cmap = (thesis / "build/claim_map.md").read_text()
    assert "**c1**" in cmap and "**c3.1**" in cmap and "## Chapter 2" in cmap and "## Chapter 3" in cmap


@pytest.mark.skipif(shutil.which("latexmk") is None, reason="latexmk not installed")
def test_build_thesis_pdf_when_latexmk_present(examples):
    _, thesis = examples
    done = pp.build_thesis(thesis, pdf=True)
    assert "wrote build/main.pdf" in done, done
    assert (thesis / "build/main.pdf").stat().st_size > 1000


# --------------------------------------------------------------------------- #
# The talk
# --------------------------------------------------------------------------- #


def test_talk_plan_one_slide_per_claim_and_the_minutes_add_up(examples):
    _, thesis = examples
    slides = pp.talk_plan(thesis, minutes=20)
    claim_slides = [s for s in slides if s.section.startswith("chapter")]
    assert [s.title for s in claim_slides] == [
        "Colonies grown in serum are larger than controls, and the difference holds under permutation.",
        "Colony size does not differ by country of origin in the synthetic compendium.",
    ]
    assert claim_slides[0].figure == "fig:signal" and "exp/1_signal/run_all.py" in claim_slides[0].evidence
    assert abs(sum(s.minutes for s in slides) - 20) < 1e-6
    assert slides[0].section == "title" and slides[-1].section == "acknowledgements"


def test_talk_plan_flags_too_many_claims(examples):
    _, thesis = examples

    def many(d):
        d["chapters"][2]["claims"] = [dict(id=f"c{i}", text=f"claim {i}", code="exp/3_metadata/run_all.py")
                                      for i in range(30)]

    _edit(thesis / "thesis.yaml", many)
    slides = pp.talk_plan(thesis, minutes=20)
    plan = pp.format_talk_plan(slides, minutes=20)
    assert "Too many result slides" in plan


def test_build_talk_writes_beamer_and_plan(examples, monkeypatch):
    _, thesis = examples
    monkeypatch.setattr(pp.shutil, "which", lambda name: None)
    done = pp.build_talk(thesis, minutes=15)
    assert "wrote build/talk.tex" in done and "wrote build/talk_plan.md" in done
    tex = (thesis / "build/talk.tex").read_text()
    assert "\\documentclass[aspectratio=169]{beamer}" in tex
    assert "% figure fig:signal" in tex and "\\note{" in tex
    assert "15 minutes" in (thesis / "build/talk_plan.md").read_text()


# --------------------------------------------------------------------------- #
# Paperwork
# --------------------------------------------------------------------------- #


def test_working_days_before_skips_weekends():
    friday = date(2027, 4, 16)
    assert pp.working_days_before(friday, 5) == date(2027, 4, 9)
    assert pp.working_days_before(friday, 25) == date(2027, 3, 12)


def test_paperwork_prefills_from_manifest_and_computes_deadlines(examples):
    _, thesis = examples
    text = pp.paperwork(thesis)
    assert "| Candidate | A. Candidate |" in text
    assert "Proposed defence: **2027-04-16**" in text
    assert "**2027-03-12**" in text          # 25 working days before
    assert "**2027-04-09**" in text          # examiners' reports, 5 working days before
    assert "- [x] 1 external examiner(s): 1 listed" in text
    assert "- [x] 2 program examiner(s): 2 listed" in text
    assert "- [x] Proposed Examiner Form" in text
    assert "- [x] `murmurent thesis check` passes (0 error(s)" in text
    assert "- [ ] Thesis PDF built" in text
    assert "Veritas" in text and "Non-exclusive licence" in text


def test_paperwork_flags_missing_examiners_contact_details_and_no_date(examples):
    _, thesis = examples
    (thesis / "front/acknowledgements.tex").write_text("Write to me at someone@example.org")

    def strip(d):
        d["examiners"] = d["examiners"][:1]
        d["defence"] = {}
        d["front"]["acknowledgements"] = "front/acknowledgements.tex"

    _edit(thesis / "thesis.yaml", strip)
    text = pp.paperwork(thesis)
    assert "- [ ] 2 program examiner(s): 0 listed" in text
    assert "No `defence.date:`" in text
    assert "found in: acknowledgements.tex" in text


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def test_cli_check_build_talk_paperwork(examples, monkeypatch):
    from murmurent.cli import cli

    paper, thesis = examples
    monkeypatch.setattr(pp.shutil, "which", lambda name: None)
    r = CliRunner()
    assert r.invoke(cli, ["thesis", "check", str(thesis)]).exit_code == 0
    assert r.invoke(cli, ["paper", "check", str(paper)]).exit_code == 0
    out = r.invoke(cli, ["thesis", "build", str(thesis), "--pdf"])
    assert out.exit_code == 0 and "PDF skipped" in out.output
    assert r.invoke(cli, ["thesis", "talk", str(thesis), "--minutes", "12"]).exit_code == 0
    assert "12 minutes" in (thesis / "build/talk_plan.md").read_text()
    assert r.invoke(cli, ["thesis", "paperwork", str(thesis)]).exit_code == 0
    assert (thesis / "build/paperwork.md").is_file()
    # --strict turns a warning into a failure; a failing check exits 1.
    (thesis / "queries").rename(thesis / "q_moved")
    assert r.invoke(cli, ["thesis", "check", str(thesis)]).exit_code == 0
    assert r.invoke(cli, ["thesis", "check", str(thesis), "--strict"]).exit_code == 1
    (paper / "main.tex").unlink()
    out = r.invoke(cli, ["paper", "check", str(paper)])
    assert out.exit_code == 1 and "main.tex does not exist" in out.output


def test_cli_finds_package_from_inside_it(examples, monkeypatch):
    from murmurent.cli import cli

    _, thesis = examples
    monkeypatch.chdir(thesis / "chapters")
    out = CliRunner().invoke(cli, ["thesis", "check"])
    assert out.exit_code == 0, out.output
    monkeypatch.chdir(thesis.parent)
    out = CliRunner().invoke(cli, ["paper", "check"])
    assert out.exit_code == 2 and "No paper.yaml here or above" in out.output


def test_cli_init(tmp_path):
    from murmurent.cli import cli

    out = CliRunner().invoke(cli, ["paper", "init", str(tmp_path / "p"), "--title", "T", "--lab", "mh"])
    assert out.exit_code == 0 and (tmp_path / "p/paper.yaml").is_file()
    out = CliRunner().invoke(cli, ["thesis", "init", str(tmp_path / "t"), "--title", "T", "--candidate", "C"])
    assert out.exit_code == 0 and (tmp_path / "t/thesis.yaml").is_file()


# --------------------------------------------------------------------------- #
# Adopting a monolithic thesis
# --------------------------------------------------------------------------- #

MONOLITH = r"""\documentclass[12pt]{report}
\usepackage{graphicx}
\addbibresource{refs.bib}
\title{A Thesis Title}
\author{C. Andidate}
\begin{document}
\pagenumbering{roman}
\chapter*{Abstract}
\addcontentsline{toc}{chapter}{Abstract}
Short abstract.
\chapter*{Summary for Lay Audience}
Lay words.
\chapter*{Co-Authorship Statement}
Mine.
\chapter*{Acknowledgements}
Thanks.
\tableofcontents
\chapter{Introduction}
Why.
\chapter{Background: the field}
\begin{figure}\caption{From elsewhere. Not mine.}\label{fig:bg}\end{figure}
\chapter{Results: the thing}
\section{A}
\begin{figure}
  \includegraphics{Figures/a.png}
  \caption{Colonies are bigger on serum. Second sentence.}
  \label{fig:a}
\end{figure}
\chapter{Discussion}
So.
\chapter{Methods}
How. \includegraphics{Figures/b.png}
\chapter*{Appendix stuff}
Extra.
\printbibliography
\end{document}
"""


def test_adopt_splits_front_matter_chapters_and_drafts_claims(tmp_path, monkeypatch):
    monkeypatch.setattr(pp.shutil, "which", lambda name: None)
    src = tmp_path / "src"
    (src / "Figures").mkdir(parents=True)
    (src / "Figures/a.png").write_bytes(b"png")
    (src / "refs.bib").write_text("@misc{x, title={y}}")
    (src / "thesis.tex").write_text(MONOLITH)
    target = tmp_path / "pkg"
    done = pp.adopt_thesis(src / "thesis.tex", target)
    m = yaml.safe_load((target / "thesis.yaml").read_text())
    assert m["title"] == "A Thesis Title" and m["candidate"]["name"] == "C. Andidate"
    assert m["preamble"] == "preamble.tex" and m["bibliography_backend"] == "biblatex"
    assert m["bibliography"] == "refs.bib" and (target / "refs.bib").is_file()
    kinds = [(c["kind"], c["title"]) for c in m["chapters"]]
    assert kinds == [("introduction", "Introduction"), ("chapter", "Background: the field"),
                     ("chapter", "Results: the thing"), ("conclusion", "Discussion"), ("chapter", "Methods")]
    assert m["chapters"][1]["claims"] == []                       # background: no drafts
    claims = m["chapters"][2]["claims"]
    assert claims == [{"id": "c3.1", "text": "Colonies are bigger on serum", "where": "",
                       "figure": "fig:a", "code": "", "data": []}]
    assert m["appendices"] == [{"title": "Appendix stuff", "source": "appendices/appendix_stuff.tex"}]
    assert (target / "front/abstract.tex").read_text().strip() == "Short abstract."
    assert "addcontentsline" not in (target / "front/abstract.tex").read_text()
    assert (target / "front/genai_statement.tex").is_file()      # stub, flagged in `done`
    assert any("genai_statement.tex left as a stub" in d for d in done)
    assert (target / "Figures/a.png").is_file() and not (target / "Figures/b.png").exists()
    assert "\\title" not in (target / "preamble.tex").read_text()
    assert "\\documentclass[12pt]{report}" in (target / "preamble.tex").read_text()
    # The source folder is untouched and the package checks with warnings only.
    assert (src / "thesis.tex").read_text() == MONOLITH
    rep = pp.check_thesis(target)
    assert rep.errors == [], rep.format()
    assert any("conclusion is not the last chapter" in f.message for f in rep.warnings)
    # Build uses the kept preamble and biblatex.
    pp.build_thesis(target)
    tex = (target / "build/main.tex").read_text()
    assert "\\input{" in tex and "preamble.tex}" in tex and "\\printbibliography" in tex
    assert "\\documentclass[12pt,oneside]" not in tex


def test_degree_level_and_masters_paperwork(examples):
    assert pp.degree_level("Doctor of Philosophy") == "doctoral"
    assert pp.degree_level("Master of Science") == "masters"
    assert pp.degree_level("MSc") == "masters"
    _, thesis = examples
    _edit(thesis / "thesis.yaml", lambda d: d.update(degree="Master of Science"))
    text = pp.paperwork(thesis)
    assert "**2027-03-26**" in text            # 15 working days before 2027-04-16
    assert "Master's boards" in text and "Abstract (at most 150 words)" in text


def test_cli_adopt(tmp_path):
    from murmurent.cli import cli

    src = tmp_path / "thesis.tex"
    src.write_text(MONOLITH)
    out = CliRunner().invoke(cli, ["thesis", "adopt", str(src), str(tmp_path / "pkg"), "--lab", "mh"])
    assert out.exit_code == 0, out.output
    assert "wrote thesis.yaml: 5 chapters, 1 draft claims" in out.output
    assert "lab: mh" in (tmp_path / "pkg/.murmurent.yaml").read_text()


def test_large_bibliography_is_trimmed_to_cited_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(pp.shutil, "which", lambda name: None)
    monkeypatch.setattr(pp, "BIB_TRIM_BYTES", 10)
    src = tmp_path / "src"
    src.mkdir()
    (src / "refs.bib").write_text(
        "@comment{ignored}\n@article{used_one,\n title={A {nested} title},\n year={2020}\n}\n"
        "@book{unused,\n title={No}\n}\n@misc{used_two, title={B}}\n"
    )
    (src / "thesis.tex").write_text(MONOLITH.replace("Why.", "Why \\cite{used_one, missing} and \\parencite[p.~3]{used_two}."))
    target = tmp_path / "pkg"
    pp.adopt_thesis(src / "thesis.tex", target)
    done = pp.build_thesis(target)
    note = next(d for d in done if d.startswith("wrote build/cited.bib"))
    assert "2 of 3 cited keys" in note and "not found: missing" in note
    cited = (target / "build/cited.bib").read_text()
    assert "@article{used_one" in cited and "@misc{used_two" in cited and "unused" not in cited
    assert "nested" in cited
    pre = (target / "build/preamble.tex").read_text()
    assert "\\addbibresource{" + str((target / "build/cited.bib").resolve()) + "}" in pre
    assert pre.count("\\addbibresource") == 1
    assert str((target / "build/preamble.tex").resolve()) in (target / "build/main.tex").read_text()


def test_cite_keys_and_bib_entries():
    assert pp.cite_keys("\\cite{a,b} \\textcite[x][y]{c} \\nocite{*} \\autocite*{d}") == {"a", "b", "c", "d"}
    entries = pp.bib_entries("@string{x = {y}}\n@Article{k1,\n a={{b}}\n}\n@misc{k2, t={u}}")
    assert set(entries) == {"k1", "k2"} and entries["k1"].endswith("}")


def test_plain_title_unescapes_and_drops_comments():
    assert pp._plain_title(r"Strategy $\#0$ and {\em C.\ albicans} % note") == "Strategy #0 and C. albicans"
    assert pp._tex_escape(pp._plain_title(r"$\#0$")) == r"\#0"


def test_adopt_copies_figures_split_over_two_lines(tmp_path):
    src = tmp_path / "src"
    (src / "Figures").mkdir(parents=True)
    (src / "Figures/a.png").write_bytes(b"png")
    (src / "t.tex").write_text(MONOLITH.replace("\\includegraphics{Figures/a.png}",
                                                "\\includegraphics[width=1\\textwidth]\n  {Figures/a.png}"))
    pp.adopt_thesis(src / "t.tex", tmp_path / "pkg")
    assert (tmp_path / "pkg/Figures/a.png").is_file()


def test_trimmed_bibliography_unwraps_relax_initials(tmp_path, monkeypatch):
    monkeypatch.setattr(pp.shutil, "which", lambda name: None)
    monkeypatch.setattr(pp, "BIB_TRIM_BYTES", 10)
    src = tmp_path / "src"
    src.mkdir()
    (src / "refs.bib").write_text("@misc{used_one, author={Burgess, {\\relax CP} and Lee, A}}\n")
    (src / "thesis.tex").write_text(MONOLITH.replace("Why.", "Why \\cite{used_one}."))
    pp.adopt_thesis(src / "thesis.tex", tmp_path / "pkg")
    done = pp.build_thesis(tmp_path / "pkg")
    assert any("unwrapped 1 {\\relax ...}" in d for d in done)
    assert "Burgess, CP and Lee, A" in (tmp_path / "pkg/build/cited.bib").read_text()


def test_talk_puts_background_methods_and_supplementary_claims_in_backup(examples):
    _, thesis = examples

    def add(d):
        d["chapters"].insert(3, {"kind": "chapter", "title": "Methods", "source": "chapters/03_metadata.tex",
                                 "claims": [{"id": "m1", "text": "A methods figure", "figure": "fig:country",
                                             "code": "exp/3_metadata/run_all.py"}]})

    _edit(thesis / "thesis.yaml", add)
    slides = pp.talk_plan(thesis, minutes=20)
    assert slides[-1].section == "backup" and slides[-1].title == "A methods figure" and slides[-1].minutes == 0
    assert slides[-2].section == "acknowledgements"
    assert abs(sum(s.minutes for s in slides) - 20) < 1e-6
    assert all(s.section != "chapter 4" or s.title != "Methods" for s in slides)


def test_data_root_reference_falls_back_to_legacy_folder_names(tmp_path, monkeypatch):
    """A server whose data root still says raw/ and refined/ resolves the new names."""
    root = tmp_path / "lab_vm"
    (root / "refined" / "proj" / "exp").mkdir(parents=True)
    (root / "refined" / "proj" / "exp" / "out.csv").write_text("x\n")
    monkeypatch.setenv("MURMURENT_DATA_ROOT", str(root))
    path, kind = pp.resolve_data_ref(tmp_path, "append_only/proj/exp/out.csv")
    assert kind == "root" and path.exists()
    assert path == root / "refined" / "proj" / "exp" / "out.csv"
    missing, kind = pp.resolve_data_ref(tmp_path, "append_only/proj/exp/nope.csv")
    assert kind == "root" and not missing.exists()

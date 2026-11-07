"""The docent movie (short cut): quotes from agents/docent.md, and two exchanges shared with the long thesis movie."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import LAV

SPEC = AgentSpec(
    agent="docent",
    title="The docent",
    tagline="Guide to a paper or thesis package: every answer with a location",
    colour=LAV,
    icon="doc",
    intro=["This is the docent, the guide to a paper package or a thesis package. An examiner asks it "
           "questions; it answers with locations, and it logs every question."],
    does=[
        Quote("Every answer carries a location.", "location"),
        Quote("Absent is a full answer.", "Absent"),
        Quote("Re-run before you report a number.", "Re-run"),
        Quote("The PDF is the thesis of record.", "record"),
    ],
    does_narration=[
        "Its file sets the rules. Every answer carries a location: a section, a figure, a file. Absent is a "
        "full answer when the work does not address what was asked.",
        "It re-runs the code before it reports a number. And the PDF is the thesis of record: where the package "
        "disagrees, that is a finding."],
    refuses=[
        Quote("Speak for the work, the author or the examiner.", "speaks for"),
        Quote("Search the web.", "web"),
        Quote("Grade.", "Grade"),
        Quote("Change anything outside build/ and queries/.", "Change"),
    ],
    refuses_narration=[
        "It never speaks for the work, the author or the examiner. It never searches the web, because a thesis "
        "under examination is not public.",
        "It never grades: the adversary audits, the examiner decides. And it changes nothing outside the build "
        "and the query log."],
    examples=[
        Exchange("1", ["A real exchange, on the synthetic thesis example. The examiner asks where a result is "
                       "shown and whether it holds.",
                       "Located, with the chapter, the figure and the claim. The docent re-ran the script and "
                       "reports what it printed, and names what the text does not say."],
                 [("read claim_map.md", True), ("open the PDF", True), ("re-run run_all.py", True)],
                 who="Examiner"),
        Exchange("2", ["Asked about something the thesis never addresses, it answers Absent, says what it "
                       "searched, and names the nearest thing the thesis does cover."],
                 [("search the package", True), ("fill the gap", False)], who="Examiner"),
    ],
    prompt="open examples/thesis_example and ask the docent where claim c3.1 is made and whether it holds",
    give="The package folder. The docent infers whether you are the reader or the author from the question.",
    verdicts="Located / Absent / Ready, then the locations, the re-run output, and the log entry.",
    howto_narration=[
        "To use it, open the package in Claude Code and ask the docent in plain words. It works out from the "
        "question whether you are an examiner or the author, and never asks.",
        "The first line is the verdict: Located, Absent or Ready. Every question and answer is appended to the "
        "query log. The six-minute movie on thesis packages shows the whole workflow."],
    docs=["docs/paper_package.md"],
)

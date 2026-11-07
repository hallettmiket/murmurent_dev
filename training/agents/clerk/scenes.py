"""The clerk movie: narration, quotes from agents/clerk.md, and the real exchanges in transcript.md."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import SAND

SPEC = AgentSpec(
    agent="clerk",
    title="The clerk",
    tagline="Ask it anything about your institution; it reads the answer off the institution's own pages",
    colour=SAND,
    icon="cal",
    intro=["This is the clerk. Ask it anything about your institution: who runs an office, when an exam must "
           "be printed, what a procedure requires next. It reads the answer off the institution's own web "
           "pages, and tells you which page and when."],
    does=[
        Quote("You answer from the institution's own pages, and you say which page and when you read it.", "which page"),
        Quote("The pack (institution/<unique_name>/) is your memory, not your source of truth", "memory"),
        Quote("A remembered fact older than the pack's verify_after_days is re-read from its page before you rely on it", "re-read"),
        Quote("Check when you are handed a document", "Check"),
        Quote("Compute when you are asked for a date", "Compute"),
    ],
    does_narration=[
        "Its file has one rule above the others: it answers from the institution's own pages, and says which "
        "page and when it read it. What it finds goes into a folder called the pack, which is its memory: "
        "the question, the answer, the page, the date. Nobody fills it in beforehand.",
        "People change. A remembered fact older than a month is re-read from its page before the clerk relies "
        "on it, and a weekly refresh re-reads the rest. On top of that it checks a document against what it "
        "knows, and computes dates in working days."],
    refuses=[
        Quote("Never fill the gap from memory.", "from memory"),
        Quote("Name a person the pack does not name", "about a person"),
        Quote("Offer a date that falls on a holiday.", "holiday"),
        Quote("Edit a document or the pack by hand.", "Edit"),
    ],
    refuses_narration=[
        "What it never does: fill a gap from memory, or from a page outside the institution's own sites. "
        "When the institution's pages do not say, the answer is Unknown, with the nearest thing they do say.",
        "It says nothing about a person beyond the office, title, public email and campus address the "
        "institution publishes. It never offers a date that falls on a holiday. And it never edits a document "
        "or the pack by hand: the scribe writes, and the commands record what it read."],
    examples=[
        Exchange("1", ["A real run. A course instructor asks when the final exam for their course must be "
                       "printed, for the fall of twenty twenty-six. The clerk recalls, searches the "
                       "institution's own site, and reads the pages.",
                       "The answer names the rule, the page it came from, and the date it was read, and says "
                       "which part was read and which was computed. What it found is now remembered."],
                 [("recall", True), ("search uwo.ca", True), ("read the pages", True), ("learn", True)]),
        Exchange("2", ["Asked who runs the equity, diversity and inclusion office, it finds the office's own "
                       "page, reads it, records the office holder with the page and the date, and answers."],
                 [("recall", True), ("search uwo.ca", True), ("learn --office", True)]),
    ],
    prompt="ask the clerk when the final exam for BIOCHEM 3391 has to be printed this fall",
    give="The question, in your words. For a document, the file to check. For a date, what to count from. For another institution, another pack.",
    verdicts="Correct / Fix / Unknown. Every answer names the page and the date it was read; Unknown names the nearest thing the pages say.",
    howto_narration=[
        "To use it, type to Claude Code and name it: ask the clerk a question about the institution, to check a "
        "letter, or to count working days from a date. The first time, it looks the answer up; the next time, "
        "it remembers, and re-reads the page if that memory is more than a month old.",
        "The first line is the verdict: Correct, Fix or Unknown. Every answer names the page and the date. "
        "Another university, or a company, is another pack, and the same clerk."],
    docs=["docs/institution_pack.md", "institution/README.md"],
)

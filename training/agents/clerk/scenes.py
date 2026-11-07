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
           "be printed, whether a syllabus follows the rules. It reads the answer off the institution's own "
           "pages, and says which page and when."],
    does=[
        Quote("You answer from the institution's own pages, and you say which page and when you read it.", "which page"),
        Quote("The pack (institution/<unique_name>/) is your memory, not your source of truth", "memory"),
        Quote("A remembered fact is re-read from its page before you rely on it, every time", "re-read"),
    ],
    does_narration=[
        "Its file has one rule above the others: it answers from the institution's own pages, and says which "
        "page and when it read it. What it finds goes into a folder called the pack, which is its memory: "
        "the question, the answer, the page, the date. Nobody fills it in beforehand.",
        "People change, so a remembered fact is re-read from its page every time before the clerk relies "
        "on it: the memory says where to look, the page says what is true today."],
    refuses=[
        Quote("Never fill the gap from memory.", "from memory"),
        Quote("Name a person the pack does not name", "about a person"),
        Quote("Offer a date that falls on a holiday.", "holiday"),
        Quote("Edit a document or the pack by hand.", "Edit"),
    ],
    refuses_narration=[
        "It never fills a gap from memory or from a page outside the institution's own sites. When the "
        "pages do not say, the answer is Unknown, with the nearest thing they do say.",
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
        "it remembers where it read it, and reads that page again before answering.",
        "The first line is the verdict: Correct, Fix or Unknown, and every answer names the page and the "
        "date. Another university, or a company, is another pack and the same clerk."],
    directions=[
        ("ask the clerk to look over my syllabus for BIOCHEM 3391 against the university's rules on evaluation",
         "Each rule quoted as the institution's page words it, with source and date: a test in the last three weeks of classes, a new assignment introduced too late, as Fix, Correct or Unknown."),
        ("ask the clerk who the Graduate Chair of Biochemistry is and how to reach them",
         "The office holder, title and public email from the department's page, with the date it was read; remembered in the pack."),
        ("ask the clerk for 25 working days before 2027-03-26, skipping holidays",
         "The date, the weekday, and the holidays it skipped; a holiday is never offered."),
    ],
    directions_narration=[
        "Say what to check and against what: a syllabus against the university's rules on evaluation, with "
        "each rule quoted as the page words it; who holds an office; or a count of working days."],
    docs=["docs/institution_pack.md", "institution/README.md"],
)

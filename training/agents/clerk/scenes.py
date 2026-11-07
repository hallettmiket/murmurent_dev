"""The clerk movie: narration, quotes from agents/clerk.md, and the real exchanges in transcript.md."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import SAND

SPEC = AgentSpec(
    agent="clerk",
    title="The clerk",
    tagline="The institution expert: offices, deadlines, holidays, letterhead, from a pack it never leaves",
    colour=SAND,
    icon="cal",
    intro=["This is the clerk. It knows the institution: who holds which office, the holidays and term "
           "dates, the forms and deadlines of a procedure, the letterhead. And it knows them only from a pack."],
    does=[
        Quote("You answer only from the pack.", "only from the pack"),
        Quote("Every answer carries the source and the date read", "source and the date"),
        Quote("Check when you are handed a document", "Check"),
        Quote("Compute when you are asked for a date", "Compute"),
        Quote("Walk when you are asked what is next, which form, by when", "Walk"),
    ],
    does_narration=[
        "Its file has one rule above the others: it answers only from the pack, a folder of facts for one "
        "institution, each with its source and the date it was read. Every answer carries both.",
        "Three jobs. Check a document: is the person named as Dean the Dean. Compute a date in working days "
        "that never lands on a holiday. Walk a procedure to its next steps, with the form and the deadline."],
    refuses=[
        Quote("State an institutional fact that is not in the pack.", "not in the pack"),
        Quote("Name a person the pack does not name", "Name a person"),
        Quote("Offer a date that falls on a holiday.", "holiday"),
        Quote("Edit a document or the pack by hand.", "Edit"),
    ],
    refuses_narration=[
        "What it never does: state a fact that is not in the pack, from memory or from a search. Name a "
        "person the pack does not name, or say anything about one beyond the office, title, public email "
        "and campus address.",
        "Offer a date that falls on a holiday. Or edit a document or the pack by hand: the scribe writes, "
        "the bookworm keeps the pack, and a refresh command writes what it re-read."],
    examples=[
        Exchange("1", ["A real run, on a letter written for the movie with two office holders from years ago. "
                       "The member asks the clerk to check it before sending.",
                       "The verdict is Fix. Each finding names the office, who the pack says holds it, the source "
                       "page and the date it was read. The letter is not rewritten; that is the scribe's job."],
                 [("read the pack", True), ("institution check", True), ("rewrite the letter", False)]),
        Exchange("2", ["Asked for a deadline and the next steps, it counts working days backwards, skipping the "
                       "pack's holidays, and walks the thesis procedure from the defence date."],
                 [("institution date", True), ("institution walk", True)]),
    ],
    prompt="ask the clerk to check the addresses and office holders in letter_to_dean.md",
    give="The document to check, the date to count from, or the procedure to walk. For another university or a company, another pack.",
    verdicts="Correct / Fix / Unknown. Unknown names the nearest fact the pack holds, so you know where to look.",
    howto_narration=[
        "To use it, type to Claude Code and name it: ask the clerk to check a letter, to count working days "
        "from a date, or to walk a procedure. The pack for your institution lives in the deployment, not in "
        "the public release; a company is a different pack, not a different agent.",
        "The first line is the verdict: Correct, Fix or Unknown. Unknown names the nearest fact the pack "
        "holds. A fact older than the pack's limit says its age, and the bookworm refreshes it."],
    docs=["docs/institution_pack.md", "institution/README.md"],
)

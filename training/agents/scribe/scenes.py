"""The scribe movie: narration, quotes from agents/scribe.md, and the real exchange in transcript.md."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import SAND

SPEC = AgentSpec(
    agent="scribe",
    title="The scribe",
    tagline="Scientific writing in the house style, without touching a fact",
    colour=SAND,
    icon="pencil",
    intro=["This is the scribe. It writes and revises scientific text in the house style, a style built "
           "from the PI's own hand edits, and it never changes a fact."],
    does=[
        Quote("REVISE, when you are given text. Rewrite it to the guide.", "revise"),
        Quote("DRAFT, when you are given material (results, figures, tables, notes, earlier sections) and asked for a section.",
              "draft"),
        Quote("Cutting is the main move.", "cutting"),
        Quote("Touch only what needs changing.", "touches only"),
    ],
    does_narration=[
        "Two jobs, inferred from what you hand it. Revise, when you give it text: it rewrites to the guide. "
        "Draft, when you give it results, figures and notes and ask for a section.",
        "Cutting is the main move, because most of the PI's own edits are deletions. And it touches only "
        "what needs changing, so the diff shows real edits."],
    refuses=[
        Quote("Never change a fact, a number, a citation key, a \\label or a \\ref.", "fact"),
        Quote("Never rewrap a paragraph.", "rewrap"),
        Quote("Where a claim needs a reference you do not have, write [CITE: the claim].", "marked gap"),
        Quote("Returns text; never edits the manuscript source itself.", "manuscript"),
    ],
    refuses_narration=[
        "It never changes a fact, a number, a citation key or a label; something that looks wrong is flagged, "
        "not corrected. It never rewraps a paragraph.",
        "Where a claim needs a reference it does not have, it writes a marked gap rather than inventing one. "
        "And it returns text; it never edits the manuscript itself."],
    examples=[
        Exchange("1", ["A real run, on a passage written to be bad. The member asks for a revision in the "
                       "house style.",
                       "The verdict is Revised. Every number survives. Each change is listed with the rule it "
                       "follows, and the scribe asks a question it cannot answer: mean or median?"],
                 [("read scientific_writing.md", True), ("rewrite", True), ("list each change", True)]),
    ],
    prompt="ask the scribe to revise the Results section of main.tex, lines 120 to 160",
    give="The passage, or the results and notes for a draft, and which section of the paper it is for.",
    verdicts="Revised / Drafted / Gap, then the text and a list of changes with their rules.",
    howto_narration=[
        "To use it, type to Claude Code and name it: ask the scribe to revise a passage, or to draft a section "
        "from results and notes. Say which section of the paper it is for.",
        "The first line is the verdict: Revised, Drafted or Gap. Then the text, and the list of what changed and "
        "why. You paste it in; the scribe does not."],
    docs=["docs/scientific_writing.md"],
)

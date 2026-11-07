"""The lab oracle movie: narration, quotes from agents/lab_oracle.md, and the real exchanges in transcript.md."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import LAV

SPEC = AgentSpec(
    agent="lab_oracle",
    title="The lab oracle",
    tagline="What the whole lab has agreed on, read-only",
    colour=LAV,
    icon="folder",
    intro=["This is the lab oracle, the lab's shared, reviewed memory. It answers one question: "
           "what has the lab agreed on?"],
    does=[
        Quote("recall, cross-reference, summarize, and report provenance over the whole lab's reviewed knowledge",
              "recall"),
        Quote("You answer \"what has the lab agreed on?\"", "agreed on"),
        Quote("entries arrive via the murmurent oracle publish CLI after PI/peer review", "publish"),
    ],
    does_narration=[
        "Its file says what it covers: recall, cross-reference and summarize the lab's reviewed knowledge, "
        "with provenance. It answers what the lab has agreed on, and who published it.",
        "Entries arrive only through the publish command, after review. Nothing gets in by being said once."],
    refuses=[
        Quote("You never write.", "never write"),
        Quote("You are not the personal Oracle.", "personal"),
        Quote("You do not fetch literature or run analyses", "fetch"),
        Quote("You never improvise. If the lab has no entry, say \"the Lab Oracle has no entry on <X>.\"", "improvise"),
    ],
    refuses_narration=[
        "It never writes; that is enforced by the tools it is denied. It is not your personal oracle and "
        "never blends the two tiers without saying which is which.",
        "It does not fetch literature or run analyses. And it never improvises: if the lab has no entry, "
        "it says so in those words."],
    examples=[
        Exchange("1", ["A real run, on a demo lab vault. The member asks what the lab agreed for a quality "
                       "threshold, and who published it.",
                       "Found one lab entry: the threshold, the publisher, the date of the lab meeting, and "
                       "the value earlier runs used."],
                 [("read MEMORY.md", True), ("read the entry", True)]),
        Exchange("2", ["Asked to change the entry, it refuses. The verdict is Unsure: it cannot edit; the change "
                       "goes through a member's vault and the publish command, and the lab should decide first."],
                 [("read the entry", True), ("edit", False)]),
    ],
    prompt="ask the lab oracle what the lab has agreed on for the reference genome",
    give="The topic. It reads the lab's oracle folder and names the entry, the publisher and the date.",
    verdicts="Found / Not found / Unsure, naming the publisher. Nothing is ever written.",
    howto_narration=[
        "To use it, type to Claude Code and name it: ask the lab oracle what the lab has agreed on about "
        "something. To add to it, write the entry in your own oracle and run murmurent oracle publish.",
        "The first line is the verdict: Found, Not found or Unsure, naming who published the entry. "
        "When it says the lab has no entry, that is the answer, not a gap to fill."],
    docs=["docs/oracle-workflow.md"],
)

"""The conscience movie: narration, quotes from agents/conscience.md, and the real exchange in transcript.md."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import SAND

SPEC = AgentSpec(
    agent="conscience",
    title="The conscience",
    tagline="Equity, diversity, inclusion and bias review, with a citation for every flag",
    colour=SAND,
    icon="check",
    intro=["This is the conscience. It reviews a document for equity, inclusion and bias, line by line, "
           "and every flag comes with where it came from."],
    does=[
        Quote("Reviewing is the default.", "Reviewing"),
        Quote("and say where it came from.", "where it came from"),
        Quote("Decide the work. Don't decide for a community.", "Decide the work"),
        Quote("Separate what you read from what you suspect.", "suspect"),
    ],
    does_narration=[
        "Its file has four rules. Reviewing is the default: it is pointed at something and infers what is "
        "wanted. Say it, and say where it came from: a citation, or marked as its own knowledge.",
        "Decide the work, not for a community: it recommends one change. And it separates what it read from "
        "what it suspects; a suspicion is never a flag."],
    refuses=[
        Quote("Never write in a community's voice, or on its behalf.", "community's voice"),
        Quote("Never present your own knowledge as a community's account of itself.", "account"),
        Quote("Applying the fix is a dispatch, never an inference.", "Applying"),
        Quote("Never edit institutional boilerplate", "boilerplate"),
    ],
    refuses_narration=[
        "It never writes in a community's voice or on its behalf, and never presents its own knowledge as a "
        "community's account of itself. That is where a fluent model does harm.",
        "Applying a fix is something you ask for, never something it infers. And it never edits institutional "
        "boilerplate; it flags it."],
    examples=[
        Exchange("1", ["A real run, on a synthetic participants paragraph. The member asks for a review.",
                       "The verdict is Flagged. Each finding quotes the line, names the source in the resources or "
                       "says it is not there, and the gap register lists what the bookworm should go and find."],
                 [("read the draft", True), ("read edid_resources.md", True), ("write the report", True)]),
    ],
    prompt="ask the conscience to review the Participants section of methods.md",
    give="The document or the section. For something not yet built, say so and it returns a design instead.",
    verdicts="OK / Flagged, then the located findings, each with a citation, and the gap register.",
    howto_narration=[
        "To use it, type to Claude Code and name it: ask the conscience to review a section, a grant, a course. "
        "Point it at the file; you do not pick a mode.",
        "The first line is the verdict: OK or Flagged. Then each finding with its line and its source, a "
        "recommended change, and the register of what the resources could not back up."],
    docs=["docs/edid_resources.md"],
)

"""The lookout movie: narration in the lookout's own voice, plain statements checked against agents/lookout.md, and the real exchange in transcript.md."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import SKY
from cold_open import COLD_OPEN

SPEC = AgentSpec(
    agent="lookout",
    title="The lookout",
    tagline="Reads where new agentic-AI techniques appear and reports the few worth a look",
    colour=SKY,
    icon="star",
    intro=["I am the lookout. New tools for agentic AI appear every week, and nobody has the hours to "
           "read them all. I do the reading, on a schedule, and bring back the few that would make "
           "murmurent better."],
    does=[
        Quote("Reads murmurent's own files first, then every page on the watch list, then fixed searches.", "own files first"),
        Quote("Judges each item by one question: which agent gains, and how.", "which agent gains"),
        Quote("Reports at most ten: why in plain words first, a label, the effort to build, then the detail.", "at most ten"),
        Quote("Adopt, consider or watch. One GitHub issue per run; the earlier issues are its memory.", "memory"),
    ],
    does_narration=[
        "I read murmurent's own files first, so I know what it already has. Then every page on the watch "
        "list: the Claude Code changelog, Anthropic's engineering notes, the other harnesses, arXiv, "
        "video by its transcript.",
        "I judge each item by one question: which agent gains, and how. I report at most ten, each with the "
        "reason in plain words first, then adopt, consider or watch, the effort to build it, and the detail. One issue "
        "per run; the earlier issues are my memory."],
    refuses=[
        Quote("Nothing it did not read today on its own page. A search snippet is not evidence.", "snippet"),
        Quote("A video is reported from its description and transcript, never as watched.", "never as watched"),
        Quote("Installs nothing, enables nothing, edits nothing. The PI decides; the blacksmith builds.", "install nothing"),
        Quote("A query carries public terms only, never the centre's name or a file path.", "public terms"),
    ],
    refuses_narration=[
        "I report nothing I did not read today on its own page. A search snippet is not evidence. A video "
        "I report from its description and transcript, never as watched.",
        "I install nothing and edit nothing. The PI decides, the blacksmith builds. A query carries public "
        "terms only, never the centre's name or a file path."],
    examples=[
        Exchange("1", ["A real run, by hand, on the day I was written: what is new since the first of November.",
                       "The verdict names the best item and what it would touch. Each row has the page, the "
                       "reason first, then the label, the effort to build it, and the detail."],
                 [("murmurent's files", True), ("watch list", True), ("searches", True), ("installed", False)]),
    ],
    prompt="lookout, anything new on agent memory since October?",
    give="A question, or nothing: the routine runs it twice a week on its own.",
    verdicts="Found N worth a look, Nothing new or Unknown, then the items, best first, with where each would go.",
    directions=[
        ("lookout, what is new since the first of November that murmurent should look at",
         "The scheduled report by hand: at most ten items, each placed against a murmurent file."),
        ("lookout, has Claude Code changed how subagents are defined",
         "One question, one answer, read today off the changelog and the docs."),
        ("lookout, is there a maintained MCP server for a named database",
         "What exists, where, how it loads, and which agent would use it."),
    ],
    directions_narration=[
        "Three ways to direct me. Ask for the report by hand: ten items at most, each against a "
        "murmurent file.",
        "Ask one question about one harness, answered from today's page. Or whether a tool exists for a "
        "database, and which agent would use it."],
    howto_narration=[
        "Name the lookout in Claude Code, or set the schedule once; it runs twice a week.",
        "The first line is my verdict: found N worth a look, nothing new, or unknown. Then the items, "
        "with where each would go."],
    docs=[],
    openers=[COLD_OPEN],
)

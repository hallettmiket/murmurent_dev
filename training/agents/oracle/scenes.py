"""The oracle movie: narration, quotes from agents/oracle.md, and the real exchanges in transcript.md."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import LAV

SPEC = AgentSpec(
    agent="oracle",
    title="The oracle",
    tagline="Your personal research memory",
    colour=LAV,
    icon="doc",
    kind="bot",
    intro=["This is the oracle, your personal research memory in Murmurent. It remembers what you "
           "found, and gives it back months later with its source."],
    does=[
        Quote("accumulate, organize, and recall scientific knowledge across all of your member's projects and experiments",
              "accumulate"),
        Quote("There is one Oracle per user, not one per project.", "one oracle per person"),
        Quote("Every entry you write is browsable, searchable, and graphable in the member's personal Obsidian.",
              "Obsidian"),
        Quote("Promoting a finding to the Lab Oracle is an explicit user action", "lab oracle"),
        Quote("Beside oracle/, the vault holds the member's lab notebook, and you read it through the oracle MCP", "lab notebook"),
    ],
    does_narration=[
        "Its own file says what it is for: to accumulate, organize and recall scientific knowledge across "
        "all of your projects. There is one oracle per person, not one per project.",
        "Every entry lands in your own Obsidian vault, where you can browse, search and graph it. "
        "Sharing a finding with the lab oracle is a separate step that you take yourself.",
        "It also reads your lab notebook: your own notes for each day, and a separate stream of every "
        "prompt you gave Claude Code, written by a hook so you never paste one again."],
    refuses=[
        Quote("You do not publish to the lab.", "publish"),
        Quote("You never publish protected or restricted entries", "protected"),
        Quote("You do not fetch literature or run analyses.", "fetch"),
        Quote("You never fabricate. If you hold no entry on a topic, say so plainly.", "fabricate"),
    ],
    refuses_narration=[
        "What it will not do is just as clear. It does not publish to the lab; it only stages a draft. "
        "It never publishes a protected or restricted entry.",
        "It does not fetch literature or run analyses; the bookworm and the blacksmith do that. "
        "And it never fabricates: if it holds nothing on a topic, it says so."],
    examples=[
        Exchange("1", ["A real run, on a demo vault. The member asks it to remember a finding from a "
                       "synthetic colony study, with the project, the experiment and their handle.",
                       "The oracle writes one entry with the full schema, and adds a line to the index. "
                       "The first line of its reply is the verdict."],
                 [("read MEMORY.md", True), ("write the entry", True), ("update the index", True)]),
        Exchange("2", ["Asked later what it knows about serum and colony size, it finds that one entry, "
                       "cites the project and the experiment, and says plainly that it holds nothing else."],
                 [("read MEMORY.md", True), ("read the entry", True)]),
    ],
    prompt="ask the oracle to remember that MMP11 is up in the DCIS stroma, from exp 3_de, standard sensitivity",
    give="The finding, the project and experiment it came from, and the sensitivity. It asks for a missing field rather than guessing.",
    verdicts="Found / Not found / Unsure, or Remembered when it filed something. Then the entry it wrote or read.",
    howto_narration=[
        "To use it, type to Claude Code and name the agent: ask the oracle to remember something, or ask "
        "it what you know about a topic. Give it the finding, where it came from, and the sensitivity.",
        "The first line of the reply is the verdict: Found, Not found or Unsure, or Remembered when it filed "
        "something. The detail names the entry, so you can open it in Obsidian."],
    docs=["rules/oracle_schema.md", "docs/oracle-workflow.md"],
)

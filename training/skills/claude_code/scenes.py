"""Working through Claude Code: the two-minute movie every other movie assumes (issue #290)."""
from lib.draw import AMBER, RED, TEAL
from lib.movie import Movie, Part, Quote

T_OPEN = """
$ cd ~/repos/demo_project
$ ls -a
.  ..  .git  .murmurent.yaml  data  src
$ ls -l ~/.claude/agents | head -3
adversary.md -> ~/repos/murmurent/agents/adversary.md
artist.md -> ~/repos/murmurent/agents/artist.md
blacksmith.md -> ~/repos/murmurent/agents/blacksmith.md
$ ls ~/.claude/rules
data-storage.md  headline_first.md  oracle_schema.md
project-structure.md  slack.md  voice.md
$ claude
"""

T_LOG = """
$ tail -F ~/.murmurent/agents.log
[2026-11-07 09:31] blacksmith: Done: serum effect survives stratifying by country. Weighted within-country difference is +0.85 mm
[2026-11-07 09:32] centre_millwright: Drift: no centre record on this machine, so no membership check ran; the local drift loop found 8 items
[2026-11-07 09:32] conscience: Flagged: the draft calls an English-only cohort from one clinic "representative of the Canadian population"
[2026-11-07 12:14] general-purpose: starting: Lab notebook issues 292-294
"""

MOVIE = Movie(
    key="claude_code",
    title="Working through Claude Code",
    tagline="How a member reaches Murmurent: no command line needed",
    glyph="💬",
    colour=AMBER,
    summary="Open a project, how Murmurent's agents and rules reach the session, how to address an agent by name, what a verdict line is, the agent log pane, and what the hooks refuse and why.",
    parts=[
        Part("title", ["This is how a member works with Murmurent: through Claude Code, by typing in plain words. "
                       "Every other movie assumes these two minutes."]),
        Part("terminal", chapter="Opening a project", heading="A murmurent-ready folder",
             transcript=T_OPEN, title="Terminal",
             notes=[("A project folder carries a small marker file and its own CLAUDE.md.", "marker"),
                    ("The agents and the rules are linked into your Claude Code folder once, by the install.", "linked"),
                    ("Then you start Claude Code in the folder, and that is the last command you type.", "last command")],
             narration=["You open a project folder that is murmurent-ready: it carries a small marker file and its own "
                        "CLAUDE.md. The sixteen agents and the rules are linked into your Claude Code folder once, by "
                        "the install, so every session sees them.",
                        "Then you start Claude Code in that folder, and that is the last command you type."]),
        Part("cards", chapter="Addressing an agent", heading="Addressing an agent by name",
             source="docs/agents.md", colour=TEAL,
             quotes=[Quote("The commons is a shared set of reference agents, hard rules, and baseline workflows every member of the centre draws on", "shared set"),
                     Quote("are symlinked into ~/.claude/agents/ by scripts/setup.sh", "linked into")],
             narration=["The documentation calls the agents the commons: a shared set of reference agents, rules and "
                        "workflows every member draws on. They are linked into your Claude Code folder, so you reach one "
                        "by naming it: ask the adversary, ask the oracle, ask the security guard."]),
        Part("chat", chapter="A real exchange", key="1", agent="security_guard", colour=RED, who="Member",
             chips=[("git diff", True), ("secret patterns", True), ("PHI patterns", True)],
             narration=["Here is a real exchange. The member names the security guard and says what to audit. Claude "
                        "Code reads that agent's file and hands it the task.",
                        "The first line of every reply is the verdict, two hundred characters at most. Here it is "
                        "Blocked. Read that line first; the detail below it says where and why."]),
        Part("terminal", chapter="The agent log pane", heading="The agent log pane", transcript=T_LOG,
             title="Terminal, bottom right", colour=TEAL,
             notes=[("Every agent's verdict line is appended here as it finishes.", "appended"),
                    ("Keep it open in a corner; the VS Code layout does this for you.", "corner")],
             narration=["Every agent's verdict line is also appended to a log, one line each, as it finishes. Keep "
                        "that log open in a corner of the screen and you can see the agents working without reading "
                        "their full replies. The VS Code layout does this for you."]),
        Part("bullets", chapter="What the hooks refuse", heading="What the hooks refuse, and why", colour=RED, mark="cross",
             notes=[("A write into immutable data: \"immutable data is read-only by lab policy; refusing Write\"", "immutable"),
                    ("Overwriting a file under append only: \"protected path is write-once by lab policy; use an integer-versioned name instead\"", "append only"),
                    ("A command that deletes under the data root: \"Cannot delete files/folders from the protected directory\"", "deletes"),
                    ("These are guardrails for the agents, not a security perimeter: a plain shell does not go through them.", "guardrails")],
             narration=["Some things a session is refused, by hooks that run before a tool call. A write into "
                        "immutable data. Overwriting a file under append only, where a new version gets a new number. "
                        "A command that deletes under the data root.",
                        "The messages above are what the hooks really say. They are guardrails for the agents, not a "
                        "security perimeter: a plain shell does not go through them, and that is on purpose."]),
        Part("howto", heading="The habits that matter",
             prompt="ask the adversary to audit exp/3_classifier before I send the results to my PI",
             cards=[("Name the agent", "Say which agent and what to give it: a folder, a file, a question. Files, not summaries."),
                    ("Read the verdict line", "The first line is the answer. The agent log pane shows only that line."),
                    ("Trust the documentation", "When a movie and the written documentation disagree, the documentation is right.")],
             docs=["docs/agents.md", "docs/vscode-workflow.md", "rules/headline_first.md"],
             narration=["The habits that matter: name the agent and give it files, not summaries. Read the verdict line "
                        "first. And when a movie and the written documentation disagree, the documentation is right.",
                        "The sixteen agent movies each show one agent this way, in two minutes."]),
    ],
)

"""/murmurent-update-me: the status update and its dry run (issue #290)."""
from lib.draw import SKY, TEAL
from lib.movie import Movie, Part, Quote

T_FACTS = """
$ nice -n 19 python3 skills/murmurent-update-me/gather_facts.py
UPDATE-ME FACTS for murmurent (read-only; paths, times and owners only)
Clock: Sat 2026-11-07 12:20:28 EST (from `date`)
'Since the last update' means since 00:00 today
== Running now: this project's analyses and apps on this server ==
  ERROR: ps failed: ps: user:32: keyword not found
  Only this server is checked; a job on another machine does not appear.
== Agents (from ~/.murmurent/agents.log) ==
  Claude Code sessions open on this account: 0
  Started with no certain finish line, and certainly stopped (last 24 h): 33
== Git ==
  branch claude/charming-cartwright-c0a434 at 41b35f8, in step with GitHub
  13 commits today by Mike Hallett
"""

MOVIE = Movie(
    key="update_me",
    title="A status update with /murmurent-update-me",
    tagline="What is running, what finished, what is blocked, and on whom",
    glyph="📣",
    colour=SKY,
    summary="The status-update skill: facts from a read-only script, a plain-English summary for the project's channel, the refusals, and the dry run that shows the text without posting.",
    parts=[
        Part("title", ["This is the status update skill. It tells the project's channel what is running, what "
                       "finished, what is blocked and on whom, from facts a script read, not from memory."]),
        Part("cards", chapter="Where the facts come from", heading="Facts first, then words",
             source="skills/murmurent-update-me/SKILL.md", colour=TEAL,
             quotes=[Quote("where the state document and the facts disagree, the facts win and the summary says so.", "facts win"),
                     Quote("Run it from inside the project's repository: the project is the one the session is open in.", "inside"),
                     Quote("If the arguments ($ARGUMENTS) say dry-run, do steps 1 to 5 and stop: show the text, post nothing.", "dry run")],
             narration=["Its file says why it exists: status reports went wrong three ways in one day, so the facts "
                        "now come from a script, and where the state document and the facts disagree, the facts win.",
                        "You run it from inside the project's repository. With the word dry run, it shows the text "
                        "and posts nothing."]),
        Part("terminal", chapter="The script", heading="The read-only script", transcript=T_FACTS, title="Terminal: the skill runs this",
             colour=TEAL,
             notes=[("Running jobs, the agent log, outputs, quality gates, git, GitHub issues.", "jobs"),
                    ("It reads; it changes nothing. A check it cannot run says so.", "cannot run")],
             narration=["The script reads running jobs on every lab account, the agent log, the outputs folder, "
                        "quality gates, git and the GitHub progress issues. It changes nothing.",
                        "A check it cannot run says so, as here on a laptop, rather than reporting that nothing is "
                        "running."]),
        Part("chat", chapter="A real dry run", key="1", agent="murmurent-update-me", agent_title="/murmurent-update-me", colour=SKY, who="Member",
             chips=[("gather facts", True), ("write the summary", True), ("check the rules", True), ("post", False)],
             narration=["A real dry run, in the murmurent development repository. The summary is plain English: "
                        "what finished, what is blocked, the next step and whose it is.",
                        "The posting script checks every rule before it would post, and here it stops, because the "
                        "member asked for a dry run."]),
        Part("cards", chapter="What it refuses", heading="What it refuses to post", source="skills/murmurent-update-me/SKILL.md",
             colour=SKY, mark="cross",
             quotes=[Quote("no count under six of people, events or anything else about a cohort", "counts under six"),
                     Quote("nothing from any publication/ folder, and no file contents from the data tree", "publication"),
                     Quote("no token or credential, ever.", "credentials")],
             narration=["Three things never go into a channel: credentials, paths under a publication folder, and "
                        "counts under six, which could identify a person. The skill refuses the whole post rather "
                        "than trimming it."]),
        Part("howto", heading="How to use it",
             prompt="/murmurent-update-me dry-run",
             cards=[("Type the skill", "In the project's repository. Add dry-run to read the text first; without it, the update is posted."),
                    ("Settings are optional", "An update_me block in the repository's marker can name the channel, the outputs folder and the progress label."),
                    ("Facts over memory", "If the summary says a job stopped, a script saw it stop. If it could not look, it says so.")],
             docs=["skills/murmurent-update-me/SKILL.md"],
             narration=["To use it, type the skill name in the project's repository, with dry run the first time to "
                        "read the text. Settings are optional. And when the summary says a job stopped, a script saw "
                        "it stop."]),
    ],
)

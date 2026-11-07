"""/murmurent-push and /murmurent-project-push: what the pre-flight refuses and where the note goes (issue #290)."""
from lib.draw import AMBER, RED, TEAL
from lib.movie import Movie, Part, Quote

T_NOTE = """
$ murmurent project note --dry-run ""
no Slack channel is recorded for the project 'push_demo' (there is no project record of that name)
$ cd ~/repos/dcis_imaging
$ murmurent project note --dry-run ""
C0A1B2C3D4E: the channel of project 'dcis_imaging'
"""

MOVIE = Movie(
    key="push",
    title="Backing up with /murmurent-push",
    tagline="Commit and push with the lab's safety checks, and a note where the project reads it",
    glyph="📤",
    colour=TEAL,
    summary="The two push skills: what the pre-flight refuses (secrets, secret-shaped names, large files, governed data), how a whole project is backed up, and where the Slack note goes.",
    parts=[
        Part("title", ["This is how you back up your work with Murmurent: two skills that commit and push with the "
                       "lab's safety checks, and post a note where the project reads it."]),
        Part("cards", chapter="What it refuses", heading="What the pre-flight refuses", source="skills/murmurent-push/SKILL.md",
             colour=RED, mark="cross",
             quotes=[Quote("Refuse secret-shaped filenames.", "secret-shaped"),
                     Quote("Scan staged content for secrets.", "staged content"),
                     Quote("Refuse large files in tracked dirs.", "large files"),
                     Quote("Never --amend", "amend")],
             narration=["The skill's own file lists what it refuses before anything is staged. Secret-shaped file "
                        "names, such as a key or a credentials file. Secrets inside staged content, found by a scanner "
                        "that never prints the secret itself.",
                        "Large files in tracked folders, which belong under append only on the data host. And it never "
                        "amends history: the lab's history is the audit trail."]),
        Part("chat", chapter="A real run", key="1", agent="murmurent-push", agent_title="/murmurent-push", colour=RED, who="Member",
             chips=[("secret-shaped names", True), ("secrets-scan --staged", True), ("large files", True), ("push", False)],
             narration=["A real run, on a throwaway repository made for this movie. The member types the skill name. "
                        "The scanner finds two token-shaped strings in the staged file and reports them redacted.",
                        "A credentials file was never staged, and a three-megabyte data file is named with where it "
                        "should go instead. Nothing was committed or pushed."]),
        Part("terminal", chapter="Where the note goes", heading="Where the Slack note goes", transcript=T_NOTE,
             title="Terminal: the skill runs this for you", colour=TEAL,
             notes=[("One command decides the channel: the repository's own setting, else its project, else the lab.", "decides"),
                    ("A repository with no route posts nowhere and says why.", "nowhere"),
                    ("The skill runs this itself after the push; you do not pick a channel.", "pick")],
             narration=["After a push, one command decides where the note goes: a channel set in the repository's "
                        "marker, else the channel of the project that lists the repository, else the lab's channel.",
                        "A repository with no route posts nowhere and says why. The skill runs this itself; nobody "
                        "picks a channel by hand."]),
        Part("cards", chapter="The whole project", heading="/murmurent-project-push: the whole project",
             source="skills/murmurent-project-push/SKILL.md", colour=TEAL,
             quotes=[Quote("A repo has a governed-data path / secret / secret-shaped file / oversize file | that repo is blocked (exit 1); siblings still push", "blocked"),
                     Quote("No Slack channel for the project | the push still succeeds; the Slack note is skipped silently", "summary goes"),
                     Quote("Does not run tests, bump versions, or open PRs.", "tests")],
             narration=["The second skill backs up every repository a project owns, running the same pre-flight on "
                        "each. A repository that fails is blocked while its siblings still push, and one summary goes "
                        "to the project's channel.",
                        "It does not run tests, bump versions or open pull requests. That is still yours."]),
        Part("howto", heading="How to use them",
             prompt="/murmurent-push",
             cards=[("Type the skill", "/murmurent-push in the repository; /murmurent-project-push for every repository of the project."),
                    ("Read the refusal", "A blocked push names the file and the rule. Fix the cause; never override."),
                    ("Find the note", "In the project's channel, with the commit and a line on what changed.")],
             docs=["skills/murmurent-push/SKILL.md", "docs/slack_routing.md"],
             narration=["To use them, type the skill name in Claude Code: murmurent push in a repository, or murmurent "
                        "project push for the whole project. A blocked push names the file and the rule; fix the cause "
                        "rather than overriding it. The note appears in the project's channel."]),
    ],
)

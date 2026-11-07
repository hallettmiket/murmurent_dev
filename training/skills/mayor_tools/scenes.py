"""The mayor's and PI's tools: /murmurent-admin, /murmurent-onboard, /murmurent-reset (issue #290)."""
from lib.draw import LAV, RED, TEAL
from lib.movie import Movie, Part, Quote

T_ONBOARD = """
$ murmurent centre-status
(no centre initialised; run `murmurent centre-init`)
$ murmurent join-request list
(no join requests)
$ murmurent join-request decrypt request.age
$ murmurent join-request show <id>
$ murmurent join-request approve <id> --actor @mayor
"""

MOVIE = Movie(
    key="mayor_tools",
    title="The mayor's and PI's tools",
    tagline="/murmurent-admin, /murmurent-onboard and /murmurent-reset: three skills, three users",
    glyph="🏛️",
    colour=LAV,
    summary="The three administrative skills: priming context before admin work, processing an encrypted join request with an explicit decision, and resetting a machine after a backup and a dry run.",
    parts=[
        Part("title", ["These are the three skills for the people who run a centre or a lab: priming context before "
                       "administrative work, processing a join request, and resetting a machine safely."]),
        Part("cards", chapter="/murmurent-admin", heading="/murmurent-admin: load the design first",
             source="skills/murmurent-admin/SKILL.md", colour=TEAL,
             quotes=[Quote("Before doing admin-level work", "Before"),
                     Quote("reload that context so you act from murmurent's actual design, not a half-remembered version of it.", "half-remembered"),
                     Quote("there is no \"mayor\" agent", "no mayor agent")],
             narration=["The admin skill does no work of its own. Before any centre, registrar or provisioning "
                        "change, it reloads the design from the documents and the code, so the session acts from "
                        "murmurent's actual design and not a half-remembered version.",
                        "It also settles a confusion: there is no mayor agent. The mayor is a person who bootstraps "
                        "a centre once."]),
        Part("terminal", chapter="/murmurent-onboard", heading="/murmurent-onboard: a join request, end to end",
             transcript=T_ONBOARD, title="Terminal: what the skill runs", colour=LAV,
             notes=[("It checks a centre exists first; on this laptop there is none, and it stops there.", "stops"),
                    ("Decrypt and file, show who is asking, then an explicit decision.", "explicit"),
                    ("Approval creates a channel, a repository and permissions, so it waits for a clear yes.", "clear yes")],
             narration=["The onboard skill processes an encrypted join request. It checks that a centre exists first; "
                        "on this laptop there is none, so a real run stops there, and the rest is what it runs on the "
                        "mayor's machine.",
                        "Decrypt and file the request, show who is asking, then an explicit decision. Approval "
                        "creates a channel, a repository and permissions, so it waits for a clear yes."]),
        Part("cards", chapter="What onboard refuses", heading="What it never does", source="skills/murmurent-onboard/SKILL.md",
             colour=RED, mark="cross",
             quotes=[Quote("Never approve without the mayor's explicit yes", "explicit yes"),
                     Quote("Never invent the requester's details", "invent"),
                     Quote("The decrypted plaintext contains a person's contact info: handle it like the private data it is", "private data")],
             narration=["It never approves without the mayor's explicit yes, never invents the requester's details, "
                        "and treats the decrypted request as the private data it is: it never goes into Slack or "
                        "GitHub."]),
        Part("chat", chapter="/murmurent-reset", key="1", agent="murmurent-reset", agent_title="/murmurent-reset", colour=RED, who="PI",
             chips=[("pick the level", True), ("--dry-run", True), ("backup", True), ("run for real", False)],
             narration=["The reset skill returns a machine to a clean start, in levels. A real dry run on this "
                        "laptop: it shows every step it would take, the backup it would write first, and what it "
                        "keeps.",
                        "Credentials and other projects' installs are never removed without an explicit flag. The "
                        "real run happens only after you have read this and said yes."]),
        Part("howto", heading="How to use them",
             prompt="/murmurent-reset",
             cards=[("Admin first", "/murmurent-admin before any change to the centre, the registrar, the join flow or provisioning."),
                    ("Onboard with a yes", "/murmurent-onboard when a join request arrives; it asks approve or decline and records who answered."),
                    ("Reset after a preview", "/murmurent-reset shows the dry run, takes a backup, then asks. Credentials need their own flag.")],
             docs=["skills/murmurent-admin/SKILL.md", "skills/murmurent-onboard/SKILL.md", "skills/murmurent-reset/SKILL.md"],
             narration=["To use them: admin before any change to the administrative layer. Onboard when a join "
                        "request arrives, and answer its question yourself. Reset only after reading the preview; "
                        "the backup is taken for you."]),
    ],
)

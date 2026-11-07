"""The millwright movie: narration, quotes from agents/millwright.md, and the real exchange in transcript.md."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import TEAL

SPEC = AgentSpec(
    agent="millwright",
    title="The millwright",
    tagline="Infrastructure for one lab: members, projects, machines, health checks",
    colour=TEAL,
    icon="folder",
    intro=["This is the millwright, the lab's infrastructure provisioner. It onboards members, scaffolds "
           "projects and health-checks the environment, one lab at a time."],
    does=[
        Quote("Onboard members onto machines, scaffold new projects (GitHub repo, Slack channel, data dirs), maintain the machines + installations registry, and health-check existing environments",
              "Onboard"),
        Quote("dry_run is true by default.", "dry run"),
        Quote("Never push to main directly.", "push"),
    ],
    does_narration=[
        "Its file says what it does: onboard members onto machines, scaffold new projects with their repo, "
        "channel and data folders, keep the machines registry, and health-check an environment.",
        "Every write starts as a dry run that shows the full list of commands and waits for the PI. "
        "And it never pushes to main: it opens a branch and a pull request."],
    refuses=[
        Quote("You never generate, store, or transmit private keys.", "private key"),
        Quote("You never write into immutable/ (the former raw/), and never delete data.", "delete"),
        Quote("You never touch mothballed/, and you never tidy the lab folder yourself.", "tidies"),
        Quote("You do not act without PI sign-off", "sign-off"),
    ],
    refuses_narration=[
        "It never generates, stores or transmits a private key; only public keys leave your machine. "
        "It never writes into immutable data and never deletes data.",
        "It never touches the mothballed folder and never tidies the lab folder on its own: it reports, "
        "and the PI decides. And it does not act on shared infrastructure without PI sign-off."],
    examples=[
        Exchange("1", ["A real run, read-only. The member asks for a health check of their murmurent install.",
                       "The verdict is Concerns: the install runs, but the shared agents are not linked and the hooks "
                       "use another Python. Each problem comes with the command that fixes it, and nothing was changed."],
                 [("murmurent doctor", True), ("murmurent repo status", True), ("fix anything", False)]),
    ],
    prompt="ask the millwright to scaffold a new project called dcis_imaging for this lab",
    give="For a project, its name and who is in it. For a member, their handle. For a check, nothing: it reads the machine.",
    verdicts="Provisioned / Skipped / Failed, after a dry run you confirmed.",
    howto_narration=[
        "To use it, type to Claude Code and name it: ask the millwright to scaffold a project, onboard a member, "
        "or check the install. It shows the plan first and asks the PI to confirm.",
        "The first line is the verdict: Provisioned, Skipped or Failed. Then what it did, and what it left for "
        "you to run on your own machine, such as adding your own key."],
    docs=["docs/setup.md"],
)

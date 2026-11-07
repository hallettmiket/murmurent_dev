"""The centre millwright movie: narration, quotes from agents/centre_millwright.md, and the real exchange in transcript.md."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import TEAL

SPEC = AgentSpec(
    agent="centre_millwright",
    title="The centre millwright",
    tagline="Centre-wide infrastructure: cross-lab projects, ACLs and the drift loop",
    colour=TEAL,
    icon="cloud",
    intro=["This is the centre millwright. Where the millwright serves one lab, this one serves the whole "
           "centre: cross-lab projects, permissions on shared servers, and the loop that finds drift."],
    does=[
        Quote("centre-wide reconciliation", "reconciliation"),
        Quote("Per-project filesystem ACLs on shared servers, cross-lab project provisioning (Slack ownership + guest invites), centre-level membership-drift detection",
              "permissions on shared servers"),
        Quote("Reconciles drift", "drift"),
        Quote("One project at a time.", "One project"),
    ],
    does_narration=[
        "Its file says the job is centre-wide reconciliation: per-project permissions on shared servers, "
        "cross-lab project provisioning with guest invites, and membership-drift detection.",
        "Reconciling drift is its primary job: compare what the project records say with what Slack, GitHub "
        "and the filesystem actually hold. One project at a time, so a bad step cannot cascade."],
    refuses=[
        Quote("Onboarding individual members is the per-lab millwright's.", "onboard"),
        Quote("You never modify any per-lab lab_mgmt repo.", "modifies"),
        Quote("You do not act without registrar sign-off", "sign-off"),
        Quote("Slack channel deletion is one-way.", "deletes"),
    ],
    refuses_narration=[
        "It does not onboard individual members; that is the lab millwright's. It never modifies a lab's "
        "records repository; it only reads them.",
        "It does not act on shared infrastructure without registrar sign-off. And it never deletes a Slack "
        "channel: it archives, so the registrar can restore."],
    examples=[
        Exchange("1", ["A real run, dry-run only, on a laptop with no centre record. The mayor asks for the "
                       "drift loop.",
                       "The verdict is Drift. It says plainly which comparison it could not make here, lists each "
                       "item of local drift with what it would do, and applied nothing."],
                 [("read centre.md", False), ("murmurent reconcile", True), ("apply", False)],
                 who="Mayor"),
    ],
    prompt="ask the centre millwright to reconcile project dcis_imaging across the two labs",
    give="The project, or nothing for the full loop. It reads the records and the live state, and shows the diff first.",
    verdicts="Reconciled / Drift / BLOCKED, with the diff it would apply and the sign-off it needs.",
    howto_narration=[
        "To use it, type to Claude Code and name it: ask the centre millwright to reconcile a project, or to run "
        "the drift loop. It runs on the registrar's machine and shows the diff before anything is applied.",
        "The first line is the verdict: Reconciled, Drift or Blocked. Then each delta, what it would change, and "
        "the confirmation it is waiting for."],
    docs=["docs/reconcile.md"],
)

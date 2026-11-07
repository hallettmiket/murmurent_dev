"""The registrar movie: narration, quotes from agents/registrar.md, and the real exchange in transcript.md."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import SKY

SPEC = AgentSpec(
    agent="registrar",
    title="The registrar",
    tagline="The centre's roster of labs, cores and collaborations, and its certificate authority",
    colour=SKY,
    icon="stamp",
    intro=["This is the registrar, the agent above the lab level. It keeps the centre's roster of labs, "
           "cores and collaborations, and it signs the cards that say who leads what."],
    does=[
        Quote("the centre-level roster. Lab / core / collaboration lifecycle, the authoritative _registry.yaml",
              "roster"),
        Quote("Every PI leads at most one lab or core.", "at most one"),
        Quote("Read-only oversight", "read-only view"),
        Quote("you are the centre's certificate authority", "certificate"),
    ],
    does_narration=[
        "Its file says the scope: the centre-level roster, the lifecycle of labs, cores and collaborations, and "
        "the one registry file that is authoritative. It enforces that every PI leads at most one lab or core.",
        "It gives the administrative head a read-only view of the centre. And it is the certificate authority: "
        "it signs PI cards and holds the revocation list."],
    refuses=[
        Quote("Read a lab's notebook entries, SEAs, deliberations, inventory, project source code, or personal Oracle memory.",
              "notebook"),
        Quote("Edit a lab's CHARTER, MEMBERS, or per-member members/<handle>.md profiles.", "CHARTER"),
        Quote("Delete a lab's data.", "Delete"),
    ],
    refuses_narration=[
        "What it must never do: read inside a lab, its notebooks, deliberations, source code or personal oracles. "
        "Labs are opaque units to it.",
        "It never edits a lab's charter, members or profiles; those belong to the lab. And it never deletes a "
        "lab's data: archiving flips a status flag and the repository stays."],
    examples=[
        Exchange("1", ["A real run, read-only, on this machine's registry. The administrative head asks for the "
                       "institution-level view.",
                       "The verdict is Clear: one lab, its PI, no cores yet, and one gap named plainly: nobody is "
                       "recorded as registrar. Nothing was changed."],
                 [("read _registry.yaml", True), ("check the pointer", True), ("read inside the lab", False)],
                 who="Administrative head"),
    ],
    prompt="ask the registrar which labs and cores are registered and whether any entry is incomplete",
    give="For a view, nothing. For a new lab or core, its name and its PI. For a card, the PI's enrolment request.",
    verdicts="Recorded / Conflict / Skipped, then the roster or what it refused and why.",
    howto_narration=[
        "To use it, type to Claude Code and name it: ask the registrar for the roster, to record a new lab, or to "
        "issue a PI card. It refuses a PI who already leads another group.",
        "The first line is the verdict: Recorded, Conflict or Skipped. Then the roster, with every pointer "
        "checked, or the conflict that stopped it."],
    docs=["docs/identity.md"],
)

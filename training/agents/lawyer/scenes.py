"""The lawyer movie: narration, quotes from agents/lawyer.md, and the real exchange in transcript.md."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import SKY

SPEC = AgentSpec(
    agent="lawyer",
    title="The lawyer",
    tagline="Patents, freedom to operate, and whether governed data may move",
    colour=SKY,
    icon="scale",
    intro=["This is the lawyer. It reads the patent landscape around a molecule or a method, and it rules "
           "on whether a project may move or publish governed data, always from the instrument."],
    does=[
        Quote("Search global patent databases for genes, proteins, small molecules, biologics, devices, and related technologies",
              "Search"),
        Quote("Summarize patent claims in plain language a scientist can act on", "plain language"),
        Quote("Rule on whether a project may move, share, store or publish governed data", "governed"),
        Quote("Triage referrals from the adversary before searching", "Triage"),
    ],
    does_narration=[
        "Its file lists the work. Search the patent databases for genes, molecules and devices, and summarize "
        "the claims in plain language a scientist can act on.",
        "Rule on whether governed data may move, by reading the agreement, never by assuming it. And triage "
        "every referral first, so a question with no IP surface costs one step."],
    refuses=[
        Quote("You are not a substitute for counsel of record.", "counsel"),
        Quote("You do not do the science.", "science"),
        Quote("You do not file or prosecute.", "file"),
        Quote("Always separate fact from optimism.", "optimism"),
    ],
    refuses_narration=[
        "It is not a substitute for counsel of record: a binding opinion goes through the Research and "
        "Innovation Office. It does not do the science, and it does not file or prosecute.",
        "And it always separates fact from optimism: a status is confirmed across databases, or it is inferred, "
        "and it says which."],
    examples=[
        Exchange("1", ["A real run, on a synthetic question: can we publish a protocol note and post our script "
                       "under an open licence?",
                       "The verdict is Clear, after triage alone. Disclosure is not an act a patent reaches, so no "
                       "database was searched, and the answer says so. It adds the one clock the lab should know about."],
                 [("triage", True), ("patent search", False), ("licence check", True)]),
    ],
    prompt="ask the lawyer whether we can act on these three compounds, with their identifiers",
    give="The entities with identifiers, and what you intend to do with them. For data, the agreement or the ethics approval.",
    verdicts="Clear / Conflict / Unknown, then what was searched, or why nothing needed to be.",
    howto_narration=[
        "To use it, type to Claude Code and name it: ask the lawyer whether you can act on a molecule, or whether "
        "a data move is permitted. Say what you intend to do; a landscape for its own sake is not a question.",
        "The first line is the verdict: Clear, Conflict or Unknown. Then what it searched, or why triage said "
        "nothing needed searching. The adversary also sends it work on its own during an audit."],
    docs=[],
)

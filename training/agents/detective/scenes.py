"""The detective movie: narration in the detective's own voice, plain statements checked against agents/detective.md, and the real exchange in transcript.md."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import SKY
from cold_open import COLD_OPEN

SPEC = AgentSpec(
    agent="detective",
    title="The detective",
    tagline="Whether the record a manuscript rests on is real and reachable",
    colour=SKY,
    icon="mag",
    intro=["I am the detective. Point me at a manuscript, yours or someone else's, and I check the record "
           "it rests on: the papers it cites, the data it names, the journal. Not the science. The record."],
    does=[
        Quote("Looks every citation up in the registries: missing, a different paper, retracted.", "registries"),
        Quote("Resolves every data accession at its archive, and reads whether it is public.", "archive"),
        Quote("Reads the availability statement against the journal's own policy page.", "policy"),
        Quote("Four tiers: proven, suspected, noted, clean. Never above the evidence.", "four tiers"),
    ],
    does_narration=[
        "I look every citation up in the registries: missing, a different paper, retracted. I resolve "
        "every data accession at its archive and read whether it is public. I read the availability "
        "statement against the journal's own policy page.",
        "Every finding sits in one of four tiers. Proven, when a registry's own answer is the proof and I "
        "quote it. Suspected, with what would settle it. Noted, a fact with no verdict. Clean. Never above "
        "the evidence."],
    refuses=[
        Quote("Never names intent or a person. The subject is the manuscript.", "intent"),
        Quote("No AI-text detector, no score. A generated passage is noted, not accused.", "detector"),
        Quote("Figures only through a named image tool, and at most suspected.", "image tool"),
        Quote("A manuscript under review is read only where the journal allows.", "under review"),
    ],
    refuses_narration=[
        "I never name intent, and no person is the subject of a finding. A wrong identifier is a wrong "
        "identifier; whether it was a mistake is not mine to say. No AI-text detector, no score. A generated "
        "passage is noted, not accused.",
        "Figures go through a named image tool or not at all, at most suspected. A manuscript under review "
        "is confidential: I read the journal's reviewer policy first; if it forbids, I stop."],
    examples=[
        Exchange("1", ["A real run, on a made-up draft: a retracted citation, a DOI nobody issued, a missing "
                       "GEO series, and data available upon reasonable request.",
                       "My verdict is Proven, in the registries' own words, quoted. The on-request wording I "
                       "set beside the journal's data policy and leave at suspected, with what would settle it."],
                 [("registries", True), ("archives", True), ("journal policy", True), ("adversary", False)]),
    ],
    prompt="ask the detective to investigate my draft, not yet submitted, intended for a named journal",
    give="The manuscript, whose it is, where it stands, and which model is reading it.",
    verdicts="Clean, Suspected or Proven, then every finding with its evidence and where it sits.",
    directions=[
        ("ask the detective to investigate my draft manuscript before I submit it to a named journal",
         "The marked-up manuscript: every finding highlighted where it sits, with its evidence."),
        ("ask the detective whether the data this published paper names can actually be reached",
         "Each accession resolved at its archive: exists, public, controlled, or missing."),
        ("ask the detective to check the bibliography alone, sending nothing but the identifiers",
         "For a manuscript under review: what the registries say, and nothing of the text leaves."),
    ],
    directions_narration=[
        "Three ways to direct me. Before you submit, I investigate the draft and hand back the manuscript "
        "marked where every finding sits.",
        "For a published paper, whether its data can be reached. Under review, the bibliography alone: "
        "nothing of the text leaves the machine."],
    howto_narration=[
        "Type to Claude Code and name the detective. Give me the manuscript, whose it is, where it stands, "
        "and which model is reading it.",
        "The first line is my verdict: Clean, Suspected or Proven. Then every finding with its evidence, and "
        "the manuscript marked where each sits."],
    docs=[],
    openers=[COLD_OPEN],
)

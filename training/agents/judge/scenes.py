"""The judge movie: narration, quotes from agents/judge.md, and the real exchange in transcript.md."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import SAND

SPEC = AgentSpec(
    agent="judge",
    title="The judge",
    tagline="Combines what several labs contributed to one question, without laundering it",
    colour=SAND,
    icon="scale",
    intro=["This is the judge. In a choreography where several labs each contribute an answer to one "
           "question, the judge lines the answers up and presents them honestly."],
    does=[
        Quote("align each contribution on the shared candidate key, apply the poser's criteria, surface agreement and disagreement with full provenance",
              "align"),
        Quote("Never silently discard a contribution's output.", "discard"),
        Quote("Carry full provenance.", "provenance"),
        Quote("Surface disagreement", "disagreement"),
    ],
    does_narration=[
        "Its file says how it combines. Align every contribution on the shared candidate key, apply the poser's "
        "criteria, and present with full provenance.",
        "It never silently discards a contribution's output. Every number carries the contribution it came from. "
        "And it surfaces disagreement rather than averaging it away."],
    refuses=[
        Quote("You do not run the contributions.", "run"),
        Quote("You do not decide the science.", "science"),
        Quote("You do not make it pretty.", "pretty"),
        Quote("You never invent a common score across incommensurable metrics", "common score"),
    ],
    refuses_narration=[
        "It does not run the contributions; they arrive already produced. It does not decide the science; the "
        "poser holds that gate. It does not make it pretty; the artist does.",
        "And it never invents a common score across metrics that do not share units. When they differ, "
        "the verdict is Split, not Presented."],
    examples=[
        Exchange("1", ["A real run, on a synthetic run package: two invented labs, five invented compounds, "
                       "a docking score and a measured binding.",
                       "The verdict is Split, because the two metrics are not on one scale. All five compounds are "
                       "shown, the disagreement is named, and the untested compound stays in the table."],
                 [("read run.yaml", True), ("join on compound_id", True), ("consensus score", False)],
                 who="Poser"),
    ],
    prompt="ask the judge to present the run package in append_only/dcis_imaging/runs/2026-11-07",
    give="A prepared run package: the manifest, the choreography and each contribution's contract and table.",
    verdicts="Presented / Split / Insufficient, then the aligned table with provenance and the handoff to the artist.",
    howto_narration=[
        "To use it, prepare the run package with murmurent choreography prepare run, then type to Claude Code "
        "and ask the judge to present it.",
        "The first line is the verdict: Presented, Split or Insufficient. Then the aligned table, every number "
        "with its source, and what it hands the artist. The adversary reviews the judge's combination step."],
    docs=["docs/assembling_choreographies.md"],
)

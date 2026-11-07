"""The adversary movie: narration, quotes from agents/adversary.md, and the real exchange in transcript.md."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import RED

SPEC = AgentSpec(
    agent="adversary",
    title="The adversary",
    tagline="Methodological audit and peer review, before a reviewer does it",
    colour=RED,
    icon="scale",
    intro=["This is the adversary. It audits how a result was produced, the way a hard reviewer would, "
           "and it re-runs the code rather than taking the write-up's word."],
    does=[
        Quote("Check for data leakage: are test observations structurally or temporally related to training observations?",
              "leakage"),
        Quote("Challenge any claim that seems too good: suspiciously high performance warrants scrutiny", "too good"),
        Quote("Verify that feature computation is correct and reproducible", "reproducible"),
        Quote("Refer IP-bearing work to the LAWYER automatically, and carry their verdict into your own", "lawyer"),
    ],
    does_narration=[
        "Its file says what it looks for. Data leakage between training and test. Claims that seem too good. "
        "Whether a computation is correct and reproducible.",
        "And when the work carries intellectual property, it refers that to the lawyer itself, and folds the "
        "lawyer's verdict into its own."],
    refuses=[
        Quote("You audit; you do not build.", "build"),
        Quote("You do not produce figures.", "figures"),
        Quote("Never present speculation as fact. If you have not run code to check something, do not assert it as true.",
              "speculation"),
        Quote("You never launder a disagreement into a verdict.", "launder"),
    ],
    refuses_narration=[
        "It audits; it does not build. It does not produce figures. It never presents speculation as fact: "
        "what it has not checked by running code is labelled as speculated.",
        "And it never launders a disagreement into a verdict. Ambiguous evidence is reported as ambiguous."],
    examples=[
        Exchange("1", ["A real run, on the synthetic example that ships with Murmurent. The member asks whether "
                       "a claimed result is sound.",
                       "The verdict is Questions. The number reproduces exactly, but the adversary found that the "
                       "two groups come from different countries, and that the Methods text describes a step the "
                       "code does not take. The last line is the mandatory counsel note."],
                 [("re-run run_all.py", True), ("stratify by country", True), ("read main.tex", True),
                  ("IP referral", False)]),
    ],
    prompt="ask the adversary to audit exp/3_classifier before I send the results to the PI",
    give="The experiment folder, or the write-up with its code and data. It reads the files and runs the scripts.",
    verdicts="Pass / Questions / Reject. Every finding is OBSERVED or SPECULATED, and the audit ends with a COUNSEL line.",
    howto_narration=[
        "To use it, type to Claude Code and name it: ask the adversary to audit an experiment or a write-up. "
        "Give it the folder with the code and the data, not a summary.",
        "The first line is the verdict: Pass, Questions or Reject. Every finding says whether it was observed or "
        "speculated, and the audit ends with the counsel line. Run it before someone else does."],
    directions=[
        ("ask the adversary to audit exp/3_classifier for leakage between training and test, re-running the split code rather than reading it",
         "Findings labelled OBSERVED or SPECULATED, the re-run shown, and the verdict Pass, Questions or Reject."),
        ("ask the adversary to check the write-up in draft_2.tex against TRIPOD+AI, item by item, and to verify the numbers behind the central claims",
         "The checklist with each item met, missing or unclear, the sources checked, and the counsel line at the end."),
        ("ask the adversary to review the judge's combination of the two labs' contributions for laundered evidence",
         "Whether incommensurable metrics were merged, with the rows that show it."),
    ],
    directions_narration=[
        "Say what to audit and what you fear. Leakage between training and test, with the split re-run rather "
        "than read. A write-up checked against a reporting guideline, item by item, with the numbers traced.",
        "Or the judge's combination of two labs' results. The adversary says what it observed and what it only "
        "suspects, and ends with the counsel line."],
    docs=["docs/reporting_guidelines.md"],
)

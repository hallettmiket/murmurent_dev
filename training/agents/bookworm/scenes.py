"""The bookworm movie: narration, quotes from agents/bookworm.md, and the real exchange in transcript.md."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import TEAL

SPEC = AgentSpec(
    agent="bookworm",
    title="The bookworm",
    tagline="Literature, databases, and the guard against invented citations",
    colour=TEAL,
    icon="mag",
    intro=["This is the bookworm. It reads the published literature for you, and it is the main guard "
           "against a citation that does not exist or a statistic nobody measured."],
    does=[
        Quote("Retrieve and summarize relevant literature for the project domain", "Retrieve"),
        Quote("Query relevant scientific databases to annotate data with published knowledge", "databases"),
        Quote("check every identifier with murmurent cite check before you report it", "cite check"),
        Quote("Trace every outside number to the study that measured it, and say so when you cannot", "Trace"),
    ],
    does_narration=[
        "Its file lists the jobs. Retrieve and summarize the literature. Query the scientific databases to "
        "annotate your data with what is already known.",
        "Check every identifier with murmurent cite check before reporting it. Trace every outside number "
        "to the study that measured it, and say so when it cannot."],
    refuses=[
        Quote("You summarize and cite; you do not run the analysis.", "run the analysis"),
        Quote("You do not decide methodological validity.", "validity"),
        Quote("You do not make the figures.", "figures"),
        Quote("never silently collapse conflicting database records into one", "collapse"),
    ],
    refuses_narration=[
        "It summarizes and cites; it does not run the analysis. It does not decide methodological validity, "
        "which is the adversary's call.",
        "It does not make figures, and it never silently collapses conflicting database records into one: "
        "it shows you the conflict."],
    examples=[
        Exchange("1", ["A real run. A draft cites a real paper for a number. The member asks the bookworm to "
                       "check the citation and the number.",
                       "The citation checks out. The number does not: the paper never says it. Each item is "
                       "labelled, verified, mismatch or unresolved, and the fix is to drop the figure."],
                 [("murmurent cite check", True), ("fetch the full text", True), ("search for 80%", False)]),
    ],
    prompt="ask the bookworm to check the citations and numbers in the introduction of draft_3.tex",
    give="The identifier, a DOI or a PubMed ID, and the sentence that leans on it. For a reading list, the project question.",
    verdicts="Found N sources, then each item marked VERIFIED, MISMATCH, RETRACTED, SECONDARY ONLY or UNRESOLVED.",
    howto_narration=[
        "To use it, type to Claude Code and name it: ask the bookworm to check the citations in a draft, "
        "or to find what is known about a gene. Give it the identifier and the sentence that leans on it.",
        "The first line is the verdict, Found and how many sources. Then each item carries its label: "
        "verified, mismatch, retracted, secondary only or unresolved. An unresolved number is not a number "
        "you can use yet."],
    directions=[
        ("ask the bookworm for a reading list on DCIS progression markers, as an HTML page with one paragraph per paper, and add each paper to Zotero tagged dcis",
         "An annotated list under outputs/bookworm/, every identifier checked, each paper in your Zotero library when the key is configured."),
        ("ask the bookworm to check every citation in main.tex and give me the findings as a table I can paste into the response to reviewers",
         "One row per citation: VERIFIED, MISMATCH, RETRACTED, SECONDARY ONLY or UNRESOLVED, with what the source actually says."),
        ("ask the bookworm to annotate the top 50 genes in results.tsv with what is published about them in breast cancer, PubMed IDs included",
         "The table with a column of findings and identifiers, and the conflicts between databases shown rather than merged."),
    ],
    directions_narration=[
        "Say what you want back. A reading list as an HTML page, one paragraph per paper, and each paper added to "
        "Zotero with a tag. The citation check as a table you can paste into a response to reviewers.",
        "Or a gene table annotated with what is published, PubMed identifiers included. The format and the "
        "destination are yours to name; the checking is always done."],
    docs=["docs/reporting_guidelines.md"],
)

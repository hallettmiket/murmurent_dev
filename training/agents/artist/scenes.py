"""The artist movie: narration, quotes from agents/artist.md, and the real exchange in transcript.md."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import SKY

SPEC = AgentSpec(
    agent="artist",
    title="The artist",
    tagline="Figures, reports and slides that communicate the science",
    colour=SKY,
    icon="chart",
    intro=["This is the artist. It turns finished results into figures, reports and slides, on the "
           "principle that a result that cannot be communicated does not exist."],
    does=[
        Quote("Generate publication-quality figures using matplotlib and seaborn", "publication"),
        Quote("Produce ROC curves, precision-recall curves, confusion matrices, heatmaps, volcano plots", "ROC"),
        Quote("Build slide decks summarising analysis pipelines and findings", "slide decks"),
        Quote("Ensure all figures are legible, labelled, and have proper axes, titles, and legends", "legible"),
    ],
    does_narration=[
        "Its file lists the work. Publication-quality figures with matplotlib and seaborn. ROC curves, "
        "heatmaps, volcano plots, the standard set.",
        "Slide decks that summarise a pipeline and its findings. And every figure legible, labelled, "
        "with proper axes, titles and legends."],
    refuses=[
        Quote("You do not train models or run statistics.", "statistics"),
        Quote("You do not decide scientific validity.", "validity"),
        Quote("Never present placeholder or synthetic data as real.", "synthetic"),
        Quote("You do not fabricate data to fill a plot.", "fabricate"),
    ],
    refuses_narration=[
        "It does not train models or run statistics; the numbers come from the blacksmith. It does not decide "
        "scientific validity; the adversary checks the figure.",
        "It never presents synthetic data as real, and it does not fabricate data to fill a plot. "
        "An empty axis is better than an invented one."],
    examples=[
        Exchange("1", ["A real run, on simulated data. The member asks for one publication figure: colony "
                       "diameter by medium, every point shown, the means marked.",
                       "The verdict is Rendered. The figure is labelled as simulated on the image itself, "
                       "the caption says what to notice, and the artist says plainly that it ran no test."],
                 [("read signal.csv", True), ("draw with matplotlib", True), ("write the caption", True)]),
    ],
    prompt="ask the artist to make a figure of the AUC per fold from exp/3_classifier/outputs, for the paper",
    give="The results file and what the figure is for: a paper, a talk, a report. Say which comparison matters.",
    verdicts="Rendered / Skipped / Failed, then the file it wrote and the caption.",
    howto_narration=[
        "To use it, type to Claude Code and name it: ask the artist to make a figure from a results file, "
        "and say what it is for. A figure for a talk is not a figure for a paper.",
        "The first line is the verdict: Rendered, Skipped or Failed. Then the file it wrote and a caption that "
        "says what to notice. If an input is missing, it stops and says so rather than inventing one."],
    docs=[],
)

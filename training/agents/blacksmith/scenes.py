"""The blacksmith movie: narration, quotes from agents/blacksmith.md, and the real exchange in transcript.md."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import AMBER

SPEC = AgentSpec(
    agent="blacksmith",
    title="The blacksmith",
    tagline="The computational workhorse: data, features, models, dashboards",
    colour=AMBER,
    icon="code",
    intro=["This is the blacksmith, the computational workhorse. It loads the data, engineers the "
           "features, trains and evaluates the models, and builds the apps you explore results in."],
    does=[
        Quote("Load and preprocess datasets (CSV, Parquet, HDF5, Excel)", "Load"),
        Quote("Engineer features, handle class imbalance, perform train/test splits", "features"),
        Quote("Train and tune classifiers (XGBoost, Random Forest, logistic regression, neural networks)", "Train"),
        Quote("Write clean, well-commented Python code", "clean"),
    ],
    does_narration=[
        "Its file lists the work. Load and preprocess data in any common format. Engineer features, handle "
        "class imbalance, make the splits.",
        "Train and tune classifiers, evaluate them with the right metrics, and leave clean, commented code "
        "behind so the run can be repeated."],
    refuses=[
        Quote("Publication figures are the artist's.", "figures"),
        Quote("Methodological validation is the adversary's.", "validation"),
        Quote("Do not mark your own homework as sound", "homework"),
        Quote("You do not write to the immutable data root.", "immutable"),
    ],
    refuses_narration=[
        "Publication figures are the artist's; its own plots are quick diagnostics. Methodological validation "
        "is the adversary's: it does not mark its own homework as sound.",
        "And it does not write to the immutable data root. Outputs go under append only, versioned, "
        "never overwriting."],
    examples=[
        Exchange("1", ["A real run, on simulated data. The adversary had found a confound, so the member asks "
                       "the blacksmith for the within-country differences and a stratified permutation test.",
                       "The verdict is Done, with the numbers: the effect survives stratification, and the caveat "
                       "that the countries do not agree. The results file and the code are named."],
                 [("read signal.csv", True), ("stratified permutation", True), ("write results.tsv", True)]),
    ],
    prompt="ask the blacksmith to train a classifier on exp/3_classifier/data with 5-fold cross-validation",
    give="The data, where it lives, what to predict, and the outputs folder. It versions files and never overwrites.",
    verdicts="Done / Failed / Partial, then the numbers, the files it wrote and the code that made them.",
    howto_narration=[
        "To use it, type to Claude Code and name it: ask the blacksmith to compute, train or build something. "
        "Give it the data, what to predict and where outputs go.",
        "The first line is the verdict: Done, Failed or Partial. Then the numbers, the files it wrote and the "
        "code, so the adversary can re-run it. Send the result to the adversary before the PI."],
    directions=[
        ("ask the blacksmith to build a Streamlit app over append_only/dcis/3_qc so I can filter cells by mitochondrial fraction and see the counts update",
         "A single-file app, how to run it in the experiment README, reading from the data root and never writing back to it."),
        ("ask the blacksmith to train an XGBoost classifier with 5-fold cross-validation, stratified by site, and report the AUC per fold with its variance",
         "The model, the folds, the metrics per fold, and clean commented code the adversary can re-run."),
        ("ask the blacksmith to turn the counts matrix into features: log-normalised, the 2000 most variable genes, then a PCA, written as versioned files",
         "Feature files under append_only with integer suffixes; nothing overwritten; the steps in the code."),
    ],
    directions_narration=[
        "Say what you want built. A Streamlit app over an experiment's outputs, with the filter you need. "
        "A classifier with the cross-validation you specify, stratified the way your data demand, with the "
        "variance across folds.",
        "Or a feature pipeline, step by step, written as versioned files. Name the tool, the method and where "
        "the outputs go; the blacksmith leaves the code to re-run it."],
    docs=["rules/data-storage.md"],
)

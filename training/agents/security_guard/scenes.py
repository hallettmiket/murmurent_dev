"""The security guard movie: narration, quotes from agents/security_guard.md, and the real exchange in transcript.md."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import RED

SPEC = AgentSpec(
    agent="security_guard",
    title="The security guard",
    tagline="Secrets, patient data and world-readable files, caught before they leave",
    colour=RED,
    icon="lock",
    intro=["This is the security guard. It audits what is about to leave a project: a diff, a pull request, "
           "an artefact, for secrets, patient data and restricted paths."],
    does=[
        Quote("Scan diffs (git diff, PR patches, pre-commit input) for credentials, API tokens, SSH keys, age keys",
              "Scan"),
        Quote("scan added text for PHI-shaped patterns", "Patient-shaped"),
        Quote("Refuse to approve a PR that adds, modifies, or deletes files under", "Refuse"),
        Quote("Identity-key hygiene.", "Identity"),
    ],
    does_narration=[
        "Its file lists what it scans for. Credentials, tokens and keys in a diff. Patient-shaped patterns in a "
        "protected project: health numbers, record numbers, a birth date near a name.",
        "It refuses to approve a change that touches the immutable data root. And it treats a private identity "
        "key in any diff, log or message as an immediate block."],
    refuses=[
        Quote("You render a verdict; you do not \"fix\" the offending code.", "fix"),
        Quote("You do not comment on cross-validation, leakage, or model choice.", "cross-validation"),
        Quote("You flag a bad permission; you never chmod/chown to fix it.", "permission"),
        Quote("You never mutate the repo to remediate.", "remediate"),
    ],
    refuses_narration=[
        "It renders a verdict; it does not fix the code. It does not comment on cross-validation or model "
        "choice; that is the adversary's.",
        "It flags a bad permission but never changes it; the millwrights own permissions. And it never changes "
        "the repository to remediate: it writes the suggested fix, and a person applies it."],
    examples=[
        Exchange("1", ["A real run, on a throwaway repository with a fake token and an invented patient line. "
                       "The member is about to push.",
                       "The verdict is Blocked. Each finding has a rule name, a file and line, what was observed, and "
                       "a fix. It notes that both problems are already in history, so a new commit is not enough."],
                 [("git diff", True), ("secret patterns", True), ("PHI patterns", True), ("file modes", True)]),
    ],
    prompt="ask the security guard to audit this branch before I open the pull request",
    give="The diff, the branch or the folder. Say if the project is protected, so the patient-data scan runs.",
    verdicts="Clear / Concerns / Blocked, then each finding with its rule, location, evidence and suggested fix.",
    howto_narration=[
        "To use it, type to Claude Code and name it: ask the security guard to audit a branch, a diff or a folder "
        "before it leaves. Say if the project is protected.",
        "The first line is the verdict: Clear, Concerns or Blocked. Then each finding with a rule, a location, "
        "what was observed and the fix. Blocked means do not push until the history is clean."],
    docs=["rules/data-storage.md"],
)

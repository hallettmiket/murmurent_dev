"""The prospector movie: narration in the prospector's own voice, plain statements checked against agents/prospector.md, and the real run in transcript.md."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import SKY

SPEC = AgentSpec(
    agent="prospector",
    title="The prospector",
    tagline="Finds the funding you may apply for, reading each opportunity off the funder's own page",
    colour=SKY,
    icon="mag",
    intro=["I am the prospector. Tell me who you are, a student, a postdoc, a PI, what you work on and how far "
           "ahead you are looking, and I find the funding you may apply for, and bring back only what I dug up."],
    does=[
        Quote("Starts from the funder registry: the institution, the province, the country, the disease, the world.", "registry"),
        Quote("Searches beyond it for the disease-specific and the international.", "beyond"),
        Quote("Reports the gate: who may apply, what it pays, the deadlines, what the pre-application asks for.", "gate"),
        Quote("Every row names the page it was read from and the date.", "the date"),
    ],
    does_narration=[
        "I start from the funder registry the bookworm keeps: the institution's own competitions, then the "
        "province, the country, the disease, the world. Then I search beyond it, for the charities that fund "
        "your condition and the competitions open to you abroad.",
        "For each opportunity I report the gate and stop there: who may apply, what it pays, the registration or "
        "letter-of-intent date, the full deadline, what the pre-application asks for, and the institution's "
        "internal deadline. Every row names the page I read it from and the date."],
    refuses=[
        Quote("Never from memory: UNRESOLVED for a page it could not read today.", "UNRESOLVED"),
        Quote("Does not write the application; the scribe writes.", "scribe"),
        Quote("Does not walk the paperwork; the clerk does, from the institution pack.", "clerk"),
        Quote("Sends only public terms out in a search, never a name or a sentence of your draft.", "public terms"),
    ],
    refuses_narration=[
        "I know a great deal about funders, and much of it is out of date, so none of it counts. A page I could "
        "not read today is reported as UNRESOLVED, with the reason, never dropped and never filled in from memory.",
        "I do not write the application; the scribe writes. I do not walk the institution's paperwork; the clerk "
        "does, from the institution pack. And when I search the web, only public terms leave the machine: your "
        "field and condition, never your name and never a sentence of your draft."],
    examples=[
        Exchange("1", ["A real run. A second-year PhD student working on cystic fibrosis genomics asks what they can "
                       "apply for in the next twelve months.",
                       "I read the institution pack and the registry, then the funders' pages. Six are open: a travel award, "
                       "the provincial scholarship, a grant to work abroad, three internal awards. One site refused me, so "
                       "that row is UNRESOLVED, not dropped. The big doctoral scholarship closed in September, and I say so."],
                 [("read the pack", True), ("read the registry", True), ("search the web", True), ("open every page", True)], who="Student"),
    ],
    prompt="ask the prospector what I can apply for in the next twelve months: second-year PhD student, cystic fibrosis genomics, Canadian",
    give="Who you are, your field and condition in public words, your citizenship if it matters, and your horizon.",
    verdicts="Found N open, None open or Unknown, then one row per opportunity with its page and date.",
    howto_narration=[
        "To use me, type to Claude Code and name me, the prospector. Give me who you are, your field and "
        "condition in a few public words, your citizenship when it matters, and how far ahead you are looking.",
        "The first line is my verdict: Found, with the number open, None open, or Unknown. On request I also "
        "write the report as a web page and the deadlines as a calendar file, under outputs slash prospector."],
    directions=[
        ("ask the prospector for postdoctoral fellowships in immunology open to a Canadian, deadlines in the next year",
         "One row per fellowship: who may apply, what it pays, the deadlines, the page, the date."),
        ("ask the prospector to take my profile from my CV and find equipment competitions for an early-career PI",
         "The terms are taken from the file on this machine; only those terms go out in a search."),
        ("ask the prospector for the same report as a calendar file",
         "One calendar event per deadline, titled with the opportunity and the funder."),
    ],
    directions_narration=[
        "These are examples. Ask me for any kind of funding: a scholarship, a fellowship, an operating grant, an "
        "equipment competition, a travel award, a disease charity's call."],
    docs=["docs/funders.md", "docs/institution_pack.md"],
)

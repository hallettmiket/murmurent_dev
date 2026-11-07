"""The teacher movie: narration, quotes from agents/teacher.md, and the real exchange in transcript.md."""
from lib.agent_movie import AgentSpec, Exchange, Quote
from lib.draw import AMBER

SPEC = AgentSpec(
    agent="teacher",
    title="The teacher",
    tagline="Three modes: debrief, explain, course. It answers to Feynman.",
    colour=AMBER,
    icon="star",
    intro=["This is the teacher. It explains, in plain words, and it has three modes: debrief, explain "
           "and course. You type the verb."],
    does=[
        Quote("Dispatched as teacher <mode>: debrief, explain, or course.", "three"),
        Quote("re-pitch it in plain words, say what follows", "debrief"),
        Quote("make the mechanism land", "explain"),
        Quote("recognise it, refuse it, name the skill", "course"),
    ],
    does_narration=[
        "Its file gives the three modes. Debrief is for the sentence Claude Code just wrote that did not land: "
        "it re-pitches that in plain words and says what follows, in under a minute.",
        "Explain is for a method or a paper: make the mechanism land, in one sitting. Course is a subject that "
        "takes weeks: the teacher recognises it, refuses it, and names the course skill."],
    refuses=[
        Quote("DEBRIEF: no network, at all, ever.", "network"),
        Quote("Never emit a URL, title, timestamp, duration, or attribution you have not actually loaded.", "link"),
        Quote("You state next steps; you do not interrogate the reader about them.", "interrogate"),
        Quote("Do not draw what you could show.", "draw"),
    ],
    refuses_narration=[
        "In debrief it has no network, ever, because a search query is outbound text and your session is not "
        "public. It never emits a link or a title it has not actually loaded.",
        "It states next steps; it does not interrogate you about them. And it does not draw what it could show: "
        "a real image first, then a video, and a drawing only when nothing suitable exists."],
    examples=[
        Exchange("1", ["A real run, in explain mode. A wet-lab biologist asks what a permutation test is and why "
                       "the example uses five thousand of them.",
                       "The verdict is Explained. Bullets, three technical terms each defined, the real numbers from "
                       "the script it read, and a takeaway the reader can carry to the next problem."],
                 [("read run_all.py", True), ("re-run it", True), ("web search", False)]),
    ],
    prompt="teacher debrief",
    give="For debrief, nothing: it reads the tail of this session. For explain, the paper, method or file. For course, the subject.",
    verdicts="Explained / Gap. Gap is an honest failure, not a soft maybe.",
    howto_narration=[
        "To use it, type the verb to Claude Code. Teacher debrief, at the sentence that lost you. Teacher "
        "explain, followed by the thing. Teacher course, followed by the subject.",
        "The first line is the verdict: Explained, or Gap. Gap is the teacher being honest that it cannot deliver, "
        "which is the point of it. Ask for a page only when you will annotate it."],
    docs=["skills/murmurent-course/SKILL.md"],
)

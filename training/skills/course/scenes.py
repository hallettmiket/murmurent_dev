"""teacher course: a course across sessions, the COURSE mode of the teacher (issue #290)."""
from lib.draw import AMBER, TEAL
from lib.movie import Movie, Part, Quote

T_DIR = """
$ ls courses/permutation_tests
MISSION.md  PLAN.md  RESOURCES.md  learning-records  lessons  reference
$ ls courses/permutation_tests/lessons courses/permutation_tests/learning-records
lessons:
lesson_1.html
learning-records:
record_0.md
$ head -3 courses/permutation_tests/learning-records/record_0.md
# Record 0: baseline from the interview (2026-11-07)
No lesson has been taken yet. This record exists so the next session has
something to open with.
"""

MOVIE = Movie(
    key="course",
    title="Learning a subject with teacher course",
    tagline="A course across sessions, with a folder as its memory",
    glyph="🎓",
    colour=AMBER,
    summary="The course mode of the teacher: an interview for the mission, a plan, self-contained lessons with a drawn figure and a quiz, and learning records so it never re-teaches what you have shown.",
    parts=[
        Part("title", ["This is the course mode of the teacher. When a subject takes weeks rather than one sitting, "
                       "you type teacher course and the subject, and a course folder becomes its memory."]),
        Part("cards", chapter="The interview", heading="It interviews you first", source="skills/murmurent-course/SKILL.md",
             colour=TEAL,
             quotes=[Quote("Do not produce a lesson in an empty directory.", "empty"),
                     Quote("Interview first, one question at a time, waiting for each answer.", "one question"),
                     Quote("Where they currently get stuck. This is the most useful answer in the interview.", "stuck")],
             narration=["The skill's own file sets the first rule: no lesson in an empty folder. It interviews you "
                        "first, one question at a time, for the concrete reason you need the subject.",
                        "Where you currently get stuck is the most useful answer, because it tells the course what to "
                        "cut. The mission is written down and re-read every session."]),
        Part("chat", chapter="A real first session", key="1", agent="teacher", colour=AMBER, who="Learner",
             chips=[("interview", True), ("MISSION.md", True), ("PLAN.md", True), ("lesson_1.html", True), ("bookworm", False)],
             narration=["A real first session, with a learner whose answers were fixed for the movie. The mission "
                        "names the deadline and what done looks like. The plan is three lessons, one an hour.",
                        "The first lesson is a page with a figure you can play with: shuffle the labels and watch "
                        "the gaps pile up. The sources are pending, because the bookworm finds them, not memory."]),
        Part("terminal", chapter="The folder is the memory", heading="The course folder is the memory", transcript=T_DIR,
             title="Terminal", colour=TEAL,
             notes=[("Mission, plan, resources, lessons, learning records.", "records"),
                    ("A record says what you demonstrated, so it is never taught twice.", "demonstrated")],
             narration=["Everything lives in the course folder: the mission, the plan, the resources, the lessons and "
                        "the learning records. A record says what you demonstrated and what you fumbled, so a later "
                        "session never teaches twice what you have shown."]),
        Part("cards", chapter="Later sessions", heading="Later sessions open with retrieval", source="skills/murmurent-course/SKILL.md",
             colour=AMBER,
             quotes=[Quote("Before teaching anything new, ask two or three questions drawn from earlier lessons", "two or three"),
                     Quote("Struggling to retrieve is not a failure state; it is where the retention comes from.", "retention")],
             narration=["Later sessions open with retrieval, not content: two or three questions from earlier lessons, "
                        "weighted to what you fumbled. Struggling to recall is where the retention comes from, and "
                        "the skill does not rescue you from a pause."]),
        Part("howto", heading="How to use it",
             prompt="teacher course survival analysis",
             cards=[("Type the verb", "teacher course and the subject, in the main session; a subagent cannot interview you or keep a folder."),
                    ("Answer the interview", "What you will do with it, by when, what you have, where you are stuck."),
                    ("Annotate the lesson", "Open the page, mark the sentence that lost you, take the quiz; the next session starts there.")],
             docs=["skills/murmurent-course/SKILL.md", "agents/teacher.md"],
             narration=["To use it, type teacher course and the subject in your main session. Answer the interview. "
                        "Open each lesson, mark the sentence that lost you, take the quiz, and the next session starts "
                        "from your record. For one method or one paper, teacher explain is enough."]),
    ],
)

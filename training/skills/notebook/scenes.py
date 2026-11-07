"""Your lab notebook: a bench scientist's day, in natural language, with the commands as footnotes
(issues #292 to #294, revised after the PI's review of the first cut)."""
from lib.draw import AMBER, LAV, RED, TEAL
from lib.movie import Movie, Part, Quote

ENTRY = """---
date: '2026-11-07'
project: demo_project
sensitivity: standard
audience: supervisor
---
# 2026-11-07
Sessions: [[sessions/2026-11-07]]
## 09:10
Plan: run gel 27 on the four serum samples, lane 3 is the control; extract RNA from plates 5 and 6 after lunch.
## 11:40 image: gel_27.jpg
![[attachments/2026-11-07/gel_27_thumb.jpg]]
- original: lab-server:/data/lab_vm/append_only/demo_project/notebook/2026-11-07/gel_27.jpg (32 KB)
- note: lane 3 is the control
> Machine reading (image description, not the record): to be added in this session
## 11:52 sound note: gel27_voice.m4a
- original: lab-server:/data/lab_vm/append_only/demo_project/notebook/2026-11-07/gel27_voice.m4a (83 KB)""".split("\n")

T_REPORT = """
$ (what Claude Code runs: murmurent notebook report --for supervisor --since 2026-11-01)
Report for supervisor, 2026-11-01 to 2026-11-07: 1 entry of 2 in the range.
Entries drawn on (whole entries; audience is per entry):
  - lab-notebook/2026-11-07.md (2026-11-07, project demo_project, audience supervisor)
Files drawn on:
  - attachments/2026-11-07/gel_27_thumb.jpg (from the vault, embedded)
  - local:~/append_only/demo_project/notebook/2026-11-07/gel_27.jpg (on the server, linked)
Written: report.html (the page), material.md (for the scribe), sources.md (the source list)
Nothing has been sent. Read the page and the source list first; then deliver it:
  as a private Claude artifact, to the channel with murmurent project note, or as a file.
"""

MOVIE = Movie(
    key="notebook",
    title="Your lab notebook",
    tagline="A day at the bench, and how it ends up in your notebook",
    glyph="📓",
    colour=LAV,
    summary="A bench scientist's day with the lab notebook: the plan in the morning, a gel photo from the phone, a voice note with gloves on, a prompt written in Obsidian and sent to Claude Code with one keystroke, the day recalled, and a report for the supervisor. Natural language throughout; the commands as footnotes.",
    parts=[
        Part("title", ["Your lab notebook lives in your own Obsidian vault. This is a day at the bench and how it "
                       "gets into the notebook, by talking to Claude Code. The command behind each step is a "
                       "footnote; you never type it."]),
        Part("story", chapter="Morning: the plan", heading="Morning: write the plan in Obsidian", picture="bench",
             prompt="(in Obsidian, in today's entry) Plan: run gel 27 on the four serum samples, lane 3 is the control.",
             reply=["Nothing to run: the entry is a Markdown file in your vault, and the oracle reads it as it is."],
             footnote="none: lab-notebook/2026-11-07.md is yours to write; murmurent reads it",
             narration=["In the morning you write the plan in Obsidian, in today's entry, as in a paper notebook: a "
                        "line or two under a heading."]),
        Part("story", chapter="The gel photo", heading="At the bench: the gel photo, phone to laptop to notebook", picture="phone",
             prompt="add this photo of gel 27 to today's notebook, lane 3 is the control",
             reply=["Added image gel_27.jpg to today's entry under 11:40. Original sent to the lab server,",
                    "append_only/demo_project/notebook/2026-11-07/, never overwritten; a thumbnail in the vault.",
                    "Machine reading (not the record): four lanes, bands at two heights; lane 4 has an extra band."],
             footnote="murmurent notebook add ~/Desktop/gel_27.jpg --note \"lane 3 is the control\"",
             narration=["You photograph the gel with your phone and AirDrop it to the laptop. Drag the file into the "
                        "Claude Code window and say: add this photo of gel 27 to today's notebook, lane 3 is the "
                        "control.",
                        "The original goes to the lab server, never overwritten; the vault keeps a thumbnail and the "
                        "link; Claude Code adds one line on what it sees, marked as a reading, not the record."]),
        Part("story", chapter="A voice note", heading="Gloves on: a voice note", picture="gel",
             prompt="add my voice note gel27_voice.m4a to today's notebook",
             reply=["Added sound note gel27_voice.m4a under 11:52; the recording is on the lab server.",
                    "Not transcribed: the ElevenLabs key lacks the speech-to-text permission. The entry says so."],
             footnote="murmurent notebook add ~/Desktop/gel27_voice.m4a",
             narration=["With gloves on you record a voice note: lane four has an extra band, re-run it tomorrow. "
                        "Dropped into Claude Code the same way, it goes to the server and is transcribed when the "
                        "speech-to-text key is set up. Here it was not, and the entry says so."]),
        Part("obsidian", chapter="The entry", heading="The day's entry, as Obsidian shows it", note_title="2026-11-07",
             note_lines=ENTRY, sidebar=["2026-11-05", "2026-11-07", "attachments", "prompts", "sessions"],
             narration=["In Obsidian the day is one page: the plan, the gel with its thumbnail and the link to the "
                        "original, the voice note. At the top, the project and the audience: who may read this entry."]),
        Part("story", chapter="Prompts: write, send, keep", heading="Afternoon: a prompt written in Obsidian, sent with one keystroke",
             picture="obsidian",
             prompt="(written in prompts/2026-11-07.md, sent with the hotkey) ask the blacksmith to count the bands in gel_27.jpg per lane and compare lane 3, the control, with the others",
             reply=["The prompt lands in Claude Code and the blacksmith gets to work. It is also recorded in",
                    "sessions/2026-11-07/sent.md with the time, so it is never lost when the session closes."],
             footnote="murmurent prompt send   (an Obsidian hotkey runs it on the selected text)",
             narration=["Long prompts are easier to write in Obsidian than in a terminal. So you write them in a "
                        "prompts file in the vault and press one key: the prompt is pasted into Claude Code and "
                        "recorded with the time. A hook records every prompt that reaches Claude Code the same way, "
                        "so none scrolls away and vanishes."]),
        Part("chat", chapter="End of day: ask", key="1", agent="oracle", colour=LAV, who="Member",
             chips=[("read today's entry", True), ("read the sessions", True)],
             narration=["At the end of the day you ask the oracle what you noted about gel 27 and what is for "
                        "tomorrow. It answers from the entry, block by block, with the times, and says what it "
                        "could not read."]),
        Part("terminal", chapter="End of week: the report", heading="End of week: a report for your supervisor",
             transcript=T_REPORT, title="What Claude Code runs when you ask for the report", colour=LAV,
             notes=[("Only the entries you marked for a supervisor, whole entries.", "marked"),
                    ("Every entry and file it drew on is listed first.", "lists"),
                    ("Nothing is sent until you say so.", "sends nothing")],
             narration=["At the end of the week: make my report for my supervisor since Monday. It takes only the "
                        "entries you marked for a supervisor, lists every entry and file it drew on, and writes a "
                        "page, and sends nothing until you say so."]),
        Part("howto", heading="How to use it, day to day",
             prompt="add this photo of gel 27 to today's notebook, lane 3 is the control",
             cards=[("Photos and voice notes", "AirDrop from the phone to the laptop, then drag the file into Claude Code and say what it is."),
                    ("Prompts", "Write them in prompts/<date>.md in Obsidian; one hotkey sends the selection to Claude Code and keeps it."),
                    ("Sharing", "Set the entry's audience: me, supervisor, lab or a project. Ask for the report; nothing leaves without it.")],
             docs=["docs/lab_notebook.md"],
             narration=["Day to day: photos and voice notes go from the phone to the laptop and into Claude Code with "
                        "a sentence. Prompts are written in Obsidian and sent with a key. Sharing is per entry, by "
                        "its audience."]),
    ],
)

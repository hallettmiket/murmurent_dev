"""Your lab notebook: notes, captured media, prompts kept apart, and reports you choose to share (issues #292 to #294)."""
from lib.draw import AMBER, LAV, RED, TEAL
from lib.movie import Movie, Part, Quote

ENTRY = """---
title: '2026-11-07'
date: '2026-11-07'
project: demo_project
sensitivity: standard
audience: supervisor
tags: []
---
# 2026-11-07
Sessions: [[sessions/2026-11-07]]
## 14:48
Run 3 serum plates look bigger than the controls; re-plate the two Peru isolates tomorrow.
## 14:48 image: colony_figure.png
![[attachments/2026-11-07/colony_figure_thumb.jpg]]
- original: local:~/append_only/demo_project/notebook/2026-11-07/colony_figure.png (137.5 KB)
- note: the figure from this morning's run
> Machine reading (image description, not the record): to be added in this session
## 14:48 sound note: voice_note.m4a
- original: local:~/append_only/demo_project/notebook/2026-11-07/voice_note.m4a (63.8 KB)
## 14:48 file: counts_run3.csv
[[attachments/2026-11-07/counts_run3.csv]] (63 B)""".split("\n")

T_SPLIT = """
$ murmurent notebook split --dry-run
Would move pasted prompts from 1 entry:
  lab-notebook/2026-11-05.md: 1 block(s), 426 characters -> sessions/2026-11-05/pasted.md
      "You are the blacksmith. Please load data/signal.csv, compute the mean colony ..."
Nothing written (--dry-run).
$ murmurent notebook split
lab-notebook/2026-11-05.md: moved 1 block(s) to sessions/2026-11-05/pasted.md; original kept at obsolete/
Moved pasted prompts out of 1 entry. Originals are under obsolete/; nothing was deleted.
"""

T_REPORT = """
$ murmurent notebook report --for supervisor --since 2026-11-01 --title "Week of 3 November, for Mike"
Report for supervisor, 2026-11-01 to 2026-11-07: 1 entry of 2 in the range.
Entries drawn on (whole entries; audience is per entry):
  - lab-notebook/2026-11-07.md (2026-11-07, project demo_project, audience supervisor)
Files drawn on:
  - attachments/2026-11-07/colony_figure_thumb.jpg (from the vault, embedded)
  - attachments/2026-11-07/counts_run3.csv (from the vault, embedded)
  - local:~/append_only/demo_project/notebook/2026-11-07/colony_figure.png (on the server, linked)
Written: report.html (the page), material.md (for the scribe), sources.md (the source list)
Nothing has been sent. Read the page and the source list first; then deliver it:
  as a private Claude artifact, to the channel with murmurent project note, or as a file.
"""

MOVIE = Movie(
    key="notebook",
    title="Your lab notebook",
    tagline="Notes, photos and voice notes in your vault; prompts kept apart; reports you choose to share",
    glyph="📓",
    colour=LAV,
    summary="The lab notebook in your Obsidian vault: how to add text, photos, voice notes and files from Claude Code, where large files go, how prompts are kept out of your notes, and how to build a report for your supervisor or the lab from entries you chose to share.",
    parts=[
        Part("title", ["This is your lab notebook in Murmurent: in your own Obsidian vault, read by the oracle. From "
                       "Claude Code you drop in a line, a photo, a voice note or a file, and build a report from the "
                       "entries you choose to share."]),
        Part("cards", chapter="Two streams", heading="Two streams, written by two hands", source="docs/lab_notebook.md",
             colour=TEAL,
             quotes=[Quote("the day's own notes: short, headed, with frontmatter", "own notes"),
                     Quote("every prompt you gave Claude Code, with the time, project, repository and commit", "every prompt"),
                     Quote("you never paste a prompt into the notebook again", "pastes")],
             narration=["Two streams, because notes used to drown among pasted prompts. The day's entry holds your "
                        "own notes, and only that. Every prompt you give Claude Code goes to a separate sessions "
                        "stream, written by a hook with the time, project and commit. Nobody pastes a prompt again."]),
        Part("chat", chapter="Adding things", key="1", agent="notebook", agent_title="murmurent notebook add",
             colour=LAV, who="Member",
             chips=[("text", True), ("image to the server", True), ("thumbnail", True), ("sound note", True), ("transcribe", False)],
             narration=["A real run on a throwaway vault: add this to today's notebook, a line of text, a figure and a "
                        "voice note. Each becomes a block under a time heading.",
                        "The image goes to the project's folder on the data host, never overwritten; the vault keeps a "
                        "thumbnail and the link. A machine-written description is marked as a reading, not the record. "
                        "The voice note was not transcribed here, and the entry says why."]),
        Part("obsidian", chapter="In Obsidian", heading="The entry as Obsidian shows it", note_title="2026-11-07",
             note_lines=ENTRY, sidebar=["2026-11-05", "2026-11-07", "attachments", "sessions"],
             narration=["In Obsidian the entry is one page: the project, the sensitivity and the audience at the top; "
                        "a link to the day's sessions; then each block with its time, the thumbnail, the link to the "
                        "original on the server, and the small result file beside it."]),
        Part("terminal", chapter="Cleaning up old entries", heading="Prompts out of old notes: notebook split",
             transcript=T_SPLIT, title="Terminal: the skill runs this for you", colour=TEAL,
             notes=[("Prompt-shaped blocks move to the sessions stream; the notes stay.", "sessions stream"),
                    ("The original is kept under obsolete; nothing is deleted.", "deleted"),
                    ("Dry run first, so you see what moves.", "Dry run")],
             narration=["For older entries, one command moves the prompt-shaped blocks into the sessions stream "
                        "and leaves the notes. The original is kept under obsolete; nothing is deleted. A dry run "
                        "first shows what would move."]),
        Part("cards", chapter="Sharing", heading="What leaves the vault, and what never does", source="docs/lab_notebook.md",
             colour=RED, mark="cross",
             quotes=[Quote("Nothing leaves the notebook without an explicit audience.", "explicit audience"),
                     Quote("Audience is per entry, and a report takes whole entries.", "whole entries"),
                     Quote("nothing lets a supervisor read your me entries", "me entries")],
             narration=["Sharing is per entry. Each entry's audience is me by default, or supervisor, lab, or a "
                        "project. Nothing without an explicit audience ever leaves the vault, and a report takes whole "
                        "entries: to share one sentence, move it into its own entry.",
                        "Nothing lets a PI read a student's me entries. Restricted and protected entries are refused, "
                        "as publishing to the lab oracle refuses them."]),
        Part("terminal", chapter="A report for your supervisor", heading="A report for your supervisor",
             transcript=T_REPORT, title="Terminal: the skill runs this for you", colour=LAV,
             notes=[("Only the entries marked for that reader, in the date range.", "marked"),
                    ("Every entry and file it drew on is listed first.", "lists"),
                    ("Nothing is sent until you say so: an artifact, the channel, or a file.", "sent")],
             narration=["Say: make my weekly report for Mike. It takes only the entries marked for a supervisor, "
                        "lists every entry and file it drew on, and writes a page with a place for the scribe's "
                        "narrative. Nothing is sent until you say so."]),
        Part("howto", heading="How to use it",
             prompt="add this photo of the gel to today's notebook, lane 3 is the control",
             cards=[("Say it to Claude Code", "Add text, a photo, a voice note, a file; make my weekly report for Mike; split my old entries."),
                    ("Mark the audience", "In the entry's frontmatter: me, supervisor, lab, or project. Whole entries only."),
                    ("Search it", "Ask the oracle: it searches your notes first, then the prompts you gave Claude Code.")],
             docs=["docs/lab_notebook.md", "agents/oracle.md"],
             narration=["Say it to Claude Code: add this to today's notebook, make my weekly report, split my old "
                        "entries. Mark the audience when an entry is for someone else. And ask the oracle, which "
                        "searches your notes first and the prompts after."]),
    ],
)

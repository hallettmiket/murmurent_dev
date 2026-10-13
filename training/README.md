# Training

Material for learning Murmurent by watching rather than reading.

## Getting started with Murmurent (video, 6 min 50 s)

A narrated walkthrough for someone who has never used Murmurent. It explains
what Murmurent is, then goes through installing it, checking the install,
saying who you are and setting up a folder to work in. It then introduces the
agents and shows how members, lab heads (PIs) and centres join up. Each step
appears on screen as the commands you would type.

| | |
|---|---|
| **Where it is** | [Google Drive folder](https://drive.google.com/drive/folders/1KMUkXi2XyS6sO8H7M_YicwaSk8ylQ7dZ), open to anyone with the link: `murmurent_getting_started_1080p.mp4` (33 MB, 1080p, English captions built in), to watch in the browser or download |
| **Transcript** | [murmurent_getting_started.srt](murmurent_getting_started.srt), in this folder: the full narration with timings, which also works as a subtitle file |
| **Made by** | Vaibhav Gupta ([@Vaibhavg037](https://github.com/Vaibhavg037)), who keeps the script, the voiceover clips and the code that renders it |
| **Checked against** | Murmurent 2026.9.9 |

### Chapters

| Time | Chapter | Covers |
|---|---|---|
| 0:00 | Welcome | |
| 0:14 | What Murmurent is | the agents, members, groups, projects and centres; choreography, not orchestration |
| 0:55 | The plan | |
| 1:10 | Before you start | a terminal on macOS or Linux, git, Claude Code |
| 1:28 | Step 1: install | `uv tool install murmurent`, `murmurent install` |
| 2:00 | Step 2: check the install | `murmurent doctor` |
| 2:20 | Step 3: say who you are | `murmurent init`, the three roles, `murmurent whoami` |
| 2:48 | Step 4: set up a folder | `murmurent repo status`, `repo adopt`, `repo upgrade` |
| 3:20 | Meet the agents | the commons and what each agent does |
| 3:58 | Joining a lab (members) | `murmurent enroll`, member cards, confirming the trust root, `import-card` |
| 4:38 | Joining a centre (PIs) | the public hub, the encrypted join request, the PI ID |
| 5:09 | Starting a centre (mayors) | `centre-init`, `centre-hub-publish` |
| 5:26 | Choreographies | `choreography list`, `install`, `init`, publishing one to the hub |
| 6:03 | Getting help | asking Claude Code, `murmurent doctor`, where to report bugs |
| 6:30 | Recap | |

### How it was made

The narration is a synthetic voice (ElevenLabs, voice "Matilda") reading a
written script, over an instrumental ElevenLabs Music track. The slides and
terminal animations are drawn in Python. Every command shown was run against
Murmurent 2026.9.9, and the output on screen comes from those runs, with the
home folder replaced by `~` or a demo user. The profile details, the example
centre and its key are invented. No real member's contact details appear.

### When it goes out of date

If a later release changes a command shown in the video, the written
documentation is correct and the video is not. To update it:

1. Ask the maker (above) to edit the script and rebuild the video.
2. Replace the video and captions in the Google Drive folder.
3. Replace `murmurent_getting_started.srt` in this folder with the new captions,
   and update the chapter times and the "Checked against" version above.

# Training

Material for learning Murmurent, and for the tools used to make it.

**All the videos, in one place: <https://mikehallett.science/assets/videos/>.**
That page, and the "Videos and news" section of the README, are written by
`training/front_page.py` from [`index.yaml`](index.yaml) in this folder: add a
video or a news line there and run the script; never edit the generated section
by hand (a test checks it).

1. [Getting started with Murmurent](#getting-started-with-murmurent-video-7-min-10-s), a 7-minute video
2. [Using ElevenLabs from Claude Code](#using-elevenlabs-from-claude-code), from signing up to making audio, including the free student offer
3. [A thesis an examiner can question](thesis_package/README.md), a 6-minute animated walkthrough of paper packages, thesis packages and the docent, rendered from a script in that folder
4. [One short movie per agent](#one-short-movie-per-agent), twenty movies of about two minutes each: what the agent does, what it will not do, one real run, and how to use it through Claude Code
5. [Working through Claude Code, and the skills](#working-through-claude-code-and-the-skills), seven movies of two to three minutes: the one every other movie assumes, the two push skills, the status update, a course across sessions, the mayor's tools, the lab notebook, and the data root

## One short movie per agent

One movie for each of the twenty commons agents (issue #288), each about two
minutes, in the same style as the thesis-package video: drawn from a script,
every chat scene a real run of the agent on `examples/` or on synthetic data,
captions burned in, narration with ElevenLabs. Each agent speaks for itself,
in the first person and in a voice of its own (the table of voices is in
[`agents/README.md`](agents/README.md)), so a viewer gets to know them one
by one; the skill movies keep the narrator, Matilda. Each movie
quotes the agent's own `agents/<agent>.md` for what it does and what it
refuses, so a change to the agent is a change to the movie, and a hook reminds
a session to re-render when the agent file is edited. How they are made and
updated: [`agents/README.md`](agents/README.md).

**Checked against** Murmurent 2026.11.1, 9 November 2026. All twenty are
narrated; the prospector's was added 12 November 2026, the detective's 21 November 2026 and the lookout's 26 November 2026, all against 2026.11.2. Each scene is timed from the measured length of its voice clip, so
re-voicing a changed sentence re-times the picture with it.

**Every movie opens with a cold open** in the agent's own character, taken from its
`agents/<agent>.md` and nothing else: the "personality" section where there is one, the agent's
own rules where there is not. The prospector's came first (a Yukon prospector blasting a mountain of funding open, the clip
that announced the movie). Then, on the shared engine
[`lib/opening.py`](lib/opening.py), one spec each in `agents/<agent>/opening/make_clip.py`: the
blacksmith hammers a bar at the forge, loud, and then calmly measures it; the bookworm shushes the
fireworks out of the window and turns a page; the artist paints a grey bar chart into "a visual
sonnet"; the adversary, at 11 pm, types an email with the subject "a few small thoughts" and stamps
"no catastrophic failure, noted" on a result; the millwright wires one cable, ticks installed,
tested, documented, and leaves by ten. The lawyer's opening is the one that talks: a 33-second
late-night television advertisement in its own voice (have you or a loved one been handed a molecule
with a patent on it; no win, no fee; the fine print is the true part), a scene of the narrated movie
itself rather than a spliced clip. So is the clerk's: window four of a counter that has seen it all,
a lit cigarette under the NO SMOKING sign, a NOW SERVING display stuck at eight, and the one thing
said in earnest, that the answer is read off the page and is Unknown when the page does not say.
And the security guard's: a red head-up display from a certain kind of 1980s film scans the change you are
about to push, finds an API key, a date of birth and a sandwich (the sandwich may proceed), gives you
twenty seconds to comply, and says Clear, in a rugged German accent (Rufus).
The conscience's reviews those three: each gets a sticky note with a located finding and its source
(who counts as a loved one; a queue assumes you can stand in it; not everyone reads at that speed),
the footnotes pile up, and it speaks for no one. The thumbnails are the other movies' own openings,
drawn by their own files.
The scribe's is a clean, well-lighted sentence: it writes the way Ernest Hemingway wrote, and says so, taking
a forty-one-word sentence apart on a typewriter page, the passive voice mounted on the wall like a marlin,
the glass untouched until the figure legend is done, and the house style, which says do not go choppy,
winning in the end.
The lookout's is the crow's nest at dawn: a spyglass sweeps an empty horizon, then three sightings come
over it and each is rung on the ship's bell by how much it matters (a changelog, three bells, adopt; a memory
paper, two bells, consider; a video that will change everything, one bell, watch, from the transcript, not
watched), and the true part is the last line, that it rings the bell and does not steer the ship (Laura).
The last seven, added 21 November 2026, each six seconds on the shared engine: the oracle answers
before the question is typed, the notes lighting up one by one through the vault (MMP11, run 17, and you
wrote "never again"); the lab oracle is a museum case of reviewed scrolls, frost on the glass, and a sticky
note reading "my hunch!!" bounces off it while a PI-reviewed scroll comes down the publish slot; the
teacher reads a smooth sentence off the blackboard, asks what it even means, wipes it, and draws a ball
rolling down a hill; the centre millwright flips the one red cell at 8:57 and the standup walks in at 9:00
without looking at the screen; the judge ends the party for gene A with three gavel blows and rules SPLIT,
two say A, one says B, no shared metric, the work shown on the wall; the registrar stamps OPAQUE on a lab
someone tried to peek into, signs and seals a PI card, and flips a dragged lab to "archived" with the bin
still empty; the docent walks a visitor to Table 2 (Located), to the empty frame (Absent), and re-runs the
code before saying 0.81, the visitors' log ticking up by three.
`make_clip.py --prepend` renders the clip and splices it onto
the narrated movie, shifting the captions; `publish.py` shows that spliced copy. The six seconds are
counted in the lengths and chapter times below.

| Agent | Watch | Length | Narrated | Chapters |
|---|---|---|---|---|
| [`oracle`](../agents/oracle.md) | [The oracle](https://mikehallett.science/assets/videos/murmurent_agent_oracle.html) | 2:12 | yes | 0:00 Opening, 0:06 Welcome, 0:19 What it does, 0:43 Its scope, 1:06 A real example, 1:50 How to use it |
| [`bookworm`](../agents/bookworm.md) | [The bookworm](https://mikehallett.science/assets/videos/murmurent_agent_bookworm.html) | 2:37 | yes | 0:00 Opening, 0:06 Welcome, 0:16 What it does, 0:53 Its scope, 1:17 A real example, 1:36 How to direct it, 2:04 How to use it |
| [`adversary`](../agents/adversary.md) | [The adversary](https://mikehallett.science/assets/videos/murmurent_agent_adversary.html) | 2:46 | yes | 0:00 Opening, 0:06 Welcome, 0:17 What it does, 1:06 Its scope, 1:30 A real example, 2:00 How to direct it, 2:18 How to use it |
| [`artist`](../agents/artist.md) | [The artist](https://mikehallett.science/assets/videos/murmurent_agent_artist.html) | 1:49 | yes | 0:00 Opening, 0:06 Welcome, 0:13 What it does, 0:33 Its scope, 0:50 A real example, 1:11 How to direct it, 1:27 How to use it |
| [`scribe`](../agents/scribe.md) | [The scribe](https://mikehallett.science/assets/videos/murmurent_agent_scribe.html) | 2:53 | yes | 0:00 A clean, well-lighted sentence, 0:45 Welcome, 0:57 What it does, 1:28 Its scope, 1:52 A real example, 2:10 How to direct it, 2:31 How to use it |
| [`teacher`](../agents/teacher.md) | [The teacher](https://mikehallett.science/assets/videos/murmurent_agent_teacher.html) | 3:06 | yes | 0:00 Opening, 0:06 Welcome, 0:22 What it does, 0:51 Its scope, 1:29 A real example, 1:51 The idea, 2:33 How to direct it, 2:48 How to use it |
| [`lab_oracle`](../agents/lab_oracle.md) | [The lab oracle](https://mikehallett.science/assets/videos/murmurent_agent_lab_oracle.html) | 1:47 | yes | 0:00 Opening, 0:06 Welcome, 0:15 What it does, 0:31 Its scope, 0:47 A real example, 1:23 How to use it |
| [`blacksmith`](../agents/blacksmith.md) | [The blacksmith](https://mikehallett.science/assets/videos/murmurent_agent_blacksmith.html) | 1:57 | yes | 0:00 Opening, 0:06 Welcome, 0:16 What it does, 0:40 Its scope, 0:59 A real example, 1:20 How to direct it, 1:36 How to use it |
| [`conscience`](../agents/conscience.md) | [The conscience](https://mikehallett.science/assets/videos/murmurent_agent_conscience.html) | 2:59 | yes | 0:00 Reviewed before release, 0:26 Welcome, 0:42 What it does, 1:24 Its scope, 1:54 A real example, 2:15 How to direct it, 2:31 How to use it |
| [`lawyer`](../agents/lawyer.md) | [The lawyer](https://mikehallett.science/assets/videos/murmurent_agent_lawyer.html) | 2:55 | yes | 0:00 A word from our sponsor, 0:33 Welcome, 0:51 What it does, 1:22 Its scope, 2:02 A real example, 2:31 How to use it |
| [`millwright`](../agents/millwright.md) | [The millwright](https://mikehallett.science/assets/videos/murmurent_agent_millwright.html) | 2:07 | yes | 0:00 Opening, 0:06 Welcome, 0:19 What it does, 0:54 Its scope, 1:21 A real example, 1:38 How to use it |
| [`centre_millwright`](../agents/centre_millwright.md) | [The centre millwright](https://mikehallett.science/assets/videos/murmurent_agent_centre_millwright.html) | 1:47 | yes | 0:00 Opening, 0:06 Welcome, 0:18 What it does, 0:45 Its scope, 1:02 A real example, 1:19 How to use it |
| [`judge`](../agents/judge.md) | [The judge](https://mikehallett.science/assets/videos/murmurent_agent_judge.html) | 2:23 | yes | 0:00 Opening, 0:06 Welcome, 0:16 What it does, 0:52 Its scope, 1:22 A real example, 1:54 How to use it |
| [`registrar`](../agents/registrar.md) | [The registrar](https://mikehallett.science/assets/videos/murmurent_agent_registrar.html) | 1:51 | yes | 0:00 Opening, 0:06 Welcome, 0:18 What it does, 0:43 Its scope, 1:03 A real example, 1:20 How to use it |
| [`security_guard`](../agents/security_guard.md) | [The security guard](https://mikehallett.science/assets/videos/murmurent_agent_security_guard.html) | 2:25 | yes | 0:00 Halt, 0:34 Welcome, 0:46 What it does, 1:10 Its scope, 1:36 A real example, 2:03 How to use it |
| [`clerk`](../agents/clerk.md) | [The clerk](https://mikehallett.science/assets/videos/murmurent_agent_clerk.html) | 2:58 | yes | 0:00 Window four, 0:25 Welcome, 0:41 What it does, 1:09 Its scope, 1:34 A real example, 2:23 How to direct it, 2:36 How to use it |
| [`docent`](../agents/docent.md) | [The docent](https://mikehallett.science/assets/videos/murmurent_agent_docent.html) | 2:06 | yes | 0:00 Opening, 0:06 Welcome, 0:17 What it does, 0:40 Its scope, 1:09 A real example, 1:39 How to use it |
| [`prospector`](../agents/prospector.md) | [The prospector](https://mikehallett.science/assets/videos/murmurent_agent_prospector.html) | 3:06 | yes | 0:00 Opening, 0:06 Welcome, 0:22 What it does, 1:02 Its scope, 1:40 A real example, 2:16 How to direct it, 2:30 How to use it |
| [`detective`](../agents/detective.md) | [The detective](https://mikehallett.science/assets/videos/murmurent_agent_detective.html) | 2:58 | yes | 0:00 The report you are about to read, 0:38 Welcome, 0:52 What it does, 1:25 Its scope, 1:55 A real example, 2:19 How to direct it, 2:38 How to use it |
| [`lookout`](../agents/lookout.md) | [The lookout](https://mikehallett.science/assets/videos/murmurent_agent_lookout.html) | 2:31 | yes | 0:00 Crow's nest, 0:35 Welcome, 0:48 What it does, 1:20 Its scope, 1:43 A real example, 1:57 How to direct it, 2:15 How to use it |


## Working through Claude Code, and the skills

Seven movies (issue #290, and the lab notebook and the data root at Mike's request) in the same style as the agent movies, from
[`training/skills/`](skills/): one scene file each on the shared renderer
(`training/lib/movie.py`), quotes checked against the skill's own `SKILL.md`,
every terminal and chat scene a real run (dry runs where a real one would post
or change something; a throwaway repository with invented secrets for the push
skills), captions burned in, narration with ElevenLabs. **Working through
Claude Code** is the one to watch first: every other movie assumes it.

**Checked against** Murmurent 2026.11.1, 9 November 2026. The getting-started
video (made against 2026.9.9) was re-checked the same day: every command it
shows still exists, and it now ends with a short coda pointing at the Claude
Code movie.

| Movie | Watch | Length | Chapters |
|---|---|---|---|
| [`training/skills/claude_code`](skills/claude_code/scenes.py) | [Working through Claude Code](https://mikehallett.science/assets/videos/murmurent_claude_code.html) | 2:18 | 0:00 Welcome, 0:09 Opening a project, 0:31 Addressing an agent, 0:51 A real exchange, 1:13 The agent log pane, 1:31 What the hooks refuse, 1:58 How to use it |
| [`training/skills/push`](skills/push/scenes.py) | [Backing up with /murmurent-push](https://mikehallett.science/assets/videos/murmurent_push.html) | 2:04 | 0:00 Welcome, 0:09 What it refuses, 0:37 A real run, 1:01 Where the note goes, 1:22 The whole project, 1:43 How to use it |
| [`training/skills/update_me`](skills/update_me/scenes.py) | [A status update with /murmurent-update-me](https://mikehallett.science/assets/videos/murmurent_update_me.html) | 1:43 | 0:00 Welcome, 0:12 Where the facts come from, 0:34 The script, 0:53 A real dry run, 1:13 What it refuses, 1:27 How to use it |
| [`training/skills/course`](skills/course/scenes.py) | [Learning a subject with teacher course](https://mikehallett.science/assets/videos/murmurent_course.html) | 1:51 | 0:00 Welcome, 0:11 The interview, 0:33 A real first session, 0:58 The folder is the memory, 1:14 Later sessions, 1:30 How to use it |
| [`training/skills/mayor_tools`](skills/mayor_tools/scenes.py) | [The mayor's and PI's tools](https://mikehallett.science/assets/videos/murmurent_mayor_tools.html) | 1:57 | 0:00 Welcome, 0:11 /murmurent-admin, 0:36 /murmurent-onboard, 1:03 What onboard refuses, 1:17 /murmurent-reset, 1:40 How to use it |
| [`training/skills/notebook`](skills/notebook/scenes.py) | [Your lab notebook](https://mikehallett.science/assets/videos/murmurent_notebook.html) | 2:30 | 0:00 Welcome, 0:13 Morning: the plan, 0:23 The gel photo, 0:49 A voice note, 1:07 The entry, 1:23 Prompts: write, send, keep, 1:44 End of day: ask, 1:59 End of week: the report, 2:14 How to use it |
| [`training/skills/data_root`](skills/data_root/scenes.py) | [The data root: where big files live](https://mikehallett.science/assets/videos/murmurent_data_root.html) | 2:50 | 0:00 Welcome, 0:09 Three tiers, 0:29 The folders, 0:54 What each folder is for, 1:59 What the hooks refuse, 2:18 Keeping it tidy, 2:32 How to use it |

## Getting started with Murmurent (video, 7 min 10 s)

A narrated walkthrough for someone who has never used Murmurent. It explains
what Murmurent is, then goes through installing it, checking the install,
saying who you are and setting up a folder to work in. It then introduces the
agents and shows how members, lab heads (PIs) and centres join up. Each step
appears on screen as the commands you would type.

| | |
|---|---|
| **Where it is** | [mikehallett.science](https://mikehallett.science/assets/videos/murmurent_getting_started.html), to watch in the browser with captions. The [video file itself](https://mikehallett.science/assets/videos/murmurent_getting_started_1080p.mp4) (33 MB, 1080p) can be downloaded. |
| **Transcript** | [murmurent_getting_started.srt](murmurent_getting_started.srt), in this folder: the full narration with timings, which also works as a subtitle file |
| **Made with** | [ElevenLabs](https://elevenlabs.io): the narration (voice "Matilda") and the music |
| **Checked against** | Murmurent 2026.9.9; every command re-checked against 2026.11.0 on 2026-11-07 |

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
| 6:50 | Coda | watch the Claude Code movie next (added 2026-11-07) |

### How it was made

The narration and music were generated with ElevenLabs from a written script,
using the setup in the next section, and combined with on-screen slides and
terminal animations. Every command shown was run against Murmurent 2026.9.9,
and the output on screen comes from those runs, with the home folder replaced
by `~` or a demo user. The profile details, the example centre and its key are
invented. No real member's contact details appear.

### When it goes out of date

If a later release changes a command shown in the video, the written
documentation is correct and the video is not. To update it, re-voice the
changed lines with ElevenLabs (same voice, "Matilda", and model
`eleven_multilingual_v2`), rebuild the video, and replace the video and
captions in the Google Drive folder. Then replace
`murmurent_getting_started.srt` here and update the chapter times and the
"Checked against" version above.

## Using ElevenLabs from Claude Code

[ElevenLabs](https://elevenlabs.io) makes AI voice and audio. Connected to
Claude Code, it lets you ask Claude, in plain words, to:

- read text aloud and save it as an audio file
- transcribe a recording, with each speaker labelled
- make sound effects or music
- clone a voice, or design a new one from a description
- clean background noise out of a recording

The steps below are for macOS and take about 15 minutes. They were tested in
October 2026.

> **Before you send anything:** text and audio you give ElevenLabs go to its
> servers. Never use it with clinical or restricted data, or with recordings of
> people who haven't agreed to it.

### Step 1: Get an ElevenLabs account (free for 3 months if you're a student)

**University students** can get the ElevenLabs **Creator plan free for 3
months**, which includes the API that Claude Code uses. As of October 2026 the
offer is for university students aged 18 and over in Canada, the US, the UK,
the EU and Australia.

1. Go to <https://elevenlabs.io/students> and click **Get 3 months free**.
2. Sign up, or sign in if you already have an account.
3. Verify that you're a student when asked.
4. Check it worked: in your account, the plan should say **Creator**.

**Check what happens after 3 months.** ElevenLabs doesn't say publicly whether
the plan then starts charging or drops back to free. Look at
**Subscription** in your account settings as soon as you're in, and put a
reminder in your calendar a week before the 3 months end. Cancel then if you
don't want to pay.

The same page also offers a separate free year of **ElevenReader Ultra**, an
app that reads documents aloud. You don't need it for anything here.

**Not a student?** The free plan works for everything below. It gives 10,000
credits a month (roughly 10,000 characters of speech) but doesn't include voice
cloning.

### Step 2: Create an API key

The API key is the password Claude Code uses to reach your ElevenLabs account.

1. Go to <https://elevenlabs.io/app/settings/api-keys> and create a new key.
2. Name it (for example `claude`) and leave **Expire After** on **Never**. For
   full access, don't restrict it.
3. **Copy the key from the popup straight away.** It starts with `sk_` and is
   shown only this once. Afterwards the website only shows the key's ID, which
   looks similar but doesn't work as a key. If you lose the key, delete it and
   create another.

Never paste the key into a chat (with Claude, Slack or anyone), an email, or a
file in a repository. The next steps store it where only your Mac can read it.

### Step 3: Install the ElevenLabs connector

You need Claude Code and [`uv`](https://docs.astral.sh/uv/), which you already
have if you installed Murmurent. In a terminal:

```bash
uv tool install elevenlabs-mcp
```

This is ElevenLabs' official connector for the full API. ElevenLabs has also
released a hosted connector that needs no key, but it only covers voice agents
and simple text-to-speech, so it isn't used here.

### Step 4: Store the key in your Mac's Keychain

```bash
security add-generic-password -U -a "$USER" -s elevenlabs-api-key -w
```

Paste the `sk_` key when asked, press Enter, then paste it again. Nothing
appears while you paste; that's normal. Running the command again replaces the
stored key.

### Step 5: Add a launcher that reads the key

This makes a small script that fetches the key from the Keychain each time the
connector starts, so the key is never written into a settings file. Copy the
whole block into a terminal:

```bash
mkdir -p ~/.local/bin
cat > ~/.local/bin/elevenlabs-mcp-keychain <<'EOF'
#!/bin/sh
# Start the ElevenLabs connector with the API key from the macOS Keychain.
if [ -z "$ELEVENLABS_API_KEY" ]; then
  ELEVENLABS_API_KEY="$(/usr/bin/security find-generic-password \
    -a "${USER:-$(id -un)}" -s elevenlabs-api-key -w 2>/dev/null)" || {
    echo "elevenlabs-mcp: no API key in Keychain (service 'elevenlabs-api-key')" >&2
    exit 1
  }
  export ELEVENLABS_API_KEY
fi
exec "$HOME/.local/bin/elevenlabs-mcp" "$@"
EOF
chmod 700 ~/.local/bin/elevenlabs-mcp-keychain
```

### Step 6: Connect it to Claude Code

```bash
claude mcp add --scope user elevenlabs -- "$HOME/.local/bin/elevenlabs-mcp-keychain"
```

`--scope user` makes ElevenLabs available in every project. If your terminal
says `claude: command not found` (common if you only use the Claude desktop
app), open a Claude Code session and ask it to *"add a user-scope MCP server
called elevenlabs that runs ~/.local/bin/elevenlabs-mcp-keychain"*.

### Step 7: Check it works

Start a **new** Claude Code session (sessions that were already open don't see
new connectors) and ask:

> Check my ElevenLabs subscription.

Claude should reply with your plan and how many credits you've used. If it
says *"API key ID used as API key"*, you stored the key's ID rather than the
key: go back to Step 2, create a new key, and repeat Step 4.

### Step 8: Use it

Ask for what you want in plain words, for example:

- *"Use ElevenLabs to read this paragraph aloud in a calm voice and save it."*
- *"Transcribe `meeting.m4a` on my Desktop, with speakers labelled."*
- *"Make a 5-second sound effect of rain on a window."*
- *"List the ElevenLabs voices that sound like a British narrator."*

Things to know:

- **Files go to your Desktop.** Audio Claude makes is saved there, and audio
  you want transcribed, cloned or cleaned must be on your Desktop too. To use
  another folder, run Step 6 like this instead (remove the old one first with
  `claude mcp remove elevenlabs -s user`):

  ```bash
  claude mcp add --scope user elevenlabs --env ELEVENLABS_MCP_BASE_PATH="$HOME/Documents/audio" -- "$HOME/.local/bin/elevenlabs-mcp-keychain"
  ```
- **Everything uses credits.** Ask *"check my ElevenLabs subscription"* to see
  how many you have left.
- **One tool makes real phone calls.** The connector can place outbound calls
  through ElevenLabs voice agents. They reach real numbers and cost money, so
  only approve that tool if you meant to.
- **Claude asks before each ElevenLabs action**, depending on your permission
  settings. Read what it's about to do before you approve.

### Removing it

```bash
claude mcp remove elevenlabs -s user
uv tool uninstall elevenlabs-mcp
security delete-generic-password -a "$USER" -s elevenlabs-api-key
rm ~/.local/bin/elevenlabs-mcp-keychain
```

Then delete the key at <https://elevenlabs.io/app/settings/api-keys>, and
cancel the plan under **Subscription** if you no longer need it.

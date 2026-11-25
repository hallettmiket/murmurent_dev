# Slack: this deployment's specifics

**Not part of the public release.** `rules/slack.md` carries the protocol; this
file carries the facts that are true only here. Keep IDs in this file and out
of the shared rule.

Do not append a sign-off phrase to Slack messages.

## Where a note goes

**Every repository's notes go where `murmurent project note` sends them**: the
project's own channel (`#proj-<project>`, or `#murmurent` for the Murmurent
project), else the lab's channel. Do not name a channel yourself: one channel
for every push is how the notes of a dozen projects end up together.

The one exception is recorded in the repository itself, not here: a repository
whose `.murmurent.yaml` sets `slack_channel:` sends its notes there. That is
how a development repository keeps its traffic out of a channel the whole lab
reads.

## Workspace and bot

For lab `mh` the workspace is **Computational Biology Western**
(`comp-bio-westernu`), bot user `@murmurent2` (`U0BHESELBAL`). The bot is a
member of every provisioned project channel; if a post fails with
`not_in_channel`, invite it once in Slack: `/invite @murmurent2`.

`#claude-test` (`C0B3D9DS6SE`) is the public channel kept for trying things
out. Nothing routes there unless a repository's marker says so.

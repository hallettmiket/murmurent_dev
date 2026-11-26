# The lookout's videos: this deployment's specifics

**Not part of the public release.**

- On Mike's Mac, `MURMURENT_LOOKOUT_VIA` is `biodatsci` (in `~/.claude/settings.json`).
  YouTube refused the Mac's transcript requests from home (Rogers) on 2026-11-26 and
  answered biodatsci. biodatsci has `uv` at `~/.local/bin/uv`; the script adds that to
  `PATH` itself. Batch-mode ssh from the Mac to biodatsci works with the Mac's own key.
- A desktop-app scheduled task, `lookout-videos`, runs `/murmurent-lookout-videos` on the
  Mac on Monday and Thursday at 9:30, after the cloud lookout at 7:07.
- The lookout's issues are in `hallettmiket/murmurent_dev`, which is public: never put a
  transcript in it.

# Talk videos on mikehallett.science: how they get there

**Not part of the public release.** Recorded 2026-10-24, after two sessions in a
row spent most of an hour rediscovering this.

## Where things live

| What | Where |
|---|---|
| Original movies (full size) | biodatsci: `/data/lab_vm/append_only/murmurent_seminar/movies/` |
| Web-size copies | biodatsci: `/data/lab_vm/append_only/murmurent_seminar/movies_web/<name>_web.mp4` |
| What the public sees | biodatweb: `/var/www/html/mhallet/murmurent_seminar/` = `https://biodatweb.schulich.uwo.ca/mhallet/murmurent_seminar/` |
| The links | `~/repos/hallettmiket.github.io/lab-pages.jsx`, `BLOG_POSTS` (`video:` and `slides:` fields) |
| Slides | GitHub Pages: `hallettmiket.github.io/assets/<talk>_presentation.html` (too small to need biodatweb) |

Each video on biodatweb is a pair: `<talk>.mp4` and a small `<talk>.html` page
that plays it. The blog links the `.html` page. Replacing a video therefore means
replacing only the `.mp4`; the page and the website link stay the same.

## Logging in to biodatweb: only from biodatsci, with its long-running agent

**The laptop cannot log in to biodatweb.** Its keys are refused for both `mth`
and `mhallet`. Do not keep retrying from the laptop.

**biodatsci can, but only with the right SSH agent.** An SSH session from the
laptop to biodatsci forwards the laptop's agent, and those keys are refused too.
The key biodatweb accepts (`hallett.mike.t@gmail.com`, ED25519) is held by the
long-running agent whose socket is recorded in `~/.ssh/agent-env` on biodatsci:

```bash
ssh biodatsci 'source ~/.ssh/agent-env >/dev/null;
  ssh -o BatchMode=yes mhallet@biodatweb.schulich.uwo.ca "ls -la /var/www/html/mhallet/murmurent_seminar/"'
```

If that agent has died (the socket no longer exists, or `ssh-add -l` is empty),
Mike must log in to biodatsci and run `ssh-add` once; a session cannot supply the
passphrase.

## Steps to publish a new or updated talk video

1. **Copy the original to biodatsci** (new file; `append_only` never overwrites):
   `rsync -t --ignore-existing --partial movies/<file>.mp4 biodatsci:/data/lab_vm/append_only/murmurent_seminar/movies/`
2. **Make the web-size copy on biodatsci.** A 3 GB, 22-minute export comes out
   near 400 MB. ffmpeg is installed in `/data/lab_vm/cottage/mhallet/envs/ffmpeg_web`
   (the system has none; the binary is under that environment's
   `lib/python3.12/site-packages/imageio_ffmpeg/binaries/`):
   ```bash
   nice -n 19 $FF -i movies/<file>.mp4 -c:v libx264 -preset slow -crf 24 \
     -maxrate 4M -bufsize 8M -pix_fmt yuv420p -threads 24 \
     -c:a aac -b:a 128k -movflags +faststart movies_web/<file>_web.mp4
   ```
3. **Copy it to biodatweb from biodatsci**, under the name the page plays, with
   the long-running agent (step above), then `chmod 644`.
4. **New talk only:** add a `<talk>.html` page beside it (copy an existing one and
   change the title and `src`), and add the `video:` link to the blog post in
   `lab-pages.jsx`. A replacement needs neither.
5. **Check** `curl -sI https://biodatweb.schulich.uwo.ca/mhallet/murmurent_seminar/<talk>.mp4`
   reports the new `Content-Length`.

## Things that trip a session

- The murmurent hooks refuse any command that deletes under `/data/lab_vm`,
  including your own scratch folder in `cottage/`. Put server scratch in `/tmp`
  and delete it in a separate command that does not mention `/data/lab_vm`.
- `git pull` in `~/repos/hallettmiket.github.io` fails when Mike has unstaged
  changes there (`pull.rebase` is on). Use `git fetch` then `git merge --ff-only
  origin/master`, which works as long as his changes touch other files.

# The exchanges shown in the movie

Real output of the pre-flight commands the /murmurent-push skill runs, on 2026-11-07
(Murmurent 2026.11.0), in a throwaway repository made for this movie: a staged file with
token-shaped strings (both invented), an untracked credentials.yaml, and a 2.9 MB file under
data/. Nothing was pushed anywhere.

## 1
Member: /murmurent-push
BLOCKED — 2 block-severity secret(s) in staged changes; do NOT push.

src/config.py
 sev    line  rule                redacted    hint
 block  1     SLACK-TOKEN         xoxb…UvWx   Slack token: rotate it; load from env
                                              or config, never inline.
 block  2     AWS-ACCESS-KEY-ID   AKIA…MPLE   AWS access key id: rotate it and use
                                              a credentials file or env var.

Also refused before staging:
- credentials.yaml: a secret-shaped file name; not staged, listed for you.
- data/counts_matrix.csv is 2.9 MB: move it to <data root>/append_only/<project>/.
Nothing was committed or pushed.

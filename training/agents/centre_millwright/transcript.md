# The exchange shown in the movie

Real reply, run on 2026-11-07 (Murmurent 2026.11.0). The verdict line is verbatim; the detail is shortened to fit a frame. `make.py` reads this file: each `## <key>` section starts with `<who>: <question>`, then the reply lines. A dry run on this machine; nothing was applied.

## 1
Mayor: Run the drift loop in dry-run mode: does the actual membership state on this machine match what the project records say, and what would you change?
Drift: no centre record on this machine, so no membership check ran; the local drift loop found 8 items (6 orphan registry, 1 unadopted clone, 1 uncommitted lab records), dry-run only.

- Centre record: ~/.murmurent/centre.md absent; lab_info holds only
  _registry.yaml and an empty labs folder; no projects folder.
- So Slack, GitHub and ACL membership comparison: not possible here.
- Ran murmurent reconcile (dry-run is its default). Actionable drift.
- 6 x orphan_registry [WARN]: repos recorded under their projects but
  gone from disk. Would: re-clone, or drop from the project record.
- 1 x unadopted_clone [info]: a clone not yet made murmurent-ready.
  Would: leave for the owner to click Make ready.
- 1 x lab_mgmt_uncommitted [WARN]: local edits in the lab records repo
  not committed. Would: have the PI review, commit and push.
- Applied: nothing.

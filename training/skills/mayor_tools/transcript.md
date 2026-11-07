# The exchange shown in the movie

A real run of the reset skill's preview on 2026-11-07 (Murmurent 2026.11.0) on a laptop:
`bash skills/murmurent-reset/reset.sh --dry-run`. Nothing changed. Home folder paths are ~.

## 1
PI: /murmurent-reset dry-run
=== murmurent reset: level centre (dry-run). Nothing changed.

1. stopping any running dashboards
  DRY: would pkill -f 'murmurent dashboard'
2. backing up (~/.murmurent + ~/.config/murmurent)
  DRY: would write backup -> ~/.murmurent_backups/reset_centre_20261107.tgz
3. centre state
  DRY: would remove centre registry (lab_info/)  (~/.murmurent/lab_info)
  DRY: would remove saved netname (~/.murmurent/user)
4. (skip reinstall: level 'centre')
5. (skip caches: level 'centre')
6. opt-in nukes
  (keep) installations/
  (keep) credentials
7. murmurent lab repos (~/repos/murmurent_lab_mgmt_*)
  (keep) murmurent_lab_mgmt_mh  [uncommitted]  use --nuke-labs to remove
next:  murmurent centre-status   (should say 'no centre initialised')

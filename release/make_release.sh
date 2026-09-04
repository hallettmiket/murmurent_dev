#!/usr/bin/env bash
#
# Purpose: build the public release tree from a tag in the dev repo and push it
#          as ONE squashed commit to the public repo.
# Author: Mike Hallett (with Claude Code)
# Date: 2026-09-01
# Input:  a tag that exists in this repo, and the public repo's clone URL
# Output: a commit + tag on the public repo's main; prints the dev SHA to record
#
# The public repo gets one commit per release. Releases stay diffable against
# each other, and no development history, issue text or PR discussion travels.
#
# Nothing ships unless release/allowlist.yaml names it. check_allowlist.py runs
# first and a single unclassified path aborts the release, because a path
# nobody classified is a decision nobody made.

set -euo pipefail

TAG="${1:?usage: make_release.sh <tag> <public-repo-url> [--dry-run]}"
PUBLIC_URL="${2:?usage: make_release.sh <tag> <public-repo-url> [--dry-run]}"
DRY="${3:-}"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

say() { printf '  \033[32m✓\033[0m %s\n' "$*"; }
die() { printf '  \033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }

git -C "$REPO_DIR" rev-parse -q --verify "refs/tags/$TAG" >/dev/null \
  || die "tag '$TAG' does not exist in $REPO_DIR"
DEV_SHA="$(git -C "$REPO_DIR" rev-list -n1 "$TAG")"

echo "[1/5] Gate: every tracked file must be classified"
python3 "$REPO_DIR/release/check_allowlist.py" >/dev/null \
  || die "allowlist is incomplete — run release/check_allowlist.py"
say "allowlist complete"

echo "[2/5] Gate: no shipping file may name a deployment fact"
( cd "$REPO_DIR" && PYTHONPATH=src python3 -m pytest -q tests/test_release_hygiene.py >/dev/null ) \
  || die "release hygiene test failed — see tests/test_release_hygiene.py"
say "no private repos, grant documents or Slack IDs in the shipping set"

echo "[3/5] Building the release tree from $TAG ($DEV_SHA)"
SRC="$WORK/src"
mkdir -p "$SRC"
git -C "$REPO_DIR" archive "$TAG" | tar -x -C "$SRC"
# Keep only what the allowlist ships. Computed from the tag's own tree, so a
# release cannot accidentally inherit the working copy's state.
python3 - "$SRC" <<'PY'
import subprocess, sys, pathlib, yaml
sys.path.insert(0, str(pathlib.Path(__file__).parent))
root = pathlib.Path(sys.argv[1])
repo = pathlib.Path(__file__).resolve().parent
spec = yaml.safe_load((repo / "release" / "allowlist.yaml").read_text())
sys.path.insert(0, str(repo / "release"))
from check_allowlist import classify
files = [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()]
keep = set(classify(sorted(files), spec)["ship"])
removed = 0
for p in sorted(root.rglob("*"), key=lambda x: -len(str(x))):
    if p.is_file() and str(p.relative_to(root)) not in keep:
        p.unlink(); removed += 1
    elif p.is_dir() and not any(p.iterdir()):
        p.rmdir()
print(f"  kept {len(keep)} files, removed {removed}")
PY

echo "[4/5] Staging the public repo"
PUB="$WORK/public"
git clone -q "$PUBLIC_URL" "$PUB" 2>/dev/null || { mkdir -p "$PUB"; git -C "$PUB" init -q -b main; }
# Replace the tree wholesale: a release is a state, not a patch.
find "$PUB" -mindepth 1 -maxdepth 1 -not -name .git -exec rm -rf {} +
cp -a "$SRC"/. "$PUB"/
say "tree staged"

echo "[5/5] Commit, tag, push"
if [[ "$DRY" == "--dry-run" ]]; then
  ( cd "$PUB" && git add -A && git -c user.name=murmurent -c user.email=noreply@example.com \
      commit -q -m "dry run" && git show --stat --oneline HEAD | head -30 )
  say "DRY RUN — nothing pushed. Dev SHA would be $DEV_SHA"
  exit 0
fi
cd "$PUB"
git add -A
git -c user.name="Mike Hallett" commit -q -m "$(cat <<MSG
Release ${TAG#v}

Built from the development repository at ${DEV_SHA}.

This repository carries released versions only: one commit per release, no
development history. Development, issues and design discussion live in
murmurent_dev.
MSG
)"
git tag -f "$TAG"
git push -q origin main
git push -q -f origin "$TAG"
say "pushed ${TAG} — dev SHA ${DEV_SHA}"

# The docs workflow on the public repo is path-filtered (docs/**), and a
# squashed release commit replacing the whole tree does not reliably fire it.
# Ask for the build explicitly, so the documentation site follows the release.
PUBLIC_SLUG="$(printf '%s' "$PUBLIC_URL" | sed -E 's#^(https://github.com/|git@github.com:)##; s#\.git$##')"
if command -v gh >/dev/null 2>&1; then
  if gh workflow run docs.yml --repo "$PUBLIC_SLUG" --ref main >/dev/null 2>&1; then
    say "asked $PUBLIC_SLUG to rebuild the documentation site"
  else
    printf '  \033[33m!\033[0m could not trigger the docs workflow on %s; run: gh workflow run docs.yml --repo %s\n' "$PUBLIC_SLUG" "$PUBLIC_SLUG"
  fi
fi
echo
echo "Record this in the release notes:  dev ${DEV_SHA}"

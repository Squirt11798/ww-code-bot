#!/usr/bin/env bash
#
# Build a release tarball for ww-code-bot.
#
# Auto-increments the version (tracked in the VERSION file) and writes
# releases/ww_code_bot_vN.tar.gz from the latest commit (HEAD).
#
# Usage:
#   ./build-release.sh            # bump to next version and build
#   ./build-release.sh --keep     # rebuild the CURRENT version (no bump)
#   ./build-release.sh 7          # build a specific version number
#
# After it runs, commit the new VERSION file and the tarball:
#   git add VERSION releases/ && git commit -m "Release vN" && git push
#
set -euo pipefail

# Always operate from the repo root (where this script lives).
cd "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

VERSION_FILE="VERSION"
current="$(cat "$VERSION_FILE" 2>/dev/null || echo 0)"
[[ "$current" =~ ^[0-9]+$ ]] || current=0

case "${1:-}" in
  --keep|-k)        next="$current" ;;
  "")               next=$((current + 1)) ;;
  *[!0-9]*)         echo "Usage: build-release.sh [N | --keep]" >&2; exit 1 ;;
  *)                next="$1" ;;
esac

# The tarball is built from HEAD, so warn if the working tree has changes that
# won't be captured.
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "!! Warning: uncommitted changes detected. The tarball is built from the"
  echo "   last commit (HEAD) and will NOT include them. Commit first if needed."
  echo
fi

mkdir -p releases
out="releases/ww_code_bot_v${next}.tar.gz"
git archive --format=tar.gz --prefix=ww-code-bot/ -o "$out" HEAD
echo "$next" > "$VERSION_FILE"

echo "==> Built ${out}  (from commit $(git rev-parse --short HEAD))"
ls -lh "$out"
echo
echo "Next steps:"
echo "  git add VERSION ${out} && git commit -m 'Release v${next}' && git push"
echo
echo "  scp ${out} user@your-vm:~/"
echo "  # then on the VM:"
echo "  tar -xzf $(basename "$out") && cd ww-code-bot && sudo bash install.sh"

#!/usr/bin/env bash
#
# ww-code-bot updater.
#
# Pulls the latest code from GitHub, preserves your .env and database, rebuilds
# the image, and restarts the container — in one command.
#
# Usage (one-liner):
#   curl -fsSL https://raw.githubusercontent.com/Squirt11798/ww-code-bot/main/update.sh | sudo bash
#
# Or, if already installed:
#   sudo bash /opt/ww-code-bot/update.sh
#
# Update to a specific branch or tag instead of main:
#   sudo bash /opt/ww-code-bot/update.sh v2
#
set -euo pipefail

REPO_URL="https://github.com/Squirt11798/ww-code-bot.git"
INSTALL_DIR="${INSTALL_DIR:-/opt/ww-code-bot}"
REF="${1:-main}"

if [ -t 1 ]; then
  BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; RESET=$'\033[0m'
else
  BOLD=""; GREEN=""; YELLOW=""; RED=""; RESET=""
fi
info() { echo "${GREEN}==>${RESET} ${BOLD}$*${RESET}"; }
warn() { echo "${YELLOW}!!${RESET} $*"; }
die()  { echo "${RED}xx${RESET} $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Please run as root (sudo bash update.sh)."
[ -f "$INSTALL_DIR/docker-compose.yml" ] || \
  die "No install found at $INSTALL_DIR. Run install.sh first."
[ -f "$INSTALL_DIR/.env" ] || warn "No .env in $INSTALL_DIR — the bot may not start until configured."

command -v git >/dev/null 2>&1 || { apt-get update -y; apt-get install -y git; }
command -v docker >/dev/null 2>&1 || die "Docker is not installed. Run install.sh first."

# ── 1. Fetch the latest source into a temp dir ──────────────────────────────
info "Fetching '${REF}' from GitHub..."
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
git clone --depth 1 --branch "$REF" "$REPO_URL" "$tmp/src" 2>/dev/null \
  || die "Could not fetch ref '${REF}'. Is it a valid branch or tag?"
new_ver="$(git -C "$tmp/src" rev-parse --short HEAD)"

# ── 2. Copy over the install, preserving config and dev cruft ───────────────
info "Updating files in $INSTALL_DIR (keeping your .env and data)..."
for item in "$tmp/src"/* "$tmp/src"/.dockerignore "$tmp/src"/.env.example "$tmp/src"/.gitattributes; do
  [ -e "$item" ] || continue
  base="$(basename "$item")"
  case "$base" in .git|.venv|releases|.env) continue ;; esac
  cp -a "$item" "$INSTALL_DIR/"
done

# ── 3. Rebuild and restart ──────────────────────────────────────────────────
cd "$INSTALL_DIR"
info "Rebuilding image and restarting container..."
docker compose up -d --build

# Drop dangling old images so they don't pile up over many updates.
docker image prune -f >/dev/null 2>&1 || true

echo
info "${GREEN}Updated to ${new_ver}.${RESET} The bot is running."
echo "  Logs: docker compose -f $INSTALL_DIR/docker-compose.yml logs -f"
echo
echo "Recent logs:"
docker compose logs --tail 15 || true

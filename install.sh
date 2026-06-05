#!/usr/bin/env bash
#
# ww-code-bot installer for Ubuntu 24.04 (noble)
#
# Installs Docker Engine + Compose plugin, installs the bot, prompts for your
# Discord token and channel ID, writes a locked-down .env, and launches the
# container with auto-restart on boot.
#
# Usage (from a release tarball — recommended for a private repo):
#   tar -xzf ww_code_bot_vX.tar.gz
#   cd ww-code-bot
#   sudo bash install.sh
#
# Usage (one-liner, only works if the repo is public):
#   curl -fsSL https://raw.githubusercontent.com/Squirt11798/ww-code-bot/main/install.sh | sudo bash
#
# Non-interactive (e.g. automation): pre-set the values in the environment:
#   sudo DISCORD_TOKEN=xxx CHANNEL_ID=123 bash install.sh
#
set -euo pipefail

REPO_URL="https://github.com/Squirt11798/ww-code-bot.git"
INSTALL_DIR="${INSTALL_DIR:-/opt/ww-code-bot}"

# ── pretty output ───────────────────────────────────────────────────────────
if [ -t 1 ]; then
  BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; RESET=$'\033[0m'
else
  BOLD=""; GREEN=""; YELLOW=""; RED=""; RESET=""
fi
info()  { echo "${GREEN}==>${RESET} ${BOLD}$*${RESET}"; }
warn()  { echo "${YELLOW}!!${RESET} $*"; }
err()   { echo "${RED}xx${RESET} $*" >&2; }
die()   { err "$@"; exit 1; }

# ── preflight ───────────────────────────────────────────────────────────────
[ "$(id -u)" -eq 0 ] || die "Please run as root (use: sudo bash install.sh)."

if [ -r /etc/os-release ]; then
  . /etc/os-release
  [ "${ID:-}" = "ubuntu" ] || warn "This script targets Ubuntu; detected '${ID:-unknown}'. Continuing anyway."
  CODENAME="${VERSION_CODENAME:-noble}"
else
  CODENAME="noble"
fi

# Read interactive answers from the real terminal even when piped via curl|bash.
if [ -e /dev/tty ]; then TTY=/dev/tty; else TTY=/dev/stdin; fi

ask() {            # ask VAR "Prompt: "
  local __var="$1" __msg="$2" __val=""
  if [ -n "${!__var:-}" ]; then return; fi   # already provided via env
  read -rp "$__msg" __val <"$TTY" || true
  printf -v "$__var" '%s' "$__val"
}
ask_secret() {     # ask_secret VAR "Prompt: "
  local __var="$1" __msg="$2" __val=""
  if [ -n "${!__var:-}" ]; then return; fi
  read -rsp "$__msg" __val <"$TTY" || true
  echo >&2
  printf -v "$__var" '%s' "$__val"
}

# ── 1. Docker ───────────────────────────────────────────────────────────────
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  info "Docker and Compose already installed — skipping."
else
  info "Installing Docker Engine + Compose plugin..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y ca-certificates curl git
  install -m 0755 -d /etc/apt/keyrings
  if [ ! -f /etc/apt/keyrings/docker.asc ]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
  fi
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu ${CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

# Make sure Docker starts on boot and is running now.
systemctl enable --now docker >/dev/null 2>&1 || true

# ── 2. Install the bot files ────────────────────────────────────────────────
# Where is this script running from? If it sits next to the bot source (i.e. we
# were extracted from a release tarball or cloned), install from those local
# files. Otherwise fall back to cloning from GitHub (public repos only).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"

if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/docker-compose.yml" ] && [ -d "$SCRIPT_DIR/bot" ]; then
  if [ "$SCRIPT_DIR" = "$INSTALL_DIR" ]; then
    info "Installing in place at $INSTALL_DIR."
  else
    info "Installing bot files into $INSTALL_DIR ..."
    mkdir -p "$INSTALL_DIR"
    # Copy everything except an existing .env (preserve config) and dev cruft.
    for item in "$SCRIPT_DIR"/* "$SCRIPT_DIR"/.dockerignore "$SCRIPT_DIR"/.env.example "$SCRIPT_DIR"/.gitattributes; do
      [ -e "$item" ] || continue
      base="$(basename "$item")"
      case "$base" in .git|.venv|releases|.env) continue ;; esac
      cp -a "$item" "$INSTALL_DIR/"
    done
  fi
else
  info "Local source not found — cloning from GitHub (requires a public/authenticated repo)..."
  command -v git >/dev/null 2>&1 || { apt-get update -y; apt-get install -y git; }
  if [ -d "$INSTALL_DIR/.git" ]; then
    git -C "$INSTALL_DIR" pull --ff-only
  else
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
  fi
fi
cd "$INSTALL_DIR"

# ── 3. Configure .env ───────────────────────────────────────────────────────
if [ -f .env ] && [ -z "${RECONFIGURE:-}" ]; then
  info "Existing .env found — keeping it. (Re-run with RECONFIGURE=1 to change.)"
else
  echo
  info "Let's configure the bot."
  echo "  • Bot token:   Discord Dev Portal → your app → Bot → Reset Token"
  echo "  • Channel ID:  Discord → Settings → Advanced → Developer Mode ON,"
  echo "                 then right-click the target channel → Copy Channel ID"
  echo

  ask_secret DISCORD_TOKEN "Discord bot token: "
  [ -n "${DISCORD_TOKEN:-}" ] || die "A bot token is required."

  ask CHANNEL_ID "Channel ID to post codes in: "
  [[ "${CHANNEL_ID:-}" =~ ^[0-9]+$ ]] || die "Channel ID must be a number."

  ask PING_ROLE_ID "Role ID to @mention on new codes (Enter to skip): "
  PING_ROLE_ID="${PING_ROLE_ID:-0}"
  [[ "$PING_ROLE_ID" =~ ^[0-9]+$ ]] || PING_ROLE_ID=0

  POST_NOW=""
  ask POST_NOW "Post the CURRENT active codes on first launch? [y/N]: "
  case "${POST_NOW,,}" in y|yes) SEED_SILENTLY=false ;; *) SEED_SILENTLY=true ;; esac

  umask 077
  cat > .env <<EOF
# Generated by install.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)
DISCORD_TOKEN=${DISCORD_TOKEN}
CHANNEL_ID=${CHANNEL_ID}
PING_ROLE_ID=${PING_ROLE_ID}
POLL_INTERVAL_MINUTES=30
DB_PATH=/data/codes.db
SEED_SILENTLY=${SEED_SILENTLY}
ENABLED_SOURCES=game8,pockettactics,pcgamesn
LOG_LEVEL=INFO
EOF
  chmod 600 .env
  info "Wrote $INSTALL_DIR/.env (permissions 600)."
fi

# ── 4. Build & launch ───────────────────────────────────────────────────────
info "Building and starting the container..."
docker compose up -d --build

echo
info "${GREEN}Done!${RESET} ww-code-bot is running."
echo
echo "  Status:   docker compose -f $INSTALL_DIR/docker-compose.yml ps"
echo "  Logs:     docker compose -f $INSTALL_DIR/docker-compose.yml logs -f"
echo "  Restart:  docker compose -f $INSTALL_DIR/docker-compose.yml restart"
echo "  Stop:     docker compose -f $INSTALL_DIR/docker-compose.yml down"
echo
echo "The container restarts automatically on reboot (restart: unless-stopped)."
echo "In Discord, run /codes to confirm it can reach the code sources."
echo
echo "Recent logs:"
docker compose logs --tail 15 || true

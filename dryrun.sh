#!/usr/bin/env bash
#
# Show what the bot WOULD post right now — without sending anything to Discord.
# Runs the dry-run inside a throwaway container using the already-built image.
#
#   sudo bash /opt/ww-code-bot/dryrun.sh
#   sudo LOG_LEVEL=DEBUG bash /opt/ww-code-bot/dryrun.sh   # verbose parsing detail
#
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
exec docker compose run --rm --no-deps ww-code-bot python -m bot.dryrun "$@"

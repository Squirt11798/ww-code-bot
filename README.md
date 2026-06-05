# ww-code-bot

A Discord bot that watches for **Wuthering Waves redemption codes** across
multiple community sources and posts new ones to a channel automatically.

Wuthering Waves (Kuro Games) has no official codes API — codes drop via
livestreams and social media and are aggregated by community sites. This bot
polls several of those sites on a schedule, de-duplicates, remembers what it has
already posted, and announces only genuinely new codes.

## Features

- **Multi-source + dedupe** — scrapes Game8, Pocket Tactics, and PCGamesN; a code
  found on any source is posted once, attributed to every source that saw it. If
  one site is down or changes layout, the others still work.
- **Post-once memory** — a small SQLite file tracks seen codes, so restarts don't
  re-spam the channel.
- **Silent first-run seeding** — on first launch it records the current backlog
  as "seen" without posting (configurable), so you only ever get *new* drops.
- **Slash commands** — `/checknow`, `/codes`, `/redeem`.
- **Dockerized** — `docker compose up -d` and you're running.

## One-line install (Ubuntu 24.04)

Installs Docker, fetches the bot, prompts for your token + channel ID, and
launches it with auto-restart on boot:

```bash
curl -fsSL https://raw.githubusercontent.com/Squirt11798/ww-code-bot/main/install.sh | sudo bash
```

Installs to `/opt/ww-code-bot`. To reconfigure later:
`sudo RECONFIGURE=1 bash /opt/ww-code-bot/install.sh`. Non-interactive installs
can pre-set values: `sudo DISCORD_TOKEN=xxx CHANNEL_ID=123 bash install.sh`.

## Quick start (Docker, manual)

```bash
cp .env.example .env
#  → edit .env: set DISCORD_TOKEN and CHANNEL_ID (at minimum)

docker compose up -d --build
docker compose logs -f
```

The SQLite DB persists in the `ww-code-data` named volume across restarts.

## Quick start (local, no Docker)

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows  (use: source .venv/bin/activate on Linux/macOS)
pip install -r requirements.txt

cp .env.example .env          # then edit it; set DB_PATH to e.g. ./data/codes.db
python -m bot
```

## Discord setup

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
   → **New Application** → **Bot** → **Reset Token** → copy into `DISCORD_TOKEN`.
2. Under **Installation** (or OAuth2 → URL Generator), give the bot the
   `bot` and `applications.commands` scopes and the **Send Messages** /
   **Embed Links** permissions, then invite it to your server.
3. Enable **Developer Mode** in Discord (Settings → Advanced), right-click your
   target channel → **Copy Channel ID** → put it in `CHANNEL_ID`.
4. (Optional) Make a role like `@WuWa Codes`, copy its ID into `PING_ROLE_ID` to
   ping it on every new code.

No privileged intents are required — the bot only sends messages and handles
slash commands.

## Configuration

All config is via environment variables (see [`.env.example`](.env.example)):

| Var | Default | Meaning |
|-----|---------|---------|
| `DISCORD_TOKEN` | — | Bot token (required) |
| `CHANNEL_ID` | — | Channel to post into (required) |
| `PING_ROLE_ID` | `0` | Role to @mention on new codes (0 = none) |
| `POLL_INTERVAL_MINUTES` | `30` | How often to check (min 5) |
| `DB_PATH` | `/data/codes.db` | SQLite location |
| `SEED_SILENTLY` | `true` | First run records existing codes without posting |
| `ENABLED_SOURCES` | `game8,pockettactics,pcgamesn` | Which scrapers to run |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## How code detection works

Each source is an `HtmlSource` (see [`bot/sources/`](bot/sources/)). It fetches the
page and pulls out tokens that *look* like codes — 6–16 char ALL-CAPS
alphanumeric strings containing at least one letter — from the content-bearing
tags, then filters them against a blocklist of common words
(`ASTRITE`, `REDEEM`, `TWITTER`, …) in [`bot/sources/base.py`](bot/sources/base.py).

This is intentionally layout-tolerant: it survives most site redesigns at the
cost of occasional false positives, which the blocklist absorbs. **If a new false
positive sneaks through, add it to `BLOCKLIST`.** To add a new site, append one
line to `ALL_SOURCES` in [`bot/sources/__init__.py`](bot/sources/__init__.py).

## Tests

```bash
pip install pytest
pytest
```

## Layout

```
ww-code-bot/
├── bot/
│   ├── main.py          # Discord client, polling loop, slash commands
│   ├── config.py        # env-var config
│   ├── models.py        # Code dataclass
│   ├── store.py         # SQLite "seen codes" store
│   ├── aggregator.py    # runs sources concurrently, merges + dedupes
│   └── sources/
│       ├── base.py      # generic HTML extractor + blocklist
│       └── __init__.py  # source registry
├── tests/
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Notes & caveats

- Community sites may rate-limit or block datacenter IPs. Running from a normal
  VPS/home IP with the default browser User-Agent generally works. If a source
  returns nothing, check the logs — the others keep working regardless.
- This bot **finds and announces** codes; it does not auto-redeem them. Redeem at
  the [official page](https://wutheringwaves.kurogames.com/en/main/news/redeem)
  (Union Level 2+ required).

## Legal

This is an unofficial, fan-made tool provided free of charge, **"as is," with no
warranty**, and is in **active development**. It is **not affiliated with Kuro
Games, Wuthering Waves, or Discord**. See:

- [Terms of Service](TERMS_OF_SERVICE.md)
- [Privacy Policy](PRIVACY_POLICY.md)
```

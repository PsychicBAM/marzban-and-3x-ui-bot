# Deployment Guide

Deploy the Telegram VPN bot on a Linux server using Docker Compose.

**Repository:** https://github.com/PsychicBAM/marzban-and-3x-ui-bot

## Prerequisites

- Ubuntu 20.04+ / Debian 11+ (recommended)
- Root or sudo
- Outbound internet (GitHub, Docker Hub, Telegram API)
- Telegram Bot Token
- Marzban and/or 3x-ui credentials (for VPN provisioning)

---

## One-command install (recommended)

```bash
bash <(curl -Ls https://raw.githubusercontent.com/PsychicBAM/marzban-and-3x-ui-bot/main/install.sh)
```

### What the installer does

| Step | Action |
|---|---|
| 1 | Verifies root/sudo, installs `curl` and `git` if missing |
| 2 | Installs Docker + Compose plugin (with confirmation) if missing |
| 3 | Clones to `/opt/marzban-and-3x-ui-bot` or pulls latest |
| 4 | Creates `.env` interactively (or keeps existing file) |
| 5 | Runs `docker compose up -d --build` |
| 6 | Runs `alembic upgrade head` inside the bot container |

Secrets are **not** printed after input. `.env` is chmod `600`.

### After install

```bash
cd /opt/marzban-and-3x-ui-bot
docker compose logs -f bot
```

Send `/start` and `/admin` in Telegram to verify.

---

## Manual install

```bash
sudo mkdir -p /opt
sudo git clone https://github.com/PsychicBAM/marzban-and-3x-ui-bot.git /opt/marzban-and-3x-ui-bot
cd /opt/marzban-and-3x-ui-bot
cp .env.example .env
nano .env   # set BOT_TOKEN, ADMIN_TELEGRAM_IDS, POSTGRES_PASSWORD, DATABASE_URL, panels
docker compose up -d --build
docker compose exec -T bot alembic upgrade head
docker compose logs -f bot
```

Minimum `.env` for Docker:

```env
BOT_TOKEN=your_token
ADMIN_TELEGRAM_IDS=123456789
POSTGRES_PASSWORD=strong_random_password
POSTGRES_HOST=postgres
DATABASE_URL=postgresql+asyncpg://vpn_bot:strong_random_password@postgres:5432/vpn_bot
```

---

## Docker Compose layout

| Service | Notes |
|---|---|
| `postgres` | PostgreSQL 16, volume `postgres_data`, `restart: unless-stopped` |
| `bot` | Builds from `Dockerfile`, `env_file: .env`, `depends_on: postgres`, `restart: unless-stopped` |

No secrets are hardcoded in `docker-compose.yml`.

---

## Update

From the install directory:

```bash
cd /opt/marzban-and-3x-ui-bot
./update.sh
```

Or manually:

```bash
git pull
docker compose up -d --build
docker compose exec -T bot alembic upgrade head
docker compose restart bot
docker compose logs -f bot
```

---

## Backup

```bash
cd /opt/marzban-and-3x-ui-bot
./backup.sh
```

Creates `backups/vpn_bot_YYYYMMDD_HHMMSS.sql.gz` with mode `600`.

### Restore (destructive — overwrites current data)

```bash
cd /opt/marzban-and-3x-ui-bot
gunzip -c backups/vpn_bot_YYYYMMDD_HHMMSS.sql.gz | \
  docker compose exec -T postgres psql -U vpn_bot -d vpn_bot
```

Stop the bot during restore on production systems to avoid writes:

```bash
docker compose stop bot
# restore ...
docker compose start bot
```

---

## Logs

```bash
docker compose logs -f bot          # follow bot logs
docker compose logs --tail=100 bot
docker compose ps                   # service status
```

---

## Restart / stop

```bash
docker compose restart bot
docker compose down                 # stop; postgres volume persists
docker compose up -d                # start again
```

After editing `.env`:

```bash
nano .env
docker compose restart bot
```

DB-backed admin settings (payment/support/instruction) apply **without** restart. `.env` changes require restart.

---

## Migrations

```bash
docker compose exec -T bot alembic upgrade head
docker compose exec -T bot alembic current
```

Run after every update that includes new migration files.

---

## Smoke check

```bash
cd /opt/marzban-and-3x-ui-bot
python3 scripts/smoke_check.py
```

Inside container:

```bash
docker compose exec -T bot python scripts/smoke_check.py
```

Validates env presence, `DATABASE_URL` format, and Python imports. Does **not** call Telegram or VPN panels unless `SMOKE_CHECK_LIVE=1` (reserved for future use).

---

## Uninstall

```bash
cd /opt/marzban-and-3x-ui-bot
docker compose down
docker volume rm marzban-and-3x-ui-bot_postgres_data   # optional — deletes DB
sudo rm -rf /opt/marzban-and-3x-ui-bot
```

Adjust volume name: `docker volume ls | grep postgres`.

---

## First admin

Add your Telegram ID to `ADMIN_TELEGRAM_IDS` in `.env`, then:

```bash
docker compose restart bot
```

Discover ID via [@userinfobot](https://t.me/userinfobot).

---

## VPN panel configuration

**Marzban (minimum):**

```env
MARZBAN_ENABLED=true
MARZBAN_BASE_URL=https://your-marzban.example.com
MARZBAN_USERNAME=admin
MARZBAN_PASSWORD=strong_password
MARZBAN_INBOUND_VLESS=your-vless-tag
```

**3x-ui (minimum):**

```env
XUI_ENABLED=true
XUI_BASE_URL=https://your-xui.example.com:2053
XUI_USERNAME=admin
XUI_PASSWORD=strong_password
XUI_INBOUND_ID=1
```

When the panel serves subscriptions on a different host or path than the admin API, set:

```env
XUI_SUBSCRIPTION_BASE_URL=https://your-server:2096/vpn
```

The bot builds `{XUI_SUBSCRIPTION_BASE_URL}/{subId}` (no extra `/sub`). If unset, it uses `{XUI_BASE_URL}/sub/{subId}`.

For VLESS REALITY inbounds, set flow on both panels:

```env
MARZBAN_VLESS_FLOW=xtls-rprx-vision
XUI_VLESS_FLOW=xtls-rprx-vision
```

Optional: `MARZBAN_API_TOKEN`, `XUI_API_TOKEN`, `MARZBAN_SUBSCRIPTION_BASE_URL`, `*_VERIFY_SSL=false` for self-signed certs.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Bot cannot connect to DB | Wait for postgres healthcheck; verify `DATABASE_URL` and `POSTGRES_HOST=postgres` |
| `alembic` fails | `docker compose ps` — postgres must be healthy |
| Invalid bot token | Check `BOT_TOKEN` in `.env`, restart bot |
| Panel SSL errors | `MARZBAN_VERIFY_SSL=false` or `XUI_VERIFY_SSL=false` |
| Install script: permission denied | Run with `sudo bash install.sh` or as root |
| `git pull` conflicts | Stash/commit local changes or re-clone to a new directory |

---

## Security

- Never commit `.env` — it is in `.gitignore`
- Use strong `POSTGRES_PASSWORD`
- Restrict firewall; expose only required ports
- Run `./backup.sh` before major updates
- Complete [QA_CHECKLIST.md](QA_CHECKLIST.md) before production release

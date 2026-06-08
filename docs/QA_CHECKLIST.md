# Final QA Checklist

Use this checklist before a GitHub release or production deployment.

## Installation

- [ ] One-command install works on a clean Ubuntu/Debian server
- [ ] `install.sh` creates `/opt/marzban-and-3x-ui-bot`
- [ ] `.env` created from interactive wizard (or existing `.env` kept when chosen)
- [ ] `POSTGRES_PASSWORD` generated when left empty
- [ ] `docker compose up -d --build` succeeds
- [ ] `alembic upgrade head` runs without errors
- [ ] `scripts/smoke_check.py` passes inside or outside container
- [ ] No secrets printed in installer output

## Bot basics

- [ ] `/start` registers user and shows customer menu
- [ ] `/admin` opens admin panel for `ADMIN_TELEGRAM_IDS`
- [ ] Bot logs show no crash loop: `docker compose logs -f bot`

## Tariffs

- [ ] Admin `💰 Тарифы` — list, create, edit, enable/disable
- [ ] Customer `🛒 Купить VPN` — active tariffs visible

## Purchase & provisioning

- [ ] Purchase flow shows payment details from DB/settings
- [ ] Customer submits receipt → pending request created
- [ ] Admin `📥 Заявки` → approve payment
- [ ] VPN provisioned on Marzban and/or 3x-ui
- [ ] Customer receives subscription links
- [ ] QR codes sent (in memory, not saved to disk by default)

## Renewal

- [ ] `🔄 Продлить VPN` flow works
- [ ] Renewal approval extends expiry per `ExpiryCalculator` rules

## Customer VPN

- [ ] `📊 Мой VPN` shows account status
- [ ] Link and QR on demand work

## Admin clients

- [ ] `👥 Клиенты` — lists, search, client card
- [ ] Disable / enable / delete / IP limit / manual extend

## Manual key (9B)

- [ ] `➕ Создать ключ` — existing user mode
- [ ] `➕ Создать ключ` — standalone mode
- [ ] Send to customer works

## Notifications (8)

- [ ] `⚙️ → 🔔 Уведомления` settings save
- [ ] Test notification to admin works

## Statistics (9A)

- [ ] `📊 Статистика` loads and refreshes

## Settings (9C)

- [ ] Payment details edit applies without restart
- [ ] Support settings apply to customer `🆘 Поддержка`
- [ ] Instruction settings apply to customer `ℹ️ Инструкция`

## Operations

- [ ] `./backup.sh` creates timestamped `.sql.gz` in `backups/`
- [ ] Restore command documented in `docs/DEPLOY.md` tested on staging
- [ ] `./update.sh` pulls, rebuilds, migrates, restarts
- [ ] `docker compose restart bot` works
- [ ] `docker compose down` stops services (data volume persists)

## Security

- [ ] `.env` not committed to Git
- [ ] `.gitignore` covers secrets, logs, backups, qr/, tmp/
- [ ] No real tokens in README or docs
- [ ] Server firewall reviewed (only required ports open)

## Sign-off

| Role | Name | Date |
|---|---|---|
| Installer tested | | |
| Bot functional QA | | |
| Security review | | |

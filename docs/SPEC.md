# Specification — Telegram VPN Sales Bot

## Overview

Clean-architecture Telegram bot for VPN subscription sales with manual payment confirmation.

**Stack:** Python 3.11+, aiogram 3, PostgreSQL, SQLAlchemy 2 async, Alembic, httpx, APScheduler, qrcode + Pillow, Docker.

## Architecture Layers

| Layer | Responsibility |
|---|---|
| `presentation` | Telegram handlers, keyboards — no business logic |
| `application` | Use cases, service ports (interfaces) |
| `domain` | Enums, domain rules |
| `infrastructure` | DB repositories, API clients, logging, scheduler |

## VPN Panels

### Marzban

Protocols per user:

- VLESS TCP REALITY
- TROJAN TCP NOTLS
- VMESS TCP NOTLS

Operations: create, update/renew, enable, disable, delete, subscription link, status.

### 3x-ui

Client fields: `expiryTime`, `totalGB`, `limitIp`, enable/disable, update, delete, traffic, subscription/link.

### Issuing Modes

- `marzban` — Marzban only
- `xui` — 3x-ui only
- `both` — both panels

## VPN Account Naming

- Visible name = Telegram `@username` without `@`
- `telegram_id` is the primary unique identifier in DB
- No Telegram ID in visible VPN name
- If no username → ask user for manual name
- Name collision → ask again or suffix after admin approval

## Customer Flows

### Purchase

**Paid plan (`price > 0`):**

1. Select tariff
2. Show payment details from settings
3. Click «✅ Я оплатил»
4. Send receipt screenshot
5. All admins from `ADMIN_TELEGRAM_IDS` receive a push notification with «👁 Открыть заявку»
6. Admin sees request in «📥 Заявки»
7. Admin approves/rejects
8. On approve → create VPN accounts in selected panels
9. Send subscription link + QR code

**Free plan (`price == 0`):**

1. Select tariff → «🎁 Активировать бесплатно» (no payment details, no receipt)
2. Eligibility: no active VPN; one free activation per Telegram user (ever)
3. Creates `payment_requests` with `amount=0`, `status=approved` (statistics/history)
4. Immediate provisioning via `VpnProvisioningService` (respects `issuing_mode`, duration, traffic, IP)
5. Customer message: «🎁 Бесплатный доступ активирован. Ваш VPN создан.» + links + QR
6. Admin log: `free_plan_activated`

### Renewal

1. «🔄 Продлить VPN» → select tariff → receipt → admin approval
2. Active account: add days to current expiry
3. Expired account: add days from today
4. Update DB + panels

### My VPN

Show: status, tariff, expiry, days left, traffic usage/limit, IP limit, panels.

Buttons: link, QR, renew.

## Admin Panel

Sections: requests, clients, create key, tariffs, statistics, settings, broadcasts, promo codes.

Client card: full name, username, telegram_id, VPN name, status, tariff, expiry, traffic, IP limit, Marzban/3x-ui status.

Actions: send link, send QR, renew, disable, enable, change IP limit, clear IP, delete (soft).

## Database Tables

- `users` — Telegram users (`promo_enabled` — opt-in for promotional broadcasts, default `true`)
- `plans` — tariffs
- `vpn_panels` — panel configurations
- `vpn_accounts` — VPN subscriptions (soft delete)
- `payment_requests` — purchase/renewal requests
- `notifications` — expiry notification log
- `admin_logs` — admin action audit
- `settings` — key-value bot settings

## Payment Safety

- Protect against double approval
- Approved/rejected requests cannot be processed again

## Expiry Notifications (Stage 8)

`ExpiryNotificationService` + APScheduler (`ExpiryNotificationScheduler`):

- Configurable reminder days from DB `settings` or `.env` (default `7,3,1`)
- Intervals: `daily`, `hourly`, `every_10_minutes`, `every_1_minute` (last is **testing only**)
- Duplicate protection: `notifications` unique on `(vpn_account_id, notification_type, reminder_days_before)`
- Only **active** non-deleted accounts; deleted accounts are never notified
- Expired: one-time notice + optional `vpn_accounts.status = expired`
- **Test mode:** scheduler skips customer sends; `📩 Отправить тест админу` sends marked sample to clicking admin only

Admin UI: `⚙️ Настройки` → `🔔 Уведомления` — enable/disable, days, interval, test mode, expired toggle.

Settings keys: `notifications_enabled`, `notification_days`, `notification_check_interval`, `notification_test_mode`, `notify_expired_enabled`.

## Deletion Rule

Soft delete only: `status = deleted`, `deleted_at = now()`.

## Configuration

All secrets and business values in `.env` or DB `settings` table — never hardcoded.

## Data Access Layer

| Component | Location |
|---|---|
| Session scope | `app/infrastructure/db/session.py` |
| Unit of Work | `app/infrastructure/db/uow.py` |
| Repositories | `app/infrastructure/db/repositories/` |
| Services | `app/application/services/` |
| DB middleware | `app/presentation/bot/middlewares/database.py` |

Handlers receive services via middleware — no direct DB access in handlers.

## Default Demo Plans

Seeded on startup only when `plans` table is empty (`app/infrastructure/seed/default_plans.py`):

| Name | Days | Devices | Price |
|---|---|---|---|
| 30 дней | 30 | 3 | 200 ₽ |
| 60 дней | 60 | 3 | 370 ₽ |
| 90 дней | 90 | 3 | 560 ₽ |

Traffic limit defaults to unlimited (`0`). Issuing mode defaults to `both`.

## Tariff Fields

| Field | Description |
|---|---|
| `name` | Display name |
| `price` | Price in RUB (≥ 0) |
| `duration_days` | Subscription period in days (> 0) |
| `traffic_limit_gb` | Traffic cap in GB; `0` = unlimited |
| `ip_limit` | Device/IP cap; `0` = unlimited devices |
| `issuing_mode` | `marzban`, `xui`, or `both` |
| `is_active` | `true` = visible to customers; `false` = admin-only (soft disable) |
| `description` | Optional text |

Disabled tariffs remain in the admin list and keep linked accounts intact. Hard delete is not supported.

## Admin Tariff Management (Stage 3)

- Full tariff list (active + disabled) with inline actions
- FSM-based create flow with confirmation
- Per-field edit with validation and admin audit log
- Enable/disable via `is_active` flag

## Manual Payment Flow (Stage 4)

1. Customer selects tariff → sees payment details from DB `settings` or `.env` `PAYMENT_DETAILS`
2. Customer clicks «✅ Я оплатил» → sends photo/document/text receipt
3. `payment_requests` row created with `status=pending`, `receipt_file_id`, `receipt_file_type`
4. Bot notifies every `ADMIN_TELEGRAM_IDS` admin (purchase and renewal) with inline «👁 Открыть заявку» (`preq:open:{id}`); action logged as `payment_request_admin_notified`
5. Admin opens «📥 Заявки» (or notification button) → approves or rejects
6. **Stage 4 does not create VPN accounts** — approval only updates status and notifies customer

Duplicate protection: one pending `purchase` request per user. Double-click approve/reject is idempotent.

### Multi-subscription purchase (active VPN)

If the customer already has an **active** VPN and selects a **paid** tariff:

1. Bot asks: «У вас уже есть активный VPN. Что вы хотите сделать?»
2. **🔄 Продлить текущий VPN** — `request_type=renewal`, `vpn_account_id` set; one account auto-selected, or picker if several active subscriptions
3. **➕ Купить отдельную подписку** — customer enters a latin label (`grandma`, `phone`, …); bot generates unique `vpn_account_name` (`{base}_{label}`, suffix `_2` if needed); `payment_requests.target_vpn_account_name` + `target_display_name`; on approve → **new** `vpn_accounts` row + new panel clients (same Telegram user)

Free plan remains blocked when the user already has active VPN or used free plan once.

`vpn_accounts`: optional `display_name`, `is_primary` (first subscription). Global unique `vpn_account_name`.

### Payment request receipt fields

| Field | Description |
|---|---|
| `receipt_file_id` | Telegram `file_id` for photo/document |
| `receipt_file_type` | `photo`, `document`, or `text` |
| `user_comment` | Text comment or caption |
| `amount` | Snapshot of plan price at request time |
| `approved_at` / `rejected_at` | Processing timestamps |

## VPN Panel Services (Stage 5A)

### Marzban

- Auth: `MARZBAN_API_TOKEN` or username/password via `/api/admin/token`
- User protocols: VLESS, Trojan, VMESS (inbound tags from `.env`)
- VLESS flow: optional `MARZBAN_VLESS_FLOW` (e.g. `xtls-rprx-vision` for REALITY); applied to VLESS proxy only
- Operations: create, update, enable, disable, delete, get, subscription link, traffic/status
- Subscription URL: API `subscription_url` or `MARZBAN_SUBSCRIPTION_BASE_URL/{username}`

### 3x-ui

- Auth: `XUI_API_TOKEN` (Bearer) or session login (`XUI_USERNAME` / `XUI_PASSWORD`)
- Client fields: email, UUID, expiryTime (ms), totalGB (bytes), limitIp, enable, subId, flow (VLESS only)
- VLESS flow: optional `XUI_VLESS_FLOW` when inbound protocol is `vless`; omitted for trojan, vmess, hysteria
- Operations: list/get inbound, add/update/delete client, traffic, online clients, clear IPs
- Subscription URL: `XUI_SUBSCRIPTION_BASE_URL/{subId}` (no `/sub` suffix on base) or `{XUI_BASE_URL}/sub/{subId}` when base is unset. Old panel URLs are normalized by extracting the token after `/sub/` or `/vpn/`.

### Shared DTOs

- `VpnCreateInput`, `VpnAccountResult`, `VpnTrafficInfo`, `VpnStatusInfo`
- Username normalization: lowercase, `[a-z0-9_-]`, no Telegram ID suffix
- Errors: `VpnPanelError`, `VpnPanelAuthError`, `VpnPanelNotFoundError`, `VpnPanelConflictError`

### Dev scripts (manual only)

- `python scripts/test_marzban_create_user.py --username test --days 30`
- `python scripts/test_xui_create_client.py --email test --days 30 --list-inbounds`

Stage 5A does **not** connect VPN provisioning to payment approval.

## VPN Provisioning on Payment Approval (Stage 5B)

Flow: admin approves pending request → `PaymentApprovalService` → `VpnProvisioningService` → panels + `vpn_accounts`.

### Expiry rules

| Situation | New expiry |
|---|---|
| No account / deleted | `now + plan.duration_days` |
| Active, `expires_at > now` | `expires_at + plan.duration_days` |
| Expired or `expires_at <= now` | `now + plan.duration_days` |
| Disabled, `expires_at > now` | `expires_at + plan.duration_days` + re-enable (logged) |

Deleted accounts (`status=deleted` or `deleted_at` set) never extend old expiry — new DB row and new panel accounts.

### Payment request statuses after approval

| Status | Meaning |
|---|---|
| `approved` | VPN fully provisioned |
| `provisioning_failed` | Approved but VPN not issued |
| `provisioning_partial` | One panel OK, another failed (`issuing_mode=both`) |

Customer receives VPN links and QR-codes on full success (Stage 5C).

### QR-code delivery (Stage 5C)

After successful provisioning (`approved`, all panels OK):

1. Customer text message with tariff, expiry, limits, panel names, and subscription links.
2. Per-panel QR images sent after the text (`BufferedInputFile`, in-memory PNG).
3. Captions: `📷 QR-code для Marzban`, `📷 QR-code для 3x-ui`.
4. `issuing_mode=both`: separate QR per panel when both links exist.

QR images are generated in memory from subscription/VPN links (`QrCodeService`). They are **not** stored on disk by default. Optional disk storage exists for future use and is disabled.

If QR generation fails, payment approval still succeeds; the customer keeps the text link and sees: `⚠️ QR-code не удалось создать, но ссылка выше работает.` Admin log action: `qr_generation_failed`.

Partial provisioning (`provisioning_partial`): customer is not notified (no misleading full-success message, no QR).

### Soft delete (for Stage 7)

Admin delete must: disable/delete on panels, `vpn_accounts.status=deleted`, `deleted_at=now()`, keep DB row.

## Customer «Мой VPN» and Renewal (Stage 6)

### «📊 Мой VPN»

- **One subscription:** card with status, tariff, expiry, traffic, limits, panels, display name / account name; actions: link, QR, renew
- **Several subscriptions:** list (name, status, expiry) → select one → same card and actions per subscription
- Primary subscription: `vpn_accounts.is_primary` (fallback: newest non-deleted)

If panel traffic refresh fails, saved DB values are shown with: `⚠️ Не удалось обновить трафик, показаны сохранённые данные.`

Links are resolved from DB and refreshed via `MarzbanService.get_subscription_link` / `XuiService.get_subscription_link` when possible.

On-demand QR uses `QrCodeService` in memory (no disk storage). On QR failure the link is sent with a warning.

### Renewal flow

Entry points: main menu **🔄 Продлить VPN** or **🔄 Продлить VPN** from «Мой VPN».

1. Customer selects an active tariff.
2. Checkout shows current expiry (if account exists) and **expected new expiry** via `ExpiryCalculator`.
3. Customer pays → **✅ Я оплатил продление** → receipt FSM → `payment_requests` with `request_type=renewal`, `status=pending`, linked `vpn_account_id`.
4. Duplicate pending renewal is blocked: `⏳ У вас уже есть заявка на продление на проверке.`

### Expiry rules on renewal (unchanged from 5B)

| Account state | New expiry after N-day tariff |
|---|---|
| Active, `expires_at > now` | `expires_at + N` (e.g. 7 days left + 30 = 37 total) |
| Expired or `expires_at <= now` | `now + N` |
| Deleted / no account | `now + N` (new DB row + new panel accounts on approve) |
| Disabled, future expiry | `expires_at + N` + re-enable |

Admin **📥 Заявки** shows type `новая` / `новая подписка` / `продление`, subscription label, target VPN name, renewal account when applicable.

Approval reuses `PaymentApprovalService` → `VpnProvisioningService` → customer links + QR (renewal message: «Ваш VPN продлён»).

## Admin Customer Management (Stage 7)

Admin menu **👥 Клиенты** (`AdminCustomerService`) — **one row per `vpn_accounts` subscription**, not per user.

### Dashboard counts

| Metric | Meaning |
|---|---|
| Total users | All rows in `users` |
| Active / expired / disabled / deleted VPN subscriptions | Count of `vpn_accounts` rows in each category |

### Lists and search

- Filtered paginated lists (**5 per page**): active, **expiring soon (≤7 days)**, expired, disabled, deleted — each entry is one subscription
- Compact list text (message body):
  - `N) 👤 {customer} · 🔑 {display_name or short vpn name}`
  - `   до {dd.mm} · {M/XUI|M|XUI}`
- Compact inline buttons: `N. {short_customer} · {short_label}` (no full `vpn_account_name` / status in button text)
- Pagination row: `⬅️ Назад | Стр. X/Y | Далее ➡️`
- Search (FSM): `first_name`, `username`, `telegram_id`, `display_name`, `vpn_account_name`, `marzban_username`, `xui_email` — same compact list + pagination; query kept in FSM while browsing results
- Callback data uses `vpn_account_id` (`acl:o:{id}`, `acl:a:*:{id}`, etc.), never “first account for user”

### Client card (per subscription)

- 👤 Client name · 🆔 Telegram ID · 🔑 Subscription display name · 🧩 VPN account name
- 📌 Status · 📅 Expiry · 📊 Traffic / IP limit · 🖥 Marzban + 3x-ui panel status
- Live traffic refresh with DB fallback

### Actions (target selected `vpn_account_id`; per-panel results shown to admin)

| Action | Behavior |
|---|---|
| Send link / QR | Links/QR for **this** subscription only; `admin_sent_vpn_link` / `admin_sent_vpn_qr` log |
| Disable | Panels disabled for this account, `status=disabled`, customer notified |
| Enable | Blocked if expiry in past; else `status=active`, customer notified |
| Delete (soft) | Panels deleted for this account, `status=deleted`, `deleted_at=now()`, customer links cleared |
| Change IP limit | Panels + DB for this account, `ip_limit_changed` log |
| Clear IP | Marzban reset + 3x-ui clearClientIps for this account |
| Manual extend | `ExpiryCalculator` rules on this account, panels + DB updated |

Users with a single subscription see the same UX (one list row, one card).

## Admin Broadcasts / Promotions

Admin menu **📣 Рассылки** (`BroadcastService`, `BroadcastSenderService`):

- **➕ Создать рассылку** — FSM: title → text → optional photo (`file_id`) → audience → preview → confirm
- **📋 История рассылок** — recent broadcasts with status and sent/total counts
- Message: text-only or photo + HTML-escaped caption
- Audiences: all users, active VPN, expired VPN, no active VPN, expiring ≤7 days, promo-subscribed
- Always excludes `promo_enabled=false` and `telegram_id=0` (system user)
- Sender: gradual delivery (`~50ms` delay), `TelegramRetryAfter` sleep+retry, blocked/chat-not-found → recipient `blocked`/`failed`
- Admin logs: `broadcast_created`, `broadcast_sent`, `broadcast_failed`

### Customer promo opt-out

Customer menu **🔔 Акции и новости** — toggle `users.promo_enabled` (default on). Disabled users are excluded from all promotional broadcasts.

### Database

- `broadcasts` — campaign metadata and aggregate counts
- `broadcast_recipients` — per-user delivery status (`pending` / `sent` / `failed` / `blocked`)

Migration: `0007_broadcasts`.

## Promo Codes / Discounts

Admin menu **🎁 Промокоды** (`PromoCodeService`, `PromoActivationService`):

- **➕ Создать промокод** — FSM: code → discount type (`percent` / `fixed_amount` / `extra_days`) → value → optional date range → max uses → max per user → scope (any / purchase / renewal / specific plan) → preview → confirm
- **📋 Список промокодов** — code, type/value, active status, `used_count`/`max_uses`, expiry; enable/disable; view redemptions
- **🔎 Найти промокод** — search by code fragment
- **📊 Статистика** — total/active codes, redemptions, total discount amount

### Customer checkout

Before payment details (purchase, separate purchase, renewal):

- «У вас есть промокод?» → enter code or continue without
- Validation: active, date range, total/per-user limits, plan scope, request-type scope, `min_amount`, `new_users_only`
- Discount rules: percent / fixed (capped at amount) / extra days (amount unchanged); `final_amount ≥ 0`
- `payment_requests.amount` = `final_amount`; statistics revenue uses approved `amount` (post-discount)

### Zero-amount promo

If `final_amount == 0`: no receipt; auto-approve + provision (like free plan); redeem immediately.

### Redemption timing

`promo_code_redemptions` + `used_count` increment only on payment approval (manual/online) or zero-amount auto activation — not on failed/canceled requests.

### Database

- `promo_codes` — code (unique uppercase), discount type/value, limits, scope, `used_count`
- `promo_code_redemptions` — per use with amounts and optional `payment_request_id`
- `payment_requests` — `promo_code_id`, `original_amount`, `discount_amount`, `final_amount`, `extra_days_from_promo`

Migration: `0008_promo_codes`.

Admin logs: `promo_code_created`, `promo_code_disabled`, `promo_code_enabled`, `promo_code_applied`, `promo_code_redeemed`.

### Soft delete vs disabled

- **Disabled:** account remains in DB and panels; can be re-enabled if expiry valid.
- **Deleted:** soft delete only — DB row kept for history; customer links cleared; **old expiry never reused**; new purchase starts `now + plan days`.

## Admin Statistics (Stage 9A)

`StatisticsService` + `StatisticsRepository` — dashboard at `📊 Статистика`:

- Users by VPN state (latest non-deleted account per user + deleted-only users)
- Payment request counts by status (including `provisioning_failed` / `provisioning_partial`)
- **Revenue:** sum of `payment_requests.amount` where `status = approved` only
  - `provisioning_failed` and `provisioning_partial` are **not** counted as revenue
  - Today/month filters use `approved_at` in configured `TIMEZONE`
- VPN account row counts by status + Marzban/3x-ui panel linkage
- Active accounts expiring in 1 / 3 / 7 days

Buttons: refresh, today summary, month summary, back.

## Admin Manual VPN Key Creation (Stage 9B)

Admin menu **➕ Создать ключ** — FSM flow (`AdminManualKeyStates`) without payment request.

### Architecture

| Layer | Component |
|---|---|
| Handlers | `app/presentation/handlers/admin/manual_key.py` (thin FSM) |
| Flow helpers | `ManualKeyFlowService` — search, validation, confirmation text |
| Provisioning | `ManualProvisioningService` + shared `PanelProvisioner` |
| Panels | Reuses `MarzbanService` / `XuiService` (same helpers as payment approval) |
| QR | `ProvisioningNotificationService` + `send_qr_codes_for_links` (in-memory PNG) |

### Target modes

1. **Existing Telegram user** — search by `telegram_id`, `username`, or name; selected user owns the `vpn_accounts` row.
2. **Standalone / manual key** — no real customer. `vpn_accounts.user_id` is NOT NULL in schema; standalone keys attach to an internal system user:
   - `telegram_id = 0`
   - `username = manual_vpn_system`
   - Created on first use by `ManualProvisioningService.resolve_standalone_user_id()`
   - **No migration required**

### VPN account name

- Normalized: lowercase, `a-z`, `0-9`, `_`, `-` only (no spaces, no auto Telegram ID suffix).
- Existing user default: normalized `@username`; if missing, admin enters name manually.
- Admin may override before creation.
- Panel name conflicts checked before confirmation (skipped when extending existing panel accounts).

### Parameters

| Mode | Source |
|---|---|
| Tariff | Active plans — `duration_days`, `traffic_limit_gb`, `ip_limit`, `issuing_mode` |
| Custom | Admin enters each field step-by-step; optional admin comment |

Validation: `duration_days > 0`, `traffic_limit_gb >= 0`, `ip_limit >= 0`, `issuing_mode ∈ {marzban, xui, both}`.

### Expiry

| Case | Expiry |
|---|---|
| New key (standalone or separate key) | `now + duration_days` |
| Extend existing active account | `ExpiryCalculator` (active → add days; expired → from now; deleted → new from now) |

If an active non-deleted account exists for the user, admin must explicitly choose extend vs new separate key.

### Provisioning and partial failure

- `issuing_mode` controls Marzban / 3x-ui / both.
- If `both` and one panel fails: successful panel result is saved; admin sees which panel failed; log `manual_vpn_created` includes `partial: true`.
- Admin logs: `manual_vpn_created`, `manual_vpn_sent_to_customer` (when admin sends links/QR to customer).

### Post-creation

- Admin receives summary, subscription links, and QR images (generated in memory, not saved to disk by default).
- Existing user: buttons `📩 Отправить клиенту` / `🏠 В админ-панель`.
- Standalone: links and QR only to admin.

## Admin Bot Settings (Stage 9C)

`⚙️ Настройки` sections (inline keyboards + FSM for multiline edits):

| Section | Keys in `settings` table | `.env` fallback |
|---|---|---|
| 💳 Payment details | `payment_details` | `PAYMENT_DETAILS` |
| 🆘 Support | `support_username`, `support_url`, `support_text` | `SUPPORT_USERNAME`, `SUPPORT_URL`, `SUPPORT_TEXT` |
| ℹ️ Instruction | `instruction_text`, `instruction_url`, `instruction_enabled` | `INSTRUCTION_TEXT`, `INSTRUCTION_URL`, `INSTRUCTION_ENABLED` |

### Resolution order

1. If a DB row exists for a key → use DB value (empty string = explicitly empty field).
2. If no DB row → use `.env` value when set.
3. Payment: show “not configured” when both are empty.
4. Instruction disabled → customer sees «Инструкция временно недоступна.»

Changes apply **immediately** without bot restart. Purchase/renewal flows read payment details via `SettingsService.get_payment_details()`. Customer `🆘 Поддержка` and `ℹ️ Инструкция` use `SettingsService` (not raw `Settings`).

### Admin logs

| Action | When |
|---|---|
| `payment_settings_updated` / `payment_settings_cleared` | Payment details edit/clear |
| `support_settings_updated` / `support_settings_cleared` | Support fields edit/clear |
| `instruction_settings_updated` / `instruction_settings_cleared` | Instruction edit/clear/toggle |

Logs record field names only — not full payment details or secrets.

### FSM states

- `PaymentSettingsStates.waiting_details`
- `SupportSettingsStates` — username, url, text
- `InstructionSettingsStates` — text, url
- `/cancel` returns to settings menu

## GitHub Release & Installer (Stage 10)

| Script | Purpose |
|---|---|
| `install.sh` | One-command install to `/opt/marzban-and-3x-ui-bot` |
| `update.sh` | `git pull`, rebuild, migrate, restart |
| `backup.sh` | PostgreSQL `pg_dump` → `backups/*.sql.gz` |
| `scripts/smoke_check.py` | Safe env/import diagnostics |

Installer: `bash <(curl -Ls https://raw.githubusercontent.com/PsychicBAM/marzban-and-3x-ui-bot/main/install.sh)`

- `set -euo pipefail`, Russian prompts
- Does not overwrite existing `.env` without confirmation
- Does not print secrets after input
- QA: [docs/QA_CHECKLIST.md](QA_CHECKLIST.md)

## Development Stages

1. ✅ Project structure, config, Docker, models, migrations, stubs, basic menus
2. ✅ Repositories, UoW, user registration, demo plans seed, tariff list (admin), tariff selection (customer)
3. ✅ Admin tariff management (create, edit, enable/disable)
4. ✅ Manual payment request flow (no VPN issuance yet)
5. ✅ VPN panel API services (Marzban + 3x-ui)
6. ✅ VPN issuance on payment approval (5B)
7. ✅ QR-code generation and delivery (5C)
8. ✅ «Мой VPN» + renewal payment flow (Stage 6)
9. ✅ Admin client management (Stage 7)
10. ✅ Expiry notifications + settings UI (Stage 8)
11. ✅ Admin statistics (9A)
12. ✅ Admin manual VPN key creation (9B)
13. ✅ Payment/support/instruction settings in `⚙️ Настройки` (9C)
14. ✅ Admin broadcasts / promotions (`📣 Рассылки`, migration `0007`)
15. ✅ Promo codes / discounts (`🎁 Промокоды`, migration `0008`)
16. ✅ GitHub release + one-command install (`install.sh`, `update.sh`, `backup.sh`, QA checklist)

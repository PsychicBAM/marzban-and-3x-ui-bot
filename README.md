# Telegram VPN Sales Bot

Telegram-бот для продажи VPN-подписок с поддержкой панелей **Marzban** и **3x-ui**, ручным подтверждением оплаты, тарифами, QR-кодами и админ-панелью.

**Repository:** [github.com/PsychicBAM/marzban-and-3x-ui-bot](https://github.com/PsychicBAM/marzban-and-3x-ui-bot)

## Quick Start (Linux server)

One-command install on Ubuntu/Debian (root or sudo):

```bash
bash <(curl -Ls https://raw.githubusercontent.com/PsychicBAM/marzban-and-3x-ui-bot/main/install.sh)
```

The installer will:

1. Check/install `curl`, `git`, Docker, and Docker Compose v2
2. Clone the repo to `/opt/marzban-and-3x-ui-bot` (or `git pull` if already present)
3. Create `.env` from `.env.example` and ask for required settings interactively
4. Keep an existing `.env` by default (asks before overwriting)
5. Run `docker compose up -d --build` and `alembic upgrade head`
6. Never print secrets after input

**Install path:** `/opt/marzban-and-3x-ui-bot`

| Task | Command |
|---|---|
| Logs | `cd /opt/marzban-and-3x-ui-bot && docker compose logs -f bot` |
| Restart | `docker compose restart bot` |
| Stop | `docker compose down` |
| Update | `./update.sh` |
| Backup DB | `./backup.sh` |
| Edit config | `nano /opt/marzban-and-3x-ui-bot/.env` then `docker compose restart bot` |
| Migrations | `docker compose exec -T bot alembic upgrade head` |
| Smoke check | `python scripts/smoke_check.py` |

Full deployment guide: [docs/DEPLOY.md](docs/DEPLOY.md) · QA checklist: [docs/QA_CHECKLIST.md](docs/QA_CHECKLIST.md)

## Возможности

- Клиентское меню: покупка, продление, «Мой VPN», инструкция, поддержка
- Админ-панель: заявки, клиенты, тарифы, статистика, настройки
- PostgreSQL + SQLAlchemy 2 (async) + Alembic
- Интеграция с Marzban и 3x-ui через HTTP API
- Docker Compose для продакшена

## Требования

- Python 3.11+
- PostgreSQL 16 (локально или через Docker)
- Telegram Bot Token

## Настройка `.env`

Скопируйте пример и заполните значения:

```bash
cp .env.example .env
```

Обязательные переменные:

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен Telegram-бота |
| `ADMIN_TELEGRAM_IDS` | Telegram ID админов через запятую |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/db` |
| `MARZBAN_*` / `XUI_*` | Параметры VPN-панелей |

Для VLESS REALITY укажите flow (если нужен):

| Переменная | Описание |
|---|---|
| `MARZBAN_VLESS_FLOW` | Например `xtls-rprx-vision` — только для VLESS в Marzban |
| `XUI_VLESS_FLOW` | То же для VLESS inbound в 3x-ui |

Полный список — в [`.env.example`](.env.example).

## Локальный запуск

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# отредактируйте .env
alembic upgrade head
python -m app.main
```

Для локальной БД можно поднять только PostgreSQL:

```bash
docker compose up -d postgres
```

## Запуск через Docker

```bash
cp .env.example .env
# отредактируйте .env
docker compose up -d --build
docker compose exec bot alembic upgrade head
docker compose logs -f bot
```

Подробнее: [docs/DEPLOY.md](docs/DEPLOY.md).

## Первый админ

Добавьте свой Telegram ID в `.env`:

```env
ADMIN_TELEGRAM_IDS=123456789
```

Узнать ID можно через [@userinfobot](https://t.me/userinfobot). После перезапуска бота отправьте `/start` или `/admin`.

## Структура проекта

```
app/
  config/          # настройки из .env
  domain/          # enum и доменные типы
  application/     # порты (интерфейсы сервисов)
  infrastructure/  # БД, API-клиенты, логирование
  presentation/    # aiogram handlers, keyboards
alembic/           # миграции
docs/              # документация
```

## Документация

- [docs/SPEC.md](docs/SPEC.md) — спецификация
- [docs/DEPLOY.md](docs/DEPLOY.md) — деплой на сервер
- [docs/CURSOR_CHEATSHEET.md](docs/CURSOR_CHEATSHEET.md) — шпаргалка для разработки

## Статус разработки

**Этап 1:** структура проекта, конфиг, Docker, модели БД, миграции, заглушки Marzban/3x-ui, базовый запуск бота и меню.

**Этап 2:** репозитории, UnitOfWork, сервисы, регистрация пользователей, демо-тарифы, просмотр тарифов (админ), выбор тарифа (клиент).

**Этап 3:** полное управление тарифами в админке.

**Этап 4:** ручной платёжный поток — чек → заявка → подтверждение/отклонение админом.

**Этап 5A:** production-ready MarzbanService и XuiService.

**Этап 5B:** выдача VPN после подтверждения оплаты.

**Этап 5C:** QR-коды из ссылок подписки (в памяти, без сохранения на диск по умолчанию).

**Этап 6:** «📊 Мой VPN», продление VPN, ссылки/QR по запросу.

**Этап 7:** админ «👥 Клиенты» — списки, поиск, карточка, disable/enable/delete, IP limit, ручное продление.

**Этап 8:** уведомления об истечении VPN (APScheduler), настройки `⚙️ → 🔔 Уведомления`.

**Этап 9A:** админ `📊 Статистика` — пользователи, оплаты, доход (только approved), VPN, истекающие.

**Этап 9B:** админ `➕ Создать ключ` — ручное создание VPN без оплаты.

**Этап 9C:** `⚙️ Настройки` — реквизиты оплаты, поддержка, инструкция (БД с fallback на `.env`).

**Этап 10 (текущий):** GitHub release — `install.sh`, `update.sh`, `backup.sh`, smoke check, QA checklist.

### «Мой VPN», несколько подписок и продление

- `📊 Мой VPN` — одна подписка: карточка; несколько — список подписок → выбор → ссылка / QR / продление
- `🛒 Купить VPN` при активном VPN — выбор: **продлить текущий** или **отдельная подписка** (своё имя)
- `🔄 Продлить VPN` — выбор тарифа → текущий и ожидаемый срок → оплата → заявка `renewal`
- **Активный аккаунт:** оставшиеся дни + дни тарифа (7 + 30 = 37)
- **Истёкший / удалённый:** новый срок от текущей даты

### Тест VPN-панелей (dev-only)

```bash
python scripts/test_marzban_create_user.py --username testuser --days 30 --delete
python scripts/test_xui_create_client.py --list-inbounds
python scripts/test_xui_create_client.py --email testuser --days 30 --delete
python scripts/test_qr_generation.py
python scripts/test_qr_generation.py --save   # optional: tmp/qr_*.png
```

### Поля тарифа

| Поле | Значение |
|---|---|
| `traffic_limit_gb = 0` | безлимитный трафик |
| `ip_limit = 0` | безлимитное число устройств |
| `is_active = false` | тариф скрыт от клиентов, но виден админу |

## Тестирование

```bash
alembic upgrade head
python -m app.main
```

Проверьте в Telegram:

1. `/start` — регистрация пользователя в БД, приветствие
2. `/admin` — админ-панель (только для `ADMIN_TELEGRAM_IDS`)
3. `💰 Тарифы` — список активных тарифов (админ)
4. `🛒 Купить VPN` — inline-кнопки тарифов и детали выбранного тарифа
5. `💰 Тарифы` (админ) — список всех тарифов, создание, редактирование, вкл/выкл
6. `/cancel` — отмена FSM при создании тарифа

**Миграции:**

```bash
alembic upgrade head
```

Этап 5B добавляет `0003_payment_request_provisioning_status`.

### Ручная оплата

1. Клиент: `🛒 Купить VPN` → тариф → (при активном VPN: продление или новая подписка) → реквизиты → `✅ Я оплатил` → чек
   - **Бесплатный тариф** (`price=0`): `🎁 Активировать бесплатно` → мгновенная выдача VPN без заявки и чека (1 раз на пользователя)
   - **Отдельная подписка:** латинское название → уникальное имя `{username}_{label}` → новый VPN у того же пользователя
2. Админ: `📥 Заявки` → открыть → `✅ Подтвердить` / `❌ Отклонить`
3. Подтверждение **выдаёт VPN** (этап 5B) — клиент получает ссылки и QR-коды (этап 5C)
4. Проверка QR: `python scripts/test_qr_generation.py`
5. Проверка правил срока: `python scripts/test_expiry_rules.py`

### «Мой VPN» и продление (этап 6)

1. `📊 Мой VPN` — карточка VPN, кнопки ссылка / QR / продление
2. `🔗 Получить ссылку` / `📷 Получить QR-code` — по запросу из «Мой VPN»
3. `🔄 Продлить VPN` → тариф → `✅ Я оплатил продление` → чек → админ `📥 Заявки` (тип «продление»)
4. Подтверждение продления обновляет срок по правилам выше и отправляет ссылки + QR

### Админ: клиенты (этап 7)

1. `👥 Клиенты` — сводка и фильтры (активные / истёкшие / отключённые / удалённые)
2. `🔎 Найти клиента` — поиск по ID, username, имени, VPN-аккаунту
3. Карточка клиента — ссылка/QR клиенту, disable/enable/delete, IP limit, ручное продление
4. **Удалённый** аккаунт: soft delete, старый срок не продлевается; новая покупка — с текущей даты

### Статистика (этап 9A)

1. `/admin` → `📊 Статистика` — сводка
2. `🔄 Обновить` — перезагрузить данные
3. `📅 Сегодня` / `📆 Этот месяц` — доход и заявки за период
4. Доход считается **только** по заявкам со статусом `approved` (не `provisioning_failed`)

### Ручное создание ключа (этап 9B)

`/admin` → `➕ Создать ключ` — FSM без заявки на оплату.

**Два режима:**

| Режим | Описание |
|---|---|
| 👤 Существующий клиент | Поиск по Telegram ID / username / имени; владелец — выбранный пользователь |
| 🧾 Ручной ключ | Ключ без привязки к реальному клиенту; в БД используется системный пользователь `telegram_id=0` |

**Параметры:** тариф из списка активных или ввод вручную (срок, трафик, IP, режим выдачи marzban/xui/both).

**Срок:** для нового ключа — `now + duration_days`. Если у клиента уже есть активный аккаунт, админ выбирает «продлить» (правила `ExpiryCalculator`) или «отдельный ключ».

**После создания:** админу — ссылки и QR (в памяти, без сохранения на диск). Для клиента — кнопка `📩 Отправить клиенту`. Логи: `manual_vpn_created`, `manual_vpn_sent_to_customer`.

**Тесты:**

1. Ключ для клиента: `➕ Создать ключ` → существующий клиент → поиск → тариф → подтверждение → QR админу → `📩 Отправить клиенту`
2. Standalone: `➕ Создать ключ` → ручной ключ → имя `test_manual_key` → параметры вручную → только админу
3. Конфликт имени: повторить standalone с именем, уже занятым на панели — бот попросит другое имя
4. Частичный успех: `issuing_mode=both` при недоступной одной панели — сохраняется успешная панель, админ видит предупреждение

Миграция **не требуется** — `vpn_accounts.user_id` остаётся NOT NULL; standalone-ключи привязаны к системному пользователю `manual_vpn_system`.

### Настройки бота (этап 9C)

`/admin` → `⚙️ Настройки`:

| Раздел | Что настраивается |
|---|---|
| 🔔 Уведомления | Сроки, интервал scheduler (этап 8) |
| 💳 Реквизиты оплаты | Текст реквизитов для покупки/продления |
| 🆘 Поддержка | Username, ссылка, текст |
| ℹ️ Инструкция | Текст, ссылка, вкл/выкл |

**Приоритет:** значения из таблицы `settings` (PostgreSQL) → fallback на `.env`. Изменения применяются **без перезапуска** бота.

**Тесты:**

1. **Реквизиты:** `⚙️` → `💳 Реквизиты` → `✏️ Изменить` → многострочный текст → клиент `🛒 Купить VPN` видит новые реквизиты → `🧹 Очистить` → снова `.env` (если задан)
2. **Поддержка:** `🆘 Поддержка` → изменить username/ссылку/текст → клиент `🆘 Поддержка` видит обновление
3. **Инструкция:** `ℹ️ Инструкция` → текст/ссылка → `🚫 Выключить` → клиент видит «Инструкция временно недоступна» → очистить → дефолтный текст

Миграция **не требуется** — используется существующая таблица `settings`.

### Уведомления об истечении (этап 8)

```bash
alembic upgrade head   # миграция 0004
```

1. `⚙️ Настройки` → `🔔 Уведомления` — дни, интервал, тестовый режим
2. `📩 Отправить тест админу` — проверка без рассылки клиентам
3. Для проверки scheduler: интервал `every_1_minute` (только для теста), **без** test_mode
4. Дубликаты: повторные напоминания не отправляются (таблица `notifications`)

Реквизиты: таблица `settings` (`payment_details`) → fallback `.env` → `PAYMENT_DETAILS`.

## Безопасность

Не коммитьте `.env`, токены, пароли, логи и файлы БД. Используйте `.env.example` как шаблон.

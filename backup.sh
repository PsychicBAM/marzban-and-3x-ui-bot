#!/usr/bin/env bash
# Telegram VPN Bot — PostgreSQL backup
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/marzban-and-3x-ui-bot}"
BACKUP_DIR="${BACKUP_DIR:-${INSTALL_DIR}/backups}"

SUDO=""
DC_CMD=(docker compose)

info() { printf '\033[1;34m[INFO]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[OK]\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; }

if [[ ! -d "${INSTALL_DIR}" ]]; then
  err "Каталог не найден: ${INSTALL_DIR}"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  if command -v sudo >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
    DC_CMD=(sudo docker compose)
  else
    err "Docker недоступен."
    exit 1
  fi
fi

cd "${INSTALL_DIR}"

POSTGRES_USER="vpn_bot"
POSTGRES_DB="vpn_bot"
if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  POSTGRES_USER="$(grep -E '^POSTGRES_USER=' .env | head -1 | cut -d= -f2- | tr -d '"' || echo vpn_bot)"
  POSTGRES_DB="$(grep -E '^POSTGRES_DB=' .env | head -1 | cut -d= -f2- | tr -d '"' || echo vpn_bot)"
fi

mkdir -p "${BACKUP_DIR}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT="${BACKUP_DIR}/vpn_bot_${TIMESTAMP}.sql.gz"

info "Создание резервной копии PostgreSQL ..."
if ! "${DC_CMD[@]}" ps --status running postgres 2>/dev/null | grep -q postgres; then
  err "Контейнер postgres не запущен. Запустите: docker compose up -d"
  exit 1
fi

"${DC_CMD[@]}" exec -T postgres pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" | gzip > "${OUTPUT}"
chmod 600 "${OUTPUT}" 2>/dev/null || true

ok "Резервная копия: ${OUTPUT}"
echo ""
echo "Восстановление (осторожно — перезапишет данные):"
echo "  gunzip -c ${OUTPUT} | docker compose exec -T postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB}"

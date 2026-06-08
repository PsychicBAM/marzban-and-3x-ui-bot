#!/usr/bin/env bash
# Telegram VPN Bot — update script
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/marzban-and-3x-ui-bot}"
BRANCH="${BRANCH:-main}"

SUDO=""
DC_CMD=(docker compose)

info() { printf '\033[1;34m[INFO]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[OK]\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; }

if [[ ! -d "${INSTALL_DIR}/.git" ]]; then
  err "Репозиторий не найден: ${INSTALL_DIR}"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  if command -v sudo >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
    SUDO="sudo"
    DC_CMD=(sudo docker compose)
  else
    err "Docker недоступен."
    exit 1
  fi
fi

cd "${INSTALL_DIR}"

info "Получение обновлений из Git ..."
git fetch origin
git checkout "${BRANCH}"
git pull --ff-only origin "${BRANCH}"

info "Пересборка контейнеров ..."
"${DC_CMD[@]}" up -d --build

info "Миграции базы данных ..."
"${DC_CMD[@]}" exec -T bot alembic upgrade head

info "Перезапуск бота ..."
"${DC_CMD[@]}" restart bot

ok "Обновление завершено."
echo ""
echo "Логи:  cd ${INSTALL_DIR} && docker compose logs -f bot"
echo "Статус: cd ${INSTALL_DIR} && docker compose ps"

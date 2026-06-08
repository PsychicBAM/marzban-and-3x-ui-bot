#!/usr/bin/env bash
# Telegram VPN Bot — one-command installer for Ubuntu/Debian
set -euo pipefail

REPO_URL="https://github.com/PsychicBAM/marzban-and-3x-ui-bot.git"
INSTALL_DIR="/opt/marzban-and-3x-ui-bot"
BRANCH="${BRANCH:-main}"

SUDO=""
DC_CMD=(docker compose)

info()  { printf '\033[1;34m[INFO]\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m[OK]\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }
err()   { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; }

require_root_or_sudo() {
  if [[ "${EUID}" -eq 0 ]]; then
    return 0
  fi
  if command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
    return 0
  fi
  err "Запустите скрипт от root или с установленным sudo."
  exit 1
}

run_root() {
  if [[ -n "${SUDO}" ]]; then
    "${SUDO}" "$@"
  else
    "$@"
  fi
}

ensure_curl_git() {
  local missing=()
  command -v curl >/dev/null 2>&1 || missing+=(curl)
  command -v git  >/dev/null 2>&1 || missing+=(git)

  if [[ "${#missing[@]}" -eq 0 ]]; then
    return 0
  fi

  info "Устанавливаю: ${missing[*]} ..."
  if command -v apt-get >/dev/null 2>&1; then
    run_root apt-get update -qq
    run_root apt-get install -y -qq "${missing[@]}"
  elif command -v yum >/dev/null 2>&1; then
    run_root yum install -y "${missing[@]}"
  elif command -v dnf >/dev/null 2>&1; then
    run_root dnf install -y "${missing[@]}"
  else
    err "Не удалось установить ${missing[*]}. Установите вручную и повторите."
    exit 1
  fi
  ok "curl и git доступны."
}

docker_available() {
  if docker info >/dev/null 2>&1; then
    return 0
  fi
  if [[ -n "${SUDO}" ]] && ${SUDO} docker info >/dev/null 2>&1; then
    DC_CMD=("${SUDO}" docker compose)
    return 0
  fi
  return 1
}

ensure_docker() {
  if docker_available; then
    ok "Docker доступен."
    return 0
  fi

  warn "Docker не найден или недоступен."
  read -r -p "Установить Docker автоматически? [Y/n]: " answer
  answer="${answer:-Y}"
  if [[ "${answer}" =~ ^[Yy]$ ]]; then
    info "Установка Docker (get.docker.com) ..."
    curl -fsSL https://get.docker.com | run_root sh
    if [[ "${EUID}" -ne 0 ]] && groups "${USER}" | grep -qv docker; then
      run_root usermod -aG docker "${USER}" || true
      warn "Пользователь ${USER} добавлен в группу docker. Может потребоваться перелогин."
    fi
  else
    err "Установите Docker вручную: https://docs.docker.com/engine/install/"
    exit 1
  fi

  if ! docker_available; then
    DC_CMD=("${SUDO}" docker compose)
    if ! ${SUDO} docker info >/dev/null 2>&1; then
      err "Docker по-прежнему недоступен."
      exit 1
    fi
  fi
  ok "Docker установлен."
}

ensure_compose_plugin() {
  if "${DC_CMD[@]}" version >/dev/null 2>&1; then
    ok "Docker Compose plugin доступен."
    return 0
  fi

  warn "Docker Compose plugin не найден."
  if command -v apt-get >/dev/null 2>&1; then
    info "Устанавливаю docker-compose-plugin ..."
    run_root apt-get update -qq
    run_root apt-get install -y -qq docker-compose-plugin
  fi

  if ! "${DC_CMD[@]}" version >/dev/null 2>&1; then
    err "Установите Docker Compose v2: https://docs.docker.com/compose/install/linux/"
    exit 1
  fi
  ok "Docker Compose plugin установлен."
}

clone_or_update_repo() {
  run_root mkdir -p "$(dirname "${INSTALL_DIR}")"

  if [[ -d "${INSTALL_DIR}/.git" ]]; then
    info "Каталог уже существует. Обновляю репозиторий ..."
    run_root git -C "${INSTALL_DIR}" fetch origin
    run_root git -C "${INSTALL_DIR}" checkout "${BRANCH}"
    run_root git -C "${INSTALL_DIR}" pull --ff-only origin "${BRANCH}" || {
      warn "git pull не выполнен (возможны локальные изменения). Продолжаю с текущей версией."
    }
  else
    info "Клонирую репозиторий в ${INSTALL_DIR} ..."
    run_root git clone --branch "${BRANCH}" --depth 1 "${REPO_URL}" "${INSTALL_DIR}"
  fi

  if [[ "${EUID}" -ne 0 ]]; then
    run_root chown -R "${USER}:${USER}" "${INSTALL_DIR}" 2>/dev/null || true
  fi
  chmod +x "${INSTALL_DIR}/update.sh" "${INSTALL_DIR}/backup.sh" 2>/dev/null || true
  ok "Репозиторий готов: ${INSTALL_DIR}"
}

generate_password() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 32
  else
    tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32
  fi
}

escape_env_value() {
  local value="$1"
  value="${value//$'\r'/}"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  printf '%s' "${value}"
}

set_env_key() {
  local key="$1"
  local value="$2"
  local file="${INSTALL_DIR}/.env"
  local escaped
  escaped="$(escape_env_value "${value}")"

  touch "${file}"
  if grep -q "^${key}=" "${file}" 2>/dev/null; then
    grep -v "^${key}=" "${file}" > "${file}.tmp"
    mv "${file}.tmp" "${file}"
  fi
  printf '%s="%s"\n' "${key}" "${escaped}" >> "${file}"
}

read_nonempty() {
  local prompt="$1"
  local secret="${2:-false}"
  local input=""
  while [[ -z "${input}" ]]; do
    if [[ "${secret}" == "true" ]]; then
      read -r -s -p "${prompt}: " input
      echo ""
    else
      read -r -p "${prompt}: " input
    fi
    input="$(echo "${input}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    if [[ -z "${input}" ]]; then
      warn "Значение не может быть пустым."
    fi
  done
  REPLY="${input}"
}

read_optional() {
  local prompt="$1"
  local default="${2:-}"
  read -r -p "${prompt} [${default}]: " input
  input="$(echo "${input:-${default}}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  REPLY="${input}"
}

read_bool() {
  local prompt="$1"
  local default="${2:-false}"
  local hint="y/N"
  [[ "${default}" == "true" ]] && hint="Y/n"
  read -r -p "${prompt} [${hint}]: " input
  input="${input:-}"
  if [[ -z "${input}" ]]; then
    REPLY="${default}"
    return
  fi
  if [[ "${input}" =~ ^[Yy]$ ]]; then
    REPLY="true"
  else
    REPLY="false"
  fi
}

read_multiline() {
  local prompt="$1"
  local block=""
  echo "${prompt}"
  echo "(введите текст; пустая строка завершает ввод)"
  while IFS= read -r line; do
    [[ -z "${line}" ]] && break
    if [[ -n "${block}" ]]; then
      block+=$'\n'"${line}"
    else
      block="${line}"
    fi
  done
  REPLY="${block}"
}

configure_env_interactive() {
  local env_file="${INSTALL_DIR}/.env"
  cp "${INSTALL_DIR}/.env.example" "${env_file}"
  chmod 600 "${env_file}"

  echo ""
  info "=== Обязательные настройки ==="

  read_nonempty "BOT_TOKEN (токен Telegram-бота)" true
  set_env_key "BOT_TOKEN" "${REPLY}"

  read_nonempty "ADMIN_TELEGRAM_IDS (через запятую)"
  set_env_key "ADMIN_TELEGRAM_IDS" "${REPLY}"

  read_optional "POSTGRES_PASSWORD (пусто = сгенерировать автоматически)" ""
  local pg_pass="${REPLY}"
  if [[ -z "${pg_pass}" ]]; then
    pg_pass="$(generate_password)"
    ok "Сгенерирован POSTGRES_PASSWORD (не выводится в лог)."
  fi
  set_env_key "POSTGRES_PASSWORD" "${pg_pass}"

  local pg_user="vpn_bot"
  local pg_db="vpn_bot"
  local pg_host="postgres"
  local pg_port="5432"
  set_env_key "POSTGRES_USER" "${pg_user}"
  set_env_key "POSTGRES_DB" "${pg_db}"
  set_env_key "POSTGRES_HOST" "${pg_host}"
  set_env_key "POSTGRES_PORT" "${pg_port}"
  set_env_key "DATABASE_URL" "postgresql+asyncpg://${pg_user}:${pg_pass}@${pg_host}:${pg_port}/${pg_db}"

  echo ""
  info "=== Реквизиты и поддержка ==="
  read_multiline "PAYMENT_DETAILS (реквизиты оплаты)"
  set_env_key "PAYMENT_DETAILS" "${REPLY}"

  read_optional "SUPPORT_USERNAME (без @)" ""
  set_env_key "SUPPORT_USERNAME" "${REPLY}"

  read_optional "SUPPORT_URL (http/https, необязательно)" ""
  set_env_key "SUPPORT_URL" "${REPLY}"

  read_multiline "SUPPORT_TEXT (необязательно, Enter = пропустить)"
  set_env_key "SUPPORT_TEXT" "${REPLY}"

  read_multiline "INSTRUCTION_TEXT (необязательно)"
  set_env_key "INSTRUCTION_TEXT" "${REPLY}"

  read_optional "INSTRUCTION_URL (необязательно)" ""
  set_env_key "INSTRUCTION_URL" "${REPLY}"
  set_env_key "INSTRUCTION_ENABLED" "true"

  echo ""
  info "=== Marzban ==="
  read_bool "Включить Marzban?" "false"
  local marzban_enabled="${REPLY}"
  set_env_key "MARZBAN_ENABLED" "${marzban_enabled}"

  if [[ "${marzban_enabled}" == "true" ]]; then
    read_nonempty "MARZBAN_BASE_URL"
    set_env_key "MARZBAN_BASE_URL" "${REPLY}"

    read_optional "MARZBAN_API_TOKEN (если пусто — username/password)" ""
    if [[ -n "${REPLY}" ]]; then
      set_env_key "MARZBAN_API_TOKEN" "${REPLY}"
      set_env_key "MARZBAN_USERNAME" ""
      set_env_key "MARZBAN_PASSWORD" ""
    else
      set_env_key "MARZBAN_API_TOKEN" ""
      read_nonempty "MARZBAN_USERNAME"
      set_env_key "MARZBAN_USERNAME" "${REPLY}"
      read_nonempty "MARZBAN_PASSWORD" true
      set_env_key "MARZBAN_PASSWORD" "${REPLY}"
    fi

    read_optional "MARZBAN_SUBSCRIPTION_BASE_URL" ""
    set_env_key "MARZBAN_SUBSCRIPTION_BASE_URL" "${REPLY}"

    read_optional "MARZBAN_INBOUND_VLESS" "vless-tcp-reality"
    set_env_key "MARZBAN_INBOUND_VLESS" "${REPLY}"
    read_optional "MARZBAN_INBOUND_TROJAN" "trojan-tcp-notls"
    set_env_key "MARZBAN_INBOUND_TROJAN" "${REPLY}"
    read_optional "MARZBAN_INBOUND_VMESS" "vmess-tcp-notls"
    set_env_key "MARZBAN_INBOUND_VMESS" "${REPLY}"
    set_env_key "MARZBAN_VERIFY_SSL" "true"
  else
    set_env_key "MARZBAN_BASE_URL" ""
    set_env_key "MARZBAN_USERNAME" ""
    set_env_key "MARZBAN_PASSWORD" ""
    set_env_key "MARZBAN_API_TOKEN" ""
    set_env_key "MARZBAN_VERIFY_SSL" "true"
  fi

  echo ""
  info "=== 3x-ui ==="
  read_bool "Включить 3x-ui?" "false"
  local xui_enabled="${REPLY}"
  set_env_key "XUI_ENABLED" "${xui_enabled}"

  if [[ "${xui_enabled}" == "true" ]]; then
    read_nonempty "XUI_BASE_URL"
    set_env_key "XUI_BASE_URL" "${REPLY}"

    read_optional "XUI_API_TOKEN (если пусто — username/password)" ""
    if [[ -n "${REPLY}" ]]; then
      set_env_key "XUI_API_TOKEN" "${REPLY}"
      set_env_key "XUI_USERNAME" ""
      set_env_key "XUI_PASSWORD" ""
    else
      set_env_key "XUI_API_TOKEN" ""
      read_nonempty "XUI_USERNAME"
      set_env_key "XUI_USERNAME" "${REPLY}"
      read_nonempty "XUI_PASSWORD" true
      set_env_key "XUI_PASSWORD" "${REPLY}"
    fi

    read_optional "XUI_SUBSCRIPTION_BASE_URL" ""
    set_env_key "XUI_SUBSCRIPTION_BASE_URL" "${REPLY}"

    read_optional "XUI_INBOUND_ID" "1"
    set_env_key "XUI_INBOUND_ID" "${REPLY}"
    set_env_key "XUI_VERIFY_SSL" "true"
  else
    set_env_key "XUI_BASE_URL" ""
    set_env_key "XUI_USERNAME" ""
    set_env_key "XUI_PASSWORD" ""
    set_env_key "XUI_API_TOKEN" ""
    set_env_key "XUI_INBOUND_ID" "1"
    set_env_key "XUI_VERIFY_SSL" "true"
  fi

  # Defaults for remaining keys from example
  set_env_key "LOG_LEVEL" "INFO"
  set_env_key "TIMEZONE" "Europe/Moscow"
  set_env_key "DEFAULT_ISSUING_MODE" "both"
  set_env_key "NOTIFICATIONS_ENABLED" "true"
  set_env_key "NOTIFICATION_DAYS" "7,3,1"
  set_env_key "NOTIFICATION_CHECK_INTERVAL" "daily"
  set_env_key "NOTIFICATION_TEST_MODE" "false"
  set_env_key "NOTIFY_EXPIRED_ENABLED" "true"

  chmod 600 "${env_file}"
  ok "Файл .env создан (права 600). Секреты не выводятся в консоль."
}

handle_env_file() {
  local env_file="${INSTALL_DIR}/.env"
  if [[ -f "${env_file}" ]]; then
    warn "Файл .env уже существует."
    read -r -p "Пересоздать .env интерактивно? [y/N]: " answer
    answer="${answer:-N}"
    if [[ "${answer}" =~ ^[Yy]$ ]]; then
      cp "${env_file}" "${env_file}.bak.$(date +%Y%m%d_%H%M%S)"
      info "Резервная копия .env сохранена."
      configure_env_interactive
    else
      ok "Используется существующий .env"
    fi
  else
    configure_env_interactive
  fi
}

start_services() {
  cd "${INSTALL_DIR}"
  info "Сборка и запуск контейнеров ..."
  "${DC_CMD[@]}" up -d --build

  info "Ожидание готовности PostgreSQL ..."
  local i
  for i in $(seq 1 30); do
    if "${DC_CMD[@]}" exec -T postgres pg_isready -U vpn_bot -d vpn_bot >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done

  info "Применение миграций ..."
  "${DC_CMD[@]}" exec -T bot alembic upgrade head
  ok "Миграции применены."
}

print_final_message() {
  echo ""
  ok "Установка завершена!"
  echo ""
  echo "Каталог проекта: ${INSTALL_DIR}"
  echo ""
  echo "Полезные команды:"
  echo "  cd ${INSTALL_DIR}"
  echo "  docker compose logs -f bot"
  echo "  docker compose restart bot"
  echo "  docker compose down"
  echo "  ./update.sh          # обновление"
  echo "  ./backup.sh          # резервная копия БД"
  echo ""
  echo "Проверка: отправьте /start боту в Telegram."
  echo "Админ:   /admin (для ID из ADMIN_TELEGRAM_IDS)"
  echo ""
}

main() {
  echo "=============================================="
  echo "  Telegram VPN Bot — установка"
  echo "  ${REPO_URL}"
  echo "=============================================="
  echo ""

  require_root_or_sudo
  ensure_curl_git
  ensure_docker
  ensure_compose_plugin
  clone_or_update_repo
  handle_env_file
  start_services
  print_final_message
}

main "$@"

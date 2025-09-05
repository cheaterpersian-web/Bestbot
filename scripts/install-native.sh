#!/usr/bin/env bash

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}[INFO]${NC} $*"; }
ok() { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err() { echo -e "${RED}[ERR]${NC} $*"; }

# Resolve repository root robustly (supports running script outside cloned repo)
# Priority:
# 1) REPO_ROOT env var (if provided)
# 2) Parent of script directory (if contains app/)
# 3) $PWD/Bestbot (common clone path used by easy installer)
# 4) $PWD (if contains app/)
if [[ -n "${REPO_ROOT:-}" ]]; then
  REPO_ROOT="$(cd "$REPO_ROOT" && pwd)"
else
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  POSSIBLE_ROOTS=(
    "$(cd "$SCRIPT_DIR/.." && pwd)"
    "$PWD/Bestbot"
    "$PWD"
  )
  for path in "${POSSIBLE_ROOTS[@]}"; do
    if [[ -d "$path/app" ]]; then
      REPO_ROOT="$path"
      break
    fi
  done
  REPO_ROOT="${REPO_ROOT:-$SCRIPT_DIR}"
fi
APP_DIR="$REPO_ROOT/app"
ENV_FILE="$REPO_ROOT/.env"
VENVS_BASE="/opt/vpn-bot"
VENV_DIR="$VENVS_BASE/venv"
RUN_USER="vpn-bot"
RUN_GROUP="$RUN_USER"

require_root() {
  if [[ $EUID -ne 0 ]]; then
    err "Run as root (use sudo)."
    exit 1
  fi
}

detect_os() {
  if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    OS_ID="$ID"; OS_VER="$VERSION_CODENAME"
  else
    OS_ID="unknown"; OS_VER="unknown"
  fi
  info "OS: $OS_ID ($OS_VER)"
}

install_packages() {
  info "Installing system packages (MariaDB, Redis, Python, Nginx)..."
  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y python3 python3-venv python3-pip python3-dev build-essential \
                       mariadb-server mariadb-client redis-server nginx git curl
  else
    err "Unsupported OS. Install MariaDB, Redis, Python3, Nginx manually."
    exit 1
  fi
  ok "Packages installed"
}

ensure_repo_present() {
  # Ensure repository root points to a directory containing app/ and requirements.txt
  if [[ -f "$APP_DIR/requirements.txt" ]]; then
    return
  fi
  warn "Repository not found at $REPO_ROOT (missing $APP_DIR/requirements.txt)"
  if command -v git >/dev/null 2>&1; then
    info "Cloning repository into /opt/vpn-bot/src/Bestbot..."
    mkdir -p /opt/vpn-bot/src
    if [[ ! -d /opt/vpn-bot/src/Bestbot/.git ]]; then
      git clone https://github.com/cheaterpersian-web/Bestbot.git /opt/vpn-bot/src/Bestbot || true
    fi
    REPO_ROOT="/opt/vpn-bot/src/Bestbot"
    APP_DIR="$REPO_ROOT/app"
    ENV_FILE="$REPO_ROOT/.env"
    ok "Repository prepared at $REPO_ROOT"
  else
    err "Git is not installed. Cannot fetch repository."
    exit 1
  fi
}

create_user() {
  if ! id -u "$RUN_USER" >/dev/null 2>&1; then
    info "Creating system user $RUN_USER"
    useradd --system --home "$VENVS_BASE" --shell /usr/sbin/nologin "$RUN_USER"
  fi
  mkdir -p "$VENVS_BASE"
  chown -R "$RUN_USER":"$RUN_GROUP" "$VENVS_BASE"
}

setup_mysql() {
  info "Configuring MariaDB..."
  systemctl enable --now mariadb
  DB_NAME="${MYSQL_DATABASE:-vpn_bot}"
  DB_USER="${MYSQL_USER:-vpn_user}"
  DB_PASS="${MYSQL_PASSWORD:-vpn_pass}"
  DB_ROOT_PASS="${MYSQL_ROOT_PASSWORD:-root}"
  mysqladmin password "$DB_ROOT_PASS" 2>/dev/null || true
  mysql -u root -p"$DB_ROOT_PASS" -e "CREATE DATABASE IF NOT EXISTS \`$DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
  mysql -u root -p"$DB_ROOT_PASS" -e "CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';"
  mysql -u root -p"$DB_ROOT_PASS" -e "GRANT ALL PRIVILEGES ON \`$DB_NAME\`.* TO '$DB_USER'@'localhost'; FLUSH PRIVILEGES;"
  ok "MariaDB configured"
}

setup_redis() {
  info "Configuring Redis..."
  systemctl enable --now redis-server
  ok "Redis running"
}

setup_env() {
  info "Creating .env file ($ENV_FILE)"
  if [[ -f "$ENV_FILE" ]]; then
    warn ".env already exists, adjusting DATABASE_URL and Redis for native install if needed."
    # Force DATABASE_URL host to 127.0.0.1 to avoid 'db' hostname issues in native installs
    if grep -qE '^DATABASE_URL=' "$ENV_FILE"; then
      # Replace @db or @localhost with @127.0.0.1
      sed -i -E 's/@db([:/])/@127.0.0.1\1/g; s/@localhost([:/])/@127.0.0.1\1/g' "$ENV_FILE" || true
      # Ensure default port :3306 exists after 127.0.0.1 when missing
      sed -i -E 's@(@127\.0\.0\.1)/@\1:3306/@g' "$ENV_FILE" || true
    else
      DB_NAME="${MYSQL_DATABASE:-vpn_bot}"; DB_USER="${MYSQL_USER:-vpn_user}"; DB_PASS="${MYSQL_PASSWORD:-vpn_pass}"
      echo "DATABASE_URL=mysql+aiomysql://$DB_USER:$DB_PASS@127.0.0.1:3306/$DB_NAME?charset=utf8mb4" >> "$ENV_FILE"
    fi
    # Ensure Redis points to local too
    if grep -qE '^REDIS_URL=' "$ENV_FILE"; then
      sed -i -E 's#^REDIS_URL=.*#REDIS_URL=redis://127.0.0.1:6379/0#g' "$ENV_FILE" || true
    else
      echo "REDIS_URL=redis://127.0.0.1:6379/0" >> "$ENV_FILE"
    fi
    ok ".env adjusted for native install"
    return
  fi
  read -r -p "Enter Telegram BOT_TOKEN: " BOT_TOKEN
  read -r -p "Enter admin IDs (comma separated, e.g. 123,456): " ADMIN_IDS
  read -r -p "Enter bot username (without @): " BOT_USERNAME
  DB_NAME="vpn_bot"; DB_USER="vpn_user"; DB_PASS="vpn_pass"
  cat > "$ENV_FILE" <<EOF
# Telegram Bot Configuration
BOT_TOKEN=$BOT_TOKEN
ADMIN_IDS=$ADMIN_IDS
BOT_USERNAME=$BOT_USERNAME

# Database Configuration (native)
MYSQL_DATABASE=$DB_NAME
MYSQL_USER=$DB_USER
MYSQL_PASSWORD=$DB_PASS
MYSQL_ROOT_PASSWORD=root
DATABASE_URL=mysql+aiomysql://$DB_USER:$DB_PASS@127.0.0.1:3306/$DB_NAME?charset=utf8mb4

# Redis
REDIS_URL=redis://127.0.0.1:6379/0
EOF
  ok ".env created"
}

setup_venv() {
  info "Creating Python venv at $VENV_DIR"
  mkdir -p "$VENVS_BASE"
  python3 -m venv "$VENV_DIR"
  source "$VENV_DIR/bin/activate"
  pip install --upgrade pip
  pip install -r "$APP_DIR/requirements.txt"
  deactivate
  chown -R "$RUN_USER":"$RUN_GROUP" "$VENVS_BASE"
  ok "Virtualenv ready"
}

run_db_migrations() {
  info "Initializing database schema..."
  source "$VENV_DIR/bin/activate"
  export PYTHONPATH="$APP_DIR"
  export $(grep -v '^#' "$ENV_FILE" | xargs -d '\n' -I{} echo {}) >/dev/null 2>&1 || true
  python -c "import asyncio; from core.db import init_db_schema; asyncio.run(init_db_schema())"
  deactivate
  ok "Database schema initialized"
}

install_systemd() {
  info "Installing systemd services..."
  cat > /etc/systemd/system/vpn-bot-api.service <<'UNIT'
[Unit]
Description=VPN Bot API (FastAPI)
After=network.target mariadb.service redis-server.service
Wants=network-online.target

[Service]
Type=simple
User=vpn-bot
Group=vpn-bot
WorkingDirectory=REPO_ROOT/app
EnvironmentFile=REPO_ROOT/.env
Environment=PYTHONPATH=REPO_ROOT/app
ExecStart=REPO_VENV/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

  cat > /etc/systemd/system/vpn-bot-worker.service <<'UNIT'
[Unit]
Description=VPN Bot Telegram Worker
After=network.target mariadb.service redis-server.service
Wants=network-online.target

[Service]
Type=simple
User=vpn-bot
Group=vpn-bot
WorkingDirectory=REPO_ROOT/app
EnvironmentFile=REPO_ROOT/.env
Environment=PYTHONPATH=REPO_ROOT/app
ExecStart=REPO_VENV/bin/python -m bot.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

  sed -i "s#REPO_ROOT#$REPO_ROOT#g" /etc/systemd/system/vpn-bot-*.service
  sed -i "s#REPO_VENV#$VENV_DIR#g" /etc/systemd/system/vpn-bot-*.service
  chown root:root /etc/systemd/system/vpn-bot-*.service
  systemctl daemon-reload
  systemctl enable vpn-bot-api vpn-bot-worker
  ok "systemd services installed"
}

setup_nginx() {
  info "Configuring Nginx reverse proxy..."
  cat > /etc/nginx/sites-available/vpn-bot.conf <<'NGINX'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX
  ln -sf /etc/nginx/sites-available/vpn-bot.conf /etc/nginx/sites-enabled/vpn-bot.conf
  nginx -t
  systemctl enable --now nginx
  systemctl reload nginx
  ok "Nginx configured"
}

start_services() {
  info "Starting services..."
  systemctl restart vpn-bot-api vpn-bot-worker
  systemctl status --no-pager vpn-bot-api vpn-bot-worker || true
  ok "Services started"
}

print_summary() {
  echo -e "${GREEN}Installation complete.${NC}"
  echo "- API: http://YOUR_SERVER_IP:80 -> proxies to 127.0.0.1:8000"
  echo "- Manage services: systemctl [status|restart] vpn-bot-api vpn-bot-worker"
}

main() {
  require_root
  detect_os
  install_packages
  create_user
  ensure_repo_present
  setup_mysql
  setup_redis
  setup_env
  setup_venv
  run_db_migrations
  install_systemd
  setup_nginx
  start_services
  print_summary
}

main "$@"


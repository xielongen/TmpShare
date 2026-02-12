#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/secure-drop"
SERVICE_NAME="secure-drop"
SERVICE_USER="secure-drop"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"
ENV_FILE="/etc/default/secure-drop"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "[ERROR] ${PYTHON_BIN} not found. Please install Python 3.11+ first."
  exit 1
fi

if [ ! -f "app.py" ] || [ ! -f "requirements.txt" ]; then
  echo "[ERROR] Please run this script in the project root directory."
  exit 1
fi

echo "[1/8] Prepare service user and directories"
if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
  sudo useradd --system --create-home --home-dir "${APP_DIR}" --shell /sbin/nologin "${SERVICE_USER}"
fi
sudo mkdir -p "${APP_DIR}"
sudo mkdir -p "${APP_DIR}/data/files"

echo "[2/8] Sync project files"
sudo cp app.py requirements.txt pyproject.toml CLICKHOUSE_HOME.html TECH_DOC.md "${APP_DIR}/"
sudo rm -rf "${APP_DIR}/src"
sudo cp -r src "${APP_DIR}/"
sudo chown -R "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}"

echo "[3/8] Build virtual environment"
sudo -u "${SERVICE_USER}" "${PYTHON_BIN}" -m venv "${APP_DIR}/.venv"
sudo -u "${SERVICE_USER}" "${APP_DIR}/.venv/bin/pip" install --upgrade pip
sudo -u "${SERVICE_USER}" "${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

echo "[4/8] Install systemd service"
sudo cp deploy/secure-drop.service "/etc/systemd/system/${SERVICE_NAME}.service"
sudo systemctl daemon-reload

echo "[5/8] Install environment config if missing"
if [ ! -f "${ENV_FILE}" ]; then
  sudo cp deploy/secure-drop.env.example "${ENV_FILE}"
fi

echo "[6/8] Restart and enable service"
sudo systemctl enable --now "${SERVICE_NAME}"

echo "[7/8] Verify service status"
sudo systemctl --no-pager --full status "${SERVICE_NAME}" | sed -n '1,20p'

echo "[8/8] Runtime checks"
sudo -u "${SERVICE_USER}" test -w "${APP_DIR}/data/files"

echo ""
echo "Deployment finished."
echo "Service: ${SERVICE_NAME}"
echo "User: ${SERVICE_USER}"
echo "URL: http://<server-ip>:8080"

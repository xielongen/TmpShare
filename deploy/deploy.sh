#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/secure-drop"
SERVICE_NAME="secure-drop"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "[ERROR] ${PYTHON_BIN} not found. Please install Python 3.11+ first."
  exit 1
fi

if [ ! -f "app.py" ] || [ ! -f "requirements.txt" ]; then
  echo "[ERROR] Please run this script in the project root directory."
  exit 1
fi

echo "[1/6] Prepare target directory: ${APP_DIR}"
sudo mkdir -p "${APP_DIR}"

echo "[2/6] Sync project files"
sudo cp app.py requirements.txt CLICKHOUSE_HOME.html TECH_DOC.md "${APP_DIR}/"
sudo mkdir -p "${APP_DIR}/data/files"

echo "[3/6] Build virtual environment"
sudo "${PYTHON_BIN}" -m venv "${APP_DIR}/.venv"
sudo "${APP_DIR}/.venv/bin/pip" install --upgrade pip
sudo "${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

echo "[4/6] Install systemd service"
sudo cp deploy/secure-drop.service "/etc/systemd/system/${SERVICE_NAME}.service"
sudo systemctl daemon-reload

echo "[5/6] Enable and start service"
sudo systemctl enable --now "${SERVICE_NAME}"

echo "[6/6] Verify status"
sudo systemctl --no-pager --full status "${SERVICE_NAME}" | sed -n '1,20p'

echo ""
echo "Deployment finished."
echo "Service: ${SERVICE_NAME}"
echo "URL: http://<server-ip>:8080"

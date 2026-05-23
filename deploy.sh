#!/bin/bash
# Run this on the VPS to pull latest changes and restart the app.
# Usage: bash deploy.sh

set -e

APP_DIR="/var/www/wc2026"

echo "--- Pulling latest code ---"
cd "$APP_DIR"
git pull origin master

echo "--- Syncing dependencies ---"
uv sync --no-dev

echo "--- Running DB migrations ---"
FLASK_ENV=production uv run flask db upgrade

echo "--- Restarting service ---"
sudo systemctl restart wc2026

echo "--- Done. Status: ---"
sudo systemctl status wc2026 --no-pager

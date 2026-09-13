#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CRON_EXPR="${CRON_EXPR:-0 * * * *}"
LOG_FILE="$PROJECT_DIR/cron.log"

if [ ! -f "$PROJECT_DIR/.env" ]; then
  echo "ERROR: $PROJECT_DIR/.env 파일이 없습니다. .env.example을 복사해 먼저 설정하세요." >&2
  exit 1
fi

$PYTHON_BIN -m pip install -r "$PROJECT_DIR/requirements.txt"

CRON_CMD="cd $PROJECT_DIR && $PYTHON_BIN main.py >> $LOG_FILE 2>&1"
CRON_LINE="$CRON_EXPR $CRON_CMD"

TMP_CRON="$(mktemp)"
crontab -l 2>/dev/null | grep -v "cd $PROJECT_DIR && .* main.py" > "$TMP_CRON" || true
echo "$CRON_LINE" >> "$TMP_CRON"
crontab "$TMP_CRON"
rm -f "$TMP_CRON"

echo "등록 완료: $CRON_LINE"
echo "현재 crontab:"
crontab -l

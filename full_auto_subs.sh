#!/usr/bin/env bash
set -euo pipefail

MOVIES_PATH="${MOVIES_PATH:-/media}"
LOG_FILE="${SUBTITLE_AUTOMATION_LOG:-log_auto_subs.txt}"
CHECK_SCRIPT="${CHECK_SUBS_SCRIPT:-./check_subs_czech.sh}"

cd "$MOVIES_PATH"
echo "==== $(date) ====" >> "$LOG_FILE"
"$CHECK_SCRIPT" --miss --cze | head -n "${SUBTITLE_BATCH_SIZE:-8}" | ./auto_subs.sh -p "$MOVIES_PATH" >> "$LOG_FILE"
echo "==== auto_subs_finished ====" >> "$LOG_FILE"

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOVIES_PATH="${MOVIES_PATH:-${MEDIA_ROOT:-/media}}"
LOG_FILE="${SUBTITLE_AUTOMATION_LOG:-log_auto_subs.txt}"
CHECK_SCRIPT="${CHECK_SUBS_SCRIPT:-./check_subs_czech.sh}"
BATCH_SIZE="${SUBTITLE_BATCH_SIZE:-8}"

if [[ ! -x "$CHECK_SCRIPT" ]]; then
    echo "Error: missing executable checker script: $CHECK_SCRIPT" >&2
    echo "Set CHECK_SUBS_SCRIPT to a command that prints Jellyfin movie folder names." >&2
    exit 1
fi

cd "$MOVIES_PATH"
echo "==== $(date) ====" >> "$LOG_FILE"
"$CHECK_SCRIPT" --miss --cze | head -n "$BATCH_SIZE" | "$SCRIPT_DIR/auto_subs.sh" --language "${SUBTITLE_LANG:-cze}" >> "$LOG_FILE"
echo "==== auto_subs_finished ====" >> "$LOG_FILE"

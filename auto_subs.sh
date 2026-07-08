#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOVIES_PATH="${MOVIES_PATH:-${MEDIA_ROOT:-/media}}"

python3 "$SCRIPT_DIR/download_jellyfin_subtitles.py" \
    --stdin-names \
    --media-root "$MOVIES_PATH" \
    --mark-missing \
    "$@"

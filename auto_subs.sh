#!/usr/bin/env bash
set -euo pipefail

JF="${JELLYFIN_URL:-}"
KEY="${JELLYFIN_API_KEY:-}"
LANG="${SUBTITLE_LANG:-cze}"
MOVIES_PATH="${MOVIES_PATH:-/media}"
MAX_DOWNLOADS="${MAX_SUBTITLE_DOWNLOADS:-3}"

usage() {
    echo "Usage: $0 [-p PATH]"
    echo "  Reads Jellyfin movie folder names from stdin."
    echo "  Required env: JELLYFIN_URL, JELLYFIN_API_KEY"
    echo "  Optional env: SUBTITLE_LANG=cze, MOVIES_PATH=/media, MAX_SUBTITLE_DOWNLOADS=3"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -p=*)
            MOVIES_PATH="${1#*=}"
            shift
            ;;
        -p)
            MOVIES_PATH="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage
            exit 1
            ;;
    esac
done

if [[ -z "$JF" || -z "$KEY" ]]; then
    echo "Error: set JELLYFIN_URL and JELLYFIN_API_KEY before running." >&2
    exit 1
fi

if [[ ! -d "$MOVIES_PATH" ]]; then
    echo "Error: movies directory '$MOVIES_PATH' does not exist" >&2
    exit 1
fi

command -v curl >/dev/null || { echo "Error: curl is required" >&2; exit 1; }
command -v jq >/dev/null || { echo "Error: jq is required" >&2; exit 1; }

auth='X-Emby-Authorization: MediaBrowser Client="Subs", Device="shell", Version="1.0", Token="'"$KEY"'"'

declare -A folder_to_id
while IFS=$'	' read -r id path; do
    folder=$(basename "$(dirname "$path")")
    folder_to_id["$folder"]="$id"
done < <(
    curl -fsS -H "$auth" "$JF/Items?IncludeItemTypes=Movie&Fields=Path&Recursive=true" |
    jq -r '.Items[] | [.Id, .Path] | @tsv'
)

mapfile -t folders < <(cat)

for folder in "${folders[@]}"; do
    folder_clean=$(basename "${folder%/}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    [[ -z "$folder_clean" ]] && continue

    folder_path="$MOVIES_PATH/$folder_clean"
    if [[ ! -d "$folder_path" ]]; then
        echo "Folder not found: $folder_path"
        continue
    fi

    id="${folder_to_id[$folder_clean]:-}"
    if [[ -z "$id" ]]; then
        echo "No Jellyfin ID found for: $folder_clean"
        continue
    fi

    echo "Processing '$folder_clean' (ID: $id)"

    subtitle_response=$(curl -fsS -H "$auth" "$JF/Items/$id/RemoteSearch/Subtitles/$LANG" || echo '[]')
    subtitle_count=$(echo "$subtitle_response" | jq -r 'length')

    if [[ "$subtitle_count" == "0" || "$subtitle_count" == "null" ]]; then
        echo "  No subtitles available for '$folder_clean' - creating marker file"
        touch "$folder_path/no_subs.$LANG.srt"
        continue
    fi

    echo "  Found $subtitle_count subtitle(s) available"

    sub_ids=$(echo "$subtitle_response" | jq -r '.[].Id' | head -n "$MAX_DOWNLOADS")
    count=1
    download_success=false

    for sub_id in $sub_ids; do
        echo "  Attempting to download subtitle $count: $sub_id"
        download_response=$(curl -sS -w "
%{http_code}" -X POST -H "$auth" "$JF/Items/$id/RemoteSearch/Subtitles/$sub_id")
        http_code=$(echo "$download_response" | tail -n1)

        if [[ "$http_code" == "200" || "$http_code" == "204" ]]; then
            echo "    Subtitle $count downloaded successfully"
            download_success=true
        elif [[ "$http_code" == "429" ]]; then
            echo "    API rate limit reached - stopping script"
            exit 1
        else
            echo "    Download failed with HTTP code: $http_code"
        fi

        ((count++))
    done

    if [[ "$download_success" == false ]]; then
        echo "  All download attempts failed for '$folder_clean'"
    fi

    sleep 1
done

echo "Subtitle processing completed"

# Subtitle Download and Sync Automation

![Python](https://img.shields.io/badge/Python-3.10-blue) ![Jellyfin](https://img.shields.io/badge/Jellyfin-subtitle_API-00A4DC) ![Docker](https://img.shields.io/badge/Docker-supported-2496ED)

## Project Overview

Automation toolkit for subtitle workflows around a local media library. It can ask Jellyfin to download subtitles through its configured remote providers, such as OpenSubtitles, and then synchronize downloaded `.srt` files against the actual media audio with `ffsubsync`.

The repository is written for repeatable local automation: credentials and paths are passed through CLI flags or environment variables, media files are not committed, and the sync scripts preserve original subtitle files.

## Features

- Download subtitle candidates through Jellyfin's remote subtitle API
- Work with Jellyfin providers such as OpenSubtitles without calling provider APIs directly
- Select media by Jellyfin item ID, movie/episode name, file stem, folder name, stdin list, or full-library batch mode
- Optionally skip items that already have local subtitles
- Optionally create `no_subs.<lang>.srt` marker files when no remote subtitles exist
- Synchronize downloaded Czech or English `.srt` files against video audio
- Run as plain Python scripts or inside Docker

## Tech Stack

- Python standard library for Jellyfin HTTP API calls
- `ffsubsync` / `ffs` for subtitle alignment against media audio
- `ffmpeg` for media stream access
- Docker Compose for repeatable local execution

## Installation

### Virtual Environment

```bash
git clone <repo-url>
cd subtitle-sync-automation
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The host system must also provide `ffmpeg`.

### Docker

```bash
mkdir -p media
docker compose build
docker compose run --rm subtitle-sync
```

Docker mounts `./media` to `/media` and runs recursive subtitle synchronization by default.

## Jellyfin / OpenSubtitles Download

First configure Jellyfin with a remote subtitle provider, for example OpenSubtitles, in the Jellyfin admin interface. Then create a Jellyfin API key and pass it to the script.

Dry-run a subtitle search for one movie folder or item name:

```bash
export JELLYFIN_URL=http://your-jellyfin-host:8096
export JELLYFIN_API_KEY=your_jellyfin_api_key

python download_jellyfin_subtitles.py \
  --language cze \
  --name "Movie Folder Name" \
  --dry-run
```

Request downloads for folder names from stdin:

```bash
printf '%s\n' "Movie Folder Name" "Another Movie" | \
python download_jellyfin_subtitles.py \
  --stdin-names \
  --language cze \
  --media-root /path/to/movies \
  --skip-existing-local \
  --mark-missing
```

Process specific Jellyfin item IDs:

```bash
python download_jellyfin_subtitles.py \
  --item-id 0123456789abcdef \
  --language eng \
  --max-downloads 2
```

Process a bounded full-library batch:

```bash
python download_jellyfin_subtitles.py \
  --all \
  --limit-items 25 \
  --language cze \
  --sleep 1
```

`auto_subs.sh` is a small compatibility wrapper around `download_jellyfin_subtitles.py` that reads folder names from stdin:

```bash
printf '%s\n' "Movie Folder Name" | ./auto_subs.sh --language cze --skip-existing-local
```

## Subtitle Synchronization

Run a one-off subtitle synchronization from a folder containing one video and one subtitle file:

```bash
python sub.py movie.cze.srt --ref_file movie.mp4 --sub-lang cze --jobs 2 --effort 0.05
```

Run recursive synchronization across subfolders:

```bash
python sub_sync_recursive.py
```

Runtime configuration is passed through environment variables:

```bash
SUBSYNC_TEMP_DIR=/tmp/subsync_temp FFSUBSYNC_BINARY=ffs python sub_sync_recursive.py
```

## Typical Workflow

```bash
export JELLYFIN_URL=http://your-jellyfin-host:8096
export JELLYFIN_API_KEY=your_jellyfin_api_key
export SUBTITLE_LANG=cze

printf '%s\n' "Movie Folder Name" | ./auto_subs.sh --skip-existing-local
python sub_sync_recursive.py
```

## Notes

Jellyfin performs the actual provider lookup and subtitle installation. This project only automates Jellyfin API calls and local subtitle synchronization. The repository intentionally does not store subtitle files, videos, API keys, or private media paths.

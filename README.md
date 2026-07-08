# Subtitle Sync Automation

![Python](https://img.shields.io/badge/Python-3.10-blue) ![Docker](https://img.shields.io/badge/Docker-supported-2496ED)

## Project Overview

A small automation utility for synchronizing Czech or English `.srt` subtitles against local video files. It was built to batch-process folders of downloaded media while preserving already generated subtitle versions.

## Architecture / Tech Stack

- Python CLI scripts for single-file and recursive batch workflows
- `ffsubsync` / `ffs` for subtitle alignment against media audio
- `ffmpeg` for media stream access inside Docker
- Docker Compose for repeatable local execution

## Installation & Setup

### Docker

```bash
cd domaci-main
mkdir -p media
docker compose build
docker compose run --rm subtitle-sync
```

Place media folders under `media/`. Each folder should contain exactly one video file and one or more `.cze.srt` or `.eng.srt` subtitle files.

### Virtual Environment

```bash
cd domaci-main
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python sub_sync_recursive.py
```

The host system must also provide `ffmpeg`.

## Usage

### Jellyfin / OpenSubtitles Download

If Jellyfin is configured with an OpenSubtitles provider, `auto_subs.sh` can ask Jellyfin for remote subtitles and download the first matching Czech subtitles for movie folders passed on stdin.

```bash
export JELLYFIN_URL=http://your-jellyfin-host:8096
export JELLYFIN_API_KEY=your_jellyfin_api_key
export SUBTITLE_LANG=cze
printf '%s\n' "Movie Folder Name" | ./auto_subs.sh -p /path/to/movies
```

`full_auto_subs.sh` is a convenience wrapper for combining a local missing-subtitle checker with `auto_subs.sh`. It expects `check_subs_czech.sh` or `CHECK_SUBS_SCRIPT` to provide folder names.

Run a one-off subtitle synchronization from a folder containing one video and one subtitle file:

```bash
python sub.py movie.cze.srt --ref_file movie.mp4 --sub-lang cze --jobs 2 --effort 0.05
```

Run recursive synchronization across subfolders:

```bash
python sub_sync_recursive.py
```

Runtime configuration is passed through environment variables rather than hardcoded paths:

```bash
SUBSYNC_TEMP_DIR=/tmp/subsync_temp FFSUBSYNC_BINARY=ffs python sub_sync_recursive.py
```

## Results

The recursive workflow scans media subfolders, detects language-specific subtitle files, runs subtitle/audio alignment, and writes synchronized `.99.srt` outputs while preserving the original subtitles.

## Notes

The repository intentionally does not store subtitle files, videos, API keys, or private media paths. Docker mounts local media at runtime through `./media:/media`.

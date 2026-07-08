#!/usr/bin/env python3
"""Download remote subtitles through Jellyfin's subtitle provider API.

Jellyfin can be configured with providers such as OpenSubtitles. This script does
not call OpenSubtitles directly; it asks Jellyfin to search and install remote
subtitles for selected library items.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class JellyfinItem:
    item_id: str
    name: str
    path: str
    item_type: str

    @property
    def folder_name(self) -> str:
        if not self.path:
            return self.name
        path = Path(self.path)
        if path.suffix:
            return path.parent.name
        return path.name

    @property
    def file_stem(self) -> str:
        return Path(self.path).stem if self.path else self.name

    def match_keys(self) -> set[str]:
        return {
            self.item_id.lower(),
            self.name.lower(),
            self.folder_name.lower(),
            self.file_stem.lower(),
        }


def build_auth_header(api_key: str) -> dict[str, str]:
    token = api_key.strip()
    return {
        "X-Emby-Authorization": (
            'MediaBrowser Client="subtitle-sync-automation", '
            'Device="cli", Version="1.0", Token="' + token + '"'
        ),
        "Accept": "application/json",
    }


def api_url(base_url: str, path: str, params: dict[str, str] | None = None) -> str:
    url = base_url.rstrip("/") + path
    if params:
        return url + "?" + urllib.parse.urlencode(params)
    return url


def request_json(url: str, headers: dict[str, str], timeout: int) -> object:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else None


def post_status(url: str, headers: dict[str, str], timeout: int) -> int:
    request = urllib.request.Request(url, data=b"", headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)


def list_items(base_url: str, headers: dict[str, str], item_types: str, timeout: int) -> list[JellyfinItem]:
    payload = request_json(
        api_url(
            base_url,
            "/Items",
            {
                "IncludeItemTypes": item_types,
                "Fields": "Path",
                "Recursive": "true",
            },
        ),
        headers,
        timeout,
    )
    items = []
    for item in (payload or {}).get("Items", []):
        items.append(
            JellyfinItem(
                item_id=str(item.get("Id", "")),
                name=str(item.get("Name", "")),
                path=str(item.get("Path", "")),
                item_type=str(item.get("Type", "")),
            )
        )
    return [item for item in items if item.item_id]


def select_items(items: list[JellyfinItem], names: Iterable[str], item_ids: Iterable[str], include_all: bool) -> list[JellyfinItem]:
    if include_all:
        return items

    wanted_ids = {value.lower() for value in item_ids if value.strip()}
    wanted_names = {value.strip().lower() for value in names if value.strip()}
    selected = []

    for item in items:
        if item.item_id.lower() in wanted_ids or item.match_keys().intersection(wanted_names):
            selected.append(item)

    missing = wanted_ids.union(wanted_names) - set().union(*(item.match_keys() for item in selected)) if selected else wanted_ids.union(wanted_names)
    for value in sorted(missing):
        print(f"No Jellyfin item matched: {value}", file=sys.stderr)

    return selected


def read_stdin_names(enabled: bool) -> list[str]:
    if not enabled:
        return []
    return [line.strip() for line in sys.stdin if line.strip()]


def existing_local_subtitles(media_root: Path | None, item: JellyfinItem, language: str) -> list[Path]:
    if media_root is None:
        return []
    folder = media_root / item.folder_name
    if not folder.exists():
        return []
    return sorted(folder.glob(f"*.{language}*.srt"))


def create_missing_marker(media_root: Path | None, item: JellyfinItem, language: str) -> None:
    if media_root is None:
        return
    folder = media_root / item.folder_name
    if folder.exists():
        marker = folder / f"no_subs.{language}.srt"
        marker.touch(exist_ok=True)
        print(f"  Created marker: {marker}")


def process_item(
    base_url: str,
    headers: dict[str, str],
    item: JellyfinItem,
    language: str,
    max_downloads: int,
    timeout: int,
    dry_run: bool,
    media_root: Path | None,
    skip_existing_local: bool,
    mark_missing: bool,
) -> tuple[int, int]:
    print(f"Processing {item.item_type or 'Item'}: {item.name} [{item.item_id}]")

    existing = existing_local_subtitles(media_root, item, language)
    if skip_existing_local and existing:
        print(f"  Skipping: found existing local {language} subtitles")
        return (0, 0)

    search_url = api_url(base_url, f"/Items/{urllib.parse.quote(item.item_id)}/RemoteSearch/Subtitles/{language}")
    try:
        subtitles = request_json(search_url, headers, timeout) or []
    except urllib.error.HTTPError as exc:
        print(f"  Search failed with HTTP {exc.code}", file=sys.stderr)
        return (0, 1)
    except urllib.error.URLError as exc:
        print(f"  Search failed: {exc}", file=sys.stderr)
        return (0, 1)

    if not subtitles:
        print("  No remote subtitles found")
        if mark_missing:
            create_missing_marker(media_root, item, language)
        return (0, 0)

    print(f"  Found {len(subtitles)} remote subtitle candidate(s)")
    downloaded = 0
    failed = 0

    for index, subtitle in enumerate(subtitles[:max_downloads], start=1):
        subtitle_id = str(subtitle.get("Id", ""))
        provider = subtitle.get("ProviderName") or subtitle.get("Provider") or "provider unknown"
        display = subtitle.get("Name") or subtitle.get("DisplayTitle") or subtitle_id
        print(f"  Candidate {index}: {display} ({provider})")

        if dry_run:
            continue

        download_url = api_url(base_url, f"/Items/{urllib.parse.quote(item.item_id)}/RemoteSearch/Subtitles/{urllib.parse.quote(subtitle_id)}")
        status = post_status(download_url, headers, timeout)
        if status in {200, 204}:
            print("    Download requested successfully")
            downloaded += 1
        elif status == 429:
            print("    Jellyfin/provider rate limit reached", file=sys.stderr)
            failed += 1
            break
        else:
            print(f"    Download failed with HTTP {status}", file=sys.stderr)
            failed += 1

    return (downloaded, failed)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download subtitles through Jellyfin's configured remote subtitle providers.")
    parser.add_argument("--jellyfin-url", default=os.environ.get("JELLYFIN_URL"), help="Jellyfin base URL, e.g. http://localhost:8096")
    parser.add_argument("--api-key", default=os.environ.get("JELLYFIN_API_KEY"), help="Jellyfin API key")
    parser.add_argument("--language", default=os.environ.get("SUBTITLE_LANG", "cze"), help="Subtitle language code, e.g. cze, eng, ces")
    parser.add_argument("--item-types", default=os.environ.get("JELLYFIN_ITEM_TYPES", "Movie,Episode"), help="Comma-separated Jellyfin item types")
    parser.add_argument("--item-id", action="append", default=[], help="Jellyfin item ID to process; can be repeated")
    parser.add_argument("--name", action="append", default=[], help="Movie/episode name, file stem, or folder name to process; can be repeated")
    parser.add_argument("--stdin-names", action="store_true", help="Read names/folder names from stdin")
    parser.add_argument("--all", action="store_true", help="Process every matching Jellyfin library item")
    parser.add_argument("--limit-items", type=int, default=0, help="Maximum number of selected items to process; 0 means no limit")
    parser.add_argument("--max-downloads", type=int, default=int(os.environ.get("MAX_SUBTITLE_DOWNLOADS", "3")), help="Maximum subtitle candidates to request per item")
    parser.add_argument("--media-root", default=os.environ.get("MOVIES_PATH") or os.environ.get("MEDIA_ROOT"), help="Optional local media root for marker files and existing subtitle checks")
    parser.add_argument("--skip-existing-local", action="store_true", help="Skip items that already have local subtitles under --media-root")
    parser.add_argument("--mark-missing", action="store_true", help="Create no_subs.<lang>.srt markers under --media-root when no remote subtitles exist")
    parser.add_argument("--dry-run", action="store_true", help="Search and print candidates without requesting downloads")
    parser.add_argument("--sleep", type=float, default=float(os.environ.get("JELLYFIN_SUBTITLE_SLEEP", "1")), help="Delay between items")
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("JELLYFIN_TIMEOUT", "30")), help="HTTP timeout in seconds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.jellyfin_url or not args.api_key:
        print("Error: provide --jellyfin-url and --api-key, or set JELLYFIN_URL and JELLYFIN_API_KEY.", file=sys.stderr)
        return 2

    stdin_names = read_stdin_names(args.stdin_names)
    names = list(args.name) + stdin_names
    if not args.all and not args.item_id and not names:
        print("Error: select items with --name, --item-id, --stdin-names, or --all.", file=sys.stderr)
        return 2

    headers = build_auth_header(args.api_key)
    media_root = Path(args.media_root).expanduser() if args.media_root else None

    try:
        items = list_items(args.jellyfin_url, headers, args.item_types, args.timeout)
    except urllib.error.URLError as exc:
        print(f"Error: could not reach Jellyfin: {exc}", file=sys.stderr)
        return 1

    selected = select_items(items, names, args.item_id, args.all)
    if args.limit_items > 0:
        selected = selected[: args.limit_items]

    if not selected:
        print("No items selected.")
        return 1

    print(f"Selected {len(selected)} item(s); language={args.language}; dry_run={args.dry_run}")
    total_downloaded = 0
    total_failed = 0

    for item in selected:
        downloaded, failed = process_item(
            base_url=args.jellyfin_url,
            headers=headers,
            item=item,
            language=args.language,
            max_downloads=args.max_downloads,
            timeout=args.timeout,
            dry_run=args.dry_run,
            media_root=media_root,
            skip_existing_local=args.skip_existing_local,
            mark_missing=args.mark_missing,
        )
        total_downloaded += downloaded
        total_failed += failed
        if args.sleep > 0:
            time.sleep(args.sleep)

    print(f"Done. Download requests succeeded: {total_downloaded}; failed: {total_failed}")
    return 1 if total_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

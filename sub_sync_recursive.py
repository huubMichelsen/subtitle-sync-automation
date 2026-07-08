import os
import re
import subprocess
from pathlib import Path
from time import sleep

MEDIA_EXTENSIONS = (".mp4", ".avi", ".mov", ".mkv")
SYNC_BINARY = os.environ.get("FFSUBSYNC_BINARY", "ffs")
SLEEP_SECONDS = int(os.environ.get("SUBSYNC_SLEEP_SECONDS", "60"))


def planned_output_name(subtitle_name: str) -> str | None:
    match = re.match(r"^(.*\.(?:cze|eng))(?:\.(\d+))?\.srt$", subtitle_name)
    if not match:
        return None

    prefix, number = match.groups()
    if number is not None and int(number) >= 99:
        print(f"Skipping {number} in {subtitle_name}")
        return None

    new_index = 99 if number is None else int(number) + 100
    return f"{prefix}.{new_index}.srt"


def main() -> None:
    for folder in sorted(Path(".").iterdir()):
        print("\n\n")
        if not folder.is_dir():
            continue

        files = {item.name for item in folder.iterdir()}
        if "skip_sub_sync_bad_audio_codec.txt" in files:
            print(f"Skipping {folder.name}: skip_sub_sync_bad_audio_codec.txt found")
            continue

        media_files = [name for name in files if name.lower().endswith(MEDIA_EXTENSIONS)]
        if len(media_files) != 1:
            print(f"Skipping {folder.name}: expected one media file, found {len(media_files)}")
            continue

        candidates = []
        for filename in sorted(files):
            if not filename.endswith(".srt") or (".cze." not in filename and ".eng." not in filename):
                continue
            output_name = planned_output_name(filename)
            if not output_name:
                continue
            if output_name in files:
                print(f"Skipping {filename}: output {output_name} already exists in {folder.name}")
                continue
            candidates.append((filename, output_name))

        if not candidates:
            print(f"Warning: {folder.name} contains no usable .cze. or .eng. subtitles")
            continue

        media_path = folder / media_files[0]
        for subtitle_name, output_name in candidates:
            input_srt = folder / subtitle_name
            output_srt = folder / output_name
            print(f"->{folder.name}: {input_srt} -> {output_srt}")
            subprocess.run([SYNC_BINARY, str(media_path), "-i", str(input_srt), "-o", str(output_srt)], check=False)
            if SLEEP_SECONDS > 0:
                print(f"sleeping {SLEEP_SECONDS}s")
                sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()

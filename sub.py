import argparse
import glob
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def clean_temp_dir(temp_dir: Path) -> None:
    temp_dir.mkdir(parents=True, exist_ok=True)
    for file_path in temp_dir.iterdir():
        if file_path.is_file():
            file_path.unlink()


def first_match(pattern: str, description: str) -> str | None:
    matches = glob.glob(pattern)
    if not matches:
        print(f"No {description} found matching pattern: {pattern}")
        return None
    return matches[0]


def resolve_output_name(ref_file: str, ref_lang: str, sub_lang: str, output_file: str | None) -> str:
    if output_file:
        return output_file
    if ref_file.endswith(".srt"):
        base_name = ref_file.split(f".{ref_lang}.")[0]
        return f"{base_name}.{sub_lang}.srt"
    base_name = ".".join(ref_file.split(".")[:-1])
    return f"{base_name}.{sub_lang}.srt"


def move_without_overwrite(filename: str, source_dir: Path) -> None:
    target_path = source_dir / filename
    if target_path.exists():
        base, ext = os.path.splitext(filename)
        counter = 1
        while target_path.exists():
            target_path = source_dir / f"{base}{counter}{ext}"
            counter += 1
    shutil.move(filename, target_path)


def main() -> None:
    source_dir = Path.cwd()
    temp_dir = Path(
        os.environ.get(
            "SUBSYNC_TEMP_DIR",
            str(Path(tempfile.gettempdir()) / "subsync_temp"),
        )
    )
    clean_temp_dir(temp_dir)

    parser = argparse.ArgumentParser(description="Synchronize subtitles against a reference video or subtitle file.")
    parser.add_argument("input_file", nargs="?", help="Path to subtitle file (default: *.cze.srt)")
    parser.add_argument("-r", "--ref_file", help="Path to reference media file (default: first *.mp4)")
    parser.add_argument("-rl", "--ref-lang", default="eng", help="Reference language (default: eng)")
    parser.add_argument("-sl", "--sub-lang", default="cze", help="Subtitle language (default: cze)")
    parser.add_argument("-j", "--jobs", type=int, default=2, help="Number of worker jobs (default: 2)")
    parser.add_argument("-e", "--effort", type=float, default=0.05, help="Synchronization effort (default: 0.05)")
    parser.add_argument("-o", "--output", help="Output subtitle path")
    parser.add_argument(
        "--sync-binary",
        default=os.environ.get("SUBSYNC_BINARY", "subsync"),
        help="Subtitle sync executable (default: SUBSYNC_BINARY or subsync)",
    )
    args = parser.parse_args()

    input_file = args.input_file or first_match("*.cze.srt", "input subtitle files")
    if not input_file:
        return

    ref_file = args.ref_file or first_match("*.mp4", "reference media files")
    if not ref_file:
        return

    output_file = resolve_output_name(input_file, args.ref_lang, args.sub_lang, args.output)

    shutil.copy(input_file, temp_dir)
    shutil.copy(ref_file, temp_dir)
    for srt_file in glob.glob("*.srt"):
        shutil.copy(srt_file, temp_dir)

    os.chdir(temp_dir)
    command = [
        args.sync_binary,
        "-c",
        "sync",
        "-s",
        Path(input_file).name,
        "-r",
        Path(ref_file).name,
        "--ref-lang",
        args.ref_lang,
        "--sub-lang",
        args.sub_lang,
        "--out",
        Path(output_file).name,
        "--jobs",
        str(args.jobs),
        "--effort",
        str(args.effort),
        "--verbose",
        "2",
    ]

    try:
        subprocess.run(command, check=True)
        latest_file = max(glob.glob("*.srt"), key=os.path.getctime)
        move_without_overwrite(latest_file, source_dir)
    except FileNotFoundError as exc:
        print(f"Sync executable not found: {exc.filename}")
    except subprocess.CalledProcessError as exc:
        print(f"Error occurred during synchronization: {exc}")
    finally:
        clean_temp_dir(temp_dir)


if __name__ == "__main__":
    main()

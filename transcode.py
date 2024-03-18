import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Constants for cubic function coefficients
A = 0.000114092
B = -0.0181481
C = 0.98977
D = -0.010483


def is_ffmpeg_installed() -> bool:
    """Check if ffmpeg is installed."""
    return shutil.which("ffmpeg") is not None


def map_font_size(size: int) -> int:
    """Map the font size using cubic function."""
    return int(A * size**3 + B * size**2 + C * size + D)


def process_subtitles(subtitle_file: Path, forced_size) -> None:
    """Process subtitle file to map font sizes."""
    with subtitle_file.open("r", encoding="utf8") as file:
        lines = file.readlines()

    with subtitle_file.open("w", encoding="utf8") as file:
        for line in lines:
            if "face" in line:
                size = int(line.split('size="')[1].split('"')[0])
                if forced_size is not None:
                    new_size = forced_size
                else:
                    new_size = map_font_size(size)

                line = line.replace(f'size="{size}"', f'size="{new_size}"')
            file.write(line)


def dump_subtitle_tracks(input_file: Path) -> None:
    """Dump subtitle tracks using ffprobe."""
    subprocess.run(
        [
            "ffprobe",
            "-loglevel",
            "error",
            "-select_streams",
            "s",
            "-show_entries",
            "stream=index:stream_tags=language",
            "-of",
            "default=noprint_wrappers=1",
            str(input_file),
        ]
    )
    sys.exit(0)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input_file", required=True, help="Input video file")
    parser.add_argument(
        "-g", "--use_gpu", action="store_true", help="Use GPU for transcoding"
    )
    parser.add_argument(
        "-t", "--subtitle_track", type=int, help="Subtitle track number"
    )
    parser.add_argument("-s", "--subtitle_file", help="Subtitle file")
    parser.add_argument(
        "-a", "--audio_track", type=int, help="Audio track number to transcode"
    )
    parser.add_argument(
        "-d",
        "--dump_subtitles",
        action="store_true",
        help="Dump subtitle tracks and exit",
    )
    parser.add_argument(
        "-f",
        "--font_size",
        type=int,
        help="Force a font size rather than using quick maffs",
        default=None,
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    if not is_ffmpeg_installed():
        print("Error: ffmpeg is required but not installed. Aborting.")
        sys.exit(1)

    input_file = Path(args.input_file)

    if not input_file.is_file():
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)

    if args.dump_subtitles:
        dump_subtitle_tracks(input_file)

    if args.subtitle_track is not None and args.subtitle_file is not None:
        print("Error: Use either -t or -s, not both.")
        sys.exit(1)

    try:
        if args.subtitle_track is not None:
            temp_subtitle_file = Path(tempfile.mktemp(suffix=".srt"))
            subprocess.run(
                [
                    "ffmpeg",
                    "-i",
                    str(input_file),
                    "-map",
                    f"0:s:{args.subtitle_track}",
                    str(temp_subtitle_file),
                ]
            )
        elif args.subtitle_file is not None:
            temp_subtitle_file = Path(args.subtitle_file)
        else:
            print("Error: Either -t or -s must be specified.")
            sys.exit(1)

        if not temp_subtitle_file.is_file():
            print(
                f"Error: Subtitle file '{temp_subtitle_file}' not created successfully."
            )
            sys.exit(1)

        print("Processing subtitle font sizes...")
        process_subtitles(temp_subtitle_file, args.font_size)

        output_file = input_file.with_name(f"{input_file.stem}_processed.mp4")

        forward_slash_temp_path = (
            str(temp_subtitle_file).replace("\\", "/").replace(":", "\\\\:")
        )

        ffmpeg_cmd = ["ffmpeg", "-i", str(input_file)]

        if args.audio_track is not None:
            ffmpeg_cmd.extend(["-map", f"0:a:{args.audio_track}"])

        ffmpeg_cmd.extend(
            [
                "-map",
                "0:0",
                "-movflags",
                "+faststart",
                "-pix_fmt",
                "yuv420p",
                "-crf",
                "23",
                "-vf",
                f"subtitles={forward_slash_temp_path}",
                "-c:a",
                "ac3",
                str(output_file),
            ]
        )

        if args.use_gpu:
            ffmpeg_cmd.extend(["-c:v", "h264_nvenc", "-preset", "p7", "-tune", "hq"])
        else:
            ffmpeg_cmd.extend(
                ["-c:v", "libx264", "-preset", "veryslow", "-tune", "animation"]
            )

        process = None
        try:
            process = subprocess.Popen(ffmpeg_cmd)
            process.wait()
            print("Processing completed successfully.")
        except KeyboardInterrupt:
            print("Aborting...")
            process.kill()

    finally:
        if args.subtitle_track is not None and temp_subtitle_file.is_file():
            temp_subtitle_file.unlink()


if __name__ == "__main__":
    main()

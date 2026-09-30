"""Combines the Playwright screen recording, the concatenated narration
track, and the caption overlays into the final marked_demo.mp4.

    python3 mux_final.py <screen_recording.mp4> <out.mp4>

Expects audio/*.wav + audio/durations.json (generate_kokoro.py) and
captions/*.png + captions/meta.json (build_captions.py) to already exist.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(__file__)


def main():
    screen_path, out_path = sys.argv[1], sys.argv[2]

    sys.path.insert(0, HERE)
    from demo_script import SCRIPT

    audio_dir = os.path.join(HERE, "audio")
    concat_list = os.path.join(audio_dir, "concat_list.txt")
    with open(concat_list, "w") as f:
        for name, _ in SCRIPT:
            f.write(f"file '{name}.wav'\n")

    narration_path = os.path.join(audio_dir, "narration_full.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", concat_list, "-c", "pcm_s16le", narration_path],
        check=True, cwd=audio_dir,
    )
    narration_dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", narration_path],
        capture_output=True, text=True, check=True,
    ).stdout.strip())

    # pad the screen recording's tail by 1s so narration is never cut off
    padded_path = os.path.join(HERE, "_screen_padded.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", screen_path,
         "-vf", "tpad=stop_mode=clone:stop_duration=1.0",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", padded_path],
        check=True,
    )

    with open(os.path.join(HERE, "captions", "meta.json")) as f:
        meta = json.load(f)

    inputs = ["-i", padded_path, "-i", narration_path]
    filter_parts = []
    prev = "0:v"
    for idx, c in enumerate(meta):
        inputs += ["-i", os.path.join(HERE, "captions", f"cap_{c['i']:02d}.png")]
        in_idx = idx + 2
        out_label = f"v{idx}"
        filter_parts.append(
            f"[{prev}][{in_idx}:v]overlay=0:0:enable='between(t,{c['start']:.3f},{c['end']:.3f})'[{out_label}]"
        )
        prev = out_label
    filter_complex = ";".join(filter_parts)

    cmd = (
        ["ffmpeg", "-y", "-loglevel", "error"] + inputs +
        ["-filter_complex", filter_complex, "-map", f"[{prev}]", "-map", "1:a",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
         "-c:a", "aac", "-b:a", "192k", "-shortest", out_path]
    )
    subprocess.run(cmd, check=True)
    os.remove(padded_path)
    print(f"wrote {out_path} (narration {narration_dur:.1f}s)")


if __name__ == "__main__":
    main()

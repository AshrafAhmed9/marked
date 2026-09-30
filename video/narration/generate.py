"""Regenerate the narration .aiff clips from narration.py using macOS's
built-in `say` (Samantha voice). Run from this directory:

    python3 generate.py

Then rerun ../build_video.sh, which pads each clip to its slide's
duration and muxes the full track onto the video.
"""
import json
import subprocess

from narration import SCRIPT

durations = {}
for idx, text in SCRIPT:
    aiff = f"{idx}.aiff"
    subprocess.run(["say", "-v", "Samantha", "-r", "168", "-o", aiff, text], check=True)
    out = subprocess.run(["afinfo", aiff], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if "estimated duration" in line:
            durations[idx] = float(line.split(":")[1].strip().split()[0])
    print(idx, round(durations[idx], 2), text[:50])

with open("durations.json", "w") as f:
    json.dump(durations, f, indent=2)

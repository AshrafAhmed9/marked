"""Synthesizes the narration in demo_script.py with Kokoro (open-weight,
local, no API key, no cost) instead of a robotic system voice.

First run downloads the model (~325MB) and voice pack (~28MB) from the
kokoro-onnx GitHub releases into MODEL_DIR if not already present.

    pip install kokoro-onnx soundfile
    python3 generate_kokoro.py

Writes one .wav per script entry plus durations.json into OUT_DIR.
"""
import json
import os
import sys
import urllib.request

MODEL_DIR = os.path.expanduser("~/.cache/marked-demo/kokoro")
OUT_DIR = os.path.join(os.path.dirname(__file__), "audio")
VOICE = "af_heart"
SPEED = 0.98

MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"


def ensure_model():
    os.makedirs(MODEL_DIR, exist_ok=True)
    model_path = os.path.join(MODEL_DIR, "kokoro-v1.0.onnx")
    voices_path = os.path.join(MODEL_DIR, "voices-v1.0.bin")
    for url, path in [(MODEL_URL, model_path), (VOICES_URL, voices_path)]:
        if not os.path.exists(path):
            print(f"downloading {url} -> {path}")
            urllib.request.urlretrieve(url, path)
    return model_path, voices_path


def main():
    sys.path.insert(0, os.path.dirname(__file__))
    from demo_script import SCRIPT

    from kokoro_onnx import Kokoro
    import soundfile as sf

    model_path, voices_path = ensure_model()
    kokoro = Kokoro(model_path, voices_path)

    os.makedirs(OUT_DIR, exist_ok=True)
    durations = {}
    for name, text in SCRIPT:
        samples, sr = kokoro.create(text, voice=VOICE, speed=SPEED, lang="en-us")
        dur = len(samples) / sr
        sf.write(os.path.join(OUT_DIR, f"{name}.wav"), samples, sr)
        durations[name] = dur
        print(f"{name}: {dur:.2f}s")

    with open(os.path.join(OUT_DIR, "durations.json"), "w") as f:
        json.dump(durations, f, indent=2)
    print("TOTAL:", sum(durations.values()))


if __name__ == "__main__":
    main()

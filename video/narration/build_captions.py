"""Renders burned-in caption bars as transparent PNG overlays, split at
sentence boundaries and timed proportionally within each narration
segment's real (measured) duration. Used because this ffmpeg build has no
libass/drawtext -- captions are composited with the `overlay` filter
instead (see mux_final.py).

    python3 build_captions.py

Reads audio/durations.json (from generate_kokoro.py), writes PNGs and
meta.json into captions/.
"""
import json
import os
import re
import sys
import textwrap

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(__file__)
OUT_DIR = os.path.join(HERE, "captions")
W, H = 1920, 1080
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
PROTECT = "U․S․"  # placeholder so "U.S." doesn't split as a sentence


def split_sentences(text):
    text = text.replace("U.S.", PROTECT)
    parts = re.split(r"(?<=[.?!])\s+", text.strip())
    return [p.replace(PROTECT, "U.S.") for p in parts if p]


def build_caption_timeline(script, durations):
    captions = []
    t = 0.0
    for name, text in script:
        seg_dur = durations[name]
        sentences = split_sentences(text)
        weights = [len(s) for s in sentences]
        total_w = sum(weights)
        cursor = t
        for s, w in zip(sentences, weights):
            dur = seg_dur * (w / total_w)
            captions.append((s, cursor, cursor + dur))
            cursor += dur
        t += seg_dur
    return captions


def render_caption(i, text, font):
    wrapped = textwrap.fill(text, width=56)
    lines = wrapped.split("\n")
    line_h = 56
    pad_x, pad_y = 40, 26
    text_w = max(font.getlength(l) for l in lines)
    box_w = int(text_w + pad_x * 2)
    box_h = int(len(lines) * line_h + pad_y * 2)
    box_x = 60
    box_y = H - box_h - 70

    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle([box_x, box_y, box_x + box_w, box_y + box_h], radius=10, fill=(11, 14, 20, 232))
    draw.rectangle([box_x, box_y, box_x + 4, box_y + box_h], fill=(255, 92, 92, 255))
    y = box_y + pad_y
    for line in lines:
        draw.text((box_x + pad_x, y), line, font=font, fill=(237, 240, 247, 255))
        y += line_h
    im.save(os.path.join(OUT_DIR, f"cap_{i:02d}.png"))


def main():
    sys.path.insert(0, HERE)
    from demo_script import SCRIPT

    with open(os.path.join(HERE, "audio", "durations.json")) as f:
        durations = json.load(f)

    os.makedirs(OUT_DIR, exist_ok=True)
    font = ImageFont.truetype(FONT_PATH, 44)
    captions = build_caption_timeline(SCRIPT, durations)

    meta = []
    for i, (text, start, end) in enumerate(captions):
        render_caption(i, text, font)
        meta.append({"i": i, "start": start, "end": end})

    with open(os.path.join(OUT_DIR, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"rendered {len(captions)} captions, span {captions[-1][2]:.2f}s")


if __name__ == "__main__":
    main()

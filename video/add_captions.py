"""Composite a caption bar onto data-screenshot slides (title cards already
carry their own text). Matches the site's dark theme."""
from PIL import Image, ImageDraw, ImageFont
import textwrap

FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"
W, H = 1920, 1080
BAR_H = 160
BG = (11, 14, 20, 235)

def caption(path, text, accent="#ff5c5c"):
    im = Image.open(path).convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle([0, H - BAR_H, W, H], fill=BG)
    # accent top border on the bar
    ar, ag, ab = tuple(int(accent[i:i+2], 16) for i in (1, 3, 5))
    draw.rectangle([0, H - BAR_H, W, H - BAR_H + 4], fill=(ar, ag, ab, 255))
    font = ImageFont.truetype(FONT_BOLD, 40)
    wrapped = textwrap.fill(text, width=95)
    lines = wrapped.split("\n")
    line_h = 50
    total_h = len(lines) * line_h
    y = H - BAR_H + (BAR_H - total_h) // 2
    for line in lines:
        draw.text((60, y), line, font=font, fill=(232, 236, 245, 255))
        y += line_h
    out = Image.alpha_composite(im, overlay).convert("RGB")
    out.save(path)
    print(f"captioned {path}")

if __name__ == "__main__":
    import sys, json
    spec = json.loads(sys.argv[1])
    caption(**spec)

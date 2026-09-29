"""Generate a title-card PNG (dark bg, big centered text) matching the site's
visual language, via headless Chrome rendering a tiny standalone HTML file.
Used for the video's narration-free text beats."""
import os
import subprocess
import sys
import json

TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"/>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    width: 1920px; height: 1080px;
    background: #0b0e14;
    display: flex; align-items: center; justify-content: center;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif;
  }}
  .wrap {{ max-width: 1500px; padding: 0 80px; text-align: {align}; }}
  .kicker {{ color: {accent}; font-size: 32px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 28px; }}
  .main {{ color: #e8ecf5; font-size: {size}px; font-weight: 700; line-height: 1.25; letter-spacing: -0.01em; }}
  .sub {{ color: #9aa4bf; font-size: 34px; margin-top: 32px; line-height: 1.5; }}
  .accent {{ color: {accent}; }}
</style></head>
<body>
  <div class="wrap">
    {kicker_html}
    <div class="main">{main}</div>
    {sub_html}
  </div>
</body></html>
"""

def render(out_path, main, kicker="", sub="", accent="#ff5c5c", size=76, align="left"):
    kicker_html = f'<div class="kicker">{kicker}</div>' if kicker else ""
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    html = TEMPLATE.format(main=main, kicker_html=kicker_html, sub_html=sub_html, accent=accent, size=size, align=align)
    tmp = out_path.replace(".png", ".html")
    with open(tmp, "w") as f:
        f.write(html)
    subprocess.run([
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "--headless=new", "--disable-gpu",
        f"--screenshot={out_path}",
        "--window-size=1920,1080",
        "--virtual-time-budget=1500",
        f"file://{os.path.abspath(tmp)}"
    ], check=True, capture_output=True)

if __name__ == "__main__":
    spec = json.loads(sys.argv[1])
    render(**spec)

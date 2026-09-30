"""Records a real, driven walkthrough of the live Marked site: real typing,
real clicking, real slider dragging, real scrolling -- captured frame by
frame via Playwright's built-in video recorder (not a slideshow of static
screenshots). Pacing per beat comes from durations.json (the narration
clip lengths), so playback roughly tracks the voiceover. A few moments use
injected CSS pulse/zoom highlights on the real DOM to draw the eye to a
specific number without ever faking what's on screen.

Usage: python3 demo_record.py <base_url> <durations_json> <out_dir>
"""
import json
import sys
import time

from playwright.sync_api import sync_playwright

INIT_JS = """
(() => {
  const dot = document.createElement('div');
  dot.id = '__demo_cursor';
  dot.style.cssText = 'position:fixed;width:22px;height:22px;border-radius:50%;' +
    'background:rgba(255,92,92,0.5);border:2px solid rgba(255,255,255,0.95);' +
    'pointer-events:none;z-index:2147483647;transform:translate(-50%,-50%);' +
    'transition:width .12s ease,height .12s ease;left:-100px;top:-100px;' +
    'box-shadow:0 0 14px rgba(255,92,92,0.65);';
  const attach = () => document.body && document.body.appendChild(dot);
  if (document.body) attach(); else document.addEventListener('DOMContentLoaded', attach);
  window.addEventListener('mousemove', (e) => { dot.style.left = e.clientX + 'px'; dot.style.top = e.clientY + 'px'; });
  window.addEventListener('mousedown', () => { dot.style.width = '34px'; dot.style.height = '34px'; });
  window.addEventListener('mouseup', () => { dot.style.width = '22px'; dot.style.height = '22px'; });

  const style = document.createElement('style');
  style.textContent = `
    @keyframes __demo_pulse {
      0%   { box-shadow: 0 0 0 0 rgba(255,92,92,0.55); transform: scale(1); }
      40%  { box-shadow: 0 0 0 14px rgba(255,92,92,0); transform: scale(1.035); }
      100% { box-shadow: 0 0 0 0 rgba(255,92,92,0); transform: scale(1); }
    }
    .__demo_pulse { animation: __demo_pulse 1.1s ease-out 2; position: relative; z-index: 5; border-radius: 10px; }
    @keyframes __demo_zoom {
      0% { transform: scale(1); }
      100% { transform: scale(1.055); }
    }
    .__demo_zoomed { animation: __demo_zoom 1.6s ease-out forwards; transform-origin: center top; }
  `;
  document.head.appendChild(style);
})();
"""


def smooth_scroll(page, total_dy, steps=14, step_wait=45):
    per = total_dy / steps
    for _ in range(steps):
        page.mouse.wheel(0, per)
        page.wait_for_timeout(step_wait)


def hold(page, ms):
    if ms > 0:
        page.wait_for_timeout(int(ms))


def pulse(page, selector, hold_ms=1300):
    page.evaluate(
        """(sel) => { const el = document.querySelector(sel); if (el) el.classList.add('__demo_pulse'); }""",
        selector,
    )
    page.wait_for_timeout(hold_ms)
    page.evaluate(
        """(sel) => { const el = document.querySelector(sel); if (el) el.classList.remove('__demo_pulse'); }""",
        selector,
    )


def zoom(page, selector, on=True):
    prop = "add" if on else "remove"
    page.evaluate(
        f"""(sel) => {{ const el = document.querySelector(sel); if (el) el.classList.{prop}('__demo_zoomed'); }}""",
        selector,
    )


def pulse_text_paragraph(page, needle, hold_ms=1600):
    """Highlights whichever <p> contains `needle` without assuming DOM order."""
    page.evaluate(
        """(needle) => {
            const ps = Array.from(document.querySelectorAll('.limits p'));
            const el = ps.find(p => p.textContent.includes(needle));
            if (el) el.classList.add('__demo_pulse');
        }""",
        needle,
    )
    page.wait_for_timeout(hold_ms)
    page.evaluate(
        """(needle) => {
            const ps = Array.from(document.querySelectorAll('.limits p'));
            const el = ps.find(p => p.textContent.includes(needle));
            if (el) el.classList.remove('__demo_pulse');
        }""",
        needle,
    )


def drag_slider(page, selector, target_frac, steps=26):
    box = page.locator(selector).bounding_box()
    y = box["y"] + box["height"] / 2
    start_x = box["x"] + 6
    end_x = box["x"] + box["width"] * target_frac
    page.mouse.move(start_x, y)
    page.mouse.down()
    for i in range(1, steps + 1):
        x = start_x + (end_x - start_x) * (i / steps)
        page.mouse.move(x, y)
        page.wait_for_timeout(45)
    page.mouse.up()


def main():
    base_url, durations_path, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(durations_path) as f:
        dur = {k: v * 1000 for k, v in json.load(f).items()}  # -> ms

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=out_dir,
            record_video_size={"width": 1920, "height": 1080},
            device_scale_factor=1,
        )
        context.add_init_script(INIT_JS)
        page = context.new_page()

        # 01_hook -- hold on the hero, push in on the headline comparison
        t0 = time.time()
        page.goto(base_url, wait_until="load")
        page.wait_for_timeout(1400)
        zoom(page, ".hero-compare", on=True)
        page.wait_for_timeout(1800)
        zoom(page, ".hero-compare", on=False)
        page.wait_for_timeout(600)
        elapsed = (time.time() - t0) * 1000
        hold(page, dur["01_hook"] - elapsed)

        # 02_search -- type into the search box, click the SVB result, pulse the rank
        t0 = time.time()
        smooth_scroll(page, 260, steps=10, step_wait=55)
        search = page.locator("#bank-search")
        search.click()
        search.type("Silicon Valley Bank", delay=65)
        page.wait_for_timeout(500)
        page.locator("#search-results button[data-cert='24735']").first.click()
        page.wait_for_timeout(500)
        page.locator("#bank-detail").scroll_into_view_if_needed()
        page.wait_for_timeout(600)
        smooth_scroll(page, 90, steps=5, step_wait=50)
        pulse(page, "#bank-detail .stat-grid .stat:nth-child(1)", hold_ms=1400)
        elapsed = (time.time() - t0) * 1000
        hold(page, dur["02_search"] - elapsed)

        # 03_charts -- scroll through both charts, let the draw-in animation run
        t0 = time.time()
        smooth_scroll(page, 520, steps=16, step_wait=55)
        page.wait_for_timeout(900)
        smooth_scroll(page, 480, steps=14, step_wait=55)
        elapsed = (time.time() - t0) * 1000
        hold(page, dur["03_charts"] - elapsed)

        # 04_slider -- reveal the run-threshold slider, drag it to 90%
        t0 = time.time()
        page.locator("#run-slider").scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        drag_slider(page, "#run-slider", 0.90, steps=26)
        page.wait_for_timeout(500)
        pulse(page, "#run-slider-readout", hold_ms=1200)
        elapsed = (time.time() - t0) * 1000
        hold(page, dur["04_slider"] - elapsed)

        # 05_backtest -- switch tabs, scroll the failure table
        t0 = time.time()
        page.locator("#tab-backtest").click()
        page.wait_for_timeout(500)
        page.locator("#backtest-table").scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        smooth_scroll(page, 520, steps=16, step_wait=55)
        elapsed = (time.time() - t0) * 1000
        hold(page, dur["05_backtest"] - elapsed)

        # 06_depositflight -- scroll to the deposit-flight panel
        t0 = time.time()
        page.locator("#deposit-flight-panel").scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        elapsed = (time.time() - t0) * 1000
        hold(page, dur["06_depositflight"] - elapsed)

        # 07_2008 -- scroll to the D2 (2008 era) panel
        t0 = time.time()
        page.locator("#d2-panel").scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        elapsed = (time.time() - t0) * 1000
        hold(page, dur["07_2008"] - elapsed)

        # 08_luck -- scroll to the permutation-test panel
        t0 = time.time()
        page.locator("#permutation-panel").scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        elapsed = (time.time() - t0) * 1000
        hold(page, dur["08_luck"] - elapsed)

        # 09_rigor -- About tab: highlight the "frozen before any backtest" line,
        # then scroll through the honest-limits list as proof of disclosure
        t0 = time.time()
        page.locator("#tab-about").click()
        page.wait_for_timeout(500)
        page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
        page.wait_for_timeout(300)
        pulse_text_paragraph(page, "frozen before any historical backtest", hold_ms=2200)
        smooth_scroll(page, 420, steps=14, step_wait=55)
        page.wait_for_timeout(400)
        smooth_scroll(page, 380, steps=12, step_wait=55)
        elapsed = (time.time() - t0) * 1000
        hold(page, dur["09_rigor"] - elapsed)

        # 10_today -- switch to the Today tab
        t0 = time.time()
        page.locator("#tab-today").click()
        page.wait_for_timeout(500)
        page.locator("#today-panel").scroll_into_view_if_needed()
        elapsed = (time.time() - t0) * 1000
        hold(page, dur["10_today"] - elapsed)

        # 11_close -- back to the top, final push-in on the hero stat
        t0 = time.time()
        page.locator("#tab-bank").click()
        page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
        page.wait_for_timeout(500)
        zoom(page, ".hero-compare", on=True)
        elapsed = (time.time() - t0) * 1000
        hold(page, dur["11_close"] - elapsed)

        page.close()
        context.close()
        browser.close()
        print("video saved under", out_dir)


if __name__ == "__main__":
    main()

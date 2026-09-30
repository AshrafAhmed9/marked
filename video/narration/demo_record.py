"""Records a real, driven walkthrough of the live Marked site: real typing,
real clicking, real slider dragging, real scrolling -- captured frame by
frame via Playwright's built-in video recorder (not a slideshow of static
screenshots). Pacing per beat comes from durations.json (the narration
clip lengths), so playback roughly tracks the voiceover.

Usage: python3 demo_record.py <base_url> <durations_json> <out_dir>
"""
import json
import sys
import time

from playwright.sync_api import sync_playwright

CURSOR_JS = """
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
})();
"""


def smooth_scroll(page, total_dy, steps=14, step_wait=45):
    per = total_dy / steps
    for _ in range(steps):
        page.mouse.wheel(0, per)
        page.wait_for_timeout(step_wait)


def hold(page, ms):
    if ms > 0:
        page.wait_for_timeout(ms)


def drag_slider(page, selector, target_frac, steps=24):
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
        context.add_init_script(CURSOR_JS)
        page = context.new_page()

        t_start = time.time()

        # 01_hook -- load, let the hero count-up animation play, ease down
        page.goto(base_url, wait_until="load")
        page.wait_for_timeout(1200)
        smooth_scroll(page, 260, steps=10, step_wait=60)
        elapsed = (time.time() - t_start) * 1000
        hold(page, dur["01_hook"] - elapsed)

        # 02_search -- type into the search box, click the SVB result
        t0 = time.time()
        search = page.locator("#bank-search")
        search.click()
        search.type("Silicon Valley Bank", delay=65)
        page.wait_for_timeout(500)
        page.locator("#search-results button[data-cert='24735']").first.click()
        page.wait_for_timeout(500)
        page.locator("#bank-detail").scroll_into_view_if_needed()
        page.wait_for_timeout(600)
        smooth_scroll(page, 120, steps=6, step_wait=50)
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
        page.wait_for_timeout(700)
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

        # 09_today -- switch to the Today tab
        t0 = time.time()
        page.locator("#tab-today").click()
        page.wait_for_timeout(500)
        page.locator("#today-panel").scroll_into_view_if_needed()
        elapsed = (time.time() - t0) * 1000
        hold(page, dur["09_today"] - elapsed)

        # 10_close -- back to the top, hold on the hero/branding
        t0 = time.time()
        page.locator("#tab-bank").click()
        page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
        page.wait_for_timeout(500)
        elapsed = (time.time() - t0) * 1000
        hold(page, dur["10_close"] - elapsed)

        page.close()
        context.close()
        browser.close()
        print("video saved under", out_dir)


if __name__ == "__main__":
    main()

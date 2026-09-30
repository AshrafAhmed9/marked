# video/

`marked_demo.mp4` (2:06) is a real screen recording of the live product,
not a slide deck: a Playwright-driven browser actually types into the
search box, clicks the result, drags the run-risk slider, switches tabs,
and scrolls through the backtest -- captured frame by frame as it happens.
Narration is a local neural TTS voice (Kokoro, open-weight, not the
robotic system voice), timed per-beat to match the real length of its
own audio clip. Captions are burned in on top, synced to the narration at
the sentence level.

## Pipeline

1. **`narration/demo_script.py`** -- the spoken script, one entry per demo
   beat (e.g. "drag the slider", "switch to the backtest tab").
2. **`narration/generate_kokoro.py`** -- synthesizes each beat with Kokoro
   (downloads the ~350MB model to `~/.cache/marked-demo/kokoro` on first
   run) and writes `narration/audio/*.wav` + `durations.json`.
   ```
   pip install kokoro-onnx soundfile
   python3 narration/generate_kokoro.py
   ```
3. **`narration/demo_record.py`** -- launches headless Chromium via
   Playwright against the site, performs the real interaction (typing,
   clicking, dragging, scrolling) paced to each beat's measured duration,
   and records the actual rendered output to a `.webm`.
   ```
   pip install playwright && python3 -m playwright install chromium
   cd site && python3 -m http.server 8793 &   # serve the real site locally
   python3 narration/demo_record.py http://localhost:8793/index.html \
     narration/audio/durations.json narration/recording
   ```
4. **`narration/build_captions.py`** -- splits the narration into
   sentence-level captions timed proportionally within each beat, and
   renders them as transparent PNG overlays (this ffmpeg build has no
   libass/drawtext, so captions are composited with the `overlay` filter
   instead of burned in via a subtitles filter).
   ```
   python3 narration/build_captions.py
   ```
5. **`narration/mux_final.py`** -- converts the `.webm` to `.mp4`,
   concatenates the narration clips, pads the tail by 1s so audio is never
   cut off, overlays every caption at its synced timestamp, and muxes
   video + narration into the final file.
   ```
   ffmpeg -i narration/recording/*.webm -c:v libx264 -pix_fmt yuv420p \
     -crf 18 -r 30 narration/screen_only.mp4
   python3 narration/mux_final.py narration/screen_only.mp4 marked_demo.mp4
   ```

## To rebuild after a site change

Edit `narration/demo_script.py` and the action choreography in
`narration/demo_record.py` if the flow changes, then rerun steps 2-5.
Durations are re-measured automatically each run (nothing hardcoded).

If a human voiceover is preferred instead of Kokoro, `demo_script.py`
doubles as a recording script -- swap in your own narration WAVs (same
filenames) under `narration/audio/` and skip step 2.

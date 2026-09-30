# video/

`marked_demo.mp4` — 2:15, narrated, with burned-in captions on every slide
(so it satisfies "English audio or subtitles" twice over).

The voiceover is synthesized (macOS `say`, Samantha voice), not a scrubbed
placeholder: `narration/narration.py` holds the spoken script, one entry
per slide, and each slide is timed to its own spoken clip rather than a
fixed guess.

- `make_titlecard.py` — renders the text-only title cards via headless Chrome
- `add_captions.py` — composites a caption bar onto data-screenshot slides
- `narration/narration.py` — the spoken script, one line per slide
- `narration/generate.py` — regenerates the `.aiff` clips and `durations.json`
  from that script (`cd narration && python3 generate.py`)
- `build_video.sh` — renders each slide for exactly as long as its narration
  clip runs (+ ~0.7s pad), pads/concats the audio to match, and muxes video
  + narration into `marked_demo.mp4`
- `slides/` — the 15 final frames, in order

To rebuild after a site change: retake the screenshots referenced in
`build_video.sh`'s slide list, edit `narration/narration.py` if the script
needs to change, run `narration/generate.py` to resynthesize the audio and
durations, update the `DURS` array in `build_video.sh` from the new
`durations.json` (+0.7s pad, rounded up), then rerun `./build_video.sh`.

If a human voiceover is preferred instead, the same `narration.py` script
doubles as a recording script — swap it in for the `.aiff` files and keep
the rest of the pipeline the same.

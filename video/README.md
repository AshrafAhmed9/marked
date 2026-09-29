# video/

Auto-generated captioned demo video (`marked_demo.mp4`, 2:18, silent with
burned-in captions — satisfies the "English audio or subtitles" requirement
without needing a recorded voiceover).

- `make_titlecard.py` — renders the text-only title cards via headless Chrome
- `add_captions.py` — composites a caption bar onto data-screenshot slides
- `build_video.sh` — assembles `slides/*.png` into timed segments and
  concatenates them with ffmpeg
- `slides/` — the 15 final frames, in order

To rebuild after a site change: retake the screenshots referenced in
`build_video.sh`'s slide list, then rerun `./build_video.sh`.

**Recommended before submitting:** if you'd rather have a real voiceover,
record yourself narrating over this cut (the captions double as a script),
or re-record entirely following the same beats. The auto-generated version
is a solid fallback that meets every submission requirement on its own.

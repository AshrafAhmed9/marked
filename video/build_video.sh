#!/bin/bash
# Builds marked_demo.mp4: 15 caption slides, each timed to its narration
# clip (macOS `say`, Samantha voice), muxed into one video with a real
# audio track. Captions are burned into the slide PNGs already (see
# add_captions.py) so the video satisfies "English audio or subtitles"
# twice over.
set -e
cd "$(dirname "$0")"
mkdir -p segments audio

declare -a SLIDES=(
  "01_hook" "02_hook2" "03_intro" "04_svb_hero" "05_svb_charts"
  "06_number" "07_run_slider" "08_backtest_table" "09_luck"
  "10_deposit_flight" "11_classic" "12_d2_era" "13_bugs" "14_today"
  "15_closing"
)

# Narration text per slide, and the final segment duration (spoken length
# + ~0.7s breathing room, rounded up). Regenerate durations.json via
# narration.py + `say`/`afinfo` if the script text changes.
declare -a DURS=(14 3.5 5 10 7 11 10 9 7.5 11 17.5 8.5 8 4.5 8.5)

rm -f segments/*.mp4 audio/*.wav concat_list.txt audio_concat_list.txt

i=0
for name in "${SLIDES[@]}"; do
  idx=$(printf "%02d" $((i+1)))
  img="slides/${name}.png"
  dur="${DURS[$i]}"
  seg=$(printf "segments/%02d.mp4" "$i")

  # video: loop the still frame for the full segment duration
  ffmpeg -y -loglevel error -loop 1 -i "$img" -t "$dur" \
    -vf "scale=1920:1080,fps=30,format=yuv420p" \
    -c:v libx264 -pix_fmt yuv420p "$seg"
  echo "file '$seg'" >> concat_list.txt

  # audio: pad the narration clip with silence to exactly match $dur
  wav=$(printf "audio/%02d.wav" "$i")
  ffmpeg -y -loglevel error -i "narration/${idx}.aiff" \
    -af "apad" -t "$dur" -ar 44100 -ac 2 "$wav"
  echo "file '$wav'" >> audio_concat_list.txt

  i=$((i+1))
done

ffmpeg -y -loglevel error -f concat -safe 0 -i concat_list.txt -c copy video_only.mp4
ffmpeg -y -loglevel error -f concat -safe 0 -i audio_concat_list.txt -c pcm_s16le narration_track.wav

ffmpeg -y -loglevel error -i video_only.mp4 -i narration_track.wav \
  -c:v copy -c:a aac -b:a 192k -shortest marked_demo.mp4

rm -f video_only.mp4
echo "Wrote marked_demo.mp4"
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 marked_demo.mp4

#!/bin/bash
set -e
cd "$(dirname "$0")"
mkdir -p segments

declare -a FILES=(
  "slides/01_hook.png:7"
  "slides/02_hook2.png:4"
  "slides/03_intro.png:4"
  "slides/04_svb_hero.png:12"
  "slides/05_svb_charts.png:11"
  "slides/06_number.png:6"
  "slides/07_run_slider.png:13"
  "slides/08_backtest_table.png:16"
  "slides/09_luck.png:6"
  "slides/10_deposit_flight.png:13"
  "slides/11_classic.png:7"
  "slides/12_d2_era.png:13"
  "slides/13_bugs.png:7"
  "slides/14_today.png:12"
  "slides/15_closing.png:7"
)

rm -f segments/*.mp4 concat_list.txt
i=0
for entry in "${FILES[@]}"; do
  file="${entry%%:*}"
  dur="${entry##*:}"
  seg=$(printf "segments/%02d.mp4" "$i")
  ffmpeg -y -loglevel error -loop 1 -i "$file" -t "$dur" \
    -vf "scale=1920:1080,fps=30,format=yuv420p" \
    -c:v libx264 -pix_fmt yuv420p "$seg"
  echo "file '$seg'" >> concat_list.txt
  i=$((i+1))
done

ffmpeg -y -loglevel error -f concat -safe 0 -i concat_list.txt -c copy marked_demo.mp4
echo "Wrote marked_demo.mp4"
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 marked_demo.mp4

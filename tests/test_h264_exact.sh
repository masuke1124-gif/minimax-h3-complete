#!/usr/bin/env bash
set -Eeuo pipefail

ODD="/tmp/h3_exact_odd_369x387.mp4"
EVEN="/tmp/h3_exact_even_600x1200.mp4"

ffmpeg -y -hide_banner -loglevel error \
  -f lavfi -i "testsrc=s=369x387:r=2:d=1" \
  -c:v libx264 -pix_fmt yuv444p "$ODD"

ffmpeg -y -hide_banner -loglevel error \
  -f lavfi -i "testsrc=s=600x1200:r=2:d=1" \
  -c:v libx264 -pix_fmt yuv420p "$EVEN"

[ "$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,pix_fmt -of csv=p=0 "$ODD")" = "369,387,yuv444p" ]
[ "$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,pix_fmt -of csv=p=0 "$EVEN")" = "600,1200,yuv420p" ]

echo "H.264 exact dimension tests: PASS"


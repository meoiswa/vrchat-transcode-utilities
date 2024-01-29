#!/bin/bash

# Check if required tools are installed
command -v ffmpeg >/dev/null 2>&1 || { echo >&2 "Error: ffmpeg is required but not installed. Aborting."; exit 1; }

# Provided cubic function coefficients
a="0.000185632"
b="-0.0374664"
c="2.7183"
d="-51.2774"

# Parse command line options
while getopts "i:g:t:s:" opt; do
  case $opt in
    i) input_file="$OPTARG";;
    g) use_gpu=true;;
    t) subtitle_track="$OPTARG";;
    s) subtitle_file="$OPTARG";;
    \?) echo "Invalid option: -$OPTARG" >&2; exit 1;;
  esac
done

# Check if required options are provided
if [ -z "$input_file" ]; then
  echo "Usage: $0 -i <input_file> [-g] [-t <subtitle_track>] [-s <subtitle_file>]"
  exit 1
fi

# Validate input file existence
if [ ! -f "$input_file" ]; then
  echo "Error: Input file '$input_file' not found."
  exit 1
fi

# Determine subtitle input method
if [ -n "$subtitle_track" ] && [ -n "$subtitle_file" ]; then
  echo "Error: Use either -t or -s, not both."
  exit 1
elif [ -n "$subtitle_track" ]; then
  # Extract the specified subtitle track
  temp_subtitle_file="temp_subs.srt"
  ffmpeg -i "$input_file" -map 0:s:"$subtitle_track" "$temp_subtitle_file"
elif [ -n "$subtitle_file" ]; then
  # Use the provided subtitles file
  temp_subtitle_file="$subtitle_file"
else
  echo "Error: Either -t or -s must be specified."
  exit 1
fi

# Validate subtitle file existence
if [ ! -f "$temp_subtitle_file" ]; then
  echo "Error: Subtitle file '$temp_subtitle_file' not created successfully."
  exit 1
fi

echo "Processing subtitle font sizes..."
# Extract font sizes from subtitles and perform size translations
awk -v a="$a" -v b="$b" -v c="$c" -v d="$d" '
  function map_font_size(input_size) {
    return int(a * input_size^3 + b * input_size^2 + c * input_size + d);
  }
  
  /face/ {
    match($0, /size="([0-9]+)"/, arr);
    size = arr[1];
    new_size = map_font_size(size);
    gsub("size=\"" size "\"", "size=\"" new_size "\"");
  }
  { print }
' "$temp_subtitle_file" > "${temp_subtitle_file}.tmp" && mv "${temp_subtitle_file}.tmp" "$temp_subtitle_file"

# Set output file name
output_file="${input_file%.*}_processed.mp4"

# Set encoding parameters based on GPU usage
if [ "$use_gpu" = true ]; then
  # Using GPU (h264_nvenc)
  ffmpeg -i "$input_file" -map 0:0 -map 0:1 -c:v h264_nvenc -pix_fmt yuv420p -crf 23 -preset p7 -tune hq -vf "subtitles=$temp_subtitle_file" -c:a ac3 "$output_file"
else
  # Using software encoding (libx264)
  ffmpeg -i "$input_file" -map 0:0 -map 0:1 -c:v libx264 -pix_fmt yuv420p -crf 23 -preset veryslow -tune animation -vf "subtitles=$temp_subtitle_file" -c:a ac3 "$output_file"
fi

# Logging
echo "Processing completed successfully."

# Remove temporary subtitle file (if extracted)
if [ -f "$temp_subtitle_file" ]; then
  rm "$temp_subtitle_file"
fi

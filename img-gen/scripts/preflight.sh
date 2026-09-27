#!/bin/bash

if [ $# -lt 1 ]; then
  echo "Usage: $0 <file_path> [--mask]"
  exit 1
fi

FILE="$1"
IS_MASK=0

if [ "$2" = "--mask" ]; then
  IS_MASK=1
fi

if [ ! -f "$FILE" ]; then
  echo "Error: File '$FILE' does not exist."
  exit 1
fi

# Validate file size is under 50MB (50 * 1024 * 1024 = 52428800 bytes)
SIZE=$(stat -f%z "$FILE")
if [ "$SIZE" -ge 52428800 ]; then
  echo "Error: File size ($SIZE bytes) exceeds the 50MB limit."
  exit 1
fi

# Check for alpha channel if --mask is passed
if [ $IS_MASK -eq 1 ]; then
  if ! sips -g hasAlpha "$FILE" | grep -qiE "true|yes"; then
    echo "Error: Alpha channel is required when --mask is provided, but it was not found in '$FILE'."
    exit 1
  fi
fi

exit 0

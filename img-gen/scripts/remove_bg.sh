#!/bin/bash
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <input_file> <output_file>"
    exit 1
fi

INPUT_FILE="$1"
OUTPUT_FILE="$2"

if ! command -v rembg &> /dev/null; then
    if [ -x "$HOME/.local/bin/rembg" ]; then
        REMBG_CMD="$HOME/.local/bin/rembg"
    else
        echo "Error: rembg is not installed or not in PATH."
        exit 1
    fi
else
    REMBG_CMD="rembg"
fi

$REMBG_CMD i "$INPUT_FILE" "$OUTPUT_FILE"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "Error: rembg failed with exit code $EXIT_CODE"
    exit $EXIT_CODE
fi

echo "Successfully removed background from $INPUT_FILE and saved to $OUTPUT_FILE"

#!/usr/bin/env python3
import sys
import re
import glob

def clean_transcript(input_pattern, output_path):
    files = glob.glob(input_pattern)
    if not files:
        print(f"No files matched pattern: {input_pattern}", file=sys.stderr)
        sys.exit(1)
    
    filepath = files[0]
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    lines = text.split("\n")
    cleaned = []
    prev = ""
    for line in lines:
        line = line.strip()
        if not line or line.isdigit() or re.match(r"^\d{2}:\d{2}:\d{2}", line):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line != prev:
            cleaned.append(line)
            prev = line

    full_text = " ".join(cleaned)
    full_text = re.sub(r"\s+", " ", full_text)

    with open(output_path, "w", encoding="utf-8") as out:
        out.write(full_text)
    
    print(f"Cleaned {len(full_text.split())} words into {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 clean_transcript.py <glob_pattern> <output_file>")
        sys.exit(1)
    clean_transcript(sys.argv[1], sys.argv[2])

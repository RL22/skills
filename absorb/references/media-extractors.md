# Media Extraction Channels & Recipes

Use these recipes in Step 2 of the `/absorb` protocol based on the media source.

---

## 1. Video & Audio (YouTube, Vimeo, Podcasts)

Use `yt-dlp` to extract subtitles/captions without downloading heavy video streams:

```bash
# Extract auto-generated or manual subtitles to SRT in /tmp
yt-dlp --skip-download --write-auto-subs --write-subs --sub-langs "en.*" \
  --convert-subs srt -o "/tmp/absorb-%(id)s.%(ext)s" "<URL>"
```

### Clean SRT to Plain Markdown Text (Python)
```python
import re, glob

srt_files = glob.glob("/tmp/absorb-*.srt")
if srt_files:
    with open(srt_files[0], "r", encoding="utf-8") as f:
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
    with open("/tmp/absorb-clean.txt", "w", encoding="utf-8") as out:
        out.write(" ".join(cleaned))
```

---

## 2. Static Web Articles & Documentation

Use `defuddle` CLI to convert raw URLs into clean, token-efficient Markdown stripped of navigation, banners, and boilerplate:

```bash
defuddle parse "<URL>" > /tmp/absorb-clean.txt
```

If `defuddle` is unavailable, fall back to curl or python readability extractors.

---

## 3. Dynamic SPAs, Authenticated Newsletters, & Visual Diagrams

Use `capt-chrome-agent` (CDP CLI) when:
- The site requires client-side JavaScript hydration (Single Page Apps).
- The article is behind an active login session (Substack, Medium, X threads).
- The media displays crucial visual architecture diagrams or presentation slides (`--visual`).

### Headless Extraction Recipe
```bash
# 1. Launch instance
chrome-agent launch --headless

# 2. Navigate to target URL
chrome-agent 0 Page.navigate '{"url":"<URL>"}'

# 3. Wait for hydration
chrome-agent 0 Runtime.evaluate '{"expression":"document.readyState","returnByValue":true}'

# 4. Pull readable text directly from active DOM
chrome-agent 0 Runtime.evaluate '{"expression":"document.body.innerText","returnByValue":true}' \
  | python3 -c "import sys, json; open('/tmp/absorb-clean.txt','w').write(json.load(sys.stdin)['result']['value'])"
```

### Visual Slide / Diagram Capture (`--visual`)
When slides or system diagrams contain architectural blueprints not fully spoken in audio:
```bash
# Capture full viewport screenshot to inspect architecture
chrome-agent 0 Page.captureScreenshot '{"format":"png"}' \
  | python3 -c "import sys,json,base64; open('/tmp/absorb-slide.png','wb').write(base64.b64decode(json.load(sys.stdin)['data']))"

# Shutdown instance upon completion
chrome-agent stop 0
```

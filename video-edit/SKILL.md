---
name: video-edit
description: >
  Turn recorded raw footage into a finished, published video using a local
  agentic pipeline: MLX-Whisper transcription, FFmpeg cuts, Remotion graphics,
  two hard-stop human review gates, and DaVinci Resolve scripted finalize.
  Handles both outline-first (a content-outline already exists) and
  footage-first (no outline yet — drafts one retroactively from the
  transcript) recordings. Trigger: /video-edit <slug>,
  /video-edit <slug> --approve-gate1, /video-edit <slug> --approve-gate2.
  Auto-activates when the user says "edit this video", "run the video
  pipeline", "process this footage", or references a content-outlines slug
  with raw footage attached.
---

# Video Edit Pipeline

## Purpose

Take footage from `content-outlines/<slug>/raw/` through prep, two human
review gates, edit, self-verify, and a scripted DaVinci Resolve finalize —
ending in a published-ready MP4 and an updated content calendar entry. One
monolithic skill, fabric-style, mirroring the sibling `content-outline`
skill's single-file pattern. No sub-skills, no orchestrator/worker split,
no automatic trigger (Dropbox/Discord/file-watcher) — always invoked
manually once footage is ready.

Full architecture and rationale, if you keep them: see
`${VIDEO_EDIT_RESEARCH_DIR:-~/Movies/config-research}/optimal-config-architecture.md`.
Deferred enhancements (not in this version): see
`${VIDEO_EDIT_RESEARCH_DIR:-~/Movies/config-research}/backlog-enhancements.md`.

---

## Invocation

```
/video-edit <slug>                    # start: prep, stop at Gate 1
/video-edit <slug> --approve-gate1    # resume: edit + self-verify, stop at Gate 2
/video-edit <slug> --approve-gate2    # resume: finalize + publish prep
```

`slug` must match an existing folder:
`${SPRINTZ_CONTENT_DIR:-~/Sprintz/brands/sprintz/content}/content-outlines/<slug>/`

If the folder or its `raw/` subfolder doesn't exist, or `raw/` is empty, stop
and tell the user — do not create it.

---

## Step 0 — Resolve paths and state

```bash
CONTENT_DIR="${SPRINTZ_CONTENT_DIR:-$HOME/Sprintz/brands/sprintz/content}"
SLUG_DIR="$CONTENT_DIR/content-outlines/$SLUG"
RAW_DIR="$SLUG_DIR/raw"
STATE_FILE="$SLUG_DIR/.pipeline-state"
OUTLINE_FILE=$(find "$CONTENT_DIR/content-outlines" -maxdepth 1 -name "*-$SLUG.md" -o -name "$SLUG.md" 2>/dev/null | head -1)
```

Read `$STATE_FILE` if it exists (plain text: `gate1_pending`, `gate2_pending`,
or `done`). This determines which branch below to run:

| Invocation flag | Required prior state | Runs |
|---|---|---|
| (none) | no state file, or state file missing | Step 1 (Prep) → Step 2 (Gate 1) |
| `--approve-gate1` | `gate1_pending` | Step 3 (Edit + Self-Verify) → Step 4 (Gate 2) |
| `--approve-gate2` | `gate2_pending` | Step 5 (Finalize & Publish) |

If the flag doesn't match the required prior state (e.g. `--approve-gate2`
passed while state is `gate1_pending`), stop and tell the user which gate is
actually pending.

---

## Step 1 — Prep

### 1a. Ensure MLX-Whisper is available

```bash
which mlx_whisper >/dev/null || uv tool install mlx-whisper
```

`mlx-whisper` is installed as a `uv tool` (CLI `mlx_whisper`), so
`import mlx_whisper` from the system `python3` fails. Use the CLI.

Cached models (already present on this machine under
`~/.cache/huggingface/hub`): `whisper-tiny`, `whisper-small`,
`whisper-large-v3-turbo` (all `mlx-community`). Default to
`whisper-large-v3-turbo` for accuracy; fall back to `whisper-small` if the
footage is long (>20 min) and speed matters more.

### 1b. Transcribe the raw footage

```bash
mlx_whisper "$RAW_FILE" \
  --model mlx-community/whisper-large-v3-turbo \
  --word-timestamps True \
  --condition-on-previous-text False \
  --hallucination-silence-threshold 2 \
  --compression-ratio-threshold 2.0 \
  --no-speech-threshold 0.5 \
  --language en \
  --output-format json --output-name transcript --output-dir "$SLUG_DIR"
```

The anti-loop flags are required, not optional. Without them Whisper
collapsed into repeating "Yep." / "right. So," over quiet or backchannel
audio and silently dropped ~10 minutes of real speech (found on the first
real run, character-md-drift-fix). Always sanity-check the result: count
words vs. duration and scan for any repeated 3-gram over 10 times before
trusting it. Long files run several minutes, so run in the background.

Store the transcript as `$SLUG_DIR/transcript.json` (word-level timestamps —
needed both for cue-mapping and later for Remotion caption/lower-third
timing). Also check for dead-air: gaps over 3s between words mark likely
cut points and stretches where a co-host's audio was not captured.

### 1c. Determine outline-first vs. footage-first

- **If `$OUTLINE_FILE` exists** (outline-first): parse its cue markers
  (`CLIP START`/`CLIP END`, `KEY MOMENT`, `B-ROLL HERE`) and match each
  cue's surrounding script text against the transcript using fuzzy text
  matching, to anchor each cue to a real `[start, end]` timestamp range in
  `transcript.json`. Produce `$SLUG_DIR/cutlist.json`:
  ```json
  [{"cue": "CLIP START", "label": "primary-hook", "start": 12.4, "end": 87.1}, ...]
  ```

- **If `$OUTLINE_FILE` does not exist** (footage-first): draft a retroactive
  outline from `transcript.json` using the same structure, hook formulas,
  and 3-question flow (CTA, Creator POV, Angle) as the `content-outline`
  skill (`../content-outline/SKILL.md`,
  Steps 1–3) — except derive the "source" content from the transcript
  itself instead of an external URL/article, and ask the user the same
  three questions before drafting. Save this draft to
  `$SLUG_DIR/draft-outline.md` (do NOT save it into the shared
  `content-outlines/` root yet — it isn't approved). While drafting, scan
  the transcript for moments that don't fit the current outline's angle but
  stand alone as interesting — record each as a **recompose candidate**:
  timestamp + one-line description only. No clip extraction. These go into
  the Gate 1 review file, not a separate folder.

### 1d. Draft the cut list

Using `cutlist.json` (outline-first) or the draft outline's cue markers
against `transcript.json` (footage-first), call the FFmpeg wrapper to
produce non-destructive proposed cut points — do not cut anything yet:

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 "$RAW_FILE"
```

List every `B-ROLL HERE` marker with ~2 sentences of surrounding transcript
context — this becomes a **manual checklist**, not an automated b-roll
search. Do not attempt to source b-roll footage.

### 1e. Draft graphics

For each `KEY MOMENT` or caption/lower-third implied by the outline,
prepare a Remotion composition spec (JSON props: text, start/end from
`transcript.json` word timestamps, template name) under
`$SLUG_DIR/graphics-spec.json`. Do not render yet — rendering happens after
Gate 1 approval, as part of Step 3.

---

## Step 2 — Human Review Gate 1 (hard stop)

Write `$SLUG_DIR/review-gate-1.md`:

```markdown
# Review Gate 1 — <slug>

## Proposed Cut List
| Cue | Label | Start | End |
|---|---|---|---|
[from cutlist.json]

## Draft Outline (footage-first only — approve or edit before continuing)
[contents of draft-outline.md, if present]

## Recompose Candidates (noted only — no extraction)
- [timestamp] — [one-line description]

## Manual B-Roll Checklist
- [ ] [B-ROLL HERE marker context] — needs: [suggestion]

## Graphics Preview
[list of graphics-spec.json entries: template + timing]
```

Then:

```bash
echo "gate1_pending" > "$STATE_FILE"
```

Tell the user explicitly:

> Review `review-gate-1.md` in the slug folder. Edit the cut list, outline,
> or checklist directly in the file if needed. When ready, run
> `/video-edit <slug> --approve-gate1` to continue.

**Stop here. Do not proceed further in this invocation.**

---

## Step 3 — Edit + Self-Verify (runs on `--approve-gate1`)

Re-read `review-gate-1.md` for any manual edits the user made to the cut
list or outline before applying anything.

1. Apply the approved cuts via FFmpeg (non-destructive: write a new edited
   file, never overwrite `raw/`):
   ```bash
   ffmpeg -i "$RAW_FILE" -filter_complex "[0:v]trim=...,setpts=PTS-STARTPTS[v1];..." \
     -map "[v1]" -map "[a1]" "$SLUG_DIR/edit-draft.mp4"
   ```
   (Build the actual `trim`/`concat` filtergraph from `cutlist.json`'s
   approved entries.)

2. Render approved graphics via Remotion and composite them in:
   ```bash
   npx remotion render "$SLUG_DIR/graphics-spec.json" "$SLUG_DIR/graphics-render.mp4"
   ffmpeg -i "$SLUG_DIR/edit-draft.mp4" -i "$SLUG_DIR/graphics-render.mp4" \
     -filter_complex overlay "$SLUG_DIR/edit-composited.mp4"
   ```

3. Self-verify: re-transcribe `edit-composited.mp4` via MLX-Whisper (same
   call shape as Step 1b) and diff the resulting text against the approved
   outline's script sections. Flag any KEY POINT or hook whose corresponding
   segment text doesn't reasonably match what was scripted — this catches
   cuts that landed wrong or removed part of a scripted line by accident.

---

## Step 4 — Human Review Gate 2 (hard stop)

Write `$SLUG_DIR/review-gate-2.md`:

```markdown
# Review Gate 2 — <slug>

## Self-Verify Result
[any flagged discrepancies from Step 3.3, or "No discrepancies found."]

## Edited File
$SLUG_DIR/edit-composited.mp4 — ready for finalize pending approval.
```

```bash
echo "gate2_pending" > "$STATE_FILE"
```

Tell the user:

> Review `review-gate-2.md` and watch `edit-composited.mp4`. When ready,
> run `/video-edit <slug> --approve-gate2` to finalize and publish-prep.

**Stop here. Do not proceed further in this invocation.**

---

## Step 5 — Finalize & Publish (runs on `--approve-gate2`)

1. Script DaVinci Resolve via its Python API to assemble and export the
   final master from `edit-composited.mp4` (or directly from
   `cutlist.json` + `graphics-spec.json`, if driving Resolve's own cut
   application rather than FFmpeg's pre-composited file — prefer this if
   Resolve's timeline/color tools are wanted for this video):
   ```python
   import DaVinciResolveScript as dvr
   resolve = dvr.scriptapp("Resolve")
   pm = resolve.GetProjectManager()
   project = pm.CreateProject("<slug>")  # or LoadProject if re-running
   media_pool = project.GetMediaPool()
   media_pool.ImportMedia(["$SLUG_DIR/edit-composited.mp4"])
   # build timeline, add to render queue, set export preset (YouTube 1080p)
   project.GetRenderQueue()... 
   project.StartRendering()
   ```
   Export target: `$SLUG_DIR/final.mp4`.

2. Update the content calendar. Find the matching entry in
   `$CONTENT_DIR/content_cal_90/` (matched by slug) and update/add
   frontmatter:
   ```yaml
   status: produced
   video_path: <SLUG_DIR>/final.mp4
   produced_date: <today, YYYY-MM-DD>
   ```
   This makes the entry queryable via Obsidian Bases without any new
   service.

3. Generate thumbnail candidates by invoking the `create-thumbnail` skill
   with the same slug (`/create-thumbnail <slug>` — it will pull candidate
   frames from `final.mp4` automatically since no source image is passed).
   This replaces the earlier manual Photoshop thumbnail step. Candidates
   land in `$SLUG_DIR/thumbnail-candidates/renders/` for the user to pick
   from — do not auto-select one.

4. Mark pipeline done:
   ```bash
   echo "done" > "$STATE_FILE"
   ```

5. Tell the user:

   > `final.mp4` is ready at `$SLUG_DIR/final.mp4`. Calendar entry updated.
   > Thumbnail candidates ready in `thumbnail-candidates/renders/` — pick
   > one, then upload to YouTube manually. Publish itself stays a manual
   > step.

---

## Explicitly out of scope (v1)

No Dropbox integration, no Discord/chat trigger, no AI video-to-video branch,
no automated b-roll sourcing, no sub-skill decomposition, no automated clip
extraction for recompose candidates. See `backlog-enhancements.md` for where
these — plus `pipeline-state.json` (richer resumability than the current
plain-text marker), gate diffs, vocabulary-primed transcription, and a
Remotion template library — would hook in later.

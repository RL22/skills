# Nano Banana (Gemini image model)

Accessed via the Gemini CLI **nanobanana** extension (`generate_image` MCP tool), or the Gemini API (`GEMINI_API_KEY`).

Strengths: editing, character consistency, multi-turn, speed, cost.

## Delegation invocation (verified live, Task 12)

The extension currently runs `gemini-3.1-flash-image-preview` (Nano Banana 2) — the extension manages its own model, so do **not** force a stale `NANOBANANA_MODEL`.

Do **not** call the `/generate` slash command headlessly: it delegates to a sandboxed sub-agent that cannot reach the MCP tool, so no image is produced. Instead drive the main agent directly:

```
GEMINI_CLI_TRUST_WORKSPACE=true gemini --yolo --skip-trust -p \
  "Use the nanobanana generate_image tool to create exactly one image: <PROMPT>. Save the PNG into the current working directory."
```

- `--yolo` auto-approves the MCP tool call in headless mode.
- `--skip-trust` (+ `GEMINI_CLI_TRUST_WORKSPACE=true`) allows running in an untrusted dir.
- Output lands in the cwd (or `./nanobanana-output/`); the runner scans both.
- Note: Nano Banana can hit a quota cap; the Gemini agent may auto-fail-over to another engine to still deliver a file.

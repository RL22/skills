#!/usr/bin/env node
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const args = parseArgs(process.argv.slice(2));
const action = args.action ?? "trash";
const idsFile = args.ids;
const outDir = path.resolve(args.outDir ?? "gmail-cleanup-output");
const chunkSize = Number(args.chunkSize ?? 500);

if (!["trash", "delete"].includes(action)) fail("Use --action trash or --action delete.");
if (!idsFile || !existsSync(idsFile)) fail("Provide --ids <approved-message-ids.json|txt>.");
if (action === "trash" && process.env.APPROVED_TO_TRASH !== "YES") {
  fail("Refusing Trash move. Set APPROVED_TO_TRASH=YES after reviewing the approved ID file.");
}
if (action === "delete" && process.env.APPROVED_TO_DELETE_PERMANENTLY !== "YES") {
  fail("Refusing permanent delete. Set APPROVED_TO_DELETE_PERMANENTLY=YES only after explicit approval.");
}

mkdirSync(outDir, { recursive: true });
const ids = readIds(idsFile);
if (!ids.length) fail("Approved ID file is empty.");

const runId = new Date().toISOString().replace(/[:.]/g, "-");
const logPath = path.join(outDir, `action-log-${action}-${runId}.jsonl`);
const chunks = [];
for (let i = 0; i < ids.length; i += chunkSize) chunks.push(ids.slice(i, i + chunkSize));

let ok = 0;
let failed = 0;
for (let i = 0; i < chunks.length; i += 1) {
  const result = await applyBatch(action, chunks[i], i);
  if (result.ok) ok += chunks[i].length;
  else failed += chunks[i].length;
  writeFileSync(logPath, `${JSON.stringify(result)}\n`, { flag: "a" });
  console.error(`Processed batch ${i + 1}/${chunks.length}`);
}

const summary = { action, total: ids.length, ok, failed, batches: chunks.length, logPath };
writeFileSync(path.join(outDir, `action-summary-${action}-${runId}.json`), `${JSON.stringify(summary, null, 2)}\n`);
console.log(JSON.stringify(summary, null, 2));

function parseArgs(argv) {
  const parsed = {};
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (!arg.startsWith("--")) continue;
    const key = arg.slice(2).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
    const next = argv[i + 1];
    parsed[key] = next && !next.startsWith("--") ? argv[++i] : "true";
  }
  return parsed;
}

function readIds(file) {
  const text = readFileSync(file, "utf8").trim();
  if (!text) return [];
  if (file.endsWith(".json")) {
    const data = JSON.parse(text);
    const raw = Array.isArray(data)
      ? data
      : Array.isArray(data.ids)
        ? data.ids
        : Array.isArray(data.messages)
          ? data.messages
          : [];
    return [...new Set(raw.map((item) => typeof item === "string" ? item : item?.id).filter(Boolean))];
  }
  return [...new Set(text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean))];
}

function applyBatch(mode, idsChunk, index) {
  return new Promise((resolve) => {
    const gwsArgs = mode === "trash"
      ? [
          "gmail", "users", "messages", "batchModify",
          "--params", JSON.stringify({ userId: "me" }),
          "--json", JSON.stringify({ ids: idsChunk, addLabelIds: ["TRASH"] }),
          "--format", "json",
        ]
      : [
          "gmail", "users", "messages", "batchDelete",
          "--params", JSON.stringify({ userId: "me" }),
          "--json", JSON.stringify({ ids: idsChunk }),
          "--format", "json",
        ];
    const child = spawn("gws", gwsArgs, { env: { ...process.env, NO_COLOR: "1" } });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (data) => { stdout += data; });
    child.stderr.on("data", (data) => { stderr += data; });
    child.on("close", (code) => {
      const record = { batch: index + 1, action: mode, ids: idsChunk, ok: code === 0, code, at: new Date().toISOString() };
      if (!record.ok) record.error = stderr.trim() || stdout.trim();
      resolve(record);
    });
  });
}

function fail(message) {
  console.error(message);
  process.exit(2);
}

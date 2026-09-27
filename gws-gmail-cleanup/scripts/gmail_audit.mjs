#!/usr/bin/env node
import { execFileSync, spawn } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const args = parseArgs(process.argv.slice(2));
const profile = args.profile ?? "gmail-audit";
const outDir = path.resolve(args.outDir ?? `gmail-cleanup-output/${profile}`);
const cacheDir = path.join(outDir, "cache");
const pageLimit = Number(args.pageLimit ?? 250);
const pageDelay = Number(args.pageDelay ?? 25);
const fetchConcurrency = Number(args.concurrency ?? 12);
const metadataHeaders = ["From", "Subject", "Date", "To", "Cc", "List-Unsubscribe"];

mkdirSync(outDir, { recursive: true });
mkdirSync(cacheDir, { recursive: true });

const query = buildQuery(args);
if (!query.trim()) {
  console.error("Provide --query or at least one filter such as --older-than, --category, --label, --from-domain, --larger, or --has-attachment.");
  process.exit(2);
}

const keepPolicy = {
  protectedLabels: splitList(args.protectLabel ?? "SENT,STARRED,IMPORTANT"),
  keepTerms: splitList(args.keepTerm ?? ""),
  keepDomains: splitList(args.keepDomain ?? ""),
  keepExtensions: splitList(args.keepExtension ?? "pdf,mp3"),
  raw: {
    query,
    args,
  },
};

console.error(`Listing Gmail messages for query: ${query}`);
const listed = listMessages(query);
console.error(`Fetching metadata for ${listed.length} messages`);
const messages = await mapLimit(listed, fetchConcurrency, async (item, index) => {
  if ((index + 1) % 500 === 0) console.error(`Fetched ${index + 1}/${listed.length}`);
  return fetchMessage(item.id);
});

const candidates = [];
const held = [];
const errors = [];
for (const message of messages) {
  if (!message || message.error) {
    errors.push(message);
    continue;
  }
  const row = normalizeMessage(message);
  const protection = protectionReasons(row, keepPolicy);
  row.protectionReasons = protection;
  if (protection.length) held.push(row);
  else candidates.push(row);
}

candidates.sort((a, b) => b.sizeEstimate - a.sizeEstimate);
held.sort((a, b) => b.sizeEstimate - a.sizeEstimate);

const candidateBytes = candidates.reduce((sum, row) => sum + row.sizeEstimate, 0);
const heldBytes = held.reduce((sum, row) => sum + row.sizeEstimate, 0);
const summary = {
  generated: new Date().toISOString(),
  profile,
  query,
  keepPolicy,
  listed: listed.length,
  candidates: candidates.length,
  candidateSizeMB: mb(candidateBytes),
  heldProtected: held.length,
  heldProtectedSizeMB: mb(heldBytes),
  errors: errors.length,
  topCandidateDomains: groupRows(candidates, "domain"),
  candidateYears: groupRows(candidates, "year"),
  topHeldDomains: groupRows(held, "domain"),
  largestCandidates: candidates.slice(0, 50).map(compactMessage),
  largestHeld: held.slice(0, 50).map((row) => ({ ...compactMessage(row), protectionReasons: row.protectionReasons })),
  files: {
    summary: path.join(outDir, "audit-summary.json"),
    candidates: path.join(outDir, "message-candidates.json"),
    heldProtected: path.join(outDir, "held-protected.json"),
    approvedMessageIds: path.join(outDir, "approved-message-ids.json"),
    approvedMessageIdsTxt: path.join(outDir, "approved-message-ids.txt"),
  },
  note: "Non-destructive audit. approved-message-ids contains candidate IDs for user review; do not apply actions until the user approves.",
};

writeJson(summary.files.summary, summary);
writeJson(summary.files.candidates, candidates);
writeJson(summary.files.heldProtected, held);
writeJson(summary.files.approvedMessageIds, candidates.map((row) => ({ id: row.id, threadId: row.threadId })));
writeFileSync(summary.files.approvedMessageIdsTxt, `${candidates.map((row) => row.id).join("\n")}\n`);
if (errors.length) writeJson(path.join(outDir, "errors.json"), errors);

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

function buildQuery(options) {
  if (options.query) return options.query;
  const parts = [];
  if (options.olderThan) parts.push(`older_than:${options.olderThan}`);
  if (options.newerThan) parts.push(`newer_than:${options.newerThan}`);
  if (options.category) parts.push(`category:${options.category}`);
  if (options.label) parts.push(`label:"${options.label}"`);
  if (options.fromDomain) parts.push(`from:${options.fromDomain}`);
  if (options.larger) parts.push(`larger:${options.larger}`);
  if (options.hasAttachment === "true") parts.push("has:attachment");
  if (options.noAttachment === "true") parts.push("-has:attachment");
  if (options.exclude) parts.push(options.exclude);
  return parts.join(" ");
}

function listMessages(q) {
  const cachePath = path.join(cacheDir, "listed-message-ids.json");
  if (existsSync(cachePath)) return JSON.parse(readFileSync(cachePath, "utf8"));
  const output = runGws([
    "gmail", "users", "messages", "list",
    "--params", JSON.stringify({ userId: "me", q, maxResults: 500 }),
    "--page-all",
    "--page-limit", String(pageLimit),
    "--page-delay", String(pageDelay),
    "--format", "json",
  ]);
  const ids = [];
  for (const line of output.split("\n")) {
    if (!line.trim()) continue;
    const page = JSON.parse(line);
    for (const message of page.messages ?? []) ids.push({ id: message.id, threadId: message.threadId });
  }
  const unique = [...new Map(ids.map((message) => [message.id, message])).values()];
  writeJson(cachePath, unique);
  return unique;
}

function fetchMessage(itemOrId) {
  const id = typeof itemOrId === "string" ? itemOrId : itemOrId.id;
  return new Promise((resolve) => {
    const cachePath = path.join(cacheDir, `message-${id}.json`);
    if (existsSync(cachePath)) {
      resolve(JSON.parse(readFileSync(cachePath, "utf8")));
      return;
    }
    const child = spawn("gws", [
      "gmail", "users", "messages", "get",
      "--params", JSON.stringify({ userId: "me", id, format: "metadata", metadataHeaders }),
      "--format", "json",
    ], { env: { ...process.env, NO_COLOR: "1" } });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => { stdout += chunk; });
    child.stderr.on("data", (chunk) => { stderr += chunk; });
    child.on("close", (code) => {
      if (code !== 0) {
        resolve({ id, error: clean(stderr) || clean(stdout) || `gws exited ${code}` });
        return;
      }
      try {
        const message = JSON.parse(clean(stdout));
        writeJson(cachePath, message);
        resolve(message);
      } catch (error) {
        resolve({ id, error: String(error) });
      }
    });
  });
}

async function mapLimit(items, limit, fn) {
  const results = new Array(items.length);
  let index = 0;
  async function worker() {
    while (index < items.length) {
      const current = index++;
      results[current] = await fn(items[current], current);
    }
  }
  await Promise.all(Array.from({ length: Math.max(1, limit) }, worker));
  return results;
}

function runGws(gwsArgs) {
  const stdout = execFileSync("gws", gwsArgs, {
    encoding: "utf8",
    maxBuffer: 1024 * 1024 * 128,
    stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env, NO_COLOR: "1" },
  });
  return clean(stdout);
}

function clean(text) {
  return String(text)
    .split("\n")
    .filter((line) => line.trim() && !line.startsWith("Using keyring backend:"))
    .join("\n")
    .trim();
}

function normalizeMessage(message) {
  const from = getHeader(message, "From");
  return {
    id: message.id,
    threadId: message.threadId,
    labelIds: message.labelIds ?? [],
    sizeEstimate: Number(message.sizeEstimate ?? 0),
    sizeMB: mb(Number(message.sizeEstimate ?? 0)),
    year: yearFrom(message),
    from,
    domain: parseDomain(from),
    subject: getHeader(message, "Subject"),
    date: getHeader(message, "Date"),
    snippet: message.snippet ?? "",
  };
}

function protectionReasons(row, policy) {
  const reasons = [];
  const labels = new Set(row.labelIds);
  for (const label of policy.protectedLabels) {
    if (labels.has(label)) reasons.push(`label:${label}`);
  }
  const haystack = `${row.from} ${row.subject} ${row.snippet}`.toLowerCase();
  for (const term of policy.keepTerms) {
    if (haystack.includes(term.toLowerCase())) reasons.push(`term:${term}`);
  }
  for (const domain of policy.keepDomains) {
    if (row.domain === domain.toLowerCase() || row.domain.endsWith(`.${domain.toLowerCase()}`)) reasons.push(`domain:${domain}`);
  }
  for (const extension of policy.keepExtensions) {
    const needle = `.${extension.toLowerCase().replace(/^\./, "")}`;
    if (haystack.includes(needle) || haystack.includes(`filename:${extension.toLowerCase().replace(/^\./, "")}`)) {
      reasons.push(`extension:${extension}`);
    }
  }
  return reasons;
}

function getHeader(message, name) {
  return message.payload?.headers?.find((header) => header.name.toLowerCase() === name.toLowerCase())?.value ?? "";
}

function parseDomain(from) {
  const match = from.match(/<([^>]+)>/) ?? from.match(/([^\s<>@]+@[^\s<>]+)/);
  const email = (match?.[1] ?? "").toLowerCase();
  return email.includes("@") ? email.split("@").pop().replace(/[>,)]*$/, "") : "";
}

function yearFrom(message) {
  const ms = Number(message.internalDate);
  if (Number.isFinite(ms) && ms > 0) return new Date(ms).getFullYear();
  const parsed = Date.parse(getHeader(message, "Date"));
  return Number.isFinite(parsed) ? new Date(parsed).getFullYear() : "unknown";
}

function groupRows(rows, key) {
  const groups = new Map();
  for (const row of rows) {
    const groupKey = String(row[key] ?? "(unknown)");
    const current = groups.get(groupKey) ?? { key: groupKey, messages: 0, bytes: 0 };
    current.messages += 1;
    current.bytes += row.sizeEstimate;
    groups.set(groupKey, current);
  }
  return [...groups.values()]
    .sort((a, b) => b.bytes - a.bytes || b.messages - a.messages)
    .slice(0, 50)
    .map((group) => ({ ...group, sizeMB: mb(group.bytes) }));
}

function compactMessage(row) {
  return {
    id: row.id,
    threadId: row.threadId,
    sizeMB: row.sizeMB,
    year: row.year,
    domain: row.domain,
    subject: row.subject,
    labelIds: row.labelIds,
  };
}

function splitList(value) {
  return String(value ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function mb(bytes) {
  return +(bytes / 1024 / 1024).toFixed(2);
}

function writeJson(file, value) {
  writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`);
}

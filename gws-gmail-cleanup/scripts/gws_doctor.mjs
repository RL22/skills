#!/usr/bin/env node
import { execFileSync } from "node:child_process";

function run(command, args = []) {
  try {
    const stdout = execFileSync(command, args, {
      encoding: "utf8",
      maxBuffer: 1024 * 1024 * 16,
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env, NO_COLOR: "1" },
    });
    return { ok: true, stdout: clean(stdout) };
  } catch (error) {
    return {
      ok: false,
      stdout: clean(error.stdout?.toString?.() ?? ""),
      stderr: clean(error.stderr?.toString?.() ?? error.message),
      code: error.status ?? 1,
    };
  }
}

function clean(text) {
  return String(text)
    .split("\n")
    .filter((line) => line.trim() && !line.startsWith("Using keyring backend:"))
    .join("\n")
    .trim();
}

function parseJson(result) {
  if (!result.ok || !result.stdout) return null;
  try {
    return JSON.parse(result.stdout);
  } catch {
    return null;
  }
}

const checks = {
  node: run("node", ["--version"]),
  npm: run("npm", ["--version"]),
  gcloud: run("gcloud", ["--version"]),
  gws: run("gws", ["--version"]),
};

const missing = Object.entries(checks)
  .filter(([, result]) => !result.ok)
  .map(([name]) => name);

const authStatusResult = checks.gws.ok ? run("gws", ["auth", "status"]) : { ok: false, stderr: "gws missing" };
const authStatus = parseJson(authStatusResult);
const tokenValid = Boolean(authStatus?.token_valid);
const gmailProfileResult = tokenValid
  ? run("gws", ["gmail", "users", "getProfile", "--params", JSON.stringify({ userId: "me" })])
  : { ok: false, stderr: "auth token invalid or unavailable" };
const gmailProfile = parseJson(gmailProfileResult);

let recommendedNextCommand = null;
if (missing.includes("node") || missing.includes("npm")) {
  recommendedNextCommand = "Install Node.js and npm.";
} else if (missing.includes("gws")) {
  recommendedNextCommand = "npm install -g @googleworkspace/cli";
} else if (missing.includes("gcloud")) {
  recommendedNextCommand = "Install Google Cloud CLI, then rerun this doctor.";
} else if (!authStatus?.client_config_exists) {
  recommendedNextCommand = "gws auth setup";
} else if (!tokenValid) {
  recommendedNextCommand = "gws auth login";
} else if (!gmailProfileResult.ok) {
  recommendedNextCommand = "Re-authenticate with Gmail scope, then retry Gmail profile verification.";
}

const report = {
  ok: missing.length === 0 && tokenValid && gmailProfileResult.ok,
  missing,
  checks: Object.fromEntries(Object.entries(checks).map(([name, result]) => [
    name,
    { ok: result.ok, version: result.stdout.split("\n")[0] || null, error: result.ok ? null : result.stderr },
  ])),
  authStatus: authStatus ?? { ok: false, error: authStatusResult.stderr || authStatusResult.stdout || "Unable to parse auth status" },
  gmailAccess: {
    ok: gmailProfileResult.ok,
    profile: gmailProfile,
    error: gmailProfileResult.ok ? null : gmailProfileResult.stderr || gmailProfileResult.stdout,
  },
  recommendedNextCommand,
};

console.log(JSON.stringify(report, null, 2));

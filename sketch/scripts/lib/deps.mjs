// Load playwright-core with an actionable message when the one-time setup hasn't run.
export async function chromium() {
  const nodeMajor = Number.parseInt(process.versions.node, 10);
  if (nodeMajor < 20) {
    console.error(`sketch: Node 20+ is required (found Node ${process.versions.node}). Upgrade Node, then run npm install.`);
    process.exit(1);
  }

  try {
    return (await import('playwright-core')).chromium;
  } catch (e) {
    if (e.code !== 'ERR_MODULE_NOT_FOUND') throw e;
    console.error('sketch: dependencies missing. Run once in the skill folder:\n  npm install && npx playwright-core install chromium');
    process.exit(1);
  }
}

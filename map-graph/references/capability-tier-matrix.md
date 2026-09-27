# Model Capability Tiers & Provider Mapping Matrix

Canonical source: [`~/Sprintz/.agents/AGENTS.md`](../../../../Sprintz/.agents/AGENTS.md) §4 (Universal Model Routing Matrix & Agent Delegation Rules). Read it there — this file is not a copy and must not be re-populated with the table, to avoid it drifting out of sync again (it previously held a stale, incomplete duplicate missing 3 of the 6 delegation rules).

If `~/Sprintz/.agents/AGENTS.md` is unreadable in the current environment (e.g. operating entirely outside the Sprintz workspace), fall back to these tier defaults only:

- **Tier 0** — Deterministic checks (lint, tests, AST). No LLM.
- **Tier 1** — Fast/cheap triage. `Effort: Light`.
- **Tier 2** — Frontier workhorse (implementation, drafting). `Effort: Medium`.
- **Tier 3** — Deep reasoning / adversarial review. `Effort: High`, thinking mode on.

Do not pin specific model names here — they go stale. Resolve the actual model per tier from the canonical doc or the session's active model list.

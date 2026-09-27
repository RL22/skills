# Environment & Sandbox Specification (Hard Mode)

Modern autonomous agents take actions across tools, files, databases, and APIs. Consequently, evaluating agents requires evaluating **environments** rather than simple input/output text prompts.

---

## 1. The Isolation Principle

> **Core Rule**: Never allow an agent under evaluation to access, read, or mutate live production systems.

Evaluating agents on live CRMs (Salesforce, HubSpot), ticketing tools, production databases, or messaging platforms creates catastrophic risks:
- Unintended outbound customer emails or notifications.
- Corrupted database state or overwritten records.
- Inconsistent benchmark conditions that prevent reproducible measurement.

All evaluations must take place inside **isolated digital clones**—lightweight, deterministic replicas of production services.

---

## 2. Digital Clone Architecture

A digital clone consists of 4 isolated components:

```text
+-----------------------------------------------------------+
|               Isolated Digital Clone Container            |
|                                                           |
|  +---------------------+        +----------------------+  |
|  |   Mock Tool Layer   |        |   Synthetic State    |  |
|  | (Local HTTP Server) | <----> |   (SQLite / Fixture) |  |
|  +---------------------+        +----------------------+  |
|             ^                                             |
|             | Tool Calls                                  |
|  +---------------------+        +----------------------+  |
|  |     Agent Under     |        |   Binary Verifier    |  |
|  |        Test         | -----> |   (State Invariant)  |  |
|  +---------------------+        +----------------------+  |
+-----------------------------------------------------------+
```

### Key Specifications:
1. **Container Abstraction (Harbor / Docker)**:
   - Ephemeral container spins up with zero external internet access (except explicitly allowed mock endpoints).
   - Pre-loaded with fixture data representing the exact state at $T_0$.
2. **Mock Tool Layer**:
   - Replaces external APIs with lightweight local mock servers (e.g. FastAPI / Flask / WireMock).
   - Records every interaction into a local event ledger.
3. **Synthetic State Initialization**:
   - Uses synthetic data that mirrors production distributions without containing real PII or proprietary tokens.
4. **Deterministic Teardown**:
   - Environment resets to initial state immediately after verifier execution, ensuring test idempotency.

---

## 3. Detecting Information Leaks & Agent Cheating

A ubiquitous failure mode in environment design is **information leakage**:
- Developers accidentally leave the expected answer inside HTML comments, mock database seed files, or error messages.
- Autonomous agents will discover any shortcut available to minimize loss, effectively "cheating" the benchmark without demonstrating genuine problem-solving.

### The Cross-Model Heterogeneous Probing Technique

To verify that an environment does not leak answers:
1. Run a heterogeneous panel of models across the newly constructed environment:
   - **Frontier Model**: Claude 3.7 Sonnet, GPT-4o, Gemini 2.5 Pro.
   - **Mid-Tier Model**: GPT-4o-mini, Gemini 2.5 Flash.
   - **Compact / Open-Weights Model**: Qwen-2.5-7B, Llama-3-8B.
2. Compare the pass rates:
   $$\text{Expected Ordering: } \text{Frontier} \ge \text{Mid-Tier} > \text{Compact}$$
3. **The Leak Red Flag**:
   - If a compact open model (e.g., 7B) passes a complex multi-step task while the frontier model fails or struggles, the environment almost certainly contains an **information leak**.
   - Inspect the compact model's tool calls and execution trace: locate where it retrieved the answer (often a stray string or file in the sandbox).

---

## 4. Environment Checklist Before Benchmark Runs

- [ ] Zero production credentials configured in environment variables.
- [ ] Network egress blocked or restricted to localhost mock servers.
- [ ] State resets reliably between test runs (`docker-compose down -v` or ephemeral container).
- [ ] Cross-model probe executed with zero anomalous inversions.
- [ ] Verifier reads state directly from database/filesystem rather than relying on agent self-reports.

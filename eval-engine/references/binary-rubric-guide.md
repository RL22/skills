# Binary Rubric Guide & Checklist Engineering

This guide explains how to author deterministic, anti-hedging verification rubrics in Easy Mode evaluation.

---

## Why Binary Over 1–10 Continuous Scales

Extensive empirical testing across frontier LLMs demonstrates that when asked to rate complex, subjective, or open-ended agent outputs on a 1–10 scale, LLM judges exhibit severe **clustering in the middle** (defaulting to 7 or 8). 

- **Hedging Instinct**: Continuous scales offer safe harbors. LLMs avoid giving 2s or 10s.
- **Unactionable Feedback**: A score of "7.2/10" gives the agent engineer zero insight into what specific constraint failed.
- **Binary Forcing Function**: When an evaluation criterion is formulated as an atomic `True/False` question, the model cannot hedge. It either meets the standard or it fails.

---

## The Binary Deconstruction Formula

To turn any fuzzy human preference into an objective binary verifier, follow the **Atomic Triad**:

1. **State Assertion**: What observable artifact must exist? (File path, database row, response length, schema property).
2. **Boundary Condition**: What are the strict quantitative or structural limits? (e.g., `<= 3 paragraphs`, `contains exactly 4 bullet points`, `response time < 2000ms`).
3. **Negative Constraint (Disallowance)**: What must strictly *never* appear? (e.g., zero hallucinated placeholder tokens like `[insert name]`, no unverified claims).

### Example: Converting Fuzzy Feedback to Binary Checklists

| Fuzzy / 1-10 Rubric | Binary Deconstructed Checklist |
| :--- | :--- |
| *"Is the email concise and professional?" (1-10)* | 1. Does the email contain between 50 and 150 words? (`True/False`)<br>2. Does the opening sentence reference the prospect's company name? (`True/False`)<br>3. Are there zero exclamation marks in the body? (`True/False`)<br>4. Does the email end with a clear, single call to action? (`True/False`) |
| *"Did the agent conduct thorough company research?" (1-10)* | 1. Does the report list at least 3 active competitors? (`True/False`)<br>2. Does the report cite the company's latest funding round or revenue figure? (`True/False`)<br>3. Are all 3 competitor names verified against live database records? (`True/False`) |
| *"Is the refactored code clean?" (1-10)* | 1. Does the code pass `ruff check` with 0 errors? (`True/False`)<br>2. Are all new functions typed with return annotations? (`True/False`)<br>3. Do all existing unit tests pass with exit code 0? (`True/False`) |

---

## Standard Binary Checklist Schema (JSON/YAML)

Save rubrics as JSON or YAML files structured per this schema:

```json
{
  "task_id": "gtm-email-draft-001",
  "task_family": "gtm-engineering",
  "version": "1.0.0",
  "assertions": [
    {
      "id": "word_count_bounds",
      "category": "structural",
      "prompt": "Is the email body between 50 and 150 words in length?",
      "weight": 1.0,
      "required": true
    },
    {
      "id": "prospect_context_included",
      "category": "semantic",
      "prompt": "Does the email explicitly mention the prospect's recent product launch or company milestone?",
      "weight": 1.0,
      "required": true
    },
    {
      "id": "single_call_to_action",
      "category": "structural",
      "prompt": "Does the email conclude with exactly one explicit call to action or question?",
      "weight": 1.0,
      "required": true
    },
    {
      "id": "zero_placeholders",
      "category": "guardrail",
      "prompt": "Are there zero bracketed placeholders (such as '[Your Name]' or '[Company]') left unfilled in the text?",
      "weight": 1.0,
      "required": true
    }
  ]
}
```

---

## Verifier Execution Pipeline

When executing binary verifiers via `run_binary_eval.py`:
1. **Tier 0 Deterministic Checks First**: Fast regex, JSON schema validators, word counts, and AST linters execute before invoking any LLM judge.
2. **Tier 1 Binary Judge**: Remaining semantic assertions are evaluated by a fast Tier 1 model prompted with:
   ```text
   Answer STRICTLY with 'YES' or 'NO' followed by a one-sentence rationale.
   Assertion: {assertion_prompt}
   Agent Output: {agent_output}
   ```
3. **Strict Aggregation**:
   - `Pass Rate` = Total Passed Assertions / Total Assertions.
   - If any assertion marked `"required": true` fails, the entire run is marked `FAIL`.


# POC Brief — Scenario-Aware JSON Re-Contextualization

A concise plan for re-contextualizing an existing JSON document to a newly selected scenario using an agentic workflow (graph-based, multi-role agents).

## Objective

Transform an existing JSON into a scenario-consistent version when a different scenario is selected. The output JSON must keep the exact same structure as the input while adapting only narrative/content fields to the newly selected scenario.

## Scope

You will receive:

- `input.json` containing multiple sections, including `scenarioOptions`.
- A selected scenario (index or value) that differs from the active one.

## Tasks

- Re-contextualize all scenario-dependent text so it matches the new scenario.
- Keep the following fields absolutely unchanged (byte-for-byte):
  - `scenarioOptions`
- Everything else may only change to align with the new scenario.

The system should use an agentic workflow (for example: graph, multi-role agents) that supports conditional steps, verification, and shared state. Nodes, edges, and validation gates should reflect standard agentic graph concepts.

## Inputs & Outputs

**Input**

- `input.json` (schema reference)
- `selectedScenario` (index or string)

**Output**

- `output.json` with identical schema/shape as `input.json`
- All locked fields unchanged
- All scenario-dependent content rewritten coherently
- Validation report (machine-readable) confirming:
  - schema match
  - locked-field equality
  - general correctness

## Non-Functional Requirements

- **Reliability:** Output must be valid JSON and schema-consistent.
- **Latency:** Execution should complete within single-digit seconds.
- **Determinism:** Runs with identical inputs should exhibit stable behavior.
- **Observability:** Provide concise logs for auditing and debugging.

## Quality Expectations

- Global coherence across names, roles, brands, KPIs, narratives, examples, and instructions.
- Style must match the input JSON’s stylistic tone.
- Structured fidelity: No missing or extra keys; arrays/objects remain fixed.

## Validation & Evidence (deliverables)

Provide:

- Schema fidelity (pass/fail)
- Locked-field equality verification
- Changed-field summary (list of JSON paths)
- Scenario consistency checks
- Runtime statistics (latency, retries)

These may reference standard LLM evaluation principles.

## Agentic Workflow Expectations

**Roles**

1. **Generation** — Produces the rewritten JSON aligned with the new scenario while preserving locked sections.
2. **Verification / Validation** — Confirms schema correctness, checks locked-field immutability, ensures scenario consistency, and applies corrective regeneration when needed.
3. **(Optional) Consistency** — Ensures terminology and narrative coherence globally.

**Flow**

- A graph-style pipeline with pass/fail routing and validation gates.

## What to Submit

- Executable workflow that accepts `input.json` and `selectedScenario` and outputs `output.json`.
- Validation report (JSON or Markdown).
- README explaining guarantees.
- One illustrative run showing:
  - original scenario
  - chosen new scenario
  - diff summary of the resulting `output.json`.

## Evaluation Rubric

- **Correctness:** valid JSON, correct structure, locked fields intact, scenario-consistent rewriting.
- **Coherence:** natural, uniform, artifact-free adaptation.
- **Reliability:** clear validation, predictable reruns.
- **Efficiency:** minimal unnecessary regeneration.
- **Observability:** sufficient telemetry.
- **Professionalism:** clean packaging and documentation.

## Constraints

- Treat the provided JSON as the authoritative structure.
- Do not rename or delete keys.
- Do not modify `scenarioOptions`.
- Must be compatible with an agentic/graph-based workflow.

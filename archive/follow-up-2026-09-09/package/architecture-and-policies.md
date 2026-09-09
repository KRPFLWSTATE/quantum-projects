# Architecture and policies

Mailbox classes in `decision-study/src/agents.py` are **Coordinator**, **Encoder**, **SolverAdapter** and **Validator**. They are deterministic local message-passing components. They are not runtime LLM agents.

## Execution routes

1. **Physical hardware path.** `study.py run-next --hardware` → frozen `runner.py` / `runtime_adapter.py` / `hardware.py` SamplerV2. Budget, protocol, and job-cap gates run first. After a result is collected, `_evaluate_policies` applies P0–P3 to the archived shots. `_persist_policy_rows` constructs a **Coordinator** with `persist_path=store.decisions_path` and records `decision.final` messages. Encoder and SolverAdapter mailbox loops are not the IBM submission path; SamplerV2 is.

2. **Local mailbox demonstration.** Tests register Coordinator, Encoder, SolverAdapter and Validator on a `Bus`. That network is not executed on IBM.

3. **Monolithic equivalent.** Policy functions in `policies.py` are the same P0–P3 used by hardware evaluation. Actor/monolithic equivalence is a local test, not a second QPU campaign.

4. **Post-collection replay.** `tools/publication/replay_adapter.py` reuses frozen scenario generators and policy functions on archived shots. Injected envelopes are labelled and are not IBM provenance.

## P0–P3

- **P0**: unguarded modal bitstring among syntactically valid shots. `accept` is not a safety result.
- **P1**: feasibility, incumbent, and deadline on the current specification.
- **P2**: P1 plus linkage and **payload equality** (`objective_payload`). In `verifier.py`, a metadata-only `current_version` mismatch is assigned and then overwritten by the payload-only comparison. P2 can accept an otherwise eligible candidate after only a version-label change. This is not a strict version-string contract. Frozen P2 was not repaired.
- **P3**: allows revalidation when the payload changes, with schema and linkage checks.

When payloads are unchanged, P2 and P3 are expected to agree on these six jobs.

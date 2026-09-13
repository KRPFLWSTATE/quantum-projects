# Architecture and policies

Mailbox classes in `decision-study/src/agents.py` are **Coordinator**, **Encoder**, **SolverAdapter** and **Validator**. They are deterministic, synchronous, local mailbox roles (plus an equivalent monolithic controller). They are not runtime LLM agents, autonomous negotiators, learned policies, or a distributed-agent deployment.

Stable variable identifiers are `task_0` … `task_5`. Declared meaning strings are `Select maintenance task {i} in the planning window.` Schema id is `six_item_cardinality_conflict_v1` (`decision-study/src/spec.py`).

## Execution routes

1. **Physical hardware path.** `study.py run-next --hardware` → frozen `runner.py` / `runtime_adapter.py` / `hardware.py` SamplerV2. Budget, protocol, and job-cap gates run first. After a result is collected, `_evaluate_policies` applies P0–P3 to the archived shots. `_persist_policy_rows` constructs a **Coordinator** with `persist_path=store.decisions_path` and records `decision.final` messages. Encoder and SolverAdapter mailbox loops are not the IBM submission path; SamplerV2 is.

2. **Local mailbox demonstration.** Tests register Coordinator, Encoder, SolverAdapter and Validator on a `Bus`. That network is not executed on IBM.

3. **Monolithic equivalent.** Policy functions in `policies.py` are the same P0–P3 used by hardware evaluation. Actor/monolithic equivalence is a local test, not a second QPU campaign.

4. **Post-collection replay.** `tools/publication/replay_adapter.py` reuses frozen scenario generators and policy functions on archived shots. Injected envelopes are labelled and are not IBM provenance.

## P0–P3

P1–P3 require a **current feasible incumbent**; otherwise they abstain. Eligible candidates maximize current utility, tie-broken in variable-ID bit-tuple order. Fallback is not a quantum improvement. Hashes and mathematical feasibility do not establish real-world semantic validity, atomic commitment, or legal compliance.

- **P0**: modal valid-format bitstring with displayed-string lexicographic tie-breaking; ignores safeguards. `accept` is not a safety result.
- **P1**: current feasibility, incumbent non-inferiority, and deadline; no provenance guards.
- **P2**: P1 plus linkage and **unchanged substantive payload** (`objective_payload`). A metadata-only `current_version` mismatch is not a strict version-string gate; P2 can accept after a label-only change. Frozen P2 was not repaired.
- **P3**: permits numerical/payload change only with compatible variable identifiers, declared meanings, and schema, plus valid linkage. P3 does **not** infer semantic equivalence or substantive understanding of meaning strings.

When payloads are unchanged, P2 and P3 are expected to agree on these six jobs.

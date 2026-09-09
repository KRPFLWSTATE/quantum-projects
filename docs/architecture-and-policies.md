# Architecture and policies

Mailbox components in `decision-study/src/agents.py` are local message-passing tests (coordinator, proposer, validator, actuator). They are **not** runtime LLM agents and were **not** the QPU dispatch path.

Hardware dispatch is `study.py run-next --hardware` → frozen `runner.py` / `runtime_adapter.py` / `hardware.py` SamplerV2. Each authorised “do a run” submitted one 12-PUB block after budget and protocol gates.

## P0–P3

- **P0**: unguarded modal bitstring among syntactically valid shots. No feasibility, incumbent, deadline, or provenance checks.
- **P1**: feasibility, incumbent, and deadline on the current specification.
- **P2**: P1 plus linkage and payload-equality (`objective_payload`). In `verifier.py`, a metadata-only `current_version` mismatch is assigned and then overwritten by the payload-only comparison. Independent review: P2 can accept an otherwise eligible candidate after only a version-label change. This is **not** unconditional rejection of every version-string mismatch. The executed contract is left unchanged.
- **P3**: allows revalidation when the payload changes, still requiring schema compatibility and linkage.

When payloads are unchanged, P2 and P3 are expected to agree on these six jobs.

Deadlines 5/30/300 s exist in the protocol. These six jobs all returned inside 30 s of client receipt; that is not an independently timestamped organisational decision.

Replay uses the frozen scenario generators (objective drift, added conflict, k=2, meaning change, bad linkage, empty candidates) on **the same hardware shot pools**, labelled `post_collection_policy_replay`. Injected on-time/late schedules are not IBM failures.

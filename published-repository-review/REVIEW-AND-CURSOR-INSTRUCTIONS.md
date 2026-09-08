# Review of the pushed decision-study implementation

Reviewed public commit: [3f5b139cb523c83c354a71429b472d5a2e3e6103](https://github.com/KRPFLWSTATE/quantum-projects/tree/3f5b139cb523c83c354a71429b472d5a2e3e6103).

**Verdict: do not start the physical campaign from this commit yet.** The real submission call exists, but the implementation does not support the reported claim that all required acceptance checks pass. The issues below are reproduced implementation defects and missing integration, not a request to change the circuit or collect more runs.

## What passed

- The push is present. The committed return ZIP SHA-256 is `731d63825e41d9173bc20366f800ff07bcd5fa2c9314be730fa36ee4ba4475ea`, matching the supplied value and committed sidecar. Source files inside that ZIP match the published source files checked.
- The 20 historical GHZ jobs and their code/data namespace are unchanged relative to `4893f3e`. They remain separate from the new campaign.
- The repository's 29 supplied tests pass independently with Qiskit 2.5.2 and qiskit-ibm-runtime 0.49.0.
- All 12 saved logical, physical ISA and compact circuits agree numerically with the independently calculated distributions. Maximum error in this review: `5.412337245047638e-16`, below the declared `1e-10` tolerance. The deliberate measurement-mapping error is detected.
- The frozen protocol's current self-hash, recorded code hashes, parameter-file hash and circuit-equivalence-file hash match the files inspected. The issue is lack of enforcement during readiness/dispatch, not evidence that those current files have already been corrupted.
- The saved parameter-selection description now accurately says the retained parameters are the pre-repair Powell `result.x` selections. No new selection procedure is being falsely attributed to those values.
- The saved usage estimate now uses target durations for all instructions in the inspected table (`instructions_fallback` totals zero). The 7.22-second value is a model with a partition assumption and margin, not measured charged usage.

This review used no IBM account credentials and submitted no QPU jobs. The reported 554 seconds of free allowance is the archived observation at 2026-09-08T22:07:24.938959+00:00; this review did not independently query a current account balance.

## Blocking findings

### R1 — Real usage API crashes, or unresolved usage is silently treated as zero

In `src/runner.py:dispatch_block`, `job.usage()` is processed with `.get(...)`. The installed IBM RuntimeJobV2 API returns a scalar number of seconds, not the dictionary returned by the project's fake job. When the fake is changed to return the documented `2.0`, the runner raises:

    AttributeError: 'float' object has no attribute 'get'

The mock submission had already happened; no raw result file was saved; the outstanding reservation remained. With `usage()` returning `None`, the runner instead returns success, clears the reservation, records zero usage and leaves the campaign balance at 300 seconds.

IBM's installed 0.49.0 implementation also returns zero while usage is pending. Therefore zero alone is insufficient to conclude that reconciliation is complete. Save the raw result before querying usage, use the documented scalar and metrics/status fields, and keep a reservation until usage is actually resolved. Genuine final zero usage must remain distinguishable from pending/unknown usage. [IBM RuntimeJobV2 documentation](https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/runtime-job-v2)

The project's fake and acceptance tests hid this defect by supplying dictionary usage or overriding `usage_seconds=2.0`.

### R2 — Resume does not complete accounting or preserve equivalent evidence

`resume_block` retrieves shots but does not retrieve/reconcile charged usage, decrement the campaign budget, preserve the original PUB mapping in the recovered raw record, or record the same history/metadata as normal completion.

Reproduction: a job with two seconds of usage resumed successfully, but recorded usage remained 0.0 and available campaign time remained 300.0. Its raw record had no `pub_mapping`.

If a raw file already exists while the ledger is still outstanding, resume returns success without clearing/reconciling the outstanding state. This can permanently block the next command following a crash between archive publication and the ledger update.

Normal completion and recovery should call one idempotent finalisation routine. Charge/count a job exactly once, preserve mapping/metadata, and reconcile an existing raw file against the ledger.

### R3 — Recovery tags are saved locally but never attached to IBM submissions

The runner creates unique tags in a local record, but neither PhysicalAdapter nor the Sampler options receives them. The actual options object's `environment.job_tags` is `None`. If submission succeeds but the job ID is lost before persistence, `resume_block` immediately returns `AMBIGUOUS_SUBMISSION_NO_JOB_ID`; it does not search the provider by tag.

The claimed fresh-process recovery test creates new Python objects in the same process and copies the original in-memory job dictionary. It tests recovery with a known ID; it does not exercise recovery after provider acceptance but before ID persistence.

Pass the durable intent tags into the actual Sampler options before dispatch. Recover an uncertain submission by provider tags within the verified instance, check the recovered circuit/PUB identity, and retain the reservation whenever recovery is ambiguous. Do not blindly resubmit.

### R4 — Readiness accepts a corrupt protocol and omits material verification

Patching only the protocol path to an isolated temporary JSON file containing `{"protocol_hash":"not-a-valid-frozen-protocol"}` still produces `READY_FOR_FIRST_HARDWARE` with no blockers. The current readiness function checks that a protocol file exists, but does not verify its self-hash or enforce its recorded code/parameter/evidence hashes.

Other gaps: missing duration evidence is not rejected; equivalence is accepted from a Boolean/count without linking the evidence to the precise submitted circuit hashes; test success is not tied to the tested source version. The physical run uses a cached estimate rather than refreshing/validating its target assumptions at dispatch.

Require all necessary records and verify the frozen content before dispatch. Do not fix this by silently regenerating a new freeze over unexpected changes. Deliberate pre-hardware fixes can issue a documented revision, with tests/equivalence rerun as needed.

`compile_all_fixtures` still rewrites QPY artefacts on validation even when a prior submission exists. Pinning the backend name alone does not freeze transpilation output. Validate frozen circuits without overwriting them; treat a necessary later recompile as a distinct protocol amendment.

### R5 — Invalid result cardinality can still be reported as success

A mocked result with only one PUB and one shot produces:

    ok: true
    shots_valid: false
    n_pubs: 12

The displayed PUB count is hard-coded, and `shots_valid` does not control success. Preserve malformed evidence, account for any usage, and mark validation failure. Check actual PUB count, shot counts, binary format, and counts-versus-ordered-shot reconciliation before marking a block valid.

### R6 — The real hardware path is not connected to the claimed decision workflow

`dispatch_block` blocks inside `job.result()` while holding the campaign lock. It does not invoke the coordinator, business verifier, P0–P3 policies or a deadline timer. A spy on the actual policy function records zero calls during the dispatch path. The actor timeout test uses a manually held toy worker and a validator that simply returns `ok=True`; it does not verify the physical workflow.

Raw records do not contain the intended complete timing/provenance evidence: the recorded `created_utc` is added after result retrieval, and job metrics/options/Runtime metadata, dispatch/receipt timing and execution spans are not retained there. This would undermine claims about response deadlines, current-specification decisions or actual orchestration.

Wire the actual solver adapter to the decision coordinator and verifier, process updates/timeouts while retrieval runs, persist final decisions, and archive late outputs without replacing them. Preserve real timing/metadata and evaluate hardware candidates through the same policies and analyses as the frozen local protocol.

### R7 — The reporting/replay pipeline is not yet the promised campaign evaluation

`cmd_run_next` refreshes report/export after a successful return but does not invoke hardware-result analysis. The reporting function still hard-codes “Decision hardware evidence count: 0” and “NEW QPU JOBS SUBMITTED: 0.” They are true now but would remain false statements after a successful physical run. The support table also hard-codes hardware evidence as unavailable.

Replay now iterates prefixes and deadlines, but that loop evaluates only P2 and sets arrival to `min(deadline, 1.0)`—one second for all three deadlines. It therefore cannot assess deadline sensitivity. The existing full scenario replay is based on p=1, while the p=2 prefix loop does not supply equivalent P0–P3 comparisons over specification changes. The 24 generated extra cases still need their promised executed evaluation if claimed in the study.

Produce the predeclared paired scenario/solver/policy evaluation from actual frozen pools and later hardware records. Distinguish observed timing from injected schedules. Generate job counts, actual usage and findings from records, not constants. The author’s novelty question remains unresolved; generic QAOA or passing software tests does not settle it.

## Reproducible checks supplied with this review

`test_release_regressions.py` expresses six required behaviours using temporary stores and a fake provider. On the reviewed commit it runs six tests with **five failures and one error**. These are separate from the original 29 passing tests. See `regression-results.txt` for complete tracebacks.

The regression suite covers scalar usage, unknown usage, malformed result cardinality, resume accounting, existing-raw crash recovery and corrupted-protocol rejection. It is not a complete replacement for the end-to-end acceptance tests required for R3/R6/R7. `reproduced-findings.json` records additional targeted probes. `supplied-tests.log` and `circuit-checks.json` document the checks that pass.

## Instructions to give Cursor

Review the checked-out HEAD and the supplied review package. Fix R1–R7 in the current implementation without redesigning the circuit, changing the saved parameter set for favourable results, submitting QPU jobs, touching the 20 GHZ records or invoking paid services. Keep the existing plan/campaign limits and user-triggered run semantics. Do not stage/commit/push additional fixes unless separately authorized for that new push.

Run `python -u <path>/test_release_regressions.py <repo>/decision-study` in the existing environment before edits so the failures are visible. Repair the production functions, then run the tests again. Do not delete assertions, replace production calls with a detached demonstration, or change the fake back to a dictionary usage return. If refactoring changes imports or injection interfaces, adapt only those mechanical test bindings while preserving the tested behaviour.

Use one idempotent finalisation path for new and resumed jobs. Test the documented Runtime usage scalar, pending metrics, final zero, API failure, malformed PUB/shot data, crash after raw write, crash after provider acceptance before ID persistence, and repeated resume. Attach intent tags to actual provider options and test their recovery. Test the actual physical adapter with a patched IBM service/Sampler boundary; no real jobs are needed to exercise it.

Make the shared readiness function enforce the frozen protocol and matching test/equivalence evidence. Add failure tests for missing/changed records and ensure they prevent the patched provider's run call. Existing required source/circuit hashes currently match; do not mislabel the review's deliberately corrupted temporary fixture as actual corruption of the user's experiment.

Connect actual result retrieval, coordinator events, current-spec verification, fallback and final decision persistence. A thread/future or nonblocking polling adapter can allow deadline/update processing; a toy hold flag alone cannot validate that physical execution path. Feed archived hardware candidates into the real analysis/report pipeline, preserve metrics and provenance, and remove hard-coded hardware counts.

Recheck free-instance binding and current quota on the user's machine. Preserve the 45-second per-job cap, 300-second maximum campaign allowance, 90-second reserve and six-job ceiling. Unknown usage must keep its reservation; a failed or resumed job must not disappear from the count. Distinguish a verified final zero charge from pending usage.

Complete these concrete fixes and their acceptance tests locally. Report each R-number with the implementation and executed evidence that resolves it. Generate an updated content-addressed protocol only for the intentional pre-hardware changes and retain its prior revision. Re-export the final code, tests, logs, reports and sidecar ZIP hash after all edits. Do not print READY_FOR_FIRST_HARDWARE unless the final production paths pass these checks. This instruction does not authorize a physical run.

The next physical action, after these defects are resolved, is one explicitly user-triggered decision-study block. The scientific design and 20 prior observations remain usable; the current problem is execution correctness and evidence completeness.

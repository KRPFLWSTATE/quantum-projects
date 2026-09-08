# Complete the existing implementation, then enable one user-triggered run

Give this folder to Cursor and paste the instruction below. It contains a working offline circuit verifier, its independently generated results, and the independent unit-test log. No IBM job was submitted in this review. The circuit and research design are not being replaced.

## Paste this instruction into Cursor

Finish the existing decision-study implementation now. I am authorizing the unfinished local work already specified by the master prompt and repair prompt. Do not ask whether to finish it, stop at an implementation plan, or offer to accept unimplemented requirements. Complete the work, run the checks, and return a short evidence-backed status. No physical QPU submission is authorized by this completion instruction; the subsequent explicit “do a run” command will authorize one block.

The last repair stopped incomplete. Your report acknowledges that the physical runner still raises, free-instance binding is incomplete, the usage estimate uses proxies, protocol freeze is incomplete, and campaign replay is unfinished. These are existing requirements, not requests to redesign the study.

ChatGPT has now performed additional independent work:

- Reviewed packet SHA-256: 7b9d85abc41dde13e13e2fb560a559e8ea7434b50a8979613124decdc3cef739.
- All 126 file entries in the ZIP's manifest match their hashes and sizes.
- The separately supplied return report matches the copy inside the ZIP. Its claimed ZIP hash is stale; do not copy it into the next report.
- The supplied 22 tests pass when independently rerun with Qiskit 2.5.2 and qiskit-ibm-runtime 0.49.0. The legacy files used for the preservation check came from the previously inspected public repository snapshot. Passing those tests does not establish that the unimplemented physical path works.
- All 12 saved physical ISA circuits, logical circuits, and compact analysis circuits agree with the independent NumPy simulation for their saved fixture parameters, at tolerance 1e-10. Maximum probability difference: 5.412337245047638e-16. The verifier's deliberate incorrect measurement mapping produces a detectable error of approximately 0.1930.
- The verifier uses at most 12 active qubits and never calls an IBM service. Run it again locally and include its numerical evidence in readiness. This does not certify live backend compatibility or hardware performance.

Use the included verify_isa.py and circuit-verification.json. Put the verifier in a suitable study tools/tests directory and run, using the existing project environment:

    python -u <path-to-verify_isa.py> <path-to-decision-study> --output <path-to-decision-study>/data/derived/circuit_equivalence.json

The remaining completion requirements are below. Work sequentially through them and continue after routine local failures until fixed. If an actual external API/access blocker prevents completion, report that concrete blocker after completing independent local work. Do not request permission to finish code that is already authorized.

### 1. Implement the actual IBM path and its real recovery path

Replace the intentional exceptions in hardware.py and runner.py. Keep execution opt-in at the CLI/agent layer, but implement the entire path now. Do not defer construction of the real runner to the first hardware command. Do not require me to edit environment flags or Python manually.

Use a verified backend in job mode, with the physical ISA circuits from the frozen manifest, a shuffled per-block mapping of 12 PUBs, and 1024 shots per PUB. Configure Sampler options on its constructor/options object. The real interface is SamplerV2(mode=backend, options=options).run(pubs, shots=1024); it does not take max_execution_time/twirling/DD as arbitrary run keywords, although the current FakeSampler accepts those. Keep max_execution_time=45, disabled twirling/DD where supported, no sessions, no hidden shot multipliers, and the default repetition delay.

Use an explicit provider adapter to reconcile real RuntimeJobV2.job_id() and PrimitiveResult/BitArray behaviour with the fake provider. A fake job with a job_id property and a custom dictionary result is not sufficient proof that a RuntimeJobV2 can be processed. Exercise production argument building, job-ID handling and result decoding with realistic mocks/specs based on the installed interfaces.

The actual dispatch function must perform all readiness and budget checks before saving a submission intent; then durably reserve 45 seconds, record the exact circuit/PUB mapping and provider tags, submit once, and persist the job ID immediately. A transport failure is an unresolved attempt, not permission to resubmit. Resume must retrieve by job ID or recover by durable tags without calling run again. Simulate an actual process restart with fresh local objects and persisted state; the current interrupted_dispatch_then_resume merely looks up a job in the same in-memory dictionary and does not test resume_block.

Archive ordered measurements, complete counts, available Runtime metadata, submitted circuit hashes, job status, provider/client timing and documented charged usage. Validate 12 results and all shot totals. Preserve failed/partial jobs. Reconcile actual usage with reservations and decrement campaign availability. Permit at most six submitted jobs and one outstanding/ambiguous attempt. Mock execution must use a separate temporary ledger and data directory, never the physical campaign ledger or decision_hardware label.

Fix study.py so a successful real run returns exit code 0; it currently unconditionally returns 2 from the hardware branch. Fix resume so it actually retrieves provider results. Automatically refresh analysis/report/export after completion. Do not silently retry submission because reporting, export, retrieval or local persistence failed.

### 2. Bind to the actual free instance and calculate duration from the actual circuits

Resolve an instance explicitly verified as Open Plan; bind the backend and usage query to that same instance. Finding any free instance while using a saved paid/default instance is insufficient. Unknown plan, mismatched instance or unknown balance must block submission. Remove the live_remaining=554.0 default from the physical dispatch path and the readiness fallback to 554: the number was a past observation, not a standing authorization or current balance.

Parse documented usage fields/units only. There is still a reproducible bug: _extract_remaining_seconds({'remaining':8,'unit':'minutes'}) returns 8, although the nested-period test passes. Handle top-level and nested data consistently, require known units for ambiguous keys, and reject nonfinite values.

Use the actual ISA instructions/backend target durations, measurement/reset/initialisation, repetition delay, all 12 circuits and shots, and an explicit overhead/uncertainty model. Do not just multiply fixed gate proxies by 1.25. IBM's approximate two-second overhead applies per execution sub-job; a PUB is not automatically a sub-job. Show the assumption about partitioning and a conservative margin. If the estimate with margin cannot fit under 45 seconds, stop before dispatch; do not increase shots/jobs/time caps or switch plans.

Keep the original limits: initial allowance min(300, 540, max(0, verified_remaining_seconds-90)), reserve 45 seconds per attempt, preserve 90 seconds of free balance, maximum six submitted jobs. Freeze the initial campaign allowance rather than growing it on quota replenishment. Count failed jobs and unresolved usage appropriately.

Official interfaces and timing references:

- https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/sampler-v2
- https://quantum.cloud.ibm.com/docs/en/api/qiskit-ibm-runtime/qiskit-runtime-service
- https://quantum.cloud.ibm.com/docs/en/guides/estimate-job-run-time
- https://quantum.cloud.ibm.com/docs/en/guides/max-execution-time

### 3. Connect the verification, frozen protocol and readiness gates

Use one readiness function in CLI, report and physical dispatch. Missing tests/equivalence records must fail; checking only equivalence_ok is False incorrectly lets a missing value through. Verify all twelve physical ISA files, hashes and fixture/depth pairs, not any single *_isa.qpy. Incorporate the submit gate's failure into readiness; it is currently returned as a diagnostic without determining the status.

Freeze full fixture definitions, selected parameters, physical/logical circuits, measurement maps, policy/scenario definitions, seeds, software/code hashes, backend/instance binding and stopping rules. Validate hashes before dispatch. Prevent prepare/validate/status from replacing frozen artefacts or reselecting a backend after submission begins. Preserve the original GHZ hash baseline and histories.

The saved parameters were selected by the pre-repair optimizer. Either rerun the corrected deterministic optimizer before the first hardware run and document a protocol revision, or explicitly freeze the already-saved parameter set and accurately describe its actual selection procedure. Do not claim the corrected procedure generated old outputs. Do not select parameters by known optimum or attractive optimal-hit probability. If circuits change, rerun the included numerical verifier against the new manifest and retain the previous results as history.

Do not reopen circuit design, increase qubits/depth, seek a favourable backend, add extra hardware runs or tune after observed hardware outcomes.

### 4. Complete the existing decision workflow and evaluation

Wire the actual encoder, candidate adapter and policies into the coordinator. The candidate worker must not prevent timeout/specification-update processing while waiting for IBM. Persist final decisions and recover them after process restart; an in-memory duplicate guard alone is insufficient. Archive late results without replacing a previously committed fallback.

P2/P3 must compare actual identity against independently retained expected request/source/circuit/PUB records, not optional values in the result envelope. The current policy accepts an arbitrary nonempty circuit_hash when expected_circuit_hash is absent. Add a regression and require a trusted expected circuit hash. Validate incoming stored hashes before canonicalising data: apply_policy currently recomputes hashes first, which can conceal a supplied hash mismatch. Maintain separate immutable source/current specifications, validate schemas and finite inputs, and distinguish a controlled locally created update from an untrusted result envelope.

Keep independent incumbent feasibility/utility checks and current policy distinctions. Finish replay with the frozen p=1/p=2 pools and the promised prefixes, deadlines and scenarios; include classical comparators and explicit evidence labels. Arrays naming prefixes/deadlines without actually executing them are not evaluation. Ensure the returned hardware records can flow into these same analysis functions. Preserve the original arbitrary-parameter pools as unit-test data only. Finish the predeclared simulation-only checks without adding hardware consumption.

Record solver versus fallback contributions, late/invalid acceptance, revalidation, abstention, utility, local overhead and counterfactual assumptions. An exact classical solution or superior classical baseline must remain visible. No requirement exists for quantum advantage or positive results.

### 5. Run the decisive acceptance tests on the finished code

In addition to the existing 22 tests and the provided circuit verifier, execute behaviour tests through the actual command/dispatch/resume/report functions:

1. No physical call on imports, prepare, validation, status, report, export or this completion task.
2. One authorised mocked block submits exactly 12 actual circuit PUBs at 1024 shots, with the configured 45-second cap and correct physical mapping, decodes realistic Runtime results, archives, reconciles usage, reports and exits 0.
3. A fresh-process resume after a simulated submit/ID-save interruption finds the existing tagged job and does not submit another. Pending/ambiguous work blocks a new command. A failed job consumes its recorded attempt/usage and is not silently replaced.
4. Paid/unknown/mismatched instance, unverified units/balance, insufficient allowance, nonfinite usage, unknown actual usage, altered protocol/circuit hash, failed/missing validation, missing one ISA file, exhausted six-job budget, and unresolved reservations block dispatch before provider.run.
5. Deadline and specification changes are processed while a worker is outstanding; stale/late/duplicate results cannot overwrite a persistent final decision. P2/P3 reject absent trusted expected circuit linkage and corrupted hashes.
6. prepare/validate/status after a recorded attempt cannot reset the ledger, change the frozen campaign or rewrite historical evidence.

Tests must exercise real production paths with an injected fake backend/service and temporary state. Do not simulate these guarantees by inspecting strings, setting a result flag to True, or testing a detached demonstration helper. Keep the tested code hashes with the test output.

### 6. End with the actual operational result

Update the project command instructions now:

- “do a run” and “do a decision run” both execute exactly one decision-study block after fresh live checks.
- “do a legacy GHZ run” is the old probe.
- “resume the run” retrieves an existing attempt without creating a job.

Do not commit/push or spend money. No runtime LLM or paid API is required. Do not edit the canonical manuscript during this completion step. Novelty/literature and manuscript readiness remain separate research statuses; do not use them as a reason to leave implementable runner code unfinished or claim publication readiness.

Generate the final report from actual state, not hard-coded zero counters, stale HEAD, or manually asserted readiness. Regenerate the return ZIP after the final code/tests/report. Put its final SHA-256 in terminal output or a sidecar outside the ZIP: placing the ZIP's own final hash inside its report creates a self-reference problem. Include exact code/config/evidence hashes in the packet manifest and inspect its inventory for credentials/private account data.

Print this short final completion block with real evidence paths and values:

    ENGINEERING_STATUS: READY_FOR_FIRST_HARDWARE or BLOCKED
    REAL_IBM_RUNNER_IMPLEMENTED: true/false
    ALL_REQUIRED_ACCEPTANCE_TESTS_PASS: true/false
    CIRCUIT_EQUIVALENCE: 12/12, max error ..., tolerance ...
    REAL_DISPATCH_AND_FRESH_PROCESS_RESUME_MOCK_TEST: pass/fail
    OPEN_INSTANCE_AND_LIVE_QUOTA_VERIFIED: true/false, timestamp ...
    NEXT_BLOCK_ESTIMATE_WITH_MARGIN_SECONDS: ... (must be below 45)
    FROZEN_PROTOCOL_AND_CODE_HASH: ...
    PHYSICAL_JOBS_SUBMITTED_DURING_COMPLETION: 0
    USER_COMMAND_FOR_ONE_BLOCK: do a run
    RESEARCH_NOVELTY_STATUS: unresolved or a specifically supported assessment
    RETURN_PACKET_PATH_AND_SHA256: ...

Only print READY_FOR_FIRST_HARDWARE if all required engineering checks pass and the actual physical runner is implemented. A real external blocker should instead be named with its failed check. Do not use AWAITING_USER_RUN_COMMAND to disguise unfinished code.

After truthful READY_FOR_FIRST_HARDWARE, wait for my next “do a run.” That separate command authorizes exactly the first real block, with fresh live checks; do not submit all six. Report the IBM job ID, actual usage, result/shot validation and return packet after that block. I will bring those observed results back to ChatGPT before running further blocks.

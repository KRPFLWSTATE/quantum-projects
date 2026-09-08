"""Write ChatGPT return report and supporting manuscript files."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .budget import campaign_allowance
from .figures import write_architecture_svg, write_svg_bar
from .hashing import sha256_file
from .paths import (
    DERIVED_DIR,
    FIGURES_DIR,
    MANUSCRIPT_DIR,
    PROTOCOL_PATH,
    REPORTS_DIR,
    REPO_ROOT,
    TABLES_DIR,
    HASHES_PATH,
)
from .legacy_audit import verify_hashes


def write_reports() -> dict:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    MANUSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    audit = json.loads((DERIVED_DIR / "legacy_audit.json").read_text()) if (DERIVED_DIR / "legacy_audit.json").is_file() else {}
    prepare = {}
    if (DERIVED_DIR / "qaoa_parameters.json").is_file():
        prepare["qaoa"] = json.loads((DERIVED_DIR / "qaoa_parameters.json").read_text())
    greedy = json.loads((DERIVED_DIR / "greedy_baselines.json").read_text()) if (DERIVED_DIR / "greedy_baselines.json").is_file() else []
    replay = json.loads((DERIVED_DIR / "policy_replay.json").read_text()) if (DERIVED_DIR / "policy_replay.json").is_file() else {}
    usage = json.loads((DERIVED_DIR / "usage_probe.json").read_text()) if (DERIVED_DIR / "usage_probe.json").is_file() else {}
    protocol = json.loads(PROTOCOL_PATH.read_text()) if PROTOCOL_PATH.is_file() else {}
    hashes = json.loads(HASHES_PATH.read_text()) if HASHES_PATH.is_file() else {}
    hash_check = verify_hashes(hashes) if hashes else {"ok": False, "reason": "no_snapshot"}

    if audit.get("runs"):
        write_svg_bar(
            FIGURES_DIR / "legacy_fidelity_by_run.svg",
            "Historical GHZ Hellinger fidelity by run (sampled Aer baseline)",
            [f"R{i+1}" for i in range(len(audit["runs"]))],
            [row["hellinger_fidelity_archived"] for row in audit["runs"]],
            "Hellinger fidelity F=(sum sqrt(P Q))^2",
        )
        write_svg_bar(
            FIGURES_DIR / "legacy_queue_by_run.svg",
            "Historical GHZ client-recorded queue wait by run",
            [f"R{i+1}" for i in range(len(audit["runs"]))],
            [row["queue_wait_seconds"] for row in audit["runs"]],
            "seconds",
        )
    write_architecture_svg(FIGURES_DIR / "architecture_message_flow.svg")
    extra = {
        "compile": _load(DERIVED_DIR / "compile" / "isa_summary.json"),
        "ideal": _load(DERIVED_DIR / "ideal_qaoa_vs_uniform.json"),
        "sampler": _load(DERIVED_DIR / "sampler_options.json"),
        "estimate": _load(DERIVED_DIR / "usage_estimate.json"),
        "backend_pin": _load(DERIVED_DIR / "backend_pin.json"),
        "crosscheck": _load(DERIVED_DIR / "statevector_crosscheck.json"),
        "qaoa": prepare.get("qaoa"),
        "validate": _load(DERIVED_DIR / "validate.json"),
        "provenance": _load(DERIVED_DIR / "legacy_supplementary_provenance" / "summary.json"),
        "equivalence": _load(DERIVED_DIR / "circuit_equivalence.json"),
    }
    if audit.get("runs"):
        _write_csv_rows(TABLES_DIR / "legacy_jobs.csv", audit["runs"])

    _write_manuscript_support(audit, protocol)
    report = _compose_report(audit, greedy, replay, usage, protocol, hash_check, extra)
    (REPORTS_DIR / "CHATGPT_RETURN_REPORT.md").write_text(report, encoding="utf-8")
    return {"report_path": str(REPORTS_DIR / "CHATGPT_RETURN_REPORT.md"), "hash_check": hash_check}


def _load(path: Path):
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _write_csv_rows(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    keys = list(rows[0].keys())
    lines = [",".join(keys)]
    for row in rows:
        lines.append(",".join(str(row.get(k, "")).replace(",", ";") for k in keys))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_manuscript_support(audit: dict, protocol: dict) -> None:
    (MANUSCRIPT_DIR / "equations.md").write_text(
        r"""# Equations (clean sources)

## Decision utility and constraints

\[
U(x)=\sum_{i=0}^{5} b_i x_i + \sum_{i<j}s_{ij}x_i x_j
\]

\[
\sum_i x_i=k,\qquad x_i x_j=0\ \forall(i,j)\in C,\qquad x_i\in\{0,1\}
\]

## Penalty energy

\[
E(x)=-U(x)+A\left[\left(\sum_i x_i-k\right)^2+\sum_{(i,j)\in C}x_i x_j\right]
\]

\[
A=1+\sum_i|b_i|+\sum_{i<j}|s_{ij}|
\]

## Hellinger fidelity (distributional)

\[
F(P,Q)=\left(\sum_x\sqrt{P(x)Q(x)}\right)^2
\]

This is agreement of two probability distributions over bitstrings, not quantum state fidelity, not entanglement certification, and not decision accuracy.
""",
        encoding="utf-8",
    )
    (MANUSCRIPT_DIR / "correction_map.md").write_text(
        """# Manuscript correction map

Canonical title remains: Hybrid Multi-Agent Artificial Intelligence and Quantum Cloud Infrastructure: An Exploratory Organisational Framework for Complex Decision Processing.

The canonical DOCX was not located on this machine (searched workspace and Downloads for that title). ChatGPT should revise the DOCX; this repository was not used to rewrite it.

For each issue: affected section / factual correction / evidence / claimable now / untested / suggested replacement.

1. Abstract/title AI overstatement. Correction: implemented components are deterministic software actors/mailboxes plus a monolithic controller, not runtime LLMs. Evidence: decision-study/src/agents.py. Claimable: message-driven orchestration exists. Untested: organisational AI-agent behaviour. Replace “multi-agent AI” with “deterministic multi-component orchestration” unless LLM agents are later implemented.

2. Proposed vs implemented vs simulated vs hardware. Hardware decision circuits: not yet run. Historical 20 jobs are GHZ probes only. Evidence: protocol.json. Physical SamplerV2 runner is implemented and gated on study.py run-next --hardware after the user says do a run.

3. Integrate 20 GHZ jobs as operational observations only. Do not call them decision instances. Evidence: derived/legacy_audit.json.

4. Remove stale one-run/two-run statements. Repository now has 20 GHZ jobs plus a separate unpublished decision-study codebase.

5. Run 20 queue wait 1660.303566 s and client wait 1692.7952399253845 s are observed for the GHZ probe, not QAOA. Do not generalise latency.

6. Agent roles: coordinator, encoder, solver adapter, validator. No runtime AI/LLM.

7. Variable-to-circuit mapping and independent verification exist locally. Evidence: model.py, tests.

8. Hellinger equation as above; inspect later DOCX/PDF visually.

9. Distinguish distributional fidelity, state fidelity, feasibility, utility.

10. Replace “leakage” with off-target bitstrings unless leakage was physically measured (it was not).

11. Legacy backend selection was least_busy without a Heron-family filter.

12. Timing: client wall-clock ≠ IBM running-to-finished ≠ charged usage.

13. Validation gates are implemented in software policies; they have not been hardware-evaluated.

14. Prior-art: QAOA (Farhi et al.), QAOA ansatz (Hadfield et al.), QProv/workflows (Weder et al.). Candidate contribution is specification-change revalidation policy; novelty unresolved until human review of closest papers’ full text.

15. Organisational readiness/adoption untested. Synthetic maintenance-window mapping only.

16. Tone: design-science evaluation, limitations explicit.

17. Verify bibliography against sources; do not invent DOIs.

18. Data availability: GHZ archive is on GitHub at 4893f3e plus later docs; decision-study files are local until a later push.

19. AI disclosure: Cursor/AI used for coding, circuit design, experiment scripting and analysis, not language-only.

20. No commercial savings or multi-industry validation. No decision-hardware findings yet.
""",
        encoding="utf-8",
    )
    (MANUSCRIPT_DIR / "claims_to_evidence.csv").write_text(
        "claim,evidence_type,status,location\n"
        "20 GHZ jobs exist,historical_hardware,observed,dba-qpu-run/results/runs\n"
        "QAOA decision hardware performance,decision_hardware,unavailable,not submitted\n"
        "Independent QUBO/Ising agreement,ideal_simulation,tested,decision-study/tests\n"
        "Policy behaviour under spec change,policy_replay,simulated,derived/policy_replay.json\n"
        "Injected linkage faults,injected_fault,simulated,src/replay.py\n"
        "ISA compile on ibm_fez rule,ideal_simulation,local_compile,derived/compile/isa_summary.json\n"
        "Novelty of spec-change policy,literature,unresolved,manuscript_support/prior_art.md\n",
        encoding="utf-8",
    )


def _status_section(usage: dict, extra: dict) -> str:
    from .readiness import engineering_status

    status = engineering_status(live_usage=usage)
    return (
        f"1. Status: {status['engineering_status']}. "
        f"blockers={status.get('blockers')}. "
        f"equivalence={status.get('equivalence')}. "
        f"estimate_s={status.get('estimate_seconds')}. "
        f"pinned={status.get('pinned_backend')}. "
        f"protocol_hash={status.get('protocol_hash')}. "
        f"runner_hash={status.get('runner_hash')}. "
        f"Campaign allowance={status.get('allowance')}. "
        "Physical SamplerV2 path is implemented; Cursor will call study.py run-next --hardware only after the user says do a run. "
        "This report is not hardware permission."
    )


def _compose_report(audit, greedy, replay, usage, protocol, hash_check, extra=None) -> str:
    extra = extra or {}
    compile_summary = extra.get("compile") or {}
    rows = compile_summary.get("rows") or []
    compile_brief = [
        f"{r['instance_id']} p={r['p']} depth={r['depth']} 2q={r['two_qubit']} compact_q={r.get('compact_num_qubits')} padded_q={r.get('isa_num_qubits_padded')}"
        for r in rows
    ]
    ideal = extra.get("ideal") or []
    poor = [
        f"{r['instance_id']} p={r['p']} feas={r.get('ideal_feasibility_probability')} opt={r.get('ideal_optimal_hit_probability')} uniform_feas={r.get('uniform_feasibility_probability')} worse_opt={r.get('worse_than_uniform_optimal_hit')}"
        for r in ideal
    ]
    lines = [
        "BEGIN CHATGPT RETURN REPORT",
        "",
        _status_section(usage, extra),
        "",
        "2. Repository HEAD at setup start: 4893f3e08be47a08f369767b5e8cb56f8cd118db on main (inspected; not force-checked out). No git add/commit/push was performed. Decision-study files are local uncommitted work. Do not treat them as public until a later push.",
        "",
        f"3. Legacy audit n_jobs={audit.get('n_jobs')} unique_ids={audit.get('unique_job_ids')} issues={audit.get('issues')} "
        f"backend_counts={audit.get('backend_counts')} fidelity_mean={audit.get('fidelity_mean')} "
        f"fidelity_stdev={audit.get('fidelity_stdev_sample')} min={audit.get('fidelity_min')} max={audit.get('fidelity_max')} "
        f"queue_median={audit.get('queue_median')} queue_iqr_related_fidelity={audit.get('fidelity_iqr')} "
        f"fidelity_median={audit.get('fidelity_median')} queue_max={audit.get('queue_max')} "
        f"client_wait_max={audit.get('client_wait_max')}. "
        "Runs 3–20 exports are custom count/result dumps, not lossless IBM console payloads. Supplementary retrieval files are labelled separately under data/derived/legacy_supplementary_provenance/ and do not rewrite historical exports.",
        f"hash_check={hash_check}",
        f"supplementary_provenance={json.dumps((extra.get('provenance') or {}) if extra else {})[:1500]}",
        "Exact-GHZ baseline fidelities are labelled separately (hellinger_vs_exact_ghz_baseline) and do not replace sampled Aer baselines.",
        "Collection was user-triggered at irregular times. Do not infer backend superiority from imbalanced samples. Run 20 is retained.",
        "",
        "4. Architecture: four mailbox components (coordinator, encoder, solver adapter, validator) plus equivalent monolithic controller. Figure: reports/figures/architecture_message_flow.svg. Deterministic software. Cursor wrote code; the research system does not contain runtime LLMs. Use multi-component orchestration; do not carry LLM-based agents into the manuscript.",
        "",
        "5. Problem: six binary tasks, k=3, conflicts, pairwise interactions. Synthetic maintenance-window mapping only. Independent enumeration recomputes expected feasible counts [12,8,9,6,6,6] and optima [23,23,23,24,23,22] in tests/prepare rather than pasting them as hardware facts. Penalty A = 1+sum|b|+sum|s|: D1/D3/D5=47, D2/D4/D6=46. Assumptions: equal capacity slots, supplied scores, pairwise interactions; this is not general enterprise optimisation.",
        "",
        "6. Circuit: 6 logical qubits, p=1 and p=2 QAOA, U_C(gamma)=exp(-i gamma H_C/A), mixer RX(2 beta). Local noiseless statevector Powell protocol; simulator-optimised QAOA to be evaluated on hardware later. Independent numpy vs Qiskit overlap in statevector_crosscheck.json. Do not statevector-simulate 156-qubit padded ISA circuits; compact remap is required.",
        f"compile_rows={compile_brief}",
        f"selection_rule={compile_summary.get('selection_rule')}",
        f"ideal_vs_uniform={poor}",
        "Poor ideal results remain visible (including optimal-hit worse than uniform). Never print an ideal distribution as observed hardware counts.",
        f"sampler_api={json.dumps(extra.get('sampler') or {})[:1500]}",
        "",
        "7. Prior art: see manuscript_support/prior_art.md. Links: Farhi https://arxiv.org/abs/1411.4028; Hadfield https://arxiv.org/abs/1709.03489; QProv https://doi.org/10.1049/qtc2.12012; Weder workflow https://doi.org/10.1007/s42979-022-01625-9; Gerlach https://proceedings.mlr.press/v267/gerlach25a.html; Shi https://cpb.iphy.ac.cn/article/doi/10.1088/1674-1056/adefd7; Hevner https://aisel.aisnet.org/misq/vol28/iss1/6/; Descazeaux https://aisel.aisnet.org/icis2025/quantum/quantum/5/. Candidate contribution: accept/reject/revalidate sampled pools when the organisational specification changes during an asynchronous request. Overlap: QAOA, provenance, hybrid workflows, MAPF agents are established. Novelty: UNRESOLVED because full texts were not uniformly read. Do not mark publication-ready on novelty grounds. Classical analogues (cache invalidation / stale-result handling) are conceptual only.",
        "",
        f"8. Protocol id={protocol.get('protocol_id')} hash={protocol.get('protocol_hash')}. Local evidence: encodings, greedy, ideal QAOA parameters, policy replay, ISA compile. Decision hardware evidence count: 0. No protocol retune after hardware (none exists).",
        "",
        "9. Classical: exact enumeration is the independent oracle and a practical baseline at n=6 and may dominate the hybrid workflow. Greedy+swaps is the operational incumbent source and may be suboptimal (D3 greedy 21 vs 23; D5 greedy 22 vs 23; D1/D2/D4/D6 greedy already optimal so no incumbent headroom). Uniform bitstrings and cardinality-k sampling are in reports/tables/. Prefixes [1,4,16,64,256,1024] are dependent analyses of one stream.",
        f"greedy={json.dumps(greedy)[:4000]}",
        "",
        "10. Policies P0–P3 run on identical simulated shot pools (evidence_type=policy_replay). P2 rejects version mismatch; P3 may revalidate compatible drifts. Meaning-change and bad linkage must reject. Injected linkage/empty/late envelopes are labelled injected_fault/policy_replay, not IBM failures. Equality with incumbent is not added quantum value. Abstention is not a successful decision.",
        "",
        f"11. Quantum budget: user-stated remaining ~540s is an upper planning bound. Live service.usage() remaining was extracted from usage_remaining_seconds. usage_probe_redacted={json.dumps(usage)[:2000]} estimate={json.dumps(extra.get('estimate') or {})[:1500]}",
        "",
        "12. NEW QPU JOBS SUBMITTED: 0",
        "",
        "13. Manuscript DOCX not found locally; correction map written under manuscript_support/. Canonical manuscript not modified. Proposed working title is a proposal only.",
        "",
        "14. Evidence: decision-study/reports/CHATGPT_RETURN_REPORT.md and decision-study/reports/chatgpt_return_packet.zip. ZIP SHA-256 is written beside the archive, not inside it. Next: wait for the user phrase do a run (one decision-study block). do a legacy GHZ run is the old probe. resume the run retrieves without submitting.",
        "",
        "END CHATGPT RETURN REPORT",
        "",
    ]
    return "\n".join(lines)

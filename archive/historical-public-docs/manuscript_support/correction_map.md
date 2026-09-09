# Manuscript correction map

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

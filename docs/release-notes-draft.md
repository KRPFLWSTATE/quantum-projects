# Optional GitHub Release / Zenodo (not performed)

When the author approves publication of a tagged snapshot:

1. Review uncommitted diffs; do not include `.env`, `venv/`, or IBM tokens.
2. Create an annotated git tag on the reviewed commit (author action).
3. Open a GitHub Release from that tag with notes below.
4. If Zenodo GitHub integration is later enabled by the author, a DOI can be minted from the Release. This task does **not** create a release, enable the integration, or mint a DOI.

Suggested notes:

- Six completed `ibm_fez` decision-study SamplerV2 jobs and twenty GHZ probes.
- Offline reproduction: `python tools/reproduce.py`.
- Campaign complete; do not reopen the published ledger.

References: GitHub citation files; GitHub Python CI; GitHub/Zenodo software archival.

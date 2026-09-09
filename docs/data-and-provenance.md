# Data and provenance

## Evidence classes

| Class | Location | Meaning |
|---|---|---|
| `decision_hardware` | `decision-study/data/raw/` | Observed SamplerV2 jobs |
| `legacy_ghz_hardware` | `dba-qpu-run/results/runs/` | Observed 3-qubit GHZ probes |
| `post_collection_policy_replay` | `results/publication/tables/post_collection_*` | New analysis of old shots |
| `sampled_simulation` | derived local sampling | Not hardware |

The current `decision-study/reports/CHATGPT_RETURN_REPORT.md` is a **historical** mixed document (completed-run totals together with setup-era unpublished/future statements). Do not treat it as the current public report. The dated current report is `results/publication/reports/CURRENT_REPORT.md` after a successful `--refresh-publication`, or `build/reproduction/reports/RESULTS.md` from isolated reproduction.

`created_utc` in a decision raw file is the **client dispatch** time. IBM `metrics.timestamps.created/running/finished` are separate.

## Hashes

- Protocol self-hash: SHA-256 of the protocol JSON without the `protocol_hash` field, matching `freeze.py`.
- Pre-housekeeping file digest list: `decision-study/data/preservation/pre_housekeeping_manifest.json` (the manifest is excluded from hashing itself).
- Legacy GHZ: 65 paths in `decision-study/data/preservation/legacy_sha256.json` (verify, do not silently rewrite).

## Compact indexes

`decisions.json` (~5 MB) and `policy_replay.json` (~8 MB) are retained. Compact indexes are written under `results/publication/tables/`.

## Export

Use `tools/publication/export.py` (not frozen `src/packet.py`). Historical ChatGPT ZIPs remain identifiable under `decision-study/reports/` and may have a stale sidecar; that is a packaging defect, not raw-job corruption. Independently recomputed on this pass: ZIP `decision-study/reports/chatgpt_return_packet.zip` SHA-256 `3c4f75308d1188550bc0069c70b32082844d5ad6f6220ac6576186f57c1619e7`; sidecar `decision-study/reports/chatgpt_return_packet.sha256` begins `d3d9af6f` (full `d3d9af6fe1a2f055ce848e4ef14a734f97dea890984c3de6e2d27b6b15cee056`). The new research ZIP writes the archive first, then the external `.sha256` sidecar. Equal scientific outputs are required; ZIP bytes may still differ across platforms if metadata is not controlled. This exporter pins ZIP timestamps to a fixed date.

## Missing metadata

No complete historical Python version was stored inside every IBM job. Do not fabricate it. Per-job `qiskit_version` strings were inspected for all six decision jobs.

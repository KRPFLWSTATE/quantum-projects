"""Provider adapter: same dispatch shape for IBM SamplerV2 and injected fakes."""

from __future__ import annotations

import uuid
from typing import Any


def sampler_options_object(job_tags: list[str] | None = None):
    from qiskit_ibm_runtime.options import SamplerOptions

    options = SamplerOptions()
    options.max_execution_time = 45
    if getattr(options, "twirling", None) is not None:
        if hasattr(options.twirling, "enable_gates"):
            options.twirling.enable_gates = False
        if hasattr(options.twirling, "enable_measure"):
            options.twirling.enable_measure = False
    if getattr(options, "dynamical_decoupling", None) is not None and hasattr(options.dynamical_decoupling, "enable"):
        options.dynamical_decoupling.enable = False
    if job_tags:
        options.environment.job_tags = list(job_tags)
    return options


class FakeBitArray:
    def __init__(self, bitstrings: list[str]) -> None:
        self._bitstrings = list(bitstrings)

    def get_bitstrings(self) -> list[str]:
        return list(self._bitstrings)

    def get_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self._bitstrings:
            counts[item] = counts.get(item, 0) + 1
        return counts


class FakePubResult:
    def __init__(self, bitstrings: list[str]) -> None:
        self.data = type("Data", (), {"meas": FakeBitArray(bitstrings)})()


class FakePrimitiveResult:
    def __init__(self, pubs: list[FakePubResult]) -> None:
        self._pubs = pubs

    def __len__(self) -> int:
        return len(self._pubs)

    def __getitem__(self, index: int) -> FakePubResult:
        return self._pubs[index]


class FakeRuntimeJob:
    def __init__(self, job_id: str, result: FakePrimitiveResult, tags: list[str] | None = None) -> None:
        self._job_id = job_id
        self._result = result
        self.tags = tags or []
        self._status = "DONE"

    def job_id(self) -> str:
        return self._job_id

    def status(self) -> str:
        return self._status

    def result(self) -> FakePrimitiveResult:
        return self._result

    def usage(self, partial: bool = False) -> float:
        return 2.0


class FakeSamplerV2:
    def __init__(self, mode=None, options=None) -> None:
        self.mode = mode
        self.options = options if options is not None else sampler_options_object()
        self.run_calls = 0
        self.last_pubs = None
        self.last_shots = None
        self.jobs: dict[str, FakeRuntimeJob] = {}

    def run(self, pubs, *, shots: int | None = None):
        if shots is None:
            raise ValueError("shots required")
        self.run_calls += 1
        self.last_pubs = list(pubs)
        self.last_shots = int(shots)
        job_id = f"fake-runtime-{uuid.uuid4()}"
        pub_results = []
        for _ in pubs:
            pub_results.append(FakePubResult(["000111"] * int(shots)))
        tags = []
        env = getattr(self.options, "environment", None)
        if env is not None and getattr(env, "job_tags", None):
            tags = list(env.job_tags)
        job = FakeRuntimeJob(job_id, FakePrimitiveResult(pub_results), tags=tags)
        self.jobs[job_id] = job
        return job


class FakeService:
    def __init__(self) -> None:
        self.jobs: dict[str, FakeRuntimeJob] = {}
        self.run_count = 0

    def job(self, job_id: str) -> FakeRuntimeJob:
        return self.jobs[job_id]

    def jobs_by_tags(self, tags: list[str]) -> list[FakeRuntimeJob]:
        wanted = set(tags or [])
        found = []
        for job in self.jobs.values():
            if wanted and wanted.issubset(set(job.tags or [])):
                found.append(job)
        return found


def decode_primitive_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict) and "pubs" in result:
        return result
    pubs = []
    n = len(result)
    for index in range(n):
        pub = result[index]
        meas = getattr(getattr(pub, "data", None), "meas", None) or getattr(getattr(pub, "data", None), "c", None)
        if meas is None:
            raise ValueError("unrecognised pub result payload")
        bitstrings = list(meas.get_bitstrings())
        counts = dict(meas.get_counts()) if hasattr(meas, "get_counts") else {}
        if not counts:
            for item in bitstrings:
                counts[item] = counts.get(item, 0) + 1
        pubs.append(
            {
                "pub_index": index,
                "shots": bitstrings,
                "counts": counts,
                "n_shots": len(bitstrings),
            }
        )
    return {"pubs": pubs, "n_pubs": len(pubs)}


def interpret_usage(raw: Any, *, metrics: Any = None, status: Any = None) -> dict[str, Any]:
    """Map RuntimeJobV2.usage() (scalar seconds) and pending metrics to a resolved charge."""
    report = {"raw": raw if not isinstance(raw, float) else raw, "state": "unknown", "seconds": None, "final_zero": False}
    if raw is None:
        report["state"] = "unknown"
        return report
    if isinstance(raw, dict):
        for key in ("quantum_seconds", "qpu_usage", "seconds"):
            if isinstance(raw.get(key), (int, float)):
                raw = float(raw[key])
                break
        else:
            report["state"] = "unknown"
            return report
    if not isinstance(raw, (int, float)) or isinstance(raw, bool):
        report["state"] = "unknown"
        return report
    seconds = float(raw)
    metrics = metrics or {}
    usage_block = metrics.get("usage") if isinstance(metrics, dict) else None
    timestamps = metrics.get("timestamps") if isinstance(metrics, dict) else None
    finished = False
    if isinstance(timestamps, dict) and timestamps.get("finished"):
        finished = True
    if isinstance(usage_block, dict) and usage_block.get("quantum_seconds") is not None:
        finished = True
    status_s = str(status() if callable(status) else status or "").upper()
    if seconds != 0.0:
        report["state"] = "resolved"
        report["seconds"] = seconds
        report["final_zero"] = False
        return report
    if finished or "DONE" in status_s and isinstance(usage_block, dict):
        report["state"] = "resolved"
        report["seconds"] = 0.0
        report["final_zero"] = True
        return report
    report["state"] = "pending"
    report["seconds"] = None
    return report


def shots_are_valid(decoded: dict[str, Any]) -> bool:
    from collections import Counter

    pubs = decoded.get("pubs") or []
    if len(pubs) != 12:
        return False
    for row in pubs:
        shots = list(row.get("shots") or [])
        if len(shots) != 1024 or int(row.get("n_shots") or 0) != 1024:
            return False
        for item in shots:
            if not isinstance(item, str) or len(item) != 6 or any(ch not in "01" for ch in item):
                return False
        counts = {str(k): int(v) for k, v in (row.get("counts") or {}).items()}
        if Counter(shots) != Counter(counts):
            return False
    return True


def job_id_of(job: Any) -> str:
    if callable(getattr(job, "job_id", None)):
        return str(job.job_id())
    return str(getattr(job, "job_id"))

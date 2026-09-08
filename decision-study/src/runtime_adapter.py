"""Provider adapter: same dispatch shape for IBM SamplerV2 and injected fakes."""

from __future__ import annotations

import uuid
from typing import Any


def sampler_options_object():
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

    def usage(self) -> dict[str, Any]:
        return {"quantum_seconds": 2.0, "qpu_usage": 2.0}


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
        job = FakeRuntimeJob(job_id, FakePrimitiveResult(pub_results), tags=["decision-study"])
        self.jobs[job_id] = job
        return job


class FakeService:
    def __init__(self) -> None:
        self.jobs: dict[str, FakeRuntimeJob] = {}
        self.run_count = 0

    def job(self, job_id: str) -> FakeRuntimeJob:
        return self.jobs[job_id]


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


def job_id_of(job: Any) -> str:
    if callable(getattr(job, "job_id", None)):
        return str(job.job_id())
    return str(getattr(job, "job_id"))

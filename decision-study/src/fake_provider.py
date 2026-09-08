"""Fake SamplerV2-compatible provider for local run/resume tests. Not hardware."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeJob:
    job_id: str
    pubs: list[Any]
    shots: int
    options: dict[str, Any]
    status_value: str = "DONE"
    run_calls: int = 1

    def status(self) -> str:
        return self.status_value

    def result(self) -> dict[str, Any]:
        pub_results = []
        for index, pub in enumerate(self.pubs):
            label = pub.get("label") if isinstance(pub, dict) else f"pub_{index}"
            shots = ["000111"] * self.shots
            counts: dict[str, int] = {}
            for bitstring in shots:
                counts[bitstring] = counts.get(bitstring, 0) + 1
            pub_results.append(
                {
                    "pub_index": index,
                    "label": label,
                    "shots": shots,
                    "counts": counts,
                    "n_shots": self.shots,
                }
            )
        return {
            "evidence_type": "sampled_simulation",
            "mock": True,
            "job_id": self.job_id,
            "pubs": pub_results,
        }

    def usage(self) -> dict[str, Any]:
        return {"quantum_seconds": 0.0, "note": "fake_provider_zero_usage"}


class FakeSampler:
    def __init__(self) -> None:
        self.run_calls = 0
        self.jobs: dict[str, FakeJob] = {}
        self.last_options: dict[str, Any] = {}

    def run(self, pubs: list[Any], *, shots: int = 1024, **options: Any) -> FakeJob:
        self.run_calls += 1
        job_id = f"fake-{uuid.uuid4()}"
        self.last_options = {"shots": shots, **options}
        job = FakeJob(job_id=job_id, pubs=list(pubs), shots=int(shots), options=dict(options))
        self.jobs[job_id] = job
        return job


class FakeService:
    def __init__(self, sampler: FakeSampler | None = None) -> None:
        self.sampler = sampler or FakeSampler()
        self.plan = "open"
        self.instance = "open-fake"

    def job(self, job_id: str) -> FakeJob:
        return self.sampler.jobs[job_id]

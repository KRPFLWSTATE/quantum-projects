"""IBM SamplerV2 construction. Physical run is only invoked from runner.dispatch_block(physical=True)."""

from __future__ import annotations

from typing import Any

from .runtime_adapter import sampler_options_object

HARDWARE_SUBMIT_ENABLED = False


def submit_sampler_job(*_args, **_kwargs):
    raise RuntimeError("Direct submit_sampler_job is disabled; use study.py run-next --hardware")


def build_physical_sampler(backend) -> Any:
    from qiskit_ibm_runtime import SamplerV2

    options = sampler_options_object()
    return SamplerV2(mode=backend, options=options)


def run_physical_block(backend, pubs, shots: int = 1024):
    sampler = build_physical_sampler(backend)
    return sampler.run(pubs, shots=shots)

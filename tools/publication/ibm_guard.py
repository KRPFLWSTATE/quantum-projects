"""Runtime tripwires so offline reproduction cannot construct IBM clients."""
from __future__ import annotations

import sys
from typing import Any


class OfflineIbmBlocked(RuntimeError):
    pass


def _blocked(*_args: Any, **_kwargs: Any) -> Any:
    raise OfflineIbmBlocked("offline reproduction must not instantiate IBM Runtime services or submit Sampler jobs")


def install_tripwires() -> None:
    try:
        import qiskit_ibm_runtime
    except Exception:
        return
    qiskit_ibm_runtime.QiskitRuntimeService = _blocked  # type: ignore[misc]
    sampler_mod = sys.modules.get("qiskit_ibm_runtime.fake_provider")
    try:
        from qiskit_ibm_runtime import SamplerV2
        # Replace class constructor used by hardware adapter if imported later.
        sys.modules["qiskit_ibm_runtime"].SamplerV2 = _blocked  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        import qiskit_ibm_runtime.fake_provider as fp  # noqa: F401
    except Exception:
        pass
    for name in ("QiskitRuntimeService", "Sampler", "SamplerV2"):
        if hasattr(qiskit_ibm_runtime, name):
            setattr(qiskit_ibm_runtime, name, _blocked)

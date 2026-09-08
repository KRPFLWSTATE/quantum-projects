"""Inspect installed SamplerV2 option names. Never submit a job."""

from __future__ import annotations

from typing import Any

from .hashing import write_json_atomic
from .paths import DERIVED_DIR


def inspect_sampler_options() -> dict[str, Any]:
    report: dict[str, Any] = {
        "package": None,
        "version": None,
        "sampler_class": None,
        "option_fields": [],
        "twirling_api": None,
        "dynamical_decoupling_api": None,
        "max_execution_time_api": None,
        "planned_settings": {
            "twirling": "disabled_if_exposed",
            "dynamical_decoupling": "disabled_if_exposed",
            "max_execution_time_seconds": 45,
            "sessions": "not_used",
            "rep_delay": "provider_default",
        },
        "error": None,
    }
    try:
        import qiskit_ibm_runtime
        from qiskit_ibm_runtime import SamplerV2

        report["package"] = "qiskit-ibm-runtime"
        report["version"] = getattr(qiskit_ibm_runtime, "__version__", None)
        report["sampler_class"] = SamplerV2.__name__
        opts = getattr(SamplerV2, "version", None)
        try:
            from qiskit_ibm_runtime.options import SamplerOptions

            sample = SamplerOptions()
            fields = []
            for name in dir(sample):
                if name.startswith("_"):
                    continue
                fields.append(name)
            report["option_fields"] = fields
            tw = getattr(sample, "twirling", None)
            dd = getattr(sample, "dynamical_decoupling", None)
            met = getattr(sample, "max_execution_time", "MISSING")
            report["twirling_api"] = {
                "present": tw is not None,
                "type": type(tw).__name__,
                "dir": [n for n in dir(tw) if not n.startswith("_")] if tw is not None else [],
            }
            report["dynamical_decoupling_api"] = {
                "present": dd is not None,
                "type": type(dd).__name__,
                "dir": [n for n in dir(dd) if not n.startswith("_")] if dd is not None else [],
            }
            met_s = None if met == "MISSING" else str(met)
            report["max_execution_time_api"] = {
                "present": met != "MISSING",
                "value_default": met_s,
            }
            # Apply intended settings on a local options object only.
            if tw is not None:
                if hasattr(tw, "enable_gates"):
                    tw.enable_gates = False
                if hasattr(tw, "enable_measure"):
                    tw.enable_measure = False
                if hasattr(tw, "enable"):
                    try:
                        tw.enable = False
                    except Exception:
                        pass
            if dd is not None and hasattr(dd, "enable"):
                dd.enable = False
            if met != "MISSING":
                try:
                    sample.max_execution_time = 45
                except Exception as exc:
                    report["max_execution_time_set_error"] = f"{type(exc).__name__}:{exc}"
            report["applied_locally_without_submit"] = {
                "twirling": str(getattr(sample, "twirling", None))[:500],
                "dynamical_decoupling": str(getattr(sample, "dynamical_decoupling", None))[:500],
                "max_execution_time": str(getattr(sample, "max_execution_time", None)),
            }
        except Exception as exc:
            report["options_import_error"] = f"{type(exc).__name__}:{exc}"
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}:{exc}"
    write_json_atomic(DERIVED_DIR / "sampler_options.json", report)
    return report

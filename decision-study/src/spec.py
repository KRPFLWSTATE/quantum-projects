"""Decision specification hashes, versions, and request records."""

from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from .hashing import sha256_json
from .model import DecisionInstance


VARIABLE_IDS = [f"task_{i}" for i in range(6)]
VARIABLE_MEANINGS = [f"Select maintenance task {i} in the planning window." for i in range(6)]
SCHEMA_ID = "six_item_cardinality_conflict_v1"
POLICY_VERSION = "P0-P3-20260908"


def objective_payload(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "k": spec["k"],
        "benefits": spec["benefits"],
        "conflicts": spec["conflicts"],
        "interactions": spec["interactions"],
        "variable_ids": spec["variable_ids"],
        "variable_meanings": spec["variable_meanings"],
        "schema_id": spec.get("schema_id", SCHEMA_ID),
    }


def spec_from_instance(
    instance: DecisionInstance,
    *,
    source_version: str = "v1",
    current_version: str = "v1",
    deadline_seconds: float = 30.0,
    request_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "instance_id": instance.instance_id,
        "schema_id": SCHEMA_ID,
        "variable_ids": list(VARIABLE_IDS),
        "variable_meanings": list(VARIABLE_MEANINGS),
        "k": instance.k,
        "benefits": list(instance.benefits),
        "conflicts": [list(pair) for pair in instance.conflicts],
        "interactions": [[i, j, s] for (i, j), s in sorted(instance.interactions.items())],
        "source_version": source_version,
        "current_version": current_version,
        "policy_version": POLICY_VERSION,
        "deadline_seconds": deadline_seconds,
        "deadline_origin": "coordinator_dispatch_after_cached_prep",
    }
    payload["objective_constraint_hash"] = sha256_json(objective_payload(payload))
    payload["spec_hash"] = sha256_json({k: v for k, v in payload.items() if k not in {"spec_hash", "request_id"}})
    payload["request_id"] = request_id or str(uuid.uuid4())
    payload["source_hash"] = payload["spec_hash"]
    payload["source_spec"] = copy.deepcopy(payload)
    return payload


def recompute_current(spec: dict[str, Any], trusted_source: dict[str, Any] | None = None) -> dict[str, Any]:
    out = copy.deepcopy(spec)
    source = trusted_source or spec.get("source_spec") or spec
    out["source_hash"] = source.get("source_hash") or source.get("spec_hash")
    out["objective_constraint_hash"] = sha256_json(objective_payload(out))
    hashed = {k: v for k, v in out.items() if k not in {"spec_hash", "request_id", "source_spec"}}
    out["spec_hash"] = sha256_json(hashed)
    return out


def instance_from_spec(spec: dict[str, Any]) -> DecisionInstance:
    interactions = {(int(i), int(j)): float(s) for i, j, s in spec["interactions"]}
    return DecisionInstance(
        instance_id=spec["instance_id"],
        benefits=tuple(float(v) for v in spec["benefits"]),
        conflicts=tuple((int(i), int(j)) for i, j in spec["conflicts"]),
        interactions=interactions,
        k=int(spec["k"]),
    )

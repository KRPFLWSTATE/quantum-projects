"""Independent ISA identity: protocol record versus frozen QPY file."""
from __future__ import annotations

import sys
from typing import Any

from .hashes import load_protocol
from .paths import REPO_ROOT, STUDY_ROOT

sys.path.insert(0, str(STUDY_ROOT))
from src.hashing import sha256_file  # type: ignore  # noqa: E402


def isa_qpy_name(fixture: str, depth: int) -> str:
    return f"{fixture}_p{int(depth)}_isa.qpy"


def frozen_isa_path(fixture: str, depth: int):
    return STUDY_ROOT / "data" / "derived" / "compile" / "qpy" / isa_qpy_name(fixture, depth)


def expected_isa_digest(fixture: str, depth: int, protocol: dict[str, Any] | None = None) -> str:
    """Return the independently verified ISA SHA-256 for D{{n}}_p{{d}}.

    Compares the frozen protocol table to the bytes of the QPY file. Does not
    copy a job archive field into the expected slot.
    """
    protocol = protocol or load_protocol()
    name = isa_qpy_name(fixture, depth)
    recorded = (protocol.get("isa_qpy_sha256") or {}).get(name)
    path = frozen_isa_path(fixture, depth)
    if recorded is None:
        raise ValueError(f"protocol missing ISA digest for {name}")
    if not path.is_file():
        raise ValueError(f"frozen ISA file missing: {path.relative_to(REPO_ROOT)}")
    file_digest = sha256_file(path)
    if file_digest != recorded:
        raise ValueError(
            f"ISA protocol/file mismatch for {name}: protocol={recorded} file={file_digest}"
        )
    return recorded


def assert_archived_isa_matches_protocol(
    fixture: str,
    depth: int,
    archived_digest: str | None,
    *,
    protocol: dict[str, Any] | None = None,
    job_id: str | None = None,
    pub_index: int | None = None,
) -> str:
    expected = expected_isa_digest(fixture, depth, protocol)
    if not archived_digest:
        raise ValueError(
            f"missing archived ISA digest job={job_id} pub={pub_index} {fixture} p={depth}"
        )
    if archived_digest != expected:
        raise ValueError(
            f"archived ISA digest mismatch job={job_id} pub={pub_index} "
            f"{fixture} p={depth}: archived={archived_digest} expected={expected}"
        )
    return expected

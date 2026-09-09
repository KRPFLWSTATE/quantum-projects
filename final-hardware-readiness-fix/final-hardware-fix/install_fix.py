"""Install reviewed pre-hardware fixes. No network, Git mutation, or IBM submission."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import tempfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


@contextlib.contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        if os.name != "nt":
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    args = parser.parse_args()
    root = args.repository.resolve()
    package = Path(__file__).resolve().parent
    manifest = json.loads((package / "manifest.json").read_text())
    study = root / "decision-study"
    if not (study / "study.py").is_file() or not (root / "dba-qpu-run").is_dir():
        raise SystemExit("STOP: pass the quantum-projects repository root.")
    with locked(study / "data/campaign_ledger.lock"):
        ledger = json.loads((study / "data/campaign_ledger.json").read_text())
        if (ledger.get("jobs_submitted") or ledger.get("outstanding_job") or ledger.get("history")
                or any(r.get("open") for r in ledger.get("reservations", []))):
            raise SystemExit("STOP: a campaign attempt already exists. Preserve it; this patch is pre-hardware only.")
        for path in (study / "data/raw").glob("*.json"):
            if json.loads(path.read_text()).get("evidence_type") == "decision_hardware":
                raise SystemExit("STOP: existing hardware evidence must be reviewed before a protocol update.")
        for rel, expected in manifest["protected_sha256"].items():
            if digest(root / rel) != expected:
                raise SystemExit(f"STOP: protected source/circuit/legacy file differs: {rel}")
        changes = []
        for rel, hashes in manifest["files"].items():
            payload = package / "payload" / rel
            if digest(payload) != hashes["after"]:
                raise SystemExit(f"STOP: damaged package payload: {rel}")
            current = digest(root / rel)
            if current == hashes["after"]:
                continue
            if current != hashes["before"]:
                raise SystemExit(f"STOP: local edit differs from the reviewed version: {rel}")
            changes.append((rel, payload))
        backup = Path(tempfile.mkdtemp(prefix="decision-pre-hardware-backup-"))
        originals, written = {}, []
        try:
            for rel, payload in changes:
                target = root / rel
                originals[rel] = target.read_bytes() if target.is_file() else None
                if originals[rel] is not None:
                    saved = backup / rel
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    saved.write_bytes(originals[rel])
                target.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
                    handle.write(payload.read_bytes())
                    handle.flush()
                    os.fsync(handle.fileno())
                    temporary = Path(handle.name)
                os.replace(temporary, target)
                written.append(rel)
        except BaseException:
            for rel in reversed(written):
                if originals[rel] is None:
                    (root / rel).unlink()
                else:
                    (root / rel).write_bytes(originals[rel])
            raise
    print(json.dumps({"installed": True, "files_updated": len(changes),
        "backup_directory": str(backup), "protocol_hash": manifest["protocol_hash"],
        "physical_jobs_submitted": 0,
        "next": "Run offline unittest discovery, then study.py status on the authenticated host. No hardware command during installation."}, indent=2))


if __name__ == "__main__":
    main()

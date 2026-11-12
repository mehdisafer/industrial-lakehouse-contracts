"""Immutable artifacts. Candidate data and accepted publication are separate."""
from __future__ import annotations
import os
import uuid
from pathlib import Path
from .canonical import canonical, digest, file_digest, fsync_dir, immutable_write, read_json, within
from .errors import IntegrityError, CaptureError


def batch_path(root: Path, batch_id: str) -> Path:
    if len(batch_id) != 64 or any(c not in '0123456789abcdef' for c in batch_id):
        raise IntegrityError("Invalid batch identifier")
    return within(root, "batches/" + batch_id)


def verify_manifest(directory: Path, manifest: dict) -> None:
    expected = set(manifest["files"])
    observed = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file() and p.relative_to(directory).as_posix() != "manifest.json"}
    if expected != observed:
        raise IntegrityError("Artifact inventory differs from the committed manifest")
    for relative, details in manifest["files"].items():
        path = within(directory, relative)
        if not path.is_file() or path.stat().st_size != details['bytes'] or file_digest(path) != details['sha256']:
            raise IntegrityError("Artifact bytes differ from their committed digest")


def inventory(directory: Path):
    return {p.relative_to(directory).as_posix(): {"sha256": file_digest(p), "bytes": p.stat().st_size}
            for p in sorted(directory.rglob("*")) if p.is_file() and p.relative_to(directory).as_posix() != "manifest.json"}


def write_capture(root: Path, batch_id: str, raw: dict, source_receipts: dict,
                  source_manifest: dict, plan: dict):
    directory = batch_path(root, batch_id) / "bronze"
    if directory.exists():
        raise CaptureError("An incomplete capture is never silently overwritten or reread")
    directory.mkdir(parents=True)
    for name, rows in raw.items():
        immutable_write(directory / (name + ".json"), canonical(rows))
    capture = {"kind": "bronze_snapshot", "plan_sha256": digest(plan), "sources": source_receipts,
               "source_manifest": source_manifest, "files": inventory(directory)}
    immutable_write(directory / "manifest.json", canonical(capture))
    fsync_dir(directory)
    return capture


def read_capture(root: Path, batch_id: str, plan: dict):
    directory = batch_path(root, batch_id) / "bronze"
    if not directory.exists():
        return None
    if not (directory / "manifest.json").is_file():
        raise CaptureError("Capture did not reach its durable manifest; explicit new admission is required")
    manifest = read_json(directory / "manifest.json")
    if manifest["plan_sha256"] != digest(plan):
        raise IntegrityError("Capture is bound to another plan")
    verify_manifest(directory, manifest)
    raw = {name: read_json(directory / f"{name}.json") for name in manifest["sources"]}
    return raw, manifest


def read_target(root: Path, batch_id: str):
    directory = batch_path(root, batch_id) / "target"
    if not directory.exists():
        return None
    try:
        manifest = read_json(directory / "manifest.json")
    except (OSError, ValueError) as exc:
        raise IntegrityError("Published target manifest is unreadable") from exc
    verify_manifest(directory, manifest)
    return manifest


def read_silver(root: Path, batch_id: str | None):
    if batch_id is None:
        return {}
    manifest = read_target(root, batch_id)
    if manifest is None:
        raise IntegrityError("Published data are missing")
    directory = batch_path(root, batch_id) / "target"
    return {name: read_json(directory / "silver" / f"{name}.json") for name in manifest["entities"]}


def write_target(root: Path, batch_id: str, plan: dict, capture: dict, silver: dict,
                 facts: list, summary: list, checks: dict, contract: dict, profile: dict):
    parent = batch_path(root, batch_id)
    existing = read_target(root, batch_id)
    if existing is not None:
        if existing['plan_sha256'] != digest(plan) or existing['capture_sha256'] != digest(capture):
            raise IntegrityError("Existing target belongs to another plan/capture")
        directory=parent / 'target'
        expected_files={'gold/fact_order_fulfillment.json':facts,'gold/site_kpi.json':summary,'checks.json':checks,
                        'gold/dim_customer.json':silver['customers'],'gold/dim_product.json':silver['products'],
                        'gold/dim_site.json':[{'site_id':site} for site in contract['sites']]}
        expected_files.update({'silver/'+name+'.json':rows for name,rows in silver.items()})
        for path,expected_data in expected_files.items():
            if read_json(within(directory,path))!=expected_data:
                raise IntegrityError('Recovered target differs from recomputed bounded source results')
        return existing, True
    # Native writers get an attempt-specific staging directory. They cannot
    # modify the public candidate path or the transactional acceptance pointer.
    stage = parent / (".stage-" + uuid.uuid4().hex)
    stage.mkdir(parents=True)
    for name, rows in silver.items():
        immutable_write(stage / "silver" / f"{name}.json", canonical(rows))
    immutable_write(stage / "gold/fact_order_fulfillment.json", canonical(facts))
    immutable_write(stage / "gold/site_kpi.json", canonical(summary))
    immutable_write(stage / "gold/dim_customer.json", canonical(silver["customers"]))
    immutable_write(stage / "gold/dim_product.json", canonical(silver["products"]))
    immutable_write(stage / "gold/dim_site.json", canonical([{"site_id":site} for site in contract["sites"]]))
    immutable_write(stage / "checks.json", canonical(checks))
    tables = [{"name": name, "owner_role": entity['owner_role'], "classification": entity['classification'],
               "primary_key": entity['primary_key'], "fields": entity['fields'],
               "rows": len(silver[name]), "logical_sha256": digest(silver[name]),
               "batch_id": batch_id} for name, entity in contract['entities'].items()]
    lineage = {"inputs": ["bronze."+name for name in silver],
               "intermediate": ["silver."+name for name in silver],
               "outputs": ["gold.dim_customer", "gold.dim_product", "gold.dim_site", "gold.fact_order_fulfillment", "gold.site_kpi", "report.sales_fulfillment"],
               "batch_id": batch_id, "contract_sha256": digest(contract), "model": contract['gold_model']}
    immutable_write(stage / "catalog/tables.json", canonical(tables))
    immutable_write(stage / "catalog/lineage.json", canonical(lineage))
    immutable_write(stage / "catalog/quality.json", canonical(checks))
    native = {"status": "NOT_RUN", "reason": "Reference profile is not Spark/Delta"}
    if profile['target'] == 'delta_spark':
        from .native import materialize_delta
        native = materialize_delta(stage, silver, facts, summary, contract)
    manifest = {"kind": "candidate_dataset", "batch_id": batch_id,
                "plan_sha256": digest(plan), "capture_sha256": digest(capture),
                "entities": list(silver), "engine": profile['engine'], "target": profile['target'],
                "native_materialization": native, "files": inventory(stage)}
    immutable_write(stage / "manifest.json", canonical(manifest))
    verify_manifest(stage, manifest)
    os.rename(stage, parent / "target")
    fsync_dir(parent)
    return manifest, False



def validate_native_publication(root: Path, batch_id: str, target: dict, contract: dict):
    """Persist final-location verification BEFORE publication/watermark commit."""
    if target["target"] != "delta_spark":
        return {"status": "NOT_RUN", "reason": "Reference target is not Delta"}
    from .native import verify_delta_at_final_path
    directory = batch_path(root, batch_id)
    result = verify_delta_at_final_path(directory / "target", contract)
    if result.get("status") != "EXECUTED_AND_RECONCILED_FINAL_PATH":
        raise IntegrityError("Native final-path verifier did not establish equality")
    # Catch inventory or content changes during verification as well.
    verified = read_target(root, batch_id)
    if verified != target:
        raise IntegrityError("Native target changed during final-path verification")
    proof = {"schema_version": "ilc-native-readback/1", "batch_id": batch_id,
             "target_manifest_sha256": digest(target), **result}
    # The verified result is an immutable projection, not a new mutable status.
    immutable_write(directory / "native_final_readback.json", canonical(proof))
    return {"status": proof["status"], "proof_sha256": digest(proof),
            "tables_verified": len(proof["tables"])}


def check_native_receipt(root: Path, batch_id: str, receipt: dict):
    """Reporting and accepted retries require the native proof, not a stage claim."""
    if receipt["target"] != "delta_spark":
        return
    try:
        proof = read_json(batch_path(root, batch_id) / "native_final_readback.json")
        recorded = receipt["native_final_readback"]
        if (proof["batch_id"] != batch_id
                or proof["target_manifest_sha256"] != receipt["target_manifest_sha256"]
                or proof["status"] != "EXECUTED_AND_RECONCILED_FINAL_PATH"
                or recorded["proof_sha256"] != digest(proof)):
            raise IntegrityError("Native publication proof differs from its acceptance")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise IntegrityError("Native publication proof is absent or invalid") from exc

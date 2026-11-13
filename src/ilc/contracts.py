"""Strict, non-executable metadata. No eval, templates or SQL in a contract."""
from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation
from .canonical import IDENTIFIER, canonical, digest, utc
from .errors import ContractError

VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
DECIMAL = re.compile(r"^decimal\(([1-9][0-9]?),([0-9]+)\)$")
FIELD_KEYS = {"name", "type", "nullable", "min", "enum"}
CORE_ENTITIES = {"customers", "products", "orders", "order_lines", "shipments"}

def require(condition, message):
    if not condition:
        raise ContractError(message)

def validate_contract(contract: dict) -> dict:
    require(isinstance(contract, dict), "Contract must be an object")
    require(set(contract) == {"schema_version", "contract_id", "version", "owner_role", "classification", "sites", "entities", "gold_model", "publication_policy", "standard_conformance"}, "Unknown or missing contract property")
    require(contract["schema_version"] == "ilc-contract/1", "Unsupported contract schema")
    require(contract["standard_conformance"] == "NOT_ASSESSED_ODCS", "Do not assert unverified ODCS conformance")
    require(contract["classification"] == "PUBLIC_SYNTHETIC", "This demonstrator admits synthetic public data only")
    require(bool(VERSION.fullmatch(str(contract["version"]))), "Expected semantic version")
    require(isinstance(contract["contract_id"], str) and 1 <= len(contract["contract_id"]) <= 100, "Invalid contract identity")
    require(isinstance(contract["owner_role"], str) and bool(contract["owner_role"]), "An owner role is required")
    require(contract["publication_policy"] == "last_accepted_batch_only", "Unsupported publication policy")
    require(contract["gold_model"] == "sales_fulfillment_v1", "Only reviewed model IDs are executable")
    sites = contract["sites"]
    require(isinstance(sites, list) and 1 <= len(sites) <= 100 and len(set(sites)) == len(sites), "Invalid site registry")
    require(all(isinstance(s, str) and re.fullmatch(r"SITE_[A-Z0-9]+", s) for s in sites), "Invalid site identifier")
    entities = contract["entities"]
    require(isinstance(entities, dict) and CORE_ENTITIES <= set(entities), "Five business entities are required")
    require(len(entities) <= 30, "Bounded demonstrator: too many entities")
    for name, entity in entities.items():
        require(bool(IDENTIFIER.fullmatch(name)), "Invalid entity identifier")
        require(set(entity) == {"fields", "primary_key", "watermark", "owner_role", "classification"}, "Invalid entity properties")
        require(entity["classification"] == "PUBLIC_SYNTHETIC" and bool(entity["owner_role"]), "Entity classification/owner is required")
        require(isinstance(entity["fields"], list) and 1 <= len(entity["fields"]) <= 50, "Invalid fields")
        names = []
        for field in entity["fields"]:
            require(set(field) <= FIELD_KEYS and {"name", "type", "nullable"} <= set(field), "Invalid field properties")
            require(bool(IDENTIFIER.fullmatch(field["name"])), "Invalid field identifier")
            require(type(field["nullable"]) is bool, "Nullable must be a Boolean")
            typ = field["type"]
            require(typ in {"string", "integer", "timestamp_utc"} or bool(DECIMAL.fullmatch(typ)), "Unsupported field type")
            if DECIMAL.fullmatch(typ):
                p, s = map(int, DECIMAL.fullmatch(typ).groups())
                require(0 <= s <= p <= 18, "Decimal capacity exceeds demonstrator contract")
            if "min" in field:
                require(typ == "integer" or bool(DECIMAL.fullmatch(typ)), "min is numeric only")
                try:
                    require(Decimal(str(field["min"])).is_finite(), "min must be finite")
                except InvalidOperation:
                    raise ContractError("min must be numeric") from None
            if "enum" in field:
                require(typ == "string" and isinstance(field["enum"], list) and bool(field["enum"]), "enum must constrain a string")
                require(all(isinstance(x, str) for x in field["enum"]), "enum values must be strings")
            names.append(field["name"])
        require(len(set(names)) == len(names), "Duplicate field names")
        require(isinstance(entity["primary_key"], list) and bool(entity["primary_key"]), "Primary key required")
        require(len(set(entity["primary_key"])) == len(entity["primary_key"]), "Duplicate key component")
        require(set(entity["primary_key"]) <= set(names), "Primary key field missing")
        require(entity["watermark"] in names, "Watermark field missing")
        by_name = {f["name"]: f for f in entity["fields"]}
        require(by_name[entity["watermark"]]["type"] == "timestamp_utc", "UTC watermark required")
        require(all(not by_name[k]["nullable"] for k in entity["primary_key"] + [entity["watermark"]]), "Keys and watermark cannot be nullable")
    return contract

def validate_profile(profile: dict, contract: dict) -> dict:
    require(set(profile) == {"schema_version", "profile_id", "engine", "target", "state", "source_database", "source_schema", "rest_url_env", "entity_sources", "lookback_seconds", "max_rows_per_entity", "max_total_rows", "max_pages", "page_size", "freshness_seconds", "egress"}, "Unknown or missing execution property")
    require(profile["schema_version"] == "ilc-execution/1", "Unsupported execution schema")
    require(profile["engine"] in {"reference_sqlite", "native_spark"}, "Unsupported engine")
    require(profile["target"] == ("reference_json" if profile["engine"] == "reference_sqlite" else "delta_spark"), "Mismatched engine and target")
    require(profile["state"] in {"sqlite", "postgresql"}, "Unsupported state backend")
    require(profile["source_database"] in {"sqlite", "postgresql"}, "Unsupported source backend")
    require(profile["egress"] == "loopback_only", "External network requires a separately qualified profile")
    require(IDENTIFIER.fullmatch(profile["source_schema"] or "main") is not None, "Invalid source schema")
    require(isinstance(profile["rest_url_env"], str) and re.fullmatch(r"[A-Z][A-Z0-9_]+", profile["rest_url_env"]), "Invalid environment reference")
    for name in ["max_rows_per_entity", "max_total_rows", "max_pages", "page_size", "freshness_seconds"]:
        require(type(profile[name]) is int and 0 < profile[name] <= 1_000_000, f"Invalid {name}")
    require(type(profile["lookback_seconds"]) is int and 0 <= profile["lookback_seconds"] <= 86400, "Invalid lookback")
    require(set(profile["entity_sources"]) == set(contract["entities"]), "Every entity needs exactly one source")
    for entity, source in profile["entity_sources"].items():
        require(set(source) == {"kind", "location", "mode"}, "Invalid source entry")
        require(source["kind"] in {"database", "csv", "rest"}, "Unsupported connector")
        require(source["mode"] in {"FULL", "INCREMENTAL"}, "Unsupported ingestion mode")
        require(isinstance(source["location"], str), "Source location must be text")
        if source["kind"] != "csv":
            require(bool(IDENTIFIER.fullmatch(source["location"])), "Invalid table/resource name")
        else:
            require(bool(re.fullmatch(r"[a-z][a-z0-9_]*\.csv", source["location"])), "CSV source must be a simple local filename")
    return profile

def coerce(value, field: dict):
    if value is None or value == "":
        if field["nullable"]:
            return None
        raise ValueError("required")
    typ = field["type"]
    if typ == "string":
        if not isinstance(value, str) or len(value) > 500 or not value:
            raise ValueError("string")
        result = value
        if "enum" in field and result not in field["enum"]:
            raise ValueError("enum")
    elif typ == "integer":
        if isinstance(value, bool) or not re.fullmatch(r"-?(0|[1-9][0-9]*)", str(value)):
            raise ValueError("integer")
        result = int(value)
        if not -(2**63) <= result < 2**63:
            raise ValueError("integer_range")
    elif typ == "timestamp_utc":
        result = utc(value)
    else:
        if isinstance(value, (float, bool)) or not re.fullmatch(r"-?\d+(?:\.\d+)?", str(value)):
            raise ValueError("decimal_literal")
        p, s = map(int, DECIMAL.fullmatch(typ).groups())
        number = Decimal(str(value))
        quantized = number.quantize(Decimal(1).scaleb(-s))
        if number != quantized or abs(number) >= Decimal(10) ** (p - s):
            raise ValueError("decimal_precision")
        result = format(quantized, f".{s}f")
    if "min" in field and Decimal(str(result)) < Decimal(str(field["min"])):
        raise ValueError("min")
    return result

def parse_rows(rows: list[dict], entity: dict) -> tuple[list[dict], list[dict]]:
    good, rejected = [], []
    fields = {f["name"]: f for f in entity["fields"]}
    for ordinal, row in enumerate(rows):
        errors, output = [], {}
        if not isinstance(row, dict) or set(row) != set(fields):
            errors = ["schema_fields"]
        else:
            for name, field in fields.items():
                try:
                    output[name] = coerce(row[name], field)
                except (ValueError, TypeError, InvalidOperation):
                    errors.append(name + ":invalid")
        if errors:
            rejected.append({"row_number": ordinal, "record_sha256": digest(row), "reasons": errors})
        else:
            good.append((ordinal, output))
    occurrences = {}
    for ordinal, row in good:
        key = tuple(row[x] for x in entity["primary_key"])
        occurrences.setdefault(key, []).append((ordinal, row))
    accepted = []
    for group in occurrences.values():
        if len(group) != 1:
            for ordinal, row in group:
                rejected.append({"row_number": ordinal, "record_sha256": digest(rows[ordinal]), "reasons": ["duplicate_primary_key"]})
        else:
            accepted.append(group[0][1])
    return sorted(accepted, key=canonical), sorted(rejected, key=lambda r: r["row_number"])

def compatibility(before: dict, after: dict) -> dict:
    validate_contract(before)
    validate_contract(after)
    breaking = []
    for entity, old in before["entities"].items():
        if entity not in after["entities"]:
            breaking.append(entity + ":removed")
            continue
        new = after["entities"][entity]
        if old["primary_key"] != new["primary_key"] or old["watermark"] != new["watermark"]:
            breaking.append(entity + ":identity")
        new_fields = {f["name"]: f for f in new["fields"]}
        old_fields = {f["name"]: f for f in old["fields"]}
        for name, field in old_fields.items():
            if new_fields.get(name) != field:
                breaking.append(entity + ":changed:" + name)
        for name, field in new_fields.items():
            if name not in old_fields and not field["nullable"]:
                breaking.append(entity + ":new_required:" + name)
    return {"compatible": not breaking, "breaking_changes": breaking,
            "before": digest(before), "after": digest(after)}

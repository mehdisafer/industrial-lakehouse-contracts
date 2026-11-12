"""Original synthetic corpus: no employer, customer, credential or real-person data."""
from __future__ import annotations
import csv
import json
import random
import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from .canonical import canonical, digest, immutable_write, read_json, utc, IDENTIFIER
from .contracts import validate_contract
from .errors import ContractError


def make_records(contract: dict, rows: int = 10000, seed: int = 17, revision: int = 0,
                 anchor: str = "2026-11-12T10:00:00Z", fault: str | None = None) -> dict:
    """Exact requested total in the clean fixture. Faults may add one row."""
    validate_contract(contract)
    if type(rows) is not int or not 1000 <= rows <= 100000:
        raise ValueError("Fixture supports 1,000–100,000 records, not a scale claim")
    if type(revision) is not int or not 0 <= revision <= 100:
        raise ValueError("Invalid revision")
    rng = random.Random(seed)
    anchor_dt = datetime.fromisoformat(utc(anchor).replace("Z", "+00:00"))
    updated = utc((anchor_dt + timedelta(hours=revision)).isoformat())
    promised = utc((anchor_dt - timedelta(days=1)).isoformat())
    sites = contract["sites"]
    customers = [{"customer_id": f"C{i:03d}", "site_id": sites[i % len(sites)],
                  "customer_label": f"Synthetic business {i:03d}", "updated_at": updated}
                 for i in range(30)]
    products = [{"product_id": f"P{i:03d}", "product_label": f"Synthetic component {i:03d}",
                 "category": ["assembly", "material", "packaging"][i % 3], "updated_at": updated}
                for i in range(20)]
    n_orders = (rows - 50) // 10
    orders, lines, shipments = [], [], []
    for i in range(n_orders):
        customer = customers[i % len(customers)]
        order = {"order_id": f"O{i:06d}", "customer_id": customer["customer_id"],
                 "site_id": customer["site_id"], "currency": "EUR",
                 "promised_at": promised, "updated_at": updated}
        orders.append(order)
        for line_id in range(1, 5):
            qty = rng.randint(4, 25)
            price = Decimal(rng.randint(99, 29999)).scaleb(-2)
            lines.append({"order_id": order["order_id"], "line_id": str(line_id),
                          "product_id": products[(i + line_id) % len(products)]["product_id"],
                          "quantity": str(qty), "unit_price": f"{price:.2f}",
                          "amount": f"{price * qty:.2f}", "updated_at": updated})
    remaining = rows - (len(customers) + len(products) + len(orders) + len(lines))
    eligible = [line for i, line in enumerate(lines) if i % 5 != 0]
    if not len(eligible) <= remaining <= 2 * len(eligible):
        raise ValueError("Cannot construct this fixture cardinality")
    extra = remaining - len(eligible)
    for i, line in enumerate(eligible):
        qty = int(line["quantity"])
        parts = [qty // 2, qty - qty // 2] if i < extra else [qty // 2]
        for j, part in enumerate(parts):
            delivered = utc((anchor_dt - timedelta(days=2 if i % 4 else 0, hours=6, minutes=j)).isoformat())
            shipments.append({"shipment_id": f"S{i:06d}-{j}", "order_id": line["order_id"],
                              "line_id": line["line_id"], "quantity": str(part),
                              "delivered_at": delivered, "updated_at": updated})
    records = dict(customers=customers, products=products, orders=orders,
                   order_lines=lines, shipments=shipments)
    if revision:
        line = lines[0]
        line["unit_price"] = f"{Decimal(line['unit_price']) + Decimal(revision):.2f}"
        line["amount"] = f"{Decimal(line['unit_price']) * int(line['quantity']):.2f}"
    if fault == "duplicate_key":
        lines.append(dict(lines[0]))
    elif fault == "invalid_amount":
        lines[0]["amount"] = "not-a-decimal"
    elif fault == "schema_drift":
        for row in shipments:
            row["unreviewed_column"] = "drift"
    elif fault == "orphan":
        lines[0]["product_id"] = "MISSING_PRODUCT"
    elif fault == "overshipment":
        shipments[0]["quantity"] = "999999"
    elif fault == "incorrect_total":
        lines[0]["amount"] = "0.01"
    elif fault is not None:
        raise ValueError("Unknown synthetic fault")
    return records


def write_fixture(root: Path, contract: dict, records: dict, *, as_of: str) -> dict:
    """Only writes a new, explicitly supplied synthetic fixture directory."""
    if root.exists():
        raise FileExistsError("Fixture destination must not exist; previous input stays immutable")
    root.mkdir(parents=True)
    root.chmod(0o700)
    record_hashes = {name: digest(sorted(data, key=canonical)) for name, data in records.items()}
    snapshot = digest({"entities": record_hashes, "as_of": utc(as_of)})
    manifest = {"classification": "PUBLIC_SYNTHETIC", "snapshot_id": snapshot,
                "as_of": utc(as_of), "entities": {
                    name: {"count": len(data), "logical_sha256": record_hashes[name],
                           "fields": list(data[0]) if data else [f['name'] for f in contract['entities'][name]['fields']]}
                    for name, data in records.items()}}
    with sqlite3.connect(root / "erp.sqlite") as db:
        for name in ["customers", "orders", "order_lines"]:
            fields = list(records[name][0])
            if not all(IDENTIFIER.fullmatch(f) for f in fields):
                raise ContractError("Invalid synthetic source schema")
            db.execute(f'CREATE TABLE "{name}" (' + ",".join(f'"{f}" TEXT' for f in fields) + ")")
            db.executemany(f'INSERT INTO "{name}" VALUES (' + ",".join("?" for _ in fields) + ")",
                           [[row[f] for f in fields] for row in records[name]])
    for name, data in records.items():
        immutable_write(root / f"{name}.json", canonical(data))
        with (root / f"{name}.csv").open("x", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=manifest["entities"][name]["fields"], lineterminator="\n")
            writer.writeheader()
            writer.writerows(data)
    immutable_write(root / "source_manifest.json", canonical(manifest))
    return manifest


def create_fixture(root: Path, contract: dict, rows=10000, seed=17, revision=0,
                   anchor="2026-11-12T10:00:00Z", fault=None) -> dict:
    records = make_records(contract, rows, seed, revision, anchor, fault)
    as_of = (datetime.fromisoformat(utc(anchor).replace("Z", "+00:00")) + timedelta(hours=revision)).isoformat()
    return write_fixture(root, contract, records, as_of=as_of)

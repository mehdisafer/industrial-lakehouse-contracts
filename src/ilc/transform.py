"""Typed Silver, bounded overlap/upsert and a reviewed Gold transform registry."""
from __future__ import annotations
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from .canonical import canonical, digest, utc
from .contracts import parse_rows

EPOCH = "1970-01-01T00:00:00.000000Z"


def build_silver(raw: dict, previous: dict, contract: dict, profile: dict, bounds: dict):
    result, rejected, reconciliation = {}, {}, {}
    for name, entity in contract["entities"].items():
        parsed, bad = parse_rows(raw[name], entity)
        low, high = bounds[name]["lower"], bounds[name]["upper"]
        in_window = [r for r in parsed if low <= r[entity["watermark"]] <= high]
        excluded = len(parsed) - len(in_window)
        mode = profile["entity_sources"][name]["mode"]
        old = previous.get(name, []) if mode == "INCREMENTAL" else []
        by_key = {tuple(row[k] for k in entity["primary_key"]): row for row in old}
        conflicts = []
        for row in in_window:
            key = tuple(row[k] for k in entity["primary_key"])
            prior = by_key.get(key)
            if prior is None or row[entity["watermark"]] > prior[entity["watermark"]]:
                by_key[key] = row
            elif row[entity["watermark"]] == prior[entity["watermark"]] and row != prior:
                conflicts.append({"key_sha256": digest(key), "record_sha256": digest(row), "reasons": ["same_timestamp_different_payload"]})
        candidate = sorted(by_key.values(), key=canonical)
        result[name] = candidate
        rejected[name] = bad + conflicts
        reconciliation[name] = {"captured": len(raw[name]), "typed": len(parsed), "quarantined": len(bad),
            "inside_window": len(in_window), "outside_window": excluded, "merge_conflicts": len(conflicts),
            "candidate_rows": len(candidate), "candidate_sha256": digest(candidate),
            "capture_accounting_ok": len(raw[name]) == len(parsed)+len(bad)}
    return result, rejected, reconciliation


def bounds_for(contract: dict, profile: dict, watermarks: dict, until: str):
    upper = utc(until)
    result = {}
    for name in contract["entities"]:
        if profile["entity_sources"][name]["mode"] == "FULL" or name not in watermarks:
            lower = EPOCH
        else:
            prior = datetime.fromisoformat(watermarks[name].replace("Z", "+00:00"))
            lower = utc((prior - timedelta(seconds=profile["lookback_seconds"])).isoformat())
        if name in watermarks and upper < watermarks[name]:
            raise ValueError("The requested upper watermark moves backwards")
        result[name] = {"lower": lower, "upper": upper, "inclusive_lower": True, "inclusive_upper": True,
                        "delete_capture": "UNSUPPORTED", "mode": profile["entity_sources"][name]["mode"]}
    return result


def business_checks(silver: dict, contract: dict):
    errors = []
    customers = {r["customer_id"]: r for r in silver["customers"]}
    products = {r["product_id"]: r for r in silver["products"]}
    orders = {r["order_id"]: r for r in silver["orders"]}
    lines = {(r["order_id"], r["line_id"]): r for r in silver["order_lines"]}
    for order in orders.values():
        customer = customers.get(order["customer_id"])
        if customer is None or customer["site_id"] != order["site_id"]:
            errors.append({"rule": "order_customer_site", "key": order["order_id"]})
        if order["site_id"] not in contract["sites"]:
            errors.append({"rule": "known_site", "key": order["order_id"]})
    for key, line in lines.items():
        if line["order_id"] not in orders or line["product_id"] not in products:
            errors.append({"rule": "line_foreign_keys", "key": list(key)})
        expected = (Decimal(line["unit_price"]) * line["quantity"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        if Decimal(line["amount"]) != expected:
            errors.append({"rule": "line_amount", "key": list(key)})
    shipped = defaultdict(int)
    for shipment in silver["shipments"]:
        key = (shipment["order_id"], shipment["line_id"])
        if key not in lines:
            errors.append({"rule": "shipment_foreign_key", "key": shipment["shipment_id"]})
        shipped[key] += shipment["quantity"]
    for key, quantity in shipped.items():
        if key in lines and quantity > lines[key]["quantity"]:
            errors.append({"rule": "no_overshipment", "key": list(key)})
    return {"status": "PASS" if not errors else "FAIL", "failures": errors,
            "rules": ["order_customer_site", "known_site", "line_foreign_keys", "line_amount", "shipment_foreign_key", "no_overshipment"]}


def cents(value: str) -> int:
    return int(Decimal(value) * 100)


def money(value: int) -> str:
    return format(Decimal(value).scaleb(-2), ".2f")


def build_gold(silver: dict):
    """Real SQL transform in the reference engine, without floating monetary sums.

    Native Spark/Delta materialization is a separate adapter. This path is
    explicitly not a Spark or distributed-execution qualification.
    """
    with sqlite3.connect(":memory:") as db:
        db.row_factory = sqlite3.Row
        db.executescript('''
            CREATE TABLE orders(order_id TEXT PRIMARY KEY,customer_id TEXT,site_id TEXT,currency TEXT,promised_at TEXT);
            CREATE TABLE lines(order_id TEXT,line_id INTEGER,product_id TEXT,quantity INTEGER,price_cents INTEGER,amount_cents INTEGER);
            CREATE TABLE shipments(order_id TEXT,line_id INTEGER,quantity INTEGER,delivered_at TEXT);
        ''')
        db.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", [(r['order_id'],r['customer_id'],r['site_id'],r['currency'],r['promised_at']) for r in silver['orders']])
        db.executemany("INSERT INTO lines VALUES (?,?,?,?,?,?)", [(r['order_id'],r['line_id'],r['product_id'],r['quantity'],cents(r['unit_price']),cents(r['amount'])) for r in silver['order_lines']])
        db.executemany("INSERT INTO shipments VALUES (?,?,?,?)", [(r['order_id'],r['line_id'],r['quantity'],r['delivered_at']) for r in silver['shipments']])
        rows = db.execute('''
            WITH shipped AS (
                SELECT s.order_id,s.line_id,SUM(s.quantity) AS shipped_qty,
                SUM(CASE WHEN s.delivered_at<=o.promised_at THEN s.quantity ELSE 0 END) AS on_time_qty
                FROM shipments s JOIN orders o ON o.order_id=s.order_id GROUP BY s.order_id,s.line_id
            )
            SELECT l.order_id,l.line_id,o.customer_id,o.site_id,o.currency,l.product_id,l.quantity,
                   l.amount_cents,COALESCE(s.shipped_qty,0) AS shipped_qty,COALESCE(s.on_time_qty,0) AS on_time_qty,
                   l.quantity-COALESCE(s.shipped_qty,0) AS backlog_qty,
                   (l.quantity-COALESCE(s.shipped_qty,0))*l.price_cents AS backlog_cents
            FROM lines l JOIN orders o ON l.order_id=o.order_id
            LEFT JOIN shipped s ON s.order_id=l.order_id AND s.line_id=l.line_id ORDER BY l.order_id,l.line_id
        ''').fetchall()
        facts = []
        for row in rows:
            record = dict(row)
            if type(record['amount_cents']) is not int or type(record['backlog_cents']) is not int:
                raise OverflowError("Reference SQL monetary arithmetic overflowed; publication blocked")
            record['ordered_amount'] = money(record.pop('amount_cents'))
            record['backlog_amount'] = money(record.pop('backlog_cents'))
            facts.append(record)
    # Independent Decimal/source reconciliation, not solely a count of generated output.
    expected_total = sum((Decimal(r['amount']) for r in silver['order_lines']), Decimal(0))
    observed_total = sum((Decimal(r['ordered_amount']) for r in facts), Decimal(0))
    source_keys = {(r['order_id'],r['line_id']) for r in silver['order_lines']}
    target_keys = {(r['order_id'],r['line_id']) for r in facts}
    checks = {"line_counts_equal": len(facts)==len(silver['order_lines']),
              "keys_equal": source_keys==target_keys and len(target_keys)==len(facts),
              "amounts_equal": expected_total==observed_total,
              "source_amount": str(expected_total.quantize(Decimal('.01'))),
              "gold_amount": str(observed_total.quantize(Decimal('.01')))}
    sites = {}
    for r in facts:
        bucket = sites.setdefault(r['site_id'], dict(site_id=r['site_id'],currency='EUR',orders=set(),line_count=0,
            quantity=0,shipped_qty=0,on_time_qty=0,backlog_qty=0,ordered_amount=Decimal(0),backlog_amount=Decimal(0)))
        bucket['orders'].add(r['order_id'])
        bucket['line_count'] += 1
        for k in ('quantity','shipped_qty','on_time_qty','backlog_qty'):
            bucket[k] += r[k]
        for k in ('ordered_amount','backlog_amount'):
            bucket[k] += Decimal(r[k])
    summaries = []
    for site, value in sorted(sites.items()):
        value['order_count'] = len(value.pop('orders'))
        value['ordered_amount'] = format(value['ordered_amount'], '.2f')
        value['backlog_amount'] = format(value['backlog_amount'], '.2f')
        summaries.append(value)
    return facts, summaries, checks

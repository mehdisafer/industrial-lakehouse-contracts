"""Bounded source readers. Snapshot tokens are verified, never assumed."""
from __future__ import annotations
import csv
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit, quote
import httpx
from sqlalchemy.engine import make_url
from .canonical import canonical, digest, read_json, within, utc, IDENTIFIER
from .errors import SourceError, NativeUnavailable


def loopback_url(url: str) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
        raise SourceError("Only explicit loopback endpoints are allowed by this profile")
    return url.rstrip("/")

def validate_pg_dsn(dsn: str):
    try:
        parsed = make_url(dsn)
    except Exception:
        raise SourceError("Invalid database connection reference") from None
    if parsed.get_backend_name() != "postgresql" or parsed.host not in {"localhost", "127.0.0.1", "::1"} or not parsed.database or parsed.query:
        raise SourceError("Native demo DSN must name a loopback PostgreSQL database")
    return parsed

@contextmanager
def source_connection(root: Path, profile: dict):
    if profile["source_database"] == "sqlite":
        path = within(root, "erp.sqlite")
        if not path.is_file():
            raise SourceError("Source database is absent")
        db = sqlite3.connect("file:" + quote(str(path)) + "?mode=ro", uri=True, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN")
            yield db
        finally:
            db.rollback()
            db.close()
    else:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError:
            raise NativeUnavailable("PostgreSQL driver is not installed") from None
        dsn = os.environ.get("ILC_SOURCE_DSN", "")
        parsed = validate_pg_dsn(dsn)
        try:
            # The SQLAlchemy suffix is not a libpq DSN.
            with psycopg.connect(parsed.set(drivername="postgresql").render_as_string(hide_password=False), row_factory=dict_row, connect_timeout=5) as db:
                db.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
                yield db
                db.rollback()
        except psycopg.Error:
            raise SourceError("PostgreSQL source operation failed; no DSN is included") from None


def read_database(db, table: str, profile: dict) -> list[dict]:
    if not IDENTIFIER.fullmatch(table):
        raise SourceError("Invalid table name")
    schema = profile["source_schema"]
    limit = profile["max_rows_per_entity"] + 1
    # Identifiers are restricted, values never interpolated from row data.
    path = f'"{schema}"."{table}"' if profile["source_database"] == "postgresql" else f'"{table}"'
    cursor = db.execute(f"SELECT * FROM {path} LIMIT {limit}")
    rows = [dict(row) for row in cursor.fetchall()]
    if len(rows) >= limit:
        raise SourceError("Source row budget exceeded")
    return rows


def read_csv(root: Path, location: str, limit: int) -> list[dict]:
    path = within(root, location)
    if not path.is_file() or path.stat().st_size > 100_000_000:
        raise SourceError("CSV absent or beyond the byte budget")
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        if not fields or len(fields) != len(set(fields)):
            raise SourceError("Duplicate/absent CSV header")
        rows = []
        for row in reader:
            if None in row:
                raise SourceError("CSV record has additional cells")
            rows.append(row)
            if len(rows) > limit:
                raise SourceError("CSV row budget exceeded")
    return rows


def request_json(client: httpx.Client, path: str, **kwargs):
    try:
        # A bounded stream avoids downloading an unbounded response into memory.
        with client.stream("GET", path, **kwargs) as response:
            if response.status_code != 200:
                raise SourceError("Source did not return HTTP 200")
            content = bytearray()
            for part in response.iter_bytes():
                content.extend(part)
                if len(content) > 8_000_000:
                    raise SourceError("HTTP page byte budget exceeded")
            import json
            return json.loads(content, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite")))
    except (httpx.HTTPError, ValueError):
        raise SourceError("Source response is invalid or unavailable") from None


def read_rest(client: httpx.Client, manifest: dict, entity: str, profile: dict):
    rows, pages, seen, cursor = [], 0, set(), "0"
    details = manifest["entities"][entity]
    if details["count"] > profile["max_rows_per_entity"]:
        raise SourceError("Declared row budget exceeded")
    while cursor is not None:
        if cursor in seen or pages >= profile["max_pages"]:
            raise SourceError("Pagination cycle or budget exceeded")
        seen.add(cursor)
        page = request_json(client, f"/v1/snapshots/{manifest['snapshot_id']}/entities/{entity}",
                            params={"cursor": cursor, "limit": profile["page_size"]})
        if (not isinstance(page, dict) or page.get("snapshot_id") != manifest["snapshot_id"]
                or page.get("entity") != entity or page.get("cursor") != cursor
                or page.get("total_rows") != details["count"] or page.get("fields") != details["fields"]
                or page.get("as_of") != manifest["as_of"] or not isinstance(page.get("rows"), list)):
            raise SourceError("Pagination changed its snapshot contract")
        if len(page["rows"]) > profile["page_size"]:
            raise SourceError("Page size exceeded")
        rows.extend(page["rows"])
        if len(rows) > details["count"]:
            raise SourceError("Rows exceeded declared total")
        next_cursor = page.get("next_cursor")
        if next_cursor is not None and (not isinstance(next_cursor, str) or not next_cursor.isdigit() or int(next_cursor) != len(rows) or not page["rows"]):
            raise SourceError("Invalid pagination cursor")
        cursor = next_cursor
        pages += 1
    if len(rows) != details["count"]:
        raise SourceError("Incomplete snapshot pagination")
    return rows, pages


def extract_all(root: Path, contract: dict, profile: dict, api_url: str, *, client: httpx.Client | None = None):
    manifest = read_json(within(root, "source_manifest.json"))
    if manifest.get("classification") != "PUBLIC_SYNTHETIC":
        raise SourceError("Only the synthetic corpus is authorized")
    if not isinstance(manifest.get("snapshot_id"), str) or not re.fullmatch(r'[0-9a-f]{64}',manifest["snapshot_id"]):
        raise SourceError("Invalid source snapshot identifier")
    owned = client is None
    client = client or httpx.Client(base_url=loopback_url(api_url), timeout=10, follow_redirects=False, trust_env=False)
    records, receipts = {}, {}
    try:
        api_manifest = request_json(client, "/v1/manifest")
        if api_manifest != manifest:
            raise SourceError("The API and local sources do not declare the same fixture snapshot")
        with source_connection(root, profile) as db:
            for name, source in profile["entity_sources"].items():
                if name not in manifest["entities"]:
                    raise SourceError("Entity absent from source snapshot")
                pages = None
                if source["kind"] == "database":
                    data = read_database(db, source["location"], profile)
                elif source["kind"] == "csv":
                    data = read_csv(root, source["location"], profile["max_rows_per_entity"])
                else:
                    data, pages = read_rest(client, manifest, source["location"], profile)
                details = manifest["entities"][name]
                logical = digest(sorted(data, key=canonical))
                if len(data) != details["count"] or logical != details["logical_sha256"]:
                    raise SourceError("Source records differ from the pinned synthetic snapshot")
                records[name] = data
                receipts[name] = {"connector": source["kind"], "source_backend": profile["source_database"] if source['kind']=='database' else source['kind'],
                                  "snapshot_id": manifest["snapshot_id"], "as_of": manifest["as_of"], "pages": pages,
                                  "captured_rows": len(data), "logical_sha256": logical}
                if sum(len(x) for x in records.values()) > profile["max_total_rows"]:
                    raise SourceError("Total extraction budget exceeded")
    finally:
        if owned:
            client.close()
    return records, receipts, manifest

"""Transactional admission and publication. Target writes are reconciled separately."""
from __future__ import annotations
import json
import os
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote
from sqlalchemy import (Column, Integer, MetaData, String, Table, Text, UniqueConstraint,
                        create_engine, insert, select, update, text)
from .canonical import canonical, digest, now, immutable_write, read_json, pipeline_lock
from .errors import ConflictError, StaleBaseError, BusyError, NativeUnavailable, IntegrityError
from .sources import validate_pg_dsn

metadata = MetaData()
registry = Table("ilc_registry", metadata,
    Column("pipeline", String(64), primary_key=True), Column("accepted_batch", String(64)),
    Column("last_batch", String(64)), Column("last_status", String(32), nullable=False),
    Column("watermarks", Text, nullable=False), Column("generation", Integer, nullable=False))
runs = Table("ilc_runs", metadata,
    Column("batch_id", String(64), primary_key=True), Column("pipeline", String(64), nullable=False),
    Column("request_hash", String(64), nullable=False), Column("signature", Text, nullable=False),
    Column("plan", Text, nullable=False), Column("status", String(32), nullable=False),
    Column("attempts", Integer, nullable=False), Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False), Column("error_code", String(80)),
    Column("receipt", Text), UniqueConstraint("pipeline", "request_hash", name="uq_ilc_request"))
events = Table("ilc_events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("pipeline", String(64), nullable=False), Column("batch_id", String(64), nullable=False),
    Column("at", String(40), nullable=False), Column("event", String(60), nullable=False),
    Column("details", Text, nullable=False))


def encoded(value) -> str:
    return canonical(value).decode("utf-8")


class Journal:
    def __init__(self, root: Path, profile: dict, *, read_only: bool = False):
        self.root = root.resolve()
        self.read_only = read_only
        if (self.root / ".restore-in-progress").exists():
            raise IntegrityError("An incomplete restore must not become a writer or consumer")
        if not read_only:
            self.root.mkdir(parents=True, exist_ok=True)
        marker = root / ".ilc-sandbox.json"
        # Deterministic namespace per root; no information from private accounts.
        self.pipeline = digest({"root": str(self.root), "application": "ilc/0.1"})
        expected = {"pipeline": self.pipeline, "classification": "PUBLIC_SYNTHETIC", "single_host": True}
        if read_only:
            if not marker.is_file() or read_json(marker) != expected:
                raise IntegrityError("Read-only access requires an existing admitted runtime")
        else:
            immutable_write(marker, canonical(expected))
        self.backend = profile["state"]
        if self.backend == "sqlite":
            if read_only:
                database = self.root / "journal.sqlite"
                if not database.is_file():
                    raise IntegrityError("The journal does not exist")
                self.engine = create_engine("sqlite+pysqlite:///file:" + quote(str(database)) + "?mode=ro&uri=true",
                                            connect_args={"timeout":10})
            else:
                self.engine = create_engine("sqlite+pysqlite:///" + str(self.root / "journal.sqlite"),
                                            connect_args={"timeout": 10})
                with self.engine.connect() as db:
                    db.exec_driver_sql("PRAGMA journal_mode=WAL")
                    db.exec_driver_sql("PRAGMA synchronous=FULL")
        else:
            if os.environ.get("ILC_ALLOW_NATIVE_DEMO") != "1":
                raise NativeUnavailable("Native database initialization requires explicit demo opt-in")
            dsn = os.environ.get("ILC_STATE_DSN", "")
            parsed = validate_pg_dsn(dsn)
            if not parsed.database.startswith("ilc_demo"):
                raise NativeUnavailable("Native state database must have the ilc_demo prefix")
            options = {"connect_timeout": 5}
            if read_only:
                options["options"] = "-c default_transaction_read_only=on"
            try:
                self.engine = create_engine(parsed.set(drivername="postgresql+psycopg"), pool_pre_ping=True,
                                            connect_args=options)
            except ImportError:
                raise NativeUnavailable("PostgreSQL driver is unavailable") from None
        if read_only:
            self.state()  # Check the existing namespace; never initialize it.
            return
        metadata.create_all(self.engine)
        with self.engine.begin() as db:
            if not db.execute(select(registry).where(registry.c.pipeline == self.pipeline)).first():
                db.execute(insert(registry).values(pipeline=self.pipeline, accepted_batch=None,
                    last_batch=None, last_status="EMPTY", watermarks="{}", generation=0))

    def close(self):
        self.engine.dispose()

    @contextmanager
    def lock(self):
        if self.read_only:
            raise PermissionError("Read-only journal cannot become a writer")
        # The native profile is also single-host, with a PG session lock in addition.
        with pipeline_lock(self.root):
            if self.backend != "postgresql":
                yield
            else:
                key = int(self.pipeline[:15], 16)
                with self.engine.connect() as db:
                    acquired = db.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}).scalar_one()
                    if not acquired:
                        raise BusyError("Another process owns the database pipeline lock")
                    try:
                        yield
                    finally:
                        db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})

    def state(self) -> dict:
        with self.engine.connect() as db:
            result = dict(db.execute(select(registry).where(registry.c.pipeline == self.pipeline)).mappings().one())
        result["watermarks"] = json.loads(result["watermarks"])
        return result

    def find(self, key: str):
        with self.engine.connect() as db:
            row = db.execute(select(runs).where(runs.c.pipeline == self.pipeline, runs.c.request_hash == digest(key))).mappings().first()
        return self._decode(row)

    def get(self, batch_id: str):
        with self.engine.connect() as db:
            row = db.execute(select(runs).where(runs.c.pipeline == self.pipeline, runs.c.batch_id == batch_id)).mappings().first()
        return self._decode(row)

    @staticmethod
    def _decode(row):
        if row is None:
            return None
        result = dict(row)
        for name in ("plan", "signature", "receipt"):
            if result[name] is not None:
                result[name] = json.loads(result[name])
        return result

    def admit(self, key: str, signature: dict, plan: dict) -> dict:
        with self.engine.begin() as db:
            row = db.execute(select(runs).where(runs.c.pipeline == self.pipeline, runs.c.request_hash == digest(key))).mappings().first()
            if row is not None:
                if json.loads(row["signature"]) != signature:
                    raise ConflictError("This key is already bound to a different immutable request")
                return self._decode(row)
            batch_id = digest({"pipeline": self.pipeline, "request": key})
            plan = {**plan, "batch_id": batch_id}
            timestamp = now()
            values = dict(batch_id=batch_id, pipeline=self.pipeline, request_hash=digest(key),
                          signature=encoded(signature), plan=encoded(plan), status="ADMITTED", attempts=0,
                          created_at=timestamp, updated_at=timestamp)
            db.execute(insert(runs).values(**values))
            self._event(db, batch_id, "ADMITTED", {"plan_sha256": digest(plan)})
        return self.get(batch_id)

    def _event(self, db, batch_id: str, event: str, details: dict):
        db.execute(insert(events).values(pipeline=self.pipeline, batch_id=batch_id,
                                         at=now(), event=event, details=encoded(details)))

    def event(self, batch_id: str, event: str, details: dict):
        with self.engine.begin() as db:
            self._event(db, batch_id, event, details)

    def start_attempt(self, batch_id: str):
        with self.engine.begin() as db:
            db.execute(update(runs).where(runs.c.batch_id == batch_id).values(
                attempts=runs.c.attempts+1, updated_at=now(), error_code=None))
            db.execute(update(registry).where(registry.c.pipeline == self.pipeline).values(
                last_batch=batch_id, last_status="RUNNING"))
            self._event(db, batch_id, "ATTEMPT_STARTED", {})

    def mark(self, batch_id: str, status: str, error_code: str | None = None):
        with self.engine.begin() as db:
            db.execute(update(runs).where(runs.c.batch_id == batch_id, runs.c.pipeline == self.pipeline).values(
                status=status, updated_at=now(), error_code=error_code))
            db.execute(update(registry).where(registry.c.pipeline == self.pipeline, registry.c.last_batch == batch_id).values(last_status=status))
            self._event(db, batch_id, status, {"error_code": error_code})

    def reject(self, batch_id: str, receipt: dict):
        """Persist rejection before its optional file projection, as for acceptance."""
        with self.engine.begin() as db:
            db.execute(update(runs).where(runs.c.batch_id == batch_id,
                runs.c.pipeline == self.pipeline).values(status="REJECTED",
                receipt=encoded(receipt), updated_at=now(), error_code=receipt["reason"]))
            db.execute(update(registry).where(registry.c.pipeline == self.pipeline,
                registry.c.last_batch == batch_id).values(last_status="REJECTED"))
            self._event(db, batch_id, "REJECTED", {"reason": receipt["reason"]})

    def accept(self, batch_id: str, base: str | None, watermarks: dict, receipt: dict) -> dict:
        with self.engine.begin() as db:
            current = db.execute(select(registry).where(registry.c.pipeline == self.pipeline)).mappings().one()
            if current["accepted_batch"] != base:
                raise StaleBaseError("A newer accepted dataset must not be overwritten by an old retry")
            next_generation = current["generation"] + 1
            accepted = {**receipt, "status": "ACCEPTED", "accepted_at": now(), "generation": next_generation}
            result = db.execute(update(registry).where(registry.c.pipeline == self.pipeline,
                registry.c.generation == current["generation"]).values(accepted_batch=batch_id,
                watermarks=encoded(watermarks), generation=next_generation, last_batch=batch_id, last_status="ACCEPTED"))
            if result.rowcount != 1:
                raise StaleBaseError("Publication compare-and-swap failed")
            db.execute(update(runs).where(runs.c.batch_id == batch_id).values(status="ACCEPTED", receipt=encoded(accepted), updated_at=now(), error_code=None))
            self._event(db, batch_id, "PUBLICATION_AND_WATERMARK_COMMITTED", {"generation": next_generation})
        return accepted

    def timeline(self, batch_id: str):
        with self.engine.connect() as db:
            rows = db.execute(select(events).where(events.c.pipeline == self.pipeline, events.c.batch_id == batch_id).order_by(events.c.id)).mappings().all()
        return [{**dict(row), "details": json.loads(row["details"])} for row in rows]

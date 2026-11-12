"""Deterministic bytes, durable writes and a single-host process lock."""
from __future__ import annotations
import hashlib
import json
import os
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .errors import IntegrityError, BusyError, ContractError

IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,62}$")

def canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")

def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()

def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def utc(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|\+00:00)", value):
        raise ValueError("Expected an explicit UTC ISO-8601 timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")

def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")

def within(root: Path, relative: str) -> Path:
    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts or "\\" in relative:
        raise ContractError("Only relative non-traversing paths are allowed")
    root = root.resolve()
    candidate = root / relative_path
    current = root
    for segment in relative_path.parts:
        current = current / segment
        if current.is_symlink():
            raise ContractError("Symlink input is not admitted")
    if not candidate.resolve().is_relative_to(root):
        raise ContractError("Path escaped its root")
    return candidate

def fsync_dir(directory: Path) -> None:
    if os.name == "posix":
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

def immutable_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_symlink() or path.read_bytes() != data:
            raise IntegrityError("An immutable artifact has different bytes")
        return
    # Exclusive creation. An interrupted partial file is evidence, not silently replaced.
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        raise
    fsync_dir(path.parent)

def atomic_json(path: Path, value) -> None:
    import uuid
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    immutable_write(temp, canonical(value))
    os.replace(temp, path)
    fsync_dir(path.parent)

def read_json(path: Path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ContractError("Duplicate JSON key")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ContractError("Non-finite JSON number")))

@contextmanager
def pipeline_lock(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".pipeline.lock"
    if lock.is_symlink():
        raise IntegrityError("Invalid lock path")
    with lock.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise BusyError("Another writer owns the pipeline") from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

def code_manifest(root: Path) -> dict:
    paths = sorted((root / "src" / "ilc").glob("*.py"))
    if not paths:
        raise IntegrityError('The source checkout has no pipeline modules')
    installed = Path(__file__).resolve().parent
    for path in paths:
        loaded = installed / path.name
        if not loaded.is_file() or file_digest(loaded) != file_digest(path):
            raise IntegrityError('The imported implementation differs from the claimed source checkout')
    if {p.name for p in installed.glob('*.py')} != {p.name for p in paths}:
        raise IntegrityError('Source module inventory differs from the imported implementation')
    paths += [root / "pyproject.toml"]
    return {p.relative_to(root).as_posix(): file_digest(p) for p in paths}

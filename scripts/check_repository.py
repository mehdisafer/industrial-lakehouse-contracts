"""Check tracked documentation, qualification baselines and repository hygiene.

Standard-library only; no network, service startup or dependency installation.
Markdown support covers ATX headings, inline/reference links and fenced code.
Remote URLs are counted, not requested. Existing runtime evidence is not rerun.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
from urllib.parse import quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REGISTER = "docs/qualification-baselines.json"
STATUS_PAGE = "docs/STATUS.md"
REQUIRED = (
    "README.md", "CONTRIBUTING.md", "SECURITY.md", "docs/README.md",
    "docs/ARCHITECTURE.md", "docs/DATA_MODEL.md", "docs/DEMO.md",
    "docs/RUNBOOK.md", "docs/QUALIFICATION.md", "docs/PROVIDER_GATES.md",
    "docs/LICENSING.md", REGISTER, STATUS_PAGE,
)
STATES = {"accepted", "planned", "not-run"}
GENERATED_DIRS = {".runtime", "artifacts", "test-results", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "htmlcov", "build", "dist"}
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
INLINE = re.compile(r"!?\[[^\]\n]*\]\(")
REFERENCE = re.compile(r"!?\[([^\]\n]+)\]\[([^\]\n]*)\]")
DEFINITION = re.compile(r"^ {0,3}\[([^\]]+)\]:\s*(<[^>]+>|\S+)(?:\s+.*)?$")
MAX_DOCUMENT_BYTES = 512 * 1024
MAX_REGISTER_BYTES = 64 * 1024

HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$")


class RepositoryError(ValueError):
    """A repository input could not be checked safely or consistently."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RepositoryError(message)


def safe_path(root: Path, name: str) -> Path:
    require(isinstance(name, str), "Tracked path must be text")
    relative = PurePosixPath(name)
    require(bool(name) and not relative.is_absolute() and ".." not in relative.parts
            and "\\" not in name and not any(ord(c) < 32 for c in name),
            "Invalid tracked path")
    root = root.resolve()
    current = root
    for part in relative.parts:
        current /= part
        require(not current.is_symlink(), "Symlink path is not admitted")
    require(current.resolve().is_relative_to(root), "Path escapes repository")
    return current


def bounded_text(path: Path, limit: int) -> str:
    """Read regular UTF-8 input within a budget; never open a FIFO or symlink."""
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode), "Input must be a regular file")
    require(info.st_size <= limit, "Input exceeds the review byte budget")
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    require(len(raw) <= limit, "Input exceeds the review byte budget")
    return raw.decode("utf-8")


def failure_message(exc: Exception) -> str:
    # RepositoryError messages are constants under our control. Parser and OS
    # messages may contain the rejected input; retain only their category.
    return str(exc) if isinstance(exc, RepositoryError) else (
        "Unable to safely read or parse repository input (" + type(exc).__name__ + ")")


def tracked_files(root: Path) -> list[str]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=root,
                            capture_output=True, timeout=15)
    require(result.returncode == 0, "Cannot read the tracked-file inventory")
    files = result.stdout.decode("utf-8").rstrip("\0").split("\0")
    require(files != [""], "The tracked-file inventory is empty")
    return files


def _object_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate qualification-register key")
        result[key] = value
    return result


def load_register(root: Path) -> dict:
    raw = bounded_text(safe_path(root, REGISTER), MAX_REGISTER_BYTES)
    data = json.loads(raw, object_pairs_hook=_object_pairs)
    require(isinstance(data, dict) and set(data) == {"schema_version", "reviewed_on", "capabilities"},
            "Unexpected qualification-register fields")
    require(data["schema_version"] == "ilc-qualification-baselines/1", "Unsupported qualification register")
    require(isinstance(data["reviewed_on"], str), "Missing review date")
    require(date.fromisoformat(data["reviewed_on"]).isoformat() == data["reviewed_on"], "Invalid review date")
    capabilities = data["capabilities"]
    require(isinstance(capabilities, list) and 1 <= len(capabilities) <= 32, "Missing capabilities")
    seen = set()
    for item in capabilities:
        require(isinstance(item, dict) and set(item) == {"id", "name", "state", "revision", "evidence", "scope"},
                "Unexpected capability fields")
        require(isinstance(item["id"], str) and re.fullmatch(r"[a-z][a-z0-9-]*", item["id"]) is not None,
                "Invalid capability identifier")
        require(item["id"] not in seen, "Duplicate capability identifier")
        seen.add(item["id"])
        require(isinstance(item["state"], str) and item["state"] in STATES, "Unknown capability state")
        for key in ("name", "scope"):
            require(isinstance(item[key], str) and bool(item[key].strip())
                    and len(item[key]) <= 512 and not any(ord(c) < 32 or c in "|<>" for c in item[key]), "Invalid capability text")
        require(isinstance(item["evidence"], str), "Missing evidence path")
        evidence = safe_path(root, item["evidence"])
        require(evidence.is_file() and evidence.suffix == ".md", "Missing Markdown evidence")
        if item["state"] == "accepted":
            require(isinstance(item["revision"], str) and re.fullmatch(r"[0-9a-f]{40}", item["revision"]) is not None,
                    "An accepted capability needs an exact executed revision")
            require(re.search(r"(?<![0-9a-fA-F])" + item["revision"] + r"(?![0-9a-fA-F])",
                              bounded_text(evidence, MAX_DOCUMENT_BYTES)) is not None,
                    "Executed revision is absent from its evidence record")
        else:
            require(item["revision"] is None, "Unexecuted capability cannot claim an executed revision")
    return data


def render_status(data: dict) -> str:
    lines = [
        "# Qualification baselines", "",
        "<!-- Generated from qualification-baselines.json by scripts/check_repository.py. -->", "",
        "This register identifies the reviewed execution baselines. It is not a claim that every later commit reran those integrations.",
        "", f"Reviewed on **{data['reviewed_on']}**.", "",
        "| Capability | State | Executed revision | Scope and evidence |",
        "|---|---|---|---|",
    ]
    for item in data["capabilities"]:
        revision = f"`{item['revision']}`" if item["revision"] else "—"
        path = PurePosixPath(item["evidence"])
        target = str(path.relative_to("docs")) if path.parts[0] == "docs" else "../" + str(path)
        target = quote(target, safe="/.-_")
        lines.append(f"| {item['name']} | {item['state']} | {revision} | {item['scope']} [Evidence]({target}). |")
    lines.extend(["", "See [qualification methodology](QUALIFICATION.md) for test counts and provenance, and [remaining gates](PROVIDER_GATES.md) for planned work.", ""])
    return "\n".join(lines)


def prose(text: str) -> tuple[list[tuple[int, str]], list[str]]:
    lines, errors = [], []
    fence_char, fence_length = "", 0
    for number, line in enumerate(text.splitlines(), 1):
        marker = FENCE.match(line)
        if marker:
            token, suffix = marker.groups()
            if not fence_char:
                fence_char, fence_length = token[0], len(token)
            elif token[0] == fence_char and len(token) >= fence_length and not suffix.strip():
                fence_char = ""
            continue
        if not fence_char:
            lines.append((number, line))
    if fence_char:
        errors.append("Unclosed fenced code block")
    return lines, errors


def anchors(lines: list[tuple[int, str]]) -> set[str]:
    found, counts = set(), Counter()
    for _, line in lines:
        match = HEADING.match(line)
        if match:
            title = re.sub(r"[`*~]", "", match[1]).lower()
            slug = re.sub(r"[^\w\- ]", "", title, flags=re.UNICODE).replace(" ", "-")
            candidate = slug
            while candidate in found:
                counts[slug] += 1
                candidate = f"{slug}-{counts[slug]}"
            found.add(candidate)
    return found


def link_target(value: str) -> str:
    value = value.strip()
    if value.startswith("<"):
        end = value.find(">")
        require(end > 0, "Unclosed angle-bracket link")
        return value[1:end]
    return re.split(r"\s+[\"']", value, maxsplit=1)[0]


def reference_label(value: str) -> str:
    return " ".join(value.split()).casefold()


def escaped(text: str, position: int) -> bool:
    count = 0
    while position > 0 and text[position - 1] == "\\":
        count += 1
        position -= 1
    return count % 2 == 1


def code_spans(line: str) -> list[tuple[int, int]]:
    spans = []
    runs = list(re.finditer(r"`+", line))
    index = 0
    while index < len(runs):
        opening = runs[index]
        if escaped(line, opening.start()):
            index += 1
            continue
        closing = next((i for i in range(index + 1, len(runs))
                        if len(runs[i][0]) == len(opening[0])), None)
        if closing is None:
            index += 1
        else:
            spans.append((opening.start(), runs[closing].end()))
            index = closing + 1
    return spans


def inline_destination(line: str, start: int) -> tuple[str, int]:
    """Read a single-line destination with bounded balanced parentheses/title."""
    pos = start
    while pos < len(line) and line[pos].isspace():
        pos += 1
    if pos < len(line) and line[pos] == "<":
        end = line.find(">", pos + 1)
        require(end != -1, "Unclosed angle-bracket link")
        target, pos = line[pos + 1:end], end + 1
    else:
        parts, depth = [], 0
        while pos < len(line):
            char = line[pos]
            if char == "\\" and pos + 1 < len(line) and line[pos + 1] in "()<>\\":
                parts.append(line[pos + 1]); pos += 2; continue
            if char == "(" :
                depth += 1
                require(depth <= 8, "Link nesting exceeds the parser budget")
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            elif char.isspace() and depth == 0:
                break
            parts.append(char); pos += 1
        require(depth == 0, "Unbalanced link destination")
        target = "".join(parts)
    while pos < len(line) and line[pos].isspace():
        pos += 1
    if pos < len(line) and line[pos] in "\"'(":
        delimiter = ")" if line[pos] == "(" else line[pos]
        pos += 1
        while pos < len(line) and (line[pos] != delimiter or escaped(line, pos)):
            pos += 1
        require(pos < len(line), "Unclosed link title")
        pos += 1
        while pos < len(line) and line[pos].isspace():
            pos += 1
    require(pos < len(line) and line[pos] == ")", "Unclosed or unsupported inline link")
    return target, pos + 1


def links(lines: list[tuple[int, str]]) -> tuple[list[tuple[int, str]], list[str]]:
    found, errors, definitions = [], [], {}
    for number, line in lines:
        definition = DEFINITION.match(line)
        if definition:
            label, target = definition.groups()
            key = reference_label(label)
            if key in definitions:
                errors.append(f"{number}: duplicate reference-link definition")
            try:
                definitions[key] = link_target(target)
            except RepositoryError as exc:
                errors.append(f"{number}: {exc}")
    for number, line in lines:
        if DEFINITION.match(line):
            continue
        spans = code_spans(line)
        consumed = []
        def outside(position: int) -> bool:
            return not escaped(line, position) and not any(a <= position < b for a, b in spans + consumed)
        for match in INLINE.finditer(line):
            if not outside(match.start()):
                continue
            try:
                target, end = inline_destination(line, match.end())
                found.append((number, target))
                consumed.append((match.start(), end))
            except RepositoryError as exc:
                errors.append(f"{number}: {exc}")
        for match in REFERENCE.finditer(line):
            if not outside(match.start()):
                continue
            label = reference_label(match[2] or match[1])
            if label in definitions:
                found.append((number, definitions[label]))
            else:
                errors.append(f"{number}: undefined reference link")
    return found, errors


def validate_external(parsed) -> None:
    require(parsed.scheme in {"http", "https", "mailto"}
            and parsed.username is None and parsed.password is None,
            "Unsupported or credential-bearing link")
    if parsed.scheme in {"http", "https"}:
        require(bool(parsed.netloc) and bool(parsed.hostname), "External HTTP link needs a hostname")
        require(not any(char.isspace() or char in "\\%" for char in parsed.netloc), "Invalid HTTP authority")
        # Accessing port performs range/syntax validation in urllib.parse.
        require(parsed.port is None or 1 <= parsed.port <= 65535, "Invalid HTTP port")
    else:
        require(not parsed.netloc and bool(re.fullmatch(r"[^@\s]+@[^@\s]+", parsed.path)),
                "Invalid mailto destination")


def forbidden_file(name: str) -> bool:
    path = PurePosixPath(name)
    return (bool(set(path.parts) & GENERATED_DIRS)
            or (path.name.startswith(".env") and path.name != ".env.example")
            or path.name in {".local-secrets.json", "id_rsa", "id_ed25519", "id_ecdsa", ".coverage", ".DS_Store", "Thumbs.db"}
            or any(part.endswith(".egg-info") for part in path.parts)
            or re.search(r"\.(?:sqlite(?:3)?|db)(?:-(?:wal|shm|journal))?$", path.name, re.I) is not None
            or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".pyc", ".log"})


def audit(root: Path, inventory: list[str]) -> dict:
    root = root.resolve()
    require(len(inventory) == len(set(inventory)), "Duplicate tracked paths")
    tracked, errors, documents = set(inventory), [], {}
    for name in REQUIRED:
        if name not in tracked:
            errors.append(f"Missing required tracked file: {name}")
    for name in sorted(tracked):
        try:
            path = safe_path(root, name)
            if forbidden_file(name):
                errors.append(f"Generated or sensitive path is tracked: {name}")
                continue
            require(path.is_file(), "Tracked file is missing")
            if path.suffix.lower() == ".md":
                content = bounded_text(path, MAX_DOCUMENT_BYTES)
                document, parse_errors = prose(content)
                documents[name] = (document, anchors(document))
                errors.extend(f"{name}: {error}" for error in parse_errors)
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(f"{name}: {failure_message(exc)}")
    local_count = external_count = 0
    for name, (document, _) in documents.items():
        targets, link_errors = links(document)
        errors.extend(f"{name}:{error}" for error in link_errors)
        for number, target in targets:
            try:
                require(not any(ord(c) < 32 for c in target), "Control character in link")
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc:
                    validate_external(parsed)
                    external_count += 1
                    continue
                require(not parsed.query, "Local query strings are not supported")
                decoded = unquote(parsed.path)
                require("\\" not in decoded and not any(ord(c) < 32 for c in decoded), "Unsafe local link")
                candidate = ((root / decoded.lstrip("/")) if decoded.startswith("/")
                             else root / PurePosixPath(name).parent / decoded) if decoded else root / name
                resolved = candidate.resolve()
                require(resolved.is_relative_to(root), "Local link escapes repository")
                relative = resolved.relative_to(root).as_posix()
                # Check lexical parents as well, so an in-repository symlink is not followed.
                current = candidate
                while current != root and current != current.parent:
                    require(not current.is_symlink(), "Symlink link target is not admitted")
                    current = current.parent
                if resolved.is_dir():
                    prefix = relative.rstrip("/") + "/" if relative != "." else ""
                    require(any(p.startswith(prefix) for p in tracked), "Untracked directory link")
                    require(not parsed.fragment, "Directory anchors are not supported")
                else:
                    require(relative in tracked and resolved.is_file(), "Broken or untracked local link")
                    if parsed.fragment:
                        require(relative in documents, "Anchor target is not a Markdown document")
                        require(unquote(parsed.fragment) in documents[relative][1], "Missing local heading anchor")
                local_count += 1
            except (OSError, ValueError, RuntimeError) as exc:
                errors.append(f"{name}:{number}: {failure_message(exc)}")
    try:
        register = load_register(root)
        require(all(item["evidence"] in tracked for item in register["capabilities"]), "Untracked qualification evidence")
        require(bounded_text(safe_path(root, STATUS_PAGE), MAX_DOCUMENT_BYTES).replace("\r\n", "\n") == render_status(register),
                "STATUS.md differs from qualification-baselines.json; regenerate the status page")
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        errors.append(f"Qualification register: {failure_message(exc)}")
    return {"schema_version": "ilc-repository-check/1", "status": "PASS" if not errors else "FAIL",
            "tracked_files": len(tracked), "markdown_files": len(documents),
            "local_links_checked": local_count, "external_links_not_requested": external_count,
            "errors": errors,
            "scope": "Tracked Markdown paths/ATX anchors, generated qualification summary and repository hygiene; not runtime qualification or a secret scan"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--render-status", action="store_true", help="Print the generated status page without modifying files")
    parser.add_argument("--output", type=Path, help="Write a new JSON result; refuse an existing file")
    args = parser.parse_args(argv)
    try:
        if args.render_status:
            require(args.output is None, "--render-status and --output are mutually exclusive")
            print(render_status(load_register(args.root)), end="")
            return 0
        result = audit(args.root, tracked_files(args.root))
        serialized = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(serialized)
        print(serialized, end="")
        return 0 if result["status"] == "PASS" else 1
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "ERROR", "error": failure_message(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""A real, loopback HTTP source exposing immutable, token-bound pagination."""
from __future__ import annotations
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from .canonical import canonical, read_json, digest, within, IDENTIFIER


def build_server(root: Path, port=0):
    manifest = read_json(within(root,"source_manifest.json"))
    if any(not IDENTIFIER.fullmatch(name) for name in manifest["entities"]):
        raise ValueError("Invalid synthetic entity name")
    entities = {name: read_json(within(root, f"{name}.json")) for name in manifest["entities"]}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def respond(self, status, value):
            payload = canonical(value)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/v1/manifest":
                self.respond(200, manifest)
                return
            parts = parsed.path.split("/")
            if len(parts) != 6 or parts[1:3] != ["v1", "snapshots"] or parts[4] != "entities":
                self.respond(404, {"error": "not_found"})
                return
            snapshot, entity = parts[3], parts[5]
            if snapshot != manifest["snapshot_id"] or entity not in entities:
                self.respond(409, {"error": "snapshot_not_available"})
                return
            try:
                params = parse_qs(parsed.query)
                offset = int(params.get("cursor", ["0"])[0])
                limit = int(params.get("limit", ["137"])[0])
                if offset < 0 or not 1 <= limit <= 1000:
                    raise ValueError
            except ValueError:
                self.respond(400, {"error": "invalid_page"})
                return
            data = entities[entity]
            batch = data[offset:offset+limit]
            self.respond(200, {"snapshot_id": snapshot, "entity": entity,
                               "total_rows": len(data), "fields": manifest["entities"][entity]["fields"],
                               "as_of": manifest["as_of"], "rows": batch,
                               "cursor": str(offset),
                               "next_cursor": str(offset+len(batch)) if offset+len(batch) < len(data) else None})
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server

@contextmanager
def serving(root: Path):
    server = build_server(root)
    thread = threading.Thread(target=server.serve_forever, name="ilc-source-http", daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        if thread.is_alive():
            raise RuntimeError("Source server did not stop")

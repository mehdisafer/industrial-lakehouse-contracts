# Recovery and uncertain outcomes

| Failure window | Durable observation | Required outcome |
|---|---|---|
| Before admission | No bound key | A new admission is possible |
| During source capture | Capture-start marker without finalized Bronze manifest | Same key fails closed; do not reread different live data |
| After finalized Bronze | Manifest bound to plan | Reuse exact inputs; verify every byte |
| After target write, before state commit | Immutable candidate exists, accepted pointer/watermark unchanged | Recompute from Bronze, compare candidate, then accept once |
| After acceptance, before reply/file projection | Journal already contains accepted receipt | Return original acceptance and reconstruct missing projection; no republish |
| After rejection, before receipt-file projection | Journal contains rejection receipt | Reconstruct projection, never relabel accepted |
| Later accepted generation exists | Previous base no longer current | Old attempt cannot move the pointer backwards |
| Artifact changed/missing | Digest/inventory disagrees with receipt | Consumer/refresher fails closed; no automatic deletion or repair |

The executable reference qualification ends a separate Python process with `os._exit(73)` after target commit. It observes unchanged watermarks and the old reporting pointer, stops the source HTTP server, and recovers using the exact same logical key. It also tests an exit after state acceptance. These are real process/filesystem/SQLite tests, not a Windows/SCM/Spark qualification.

A key is bound to code and dependency versions. After a code upgrade, do not blindly resume an old ambiguous run: use the previous pinned release to reconcile it, or perform an explicitly reviewed migration. The implementation rejects changed requests rather than silently reinterpret them.

A `RUNNING` journal event is durable last-known state, not proof that a process is alive. There is no heartbeat-based lease monitor yet. Reports retain the accepted version and expose latest-attempt status and staleness; they do not imply that a refresh succeeded.

## Operator steps

Inspect `ilc status`, the run plan, event timeline and input/target manifests. Keep all ambiguous artifacts. Reuse the same key only when its exact request is unchanged. An incomplete capture needs a reviewed new admission after the original read-only capture is accounted for. A rejected contract/input needs correction and a new logical batch. Never delete a row in the journal to force reuse of a key.

Reference SQLite same-path backup/restore is implemented and tested, including real HTTP report readback and accepted replay with the source offline. PostgreSQL/Delta restore and path relocation remain unqualified. See [the restore procedure](BACKUP_RESTORE.md). The journal namespace is derived from its root location; copying the directory to a new path deliberately does not silently assume the old namespace. No retention/vacuum/deprovision operation is automated in this increment.

## Native readback and catalog effects

For a Delta target, successful staging writes are not sufficient. Before state
acceptance, the engine must reread version 0 from its final location and reconcile
its actual rows with the bounded reference projection. The proof is bound to the
target manifest and checked by reporting and replay. Its unit tests do not prove
that this works under Spark until the native harness is executed.

Catalog intent is persisted before any write and backed up with reference state.
A lost response with an exact remote readback is recoverable. A missing or
conflicting object after a recorded intent must be escalated; a new attempt is not
permission to create another effect. The contract suite demonstrates this with
MockTransport and an explicitly named HTTP protocol emulator, not a real server.

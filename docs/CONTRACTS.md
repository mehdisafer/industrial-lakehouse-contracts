# Metadata contracts and their limits

| Object | Implementation |
|---|---|
| Business contract | `contracts/sales.json`: identity/version, owner, classification, sites, fields/types/nullability, keys, watermark, reviewed model |
| Execution profile | Connector, source location, FULL/INCREMENTAL mode, backend, extraction budgets, lookback, freshness |
| Access policy | Site sets, report/catalog/evidence permissions, bearer-token SHA-256 digests; outside Git |
| Frozen plan | Complete validated contract/profile, bounds, previous accepted batch, source/runtime hashes |
| Journal | Admission, attempts, capture, failure/rejection, publication and recovery events |
| Evidence | Actual source vector, counts/bytes, exact sums, result/manifest hashes, versions, commit/dirty state and non-executed integrations |

These are original versioned `ilc-*` schemas. ODCS conformance is explicitly not assessed. There is no agent policy or LLM execution in P01.

## Value rules

Strings are bounded. Integer values reject booleans, floats, exponent notation and out-of-range integers. Monetary inputs use decimal literals, never binary floating point; their precision/scale is checked without silent rounding. Timestamps must include UTC (`Z` or `+00:00`), then normalize to six fractional digits.

Rows must have exactly the contract's fields. Unknown or missing fields are quarantined. Duplicate primary keys quarantine every conflicting member, not whichever row happens to appear later. All implemented DQ rules are blocking in this increment; configurable warning-only rules are not yet implemented.

The reviewed model checks order/customer site consistency, known sites, line/product/order relationships, line amount = quantity × unit price, shipment/line relationships, and no overshipment. Source→Silver accounting and independent Silver→Gold keys/counts/Decimal totals are stored.

## Evolution

Any changed contract needs a greater semantic version. Changes to existing fields/identity are treated conservatively as breaking. They require a new major version and FULL mode for every entity. This gate does not implement a general migration engine: the fixed Gold model must still understand the new fields/types.

Adding an entity with a compatible source and supported field types is exercised without changing engine bytes. The new entity is catalogued but is not automatically included in the fixed sales model. A new site also requires an explicit access-policy change; no token gains wider permissions automatically.

## Bounds

A plan fixes an upper timestamp. FULL starts from the epoch. INCREMENTAL uses the previous accepted upper timestamp minus the configured lookback, inclusive on both ends. The full candidate is built by primary-key upsert into the previous accepted Silver. Same timestamp with changed payload is ambiguous and blocked. No watermark advances for rejected data.

This is not transaction-log CDC. Source deletions, updates outside the overlap and cross-source changes that cannot satisfy the pinned fixture manifest require a separately designed source contract.

## Gold dimensions

Customer, product and site dimensions are materialized per accepted generation, joined by their business keys to the order-line fact. These are versioned snapshot dimensions (SCD1 within a generation), not SCD2 history. The immutable dataset generations preserve prior snapshots. A surrogate-key/SCD2 migration is not silently implied.

# API contract

All implementations bind `127.0.0.1:<port>` and serve JSON (`Content-Type:
application/json`). Responses are compared after JSON parsing; key order and
whitespace are not part of the contract.

## Data model

```json
{
  "id": 42,
  "name": "item-42",
  "price": 42.99,
  "tags": ["tag-0", "tag-3"],
  "created_at": "2026-01-01T00:00:00Z"
}
```

The store is seeded with items `1..=10000` where
`name = "item-{id}"`, `price = (id % 1000) + 0.99`,
`tags = ["tag-{id % 7}", "tag-{id % 13}"]`, `created_at` fixed as above.

## Endpoints

### `GET /health`
`200` `{"status":"ok"}`

### `GET /items/{id}`
`200` with the item, or `404` `{"error":"not found"}`.
Non-numeric `id`: a 4xx of the framework's choosing (recorded, not asserted).

### `GET /items?limit=N`
`limit` default `20`, clamped to `[1, 1000]`. Returns items with ids
`1..=limit` in ascending id order:
`200` `{"count": N, "items": [ ... ]}`

### `POST /items`
Body `{"name": string, "price": number, "tags": [string] (optional)}`.
- `201` with the created item (`id` is the next integer, `created_at` is now, RFC 3339 UTC).
- `400` `{"error": "<message>"}` when `name` is empty/whitespace or `price < 0`.
- Structurally invalid JSON / wrong types: a 4xx of the framework's choosing (recorded, not asserted).

### `GET /compute/hash?n=N`
`n` default `1000`, clamped to `[1, 1000000]`.
`digest = sha256^n(ascii(n))`, i.e. start with the decimal string of `n` as
bytes and apply SHA-256 `n` times. Returns `200` `{"n": N, "digest": "<hex>"}`.
Every implementation must return the identical digest for the same `n`.

### `GET /io/wait?ms=M`
`ms` default `10`, clamped to `[0, 5000]`. Sleeps asynchronously for `M` ms.
`200` `{"waited_ms": M}`

### `GET /mixed?id=I`
`id` default `1`. Waits 5 ms (simulated DB), computes `sha256^200(ascii(id))`,
returns `200` `{"item": <item>, "digest": "<hex>"}` or `404` as for `/items/{id}`.

# API Performance Lab — results `aggregate of 2 runs`

*2026-11-27T05:20:12+00:00* · Apple M5 (10 cores) · macOS-26.5-arm64-arm-64bit-Mach-O  
**Median of 2 runs** (`20261127-002012`, `20261127-002947`); throughput and p99 tables show min–max across runs.  
Load: oha 1.17.0, concurrency **64**, **10 s** per scenario after **3 s** warm-up, fresh process per scenario. Load generator and services share the machine; read the numbers as relative.

## Implementations and implementation complexity

LOC is non-blank, non-comment lines for the identical contract. Deps is every third-party package shipped (transitive). Cold start is process launch to first `200` from `/health`, median of 5 starts.

| Implementation | Toolchain | Contract | LOC | Deps | Build (s) | Artifact (MB) | Cold start ms (min–max) | Idle RSS (MB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | rustc 1.98.0 | pass | 256 | 207 | – | – | 22 (20–33) | 8.1 |
| `go-nethttp-pg` | go1.27.4 | pass | 283 | 15 | – | – | 12 (10–29) | 17.3 |
| `python-fastapi-pg` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | pass | 129 | 22 | – | – | 328 (293–402) | 699.5 |
| `python-fastapi-1w-pg` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | pass | 129 | 22 | – | – | 157 (154–161) | 65.0 |

## Throughput (requests/s)

| Scenario | `rust-axum-pg` | `go-nethttp-pg` | `python-fastapi-pg` | `python-fastapi-1w-pg` |
|---|---:|---:|---:|---:|
| health | 176,141 <sub>(173,523–178,758)</sub> | 143,698 <sub>(143,143–144,253)</sub> | 78,312 <sub>(77,310–79,314)</sub> | 33,313 <sub>(32,680–33,947)</sub> |
| get | 41,883 <sub>(40,456–43,310)</sub> | 66,235 <sub>(66,167–66,303)</sub> | 24,139 <sub>(22,553–25,725)</sub> | 14,107 <sub>(13,746–14,468)</sub> |
| list | 17,730 <sub>(17,088–18,371)</sub> | 14,984 <sub>(14,961–15,008)</sub> | 5,237 <sub>(4,654–5,820)</sub> | 2,181 <sub>(2,177–2,185)</sub> |
| create | 35,615 <sub>(33,814–37,416)</sub> | 47,900 <sub>(47,235–48,564)</sub> | 18,508 <sub>(17,790–19,227)</sub> | 11,078 <sub>(10,720–11,435)</sub> |
| cpu | 21,896 <sub>(20,525–23,267)</sub> | 10,408 <sub>(10,147–10,669)</sub> | 3,134 <sub>(3,006–3,262)</sub> | 979 <sub>(979–979)</sub> |
| io | 5,204 <sub>(5,182–5,227)</sub> | 5,604 <sub>(5,572–5,637)</sub> | 5,645 <sub>(5,630–5,660)</sub> | 5,465 <sub>(5,461–5,468)</sub> |
| mixed | 36,479 <sub>(35,892–37,066)</sub> | 54,439 <sub>(53,887–54,990)</sub> | 17,611 <sub>(16,830–18,392)</sub> | 8,202 <sub>(7,853–8,550)</sub> |

## Latency: p50 / p95 / p99 (ms)

| Scenario | `rust-axum-pg` | `go-nethttp-pg` | `python-fastapi-pg` | `python-fastapi-1w-pg` |
|---|---:|---:|---:|---:|
| health | 0.33 / 0.59 / 1.02 <sub>(0.79–1.25)</sub> | 0.38 / 0.99 / 1.81 <sub>(1.74–1.87)</sub> | 0.58 / 2.31 / 5.35 <sub>(4.45–6.25)</sub> | 1.88 / 2.01 / 3.73 <sub>(3.66–3.80)</sub> |
| get | 1.51 / 1.68 / 1.96 <sub>(1.80–2.11)</sub> | 0.93 / 1.33 / 1.71 <sub>(1.65–1.76)</sub> | 1.94 / 6.41 / 10.79 <sub>(10.09–11.48)</sub> | 4.54 / 7.02 / 7.74 <sub>(7.46–8.02)</sub> |
| list | 3.45 / 4.45 / 6.35 <sub>(6.17–6.53)</sub> | 4.16 / 5.70 / 6.82 <sub>(6.77–6.88)</sub> | 12.18 / 26.34 / 42.55 <sub>(33.92–51.17)</sub> | 29.09 / 37.49 / 78.05 <sub>(77.15–78.94)</sub> |
| create | 1.78 / 2.02 / 2.31 <sub>(2.23–2.39)</sub> | 1.28 / 1.87 / 2.45 <sub>(2.40–2.50)</sub> | 2.81 / 8.41 / 13.65 <sub>(13.23–14.06)</sub> | 5.68 / 6.49 / 8.45 <sub>(6.33–10.57)</sub> |
| cpu | 2.84 / 4.87 / 6.00 <sub>(5.79–6.20)</sub> | 1.81 / 24.69 / 40.60 <sub>(39.56–41.64)</sub> | 17.79 / 43.13 / 80.64 <sub>(59.22–102.07)</sub> | 65.20 / 67.13 / 75.64 <sub>(71.25–80.04)</sub> |
| io | 12.30 / 13.20 / 13.49 <sub>(13.42–13.56)</sub> | 11.40 / 12.18 / 12.67 <sub>(12.60–12.75)</sub> | 11.29 / 12.36 / 12.78 <sub>(12.70–12.86)</sub> | 11.73 / 12.81 / 13.51 <sub>(13.44–13.58)</sub> |
| mixed | 1.74 / 2.00 / 2.14 <sub>(2.08–2.20)</sub> | 1.09 / 1.86 / 2.43 <sub>(2.39–2.48)</sub> | 2.88 / 8.54 / 13.25 <sub>(10.04–16.46)</sub> | 7.60 / 12.22 / 15.68 <sub>(12.42–18.93)</sub> |

## Peak RSS during load (MB, whole process tree)

| Scenario | `rust-axum-pg` | `go-nethttp-pg` | `python-fastapi-pg` | `python-fastapi-1w-pg` |
|---|---:|---:|---:|---:|
| health | 12.4 | 29.8 | 712.4 | 68.5 |
| get | 11.8 | 31.3 | 711.7 | 67.4 |
| list | 14.5 | 38.2 | 715.1 | 69.8 |
| create | 11.9 | 31.0 | 711.6 | 67.6 |
| cpu | 11.4 | 41.3 | 719.6 | 70.1 |
| io | 11.3 | 28.5 | 707.9 | 67.5 |
| mixed | 11.8 | 34.2 | 710.8 | 67.5 |

## CPU per 1,000 requests (server CPU-ms)

Lower is better: compute each request actually consumed, independent of how saturated the machine was. Two implementations with equal req/s but 3× different CPU/1k do not have equal performance; one has 3× the headroom.

| Scenario | `rust-axum-pg` | `go-nethttp-pg` | `python-fastapi-pg` | `python-fastapi-1w-pg` |
|---|---:|---:|---:|---:|
| health | 20.3 | 33.4 | 86.0 | 30.0 |
| get | 77.9 | 65.6 | 268.8 | 70.9 |
| list | 328.6 | 353.0 | 1,415.3 | 460.3 |
| create | 87.8 | 69.3 | 337.3 | 89.4 |
| cpu | 403.8 | 667.5 | 3,015.9 | 1,040.2 |
| io | 31.2 | 62.6 | 132.6 | 64.2 |
| mixed | 100.8 | 90.6 | 403.3 | 121.4 |

## Error rate under saturation

Concurrency far above the normal runs, with a per-request timeout; every timeout, refused or reset connection and non-2xx counts as an error. macOS `kern.ipc.somaxconn` here is 128, so connection bursts above that queue in the kernel for every implementation alike.

### `sat-get` — `/items/42` at concurrency 1000, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 37,568 | 26.84 | 33.82 | 133.97 | **0.00%** | 0 | 51.3 | – |
| `go-nethttp-pg` | 65,068 | 15.01 | 22.80 | 212.81 | **0.00%** | 0 | 74.1 | – |
| `python-fastapi-pg` | 23,761 | 36.33 | 150.18 | 416.60 | **0.00%** | 0 | 736.8 | – |
| `python-fastapi-1w-pg` | 12,885 | 76.87 | 190.95 | 546.79 | **0.00%** | 0 | 93.3 | – |

### `sat-cpu` — `/compute/hash?n=20000` at concurrency 500, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 4,385 | 105.52 | 310.62 | 459.99 | **0.00%** | 0 | 28.8 | – |
| `go-nethttp-pg` | 3,660 | 19.96 | 782.87 | 999.55 | **0.48%** | 173 | 76.5 | timeout: 173 |
| `python-fastapi-pg` | 990 | 488.14 | 947.32 | 1,000.06 | **2.56%** | 239 | 749.6 | timeout: 239 |
| `python-fastapi-1w-pg` | 631 | 292.27 | 728.02 | 983.43 | **68.09%** | 3950 | 78.5 | timeout: 3950 |

## Memory per open connection

1000 keep-alive connections opened, one request each, then held idle for 1 s. Per-connection cost is what bounds long-lived streaming/WebSocket/SSE fan-out.

| Implementation | Opened | Failed | Idle RSS MB | Held RSS MB | KB / connection | After close MB |
|---|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 1000 | 0 | 8.0 | 40.4 | **31.6** | 40.4 |
| `go-nethttp-pg` | 1000 | 0 | 17.2 | 38.9 | **21.2** | 39.2 |
| `python-fastapi-pg` | 1000 | 0 | 699.3 | 718.2 | **18.4** | 718.2 |
| `python-fastapi-1w-pg` | 1000 | 0 | 65.2 | 77.3 | **11.9** | 76.3 |

## Recovery after a load spike

Probe: sequential keep-alive requests to `/items/42` from one client. Spike: `/items?limit=200` at concurrency 256 for 5 s. Then probe again immediately and after 10 s idle. *Retained* is how much of the spike's RSS growth was still held after settling: it shows whether the runtime gives memory back to the OS.

| Implementation | Spike req/s | Idle MB | Peak MB | +0 s MB | +10 s MB | Retained | Probe before p50/p99 | Probe +0 s | Probe +10 s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 17,862 | 8.1 | 22.4 | 22.4 | 22.4 | **100.0%** | 0.18 / 0.97 | 0.15 / 0.27 | 0.13 / 0.38 |
| `go-nethttp-pg` | 18,495 | 17.2 | 50.2 | 50.2 | 50.3 | **100.3%** | 0.12 / 0.34 | 0.14 / 0.24 | 0.13 / 0.31 |
| `python-fastapi-pg` | 6,620 | 699.3 | 720.7 | 720.7 | 720.7 | **100.0%** | 0.22 / 0.74 | 0.38 / 1.21 | 0.21 / 0.63 |
| `python-fastapi-1w-pg` | 2,138 | 65.1 | 75.3 | 75.3 | 75.3 | **100.0%** | 0.22 / 0.59 | 0.22 / 6.18 | 0.22 / 0.53 |

## Per-scenario detail

### `health`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 176,141 | 0.33 | 0.59 | 1.02 | 2.92 | 25.84 | 3.06× | 12.4 | 0 | 20.3 | 35% | 0 (0.00%) |
| `go-nethttp-pg` | 143,698 | 0.38 | 0.99 | 1.81 | 3.84 | 18.78 | 4.81× | 29.8 | 0 | 33.4 | 47% | 0 (0.00%) |
| `python-fastapi-pg` | 78,312 | 0.58 | 2.31 | 5.35 | 10.61 | 79.41 | 9.25× | 712.4 | 1 | 86.0 | 67% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 33,313 | 1.88 | 2.01 | 3.73 | 4.12 | 62.33 | 1.98× | 68.5 | 2 | 30.0 | 10% | 0 (0.00%) |

### `get`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 41,883 | 1.51 | 1.68 | 1.96 | 3.80 | 14.75 | 1.30× | 11.8 | 0 | 77.9 | 32% | 0 (0.00%) |
| `go-nethttp-pg` | 66,235 | 0.93 | 1.33 | 1.71 | 2.75 | 11.12 | 1.84× | 31.3 | 1 | 65.6 | 43% | 0 (0.00%) |
| `python-fastapi-pg` | 24,139 | 1.94 | 6.41 | 10.79 | 27.66 | 129.52 | 5.56× | 711.7 | 10 | 268.8 | 64% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 14,107 | 4.54 | 7.02 | 7.74 | 12.33 | 24.86 | 1.71× | 67.4 | 1 | 70.9 | 10% | 0 (0.00%) |

### `list`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 17,730 | 3.45 | 4.45 | 6.35 | 13.46 | 41.96 | 1.84× | 14.5 | 0 | 328.6 | 58% | 0 (0.00%) |
| `go-nethttp-pg` | 14,984 | 4.16 | 5.70 | 6.82 | 9.04 | 21.70 | 1.64× | 38.2 | 7 | 353.0 | 53% | 0 (0.00%) |
| `python-fastapi-pg` | 5,237 | 12.18 | 26.34 | 42.55 | 85.24 | 176.52 | 3.49× | 715.1 | 86 | 1,415.3 | 74% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 2,181 | 29.09 | 37.49 | 78.05 | 224.95 | 561.45 | 2.68× | 69.8 | 5 | 460.3 | 10% | 0 (0.00%) |

### `create`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 35,615 | 1.78 | 2.02 | 2.31 | 3.47 | 16.45 | 1.30× | 11.9 | 0 | 87.8 | 31% | 0 (0.00%) |
| `go-nethttp-pg` | 47,900 | 1.28 | 1.87 | 2.45 | 4.42 | 13.75 | 1.92× | 31.0 | 1 | 69.3 | 33% | 0 (0.00%) |
| `python-fastapi-pg` | 18,508 | 2.81 | 8.41 | 13.65 | 24.04 | 82.35 | 4.86× | 711.6 | 13 | 337.3 | 62% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 11,078 | 5.68 | 6.49 | 8.45 | 15.28 | 33.00 | 1.49× | 67.6 | 1 | 89.4 | 10% | 0 (0.00%) |

### `cpu`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 21,896 | 2.84 | 4.87 | 6.00 | 8.51 | 33.41 | 2.11× | 11.4 | 0 | 403.8 | 88% | 0 (0.00%) |
| `go-nethttp-pg` | 10,408 | 1.81 | 24.69 | 40.60 | 63.52 | 101.71 | 22.43× | 41.3 | 41 | 667.5 | 69% | 0 (0.00%) |
| `python-fastapi-pg` | 3,134 | 17.79 | 43.13 | 80.64 | 115.74 | 154.92 | 4.53× | 719.6 | 32 | 3,015.9 | 94% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 979 | 65.20 | 67.13 | 75.64 | 365.57 | 479.97 | 1.16× | 70.1 | 19 | 1,040.2 | 10% | 0 (0.00%) |

### `io`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 5,204 | 12.30 | 13.20 | 13.49 | 19.03 | 19.35 | 1.10× | 11.3 | 3 | 31.2 | 2% | 0 (0.00%) |
| `go-nethttp-pg` | 5,604 | 11.40 | 12.18 | 12.67 | 17.43 | 20.81 | 1.11× | 28.5 | 15 | 62.6 | 4% | 0 (0.00%) |
| `python-fastapi-pg` | 5,645 | 11.29 | 12.36 | 12.78 | 21.37 | 27.47 | 1.13× | 707.9 | 48 | 132.6 | 7% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 5,465 | 11.73 | 12.81 | 13.51 | 20.85 | 23.37 | 1.15× | 67.5 | 7 | 64.2 | 4% | 0 (0.00%) |

### `mixed`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 36,479 | 1.74 | 2.00 | 2.14 | 2.56 | 6.88 | 1.23× | 11.8 | 0 | 100.8 | 37% | 0 (0.00%) |
| `go-nethttp-pg` | 54,439 | 1.09 | 1.86 | 2.43 | 4.06 | 19.29 | 2.24× | 34.2 | 2 | 90.6 | 49% | 0 (0.00%) |
| `python-fastapi-pg` | 17,611 | 2.88 | 8.54 | 13.25 | 21.54 | 58.85 | 4.59× | 710.8 | 18 | 403.3 | 71% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 8,202 | 7.60 | 12.22 | 15.68 | 27.66 | 51.28 | 2.06× | 67.5 | 2 | 121.4 | 10% | 0 (0.00%) |

## Behaviour that differs despite the shared contract

Recorded by the contract test (not asserted). Same inputs, framework-chosen responses.

- `rust-axum-pg`
  - non-numeric id -> 400 'Invalid URL: Cannot parse `not-a-number` to a `u64`'
  - malformed json -> 400 'Failed to parse the request body as JSON: key must be a string at line 1 column 2'
  - wrong types -> 422 'Failed to deserialize the JSON body into the target type: name: invalid type: integer `123`, expected a string at line 1 column 12'
- `go-nethttp-pg`
  - non-numeric id -> 400 {'error': 'invalid id'}
  - malformed json -> 400 {'error': 'invalid json'}
  - wrong types -> 400 {'error': 'invalid json'}
- `python-fastapi-pg`
  - non-numeric id -> 422 b'{"detail":[{"type":"int_parsing","loc":["path","item_id"],"msg":"Input should be a valid integer, unable to parse string'
  - malformed json -> 422 b'{"detail":[{"type":"json_invalid","loc":["body",1],"msg":"JSON decode error","input":{},"ctx":{"error":"Expecting proper'
  - wrong types -> 422 b'{"detail":[{"type":"string_type","loc":["body","name"],"msg":"Input should be a valid string","input":123},{"type":"float_parsing","loc":["body","price"],"msg":'
- `python-fastapi-1w-pg`
  - non-numeric id -> 422 b'{"detail":[{"type":"int_parsing","loc":["path","item_id"],"msg":"Input should be a valid integer, unable to parse string'
  - malformed json -> 422 b'{"detail":[{"type":"json_invalid","loc":["body",1],"msg":"JSON decode error","input":{},"ctx":{"error":"Expecting proper'
  - wrong types -> 422 b'{"detail":[{"type":"string_type","loc":["body","name"],"msg":"Input should be a valid string","input":123},{"type":"float_parsing","loc":["body","price"],"msg":'

## Reading the numbers

- **p99/p50** is the tail-flatness ratio. GC pauses and the GIL show up here, not in the median.
- **CPU ms/1k** is the cost side of throughput. Equal req/s at 3× the CPU is not equal performance; it is 3× less headroom.
- **CPU util** is server CPU over all cores. Near 100% means the service was the bottleneck; well below means the load generator or the scenario's I/O wait was.
- **ΔRSS/req** is memory growth per request over the run. It only means something for `create`, where it is the per-item cost of the in-memory store; elsewhere it should be ~0.
- `io` and `mixed` are latency-bound by design: with concurrency *c* and wait *w*, throughput cannot exceed *c / w*. Converging numbers there are the expected result; the interesting columns are CPU/1k, RSS and tail latency.
- The Python rows are the same code; `python-fastapi` runs one Uvicorn worker per core, `python-fastapi-1w` runs one. The gap between them is the cost of the GIL; the gap between `python-fastapi` and Go is the cost of multi-process vs. multi-thread.

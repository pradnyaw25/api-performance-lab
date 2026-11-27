# API Performance Lab — results `20261127-000906`

*2026-11-27T05:09:06+00:00* · Apple M5 (10 cores) · macOS-26.5-arm64-arm-64bit-Mach-O  
Load: oha 1.17.0, concurrency **64**, **10 s** per scenario after **3 s** warm-up, fresh process per scenario. Load generator and services share the machine; read the numbers as relative.

## Implementations and implementation complexity

LOC is non-blank, non-comment lines for the identical contract. Deps is every third-party package shipped (transitive). Cold start is process launch to first `200` from `/health`, median of 5 starts.

| Implementation | Toolchain | Contract | LOC | Deps | Build (s) | Artifact (MB) | Cold start ms (min–max) | Idle RSS (MB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | rustc 1.98.0 | pass | 256 | 207 | – | – | 35 (27–40) | 8.1 |
| `go-nethttp-pg` | go1.27.4 | pass | 283 | 15 | – | – | 22 (22–28) | 17.3 |
| `python-fastapi-pg` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | fail | 129 | 22 | – | – | 416 (316–434) | 699.5 |
| `python-fastapi-1w-pg` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | fail | 129 | 22 | – | – | 185 (153–187) | 65.3 |

- `python-fastapi-pg` produced no results: contract test failed
- `python-fastapi-1w-pg` produced no results: contract test failed

## Throughput (requests/s)

| Scenario | `rust-axum-pg` | `go-nethttp-pg` |
|---|---:|---:|
| health | 190,432 | 171,752 |
| get | 44,218 | 75,519 |
| list | 18,775 | 16,592 |
| create | 39,160 | 54,506 |
| cpu | 23,852 | 11,321 |
| io | 5,246 | 5,591 |
| mixed | 43,890 | 56,061 |

## Latency: p50 / p95 / p99 (ms)

| Scenario | `rust-axum-pg` | `go-nethttp-pg` |
|---|---:|---:|
| health | 0.32 / 0.52 / 0.79 | 0.27 / 0.99 / 2.16 |
| get | 1.42 / 1.57 / 1.86 | 0.79 / 1.28 / 1.89 |
| list | 3.18 / 4.58 / 7.28 | 3.67 / 5.36 / 7.12 |
| create | 1.61 / 1.84 / 2.27 | 1.10 / 1.68 / 2.38 |
| cpu | 2.63 / 4.39 / 5.39 | 1.65 / 23.11 / 37.89 |
| io | 12.16 / 13.11 / 13.37 | 11.40 / 12.27 / 12.90 |
| mixed | 1.45 / 1.59 / 1.69 | 1.05 / 1.83 / 2.43 |

## Peak RSS during load (MB, whole process tree)

| Scenario | `rust-axum-pg` | `go-nethttp-pg` |
|---|---:|---:|
| health | 12.2 | 31.5 |
| get | 11.8 | 30.6 |
| list | 14.1 | 39.7 |
| create | 11.9 | 31.6 |
| cpu | 11.5 | 43.5 |
| io | 11.4 | 28.5 |
| mixed | 11.9 | 34.8 |

## CPU per 1,000 requests (server CPU-ms)

Lower is better: compute each request actually consumed, independent of how saturated the machine was. Two implementations with equal req/s but 3× different CPU/1k do not have equal performance; one has 3× the headroom.

| Scenario | `rust-axum-pg` | `go-nethttp-pg` |
|---|---:|---:|
| health | 20.6 | 28.0 |
| get | 74.5 | 54.4 |
| list | 306.5 | 304.4 |
| create | 82.1 | 60.4 |
| cpu | 371.4 | 599.0 |
| io | 33.4 | 58.9 |
| mixed | 87.6 | 85.4 |

## Error rate under saturation

Concurrency far above the normal runs, with a per-request timeout; every timeout, refused or reset connection and non-2xx counts as an error. macOS `kern.ipc.somaxconn` here is 128, so connection bursts above that queue in the kernel for every implementation alike.

### `sat-get` — `/items/42` at concurrency 1000, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 43,751 | 22.82 | 25.00 | 117.75 | **0.00%** | 0 | 51.3 | – |
| `go-nethttp-pg` | 68,439 | 14.47 | 21.30 | 74.72 | **0.00%** | 0 | 74.7 | – |

### `sat-cpu` — `/compute/hash?n=20000` at concurrency 500, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 7,784 | 57.86 | 180.84 | 261.36 | **0.00%** | 0 | 28.8 | – |
| `go-nethttp-pg` | 3,803 | 34.90 | 733.22 | 999.89 | **0.25%** | 93 | 77.3 | timeout: 93 |

## Memory per open connection

1000 keep-alive connections opened, one request each, then held idle for 1 s. Per-connection cost is what bounds long-lived streaming/WebSocket/SSE fan-out.

| Implementation | Opened | Failed | Idle RSS MB | Held RSS MB | KB / connection | After close MB |
|---|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 1000 | 0 | 8.1 | 40.5 | **31.6** | 40.5 |
| `go-nethttp-pg` | 1000 | 0 | 17.6 | 38.8 | **20.8** | 39.5 |

## Recovery after a load spike

Probe: sequential keep-alive requests to `/items/42` from one client. Spike: `/items?limit=200` at concurrency 256 for 5 s. Then probe again immediately and after 10 s idle. *Retained* is how much of the spike's RSS growth was still held after settling: it shows whether the runtime gives memory back to the OS.

| Implementation | Spike req/s | Idle MB | Peak MB | +0 s MB | +10 s MB | Retained | Probe before p50/p99 | Probe +0 s | Probe +10 s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 19,771 | 8.1 | 22.7 | 22.7 | 22.7 | **100.0%** | 0.16 / 0.99 | 0.08 / 0.12 | 0.15 / 0.38 |
| `go-nethttp-pg` | 20,255 | 17.7 | 48.9 | 48.9 | 49.0 | **100.2%** | 0.13 / 0.31 | 0.11 / 0.25 | 0.13 / 0.33 |

## Per-scenario detail

### `health`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 190,432 | 0.32 | 0.52 | 0.79 | 1.58 | 5.92 | 2.51× | 12.2 | 0 | 20.6 | 39% | 0 (0.00%) |
| `go-nethttp-pg` | 171,752 | 0.27 | 0.99 | 2.16 | 4.64 | 11.83 | 8.10× | 31.5 | 1 | 28.0 | 47% | 0 (0.00%) |

### `get`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 44,218 | 1.42 | 1.57 | 1.86 | 5.67 | 94.96 | 1.31× | 11.8 | 0 | 74.5 | 33% | 0 (0.00%) |
| `go-nethttp-pg` | 75,519 | 0.79 | 1.28 | 1.89 | 4.99 | 26.58 | 2.40× | 30.6 | 1 | 54.4 | 41% | 0 (0.00%) |

### `list`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 18,775 | 3.18 | 4.58 | 7.28 | 17.48 | 78.91 | 2.29× | 14.1 | 0 | 306.5 | 57% | 0 (0.00%) |
| `go-nethttp-pg` | 16,592 | 3.67 | 5.36 | 7.12 | 14.93 | 37.70 | 1.94× | 39.7 | 8 | 304.4 | 50% | 0 (0.00%) |

### `create`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 39,160 | 1.61 | 1.84 | 2.27 | 4.52 | 13.60 | 1.41× | 11.9 | 0 | 82.1 | 32% | 0 (0.00%) |
| `go-nethttp-pg` | 54,506 | 1.10 | 1.68 | 2.38 | 5.72 | 36.70 | 2.16× | 31.6 | 2 | 60.4 | 33% | 0 (0.00%) |

### `cpu`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 23,852 | 2.63 | 4.39 | 5.39 | 7.93 | 68.08 | 2.05× | 11.5 | 1 | 371.4 | 88% | 0 (0.00%) |
| `go-nethttp-pg` | 11,321 | 1.65 | 23.11 | 37.89 | 59.65 | 96.61 | 22.94× | 43.5 | 21 | 599.0 | 68% | 0 (0.00%) |

### `io`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 5,246 | 12.16 | 13.11 | 13.37 | 13.66 | 14.18 | 1.10× | 11.4 | 7 | 33.4 | 2% | 0 (0.00%) |
| `go-nethttp-pg` | 5,591 | 11.40 | 12.27 | 12.90 | 21.04 | 23.28 | 1.13× | 28.5 | 13 | 58.9 | 3% | 0 (0.00%) |

### `mixed`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 43,890 | 1.45 | 1.59 | 1.69 | 2.13 | 5.57 | 1.17× | 11.9 | 0 | 87.6 | 38% | 0 (0.00%) |
| `go-nethttp-pg` | 56,061 | 1.05 | 1.83 | 2.43 | 4.49 | 52.13 | 2.33× | 34.8 | 4 | 85.4 | 48% | 0 (0.00%) |

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

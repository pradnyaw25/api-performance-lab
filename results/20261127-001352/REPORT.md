# API Performance Lab — results `20261127-001352`

*2026-11-27T05:13:52+00:00* · Apple M5 (10 cores) · macOS-26.5-arm64-arm-64bit-Mach-O  
Load: oha 1.17.0, concurrency **64**, **10 s** per scenario after **3 s** warm-up, fresh process per scenario. Load generator and services share the machine; read the numbers as relative.

## Implementations and implementation complexity

LOC is non-blank, non-comment lines for the identical contract. Deps is every third-party package shipped (transitive). Cold start is process launch to first `200` from `/health`, median of 5 starts.

| Implementation | Toolchain | Contract | LOC | Deps | Build (s) | Artifact (MB) | Cold start ms (min–max) | Idle RSS (MB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | rustc 1.98.0 | pass | 256 | 207 | – | – | 40 (18–41) | 8.1 |
| `go-nethttp-pg` | go1.27.4 | pass | 283 | 15 | – | – | 22 (10–22) | 17.4 |
| `python-fastapi-pg` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | fail | 129 | 22 | – | – | 421 (364–460) | 699.2 |
| `python-fastapi-1w-pg` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | fail | 129 | 22 | – | – | 186 (159–205) | 64.7 |

- `python-fastapi-pg` produced no results: contract test failed
- `python-fastapi-1w-pg` produced no results: contract test failed

## Throughput (requests/s)

| Scenario | `rust-axum-pg` | `go-nethttp-pg` |
|---|---:|---:|
| health | 170,925 | 147,491 |
| get | 40,904 | 66,392 |
| list | 17,474 | 13,742 |
| create | 32,880 | 49,441 |
| cpu | 22,530 | 10,010 |
| io | 5,233 | 5,534 |
| mixed | 36,501 | 51,930 |

## Latency: p50 / p95 / p99 (ms)

| Scenario | `rust-axum-pg` | `go-nethttp-pg` |
|---|---:|---:|
| health | 0.36 / 0.49 / 0.62 | 0.35 / 1.04 / 2.03 |
| get | 1.56 / 1.68 / 1.75 | 0.92 / 1.36 / 1.77 |
| list | 3.56 / 4.30 / 5.69 | 4.44 / 6.57 / 8.54 |
| create | 1.91 / 2.19 / 2.90 | 1.21 / 1.85 / 2.75 |
| cpu | 2.79 / 4.53 / 5.31 | 1.90 / 25.37 / 41.86 |
| io | 12.19 / 13.15 / 13.50 | 11.54 / 12.36 / 12.89 |
| mixed | 1.74 / 1.93 / 2.09 | 1.14 / 1.98 / 2.69 |

## Peak RSS during load (MB, whole process tree)

| Scenario | `rust-axum-pg` | `go-nethttp-pg` |
|---|---:|---:|
| health | 12.4 | 30.4 |
| get | 11.7 | 30.9 |
| list | 14.3 | 38.3 |
| create | 11.8 | 31.6 |
| cpu | 11.4 | 44.1 |
| io | 11.5 | 28.6 |
| mixed | 12.0 | 34.8 |

## CPU per 1,000 requests (server CPU-ms)

Lower is better: compute each request actually consumed, independent of how saturated the machine was. Two implementations with equal req/s but 3× different CPU/1k do not have equal performance; one has 3× the headroom.

| Scenario | `rust-axum-pg` | `go-nethttp-pg` |
|---|---:|---:|
| health | 21.9 | 32.2 |
| get | 81.1 | 63.2 |
| list | 341.6 | 355.9 |
| create | 90.5 | 66.9 |
| cpu | 402.1 | 674.1 |
| io | 30.8 | 61.7 |
| mixed | 100.3 | 92.4 |

## Error rate under saturation

Concurrency far above the normal runs, with a per-request timeout; every timeout, refused or reset connection and non-2xx counts as an error. macOS `kern.ipc.somaxconn` here is 128, so connection bursts above that queue in the kernel for every implementation alike.

### `sat-get` — `/items/42` at concurrency 1000, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 37,765 | 26.58 | 44.90 | 118.31 | **0.00%** | 0 | 51.3 | – |
| `go-nethttp-pg` | 66,603 | 14.92 | 17.70 | 76.32 | **0.00%** | 0 | 74.7 | – |

### `sat-cpu` — `/compute/hash?n=20000` at concurrency 500, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 4,987 | 91.91 | 261.02 | 368.15 | **0.00%** | 0 | 28.8 | – |
| `go-nethttp-pg` | 3,655 | 18.56 | 784.04 | 999.43 | **0.40%** | 143 | 71.3 | timeout: 143 |

## Memory per open connection

1000 keep-alive connections opened, one request each, then held idle for 1 s. Per-connection cost is what bounds long-lived streaming/WebSocket/SSE fan-out.

| Implementation | Opened | Failed | Idle RSS MB | Held RSS MB | KB / connection | After close MB |
|---|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 1000 | 0 | 8.1 | 40.4 | **31.6** | 40.5 |
| `go-nethttp-pg` | 1000 | 0 | 18.6 | 38.9 | **19.9** | 39.3 |

## Recovery after a load spike

Probe: sequential keep-alive requests to `/items/42` from one client. Spike: `/items?limit=200` at concurrency 256 for 5 s. Then probe again immediately and after 10 s idle. *Retained* is how much of the spike's RSS growth was still held after settling: it shows whether the runtime gives memory back to the OS.

| Implementation | Spike req/s | Idle MB | Peak MB | +0 s MB | +10 s MB | Retained | Probe before p50/p99 | Probe +0 s | Probe +10 s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 16,756 | 8.2 | 22.5 | 22.5 | 22.5 | **100.0%** | 0.16 / 0.93 | 0.15 / 0.31 | 0.17 / 0.35 |
| `go-nethttp-pg` | 17,170 | 17.8 | 49.0 | 49.1 | 49.1 | **100.3%** | 0.13 / 0.31 | 0.14 / 0.23 | 0.12 / 0.30 |

## Per-scenario detail

### `health`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 170,925 | 0.36 | 0.49 | 0.62 | 0.89 | 2.32 | 1.70× | 12.4 | 0 | 21.9 | 37% | 0 (0.00%) |
| `go-nethttp-pg` | 147,491 | 0.35 | 1.04 | 2.03 | 4.49 | 27.29 | 5.84× | 30.4 | 1 | 32.2 | 47% | 0 (0.00%) |

### `get`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 40,904 | 1.56 | 1.68 | 1.75 | 1.86 | 5.29 | 1.12× | 11.7 | 0 | 81.1 | 33% | 0 (0.00%) |
| `go-nethttp-pg` | 66,392 | 0.92 | 1.36 | 1.77 | 2.90 | 20.32 | 1.92× | 30.9 | 1 | 63.2 | 42% | 0 (0.00%) |

### `list`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 17,474 | 3.56 | 4.30 | 5.69 | 10.29 | 21.59 | 1.60× | 14.3 | 0 | 341.6 | 60% | 0 (0.00%) |
| `go-nethttp-pg` | 13,742 | 4.44 | 6.57 | 8.54 | 14.75 | 44.41 | 1.92× | 38.3 | 15 | 355.9 | 49% | 0 (0.00%) |

### `create`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 32,880 | 1.91 | 2.19 | 2.90 | 6.01 | 23.39 | 1.52× | 11.8 | 0 | 90.5 | 30% | 0 (0.00%) |
| `go-nethttp-pg` | 49,441 | 1.21 | 1.85 | 2.75 | 6.24 | 23.11 | 2.27× | 31.6 | 3 | 66.9 | 33% | 0 (0.00%) |

### `cpu`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 22,530 | 2.79 | 4.53 | 5.31 | 6.37 | 16.30 | 1.90× | 11.4 | 0 | 402.1 | 90% | 0 (0.00%) |
| `go-nethttp-pg` | 10,010 | 1.90 | 25.37 | 41.86 | 62.95 | 117.33 | 22.01× | 44.1 | 61 | 674.1 | 67% | 0 (0.00%) |

### `io`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 5,233 | 12.19 | 13.15 | 13.50 | 14.12 | 14.81 | 1.11× | 11.5 | 8 | 30.8 | 2% | 0 (0.00%) |
| `go-nethttp-pg` | 5,534 | 11.54 | 12.36 | 12.89 | 13.96 | 14.96 | 1.12× | 28.6 | 17 | 61.7 | 3% | 0 (0.00%) |

### `mixed`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 36,501 | 1.74 | 1.93 | 2.09 | 3.66 | 20.29 | 1.20× | 12.0 | 1 | 100.3 | 36% | 0 (0.00%) |
| `go-nethttp-pg` | 51,930 | 1.14 | 1.98 | 2.69 | 4.72 | 34.56 | 2.37× | 34.8 | 3 | 92.4 | 48% | 0 (0.00%) |

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

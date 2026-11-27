# API Performance Lab — results `20261127-002012`

*2026-11-27T05:20:12+00:00* · Apple M5 (10 cores) · macOS-26.5-arm64-arm-64bit-Mach-O  
Load: oha 1.17.0, concurrency **64**, **10 s** per scenario after **3 s** warm-up, fresh process per scenario. Load generator and services share the machine; read the numbers as relative.

## Implementations and implementation complexity

LOC is non-blank, non-comment lines for the identical contract. Deps is every third-party package shipped (transitive). Cold start is process launch to first `200` from `/health`, median of 5 starts.

| Implementation | Toolchain | Contract | LOC | Deps | Build (s) | Artifact (MB) | Cold start ms (min–max) | Idle RSS (MB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | rustc 1.98.0 | pass | 256 | 207 | – | – | 21 (20–24) | 8.1 |
| `go-nethttp-pg` | go1.27.4 | pass | 283 | 15 | – | – | 12 (10–29) | 17.4 |
| `python-fastapi-pg` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | pass | 129 | 22 | – | – | 324 (304–402) | 699.4 |
| `python-fastapi-1w-pg` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | pass | 129 | 22 | – | – | 158 (154–159) | 64.8 |

## Throughput (requests/s)

| Scenario | `rust-axum-pg` | `go-nethttp-pg` | `python-fastapi-pg` | `python-fastapi-1w-pg` |
|---|---:|---:|---:|---:|
| health | 178,758 | 144,253 | 79,314 | 33,947 |
| get | 43,310 | 66,167 | 25,725 | 14,468 |
| list | 18,371 | 14,961 | 5,820 | 2,185 |
| create | 37,416 | 47,235 | 19,227 | 11,435 |
| cpu | 23,267 | 10,147 | 3,262 | 979 |
| io | 5,182 | 5,572 | 5,660 | 5,461 |
| mixed | 37,066 | 53,887 | 18,392 | 7,853 |

## Latency: p50 / p95 / p99 (ms)

| Scenario | `rust-axum-pg` | `go-nethttp-pg` | `python-fastapi-pg` | `python-fastapi-1w-pg` |
|---|---:|---:|---:|---:|
| health | 0.31 / 0.65 / 1.25 | 0.38 / 0.96 / 1.74 | 0.54 / 2.41 / 6.25 | 1.86 / 1.96 / 3.66 |
| get | 1.46 / 1.61 / 1.80 | 0.93 / 1.32 / 1.65 | 1.66 / 6.08 / 10.09 | 4.43 / 6.85 / 7.46 |
| list | 3.29 / 4.44 / 6.53 | 4.17 / 5.70 / 6.77 | 11.79 / 23.03 / 33.92 | 29.09 / 36.65 / 78.94 |
| create | 1.68 / 1.94 / 2.39 | 1.29 / 1.89 / 2.50 | 2.43 / 8.45 / 14.06 | 5.62 / 6.04 / 6.33 |
| cpu | 2.64 / 4.66 / 5.79 | 1.85 / 25.46 / 41.64 | 16.60 / 43.79 / 102.07 | 65.13 / 67.23 / 71.25 |
| io | 12.39 / 13.26 / 13.56 | 11.47 / 12.25 / 12.75 | 11.26 / 12.28 / 12.70 | 11.75 / 12.80 / 13.58 |
| mixed | 1.71 / 1.92 / 2.08 | 1.10 / 1.88 / 2.48 | 3.25 / 6.87 / 10.04 | 7.69 / 12.64 / 18.93 |

## Peak RSS during load (MB, whole process tree)

| Scenario | `rust-axum-pg` | `go-nethttp-pg` | `python-fastapi-pg` | `python-fastapi-1w-pg` |
|---|---:|---:|---:|---:|
| health | 12.4 | 29.9 | 712.9 | 68.3 |
| get | 11.7 | 31.2 | 711.1 | 67.4 |
| list | 14.4 | 38.1 | 713.5 | 69.8 |
| create | 11.9 | 30.9 | 711.8 | 67.7 |
| cpu | 11.4 | 41.6 | 719.4 | 70.2 |
| io | 11.3 | 28.5 | 708.1 | 67.6 |
| mixed | 11.9 | 34.8 | 711.1 | 67.4 |

## CPU per 1,000 requests (server CPU-ms)

Lower is better: compute each request actually consumed, independent of how saturated the machine was. Two implementations with equal req/s but 3× different CPU/1k do not have equal performance; one has 3× the headroom.

| Scenario | `rust-axum-pg` | `go-nethttp-pg` | `python-fastapi-pg` | `python-fastapi-1w-pg` |
|---|---:|---:|---:|---:|
| health | 19.2 | 33.5 | 85.6 | 29.4 |
| get | 76.1 | 66.2 | 262.7 | 69.1 |
| list | 315.9 | 355.2 | 1,364.1 | 459.3 |
| create | 83.8 | 70.2 | 328.7 | 86.9 |
| cpu | 374.3 | 680.1 | 2,946.2 | 1,040.0 |
| io | 30.5 | 58.9 | 136.5 | 64.0 |
| mixed | 98.5 | 91.0 | 390.8 | 125.7 |

## Error rate under saturation

Concurrency far above the normal runs, with a per-request timeout; every timeout, refused or reset connection and non-2xx counts as an error. macOS `kern.ipc.somaxconn` here is 128, so connection bursts above that queue in the kernel for every implementation alike.

### `sat-get` — `/items/42` at concurrency 1000, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 38,298 | 26.01 | 37.74 | 84.59 | **0.00%** | 0 | 51.4 | – |
| `go-nethttp-pg` | 68,507 | 14.66 | 16.93 | 189.20 | **0.00%** | 0 | 74.5 | – |
| `python-fastapi-pg` | 24,486 | 35.40 | 146.91 | 392.91 | **0.00%** | 0 | 737.6 | – |
| `python-fastapi-1w-pg` | 12,818 | 77.09 | 179.11 | 518.87 | **0.00%** | 0 | 93.3 | – |

### `sat-cpu` — `/compute/hash?n=20000` at concurrency 500, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 4,734 | 97.78 | 275.88 | 408.30 | **0.00%** | 0 | 28.8 | – |
| `go-nethttp-pg` | 3,730 | 10.61 | 779.37 | 999.07 | **0.45%** | 165 | 74.9 | timeout: 165 |
| `python-fastapi-pg` | 1,006 | 485.49 | 944.88 | 1,000.14 | **1.75%** | 167 | 748.1 | timeout: 167 |
| `python-fastapi-1w-pg` | 643 | 438.89 | 507.47 | 972.94 | **60.49%** | 3591 | 71.8 | timeout: 3591 |

## Memory per open connection

1000 keep-alive connections opened, one request each, then held idle for 1 s. Per-connection cost is what bounds long-lived streaming/WebSocket/SSE fan-out.

| Implementation | Opened | Failed | Idle RSS MB | Held RSS MB | KB / connection | After close MB |
|---|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 1000 | 0 | 8.0 | 40.4 | **31.6** | 40.4 |
| `go-nethttp-pg` | 1000 | 0 | 17.3 | 38.7 | **20.9** | 39.0 |
| `python-fastapi-pg` | 1000 | 0 | 698.7 | 717.5 | **18.3** | 717.5 |
| `python-fastapi-1w-pg` | 1000 | 0 | 65.2 | 77.3 | **11.8** | 76.3 |

## Recovery after a load spike

Probe: sequential keep-alive requests to `/items/42` from one client. Spike: `/items?limit=200` at concurrency 256 for 5 s. Then probe again immediately and after 10 s idle. *Retained* is how much of the spike's RSS growth was still held after settling: it shows whether the runtime gives memory back to the OS.

| Implementation | Spike req/s | Idle MB | Peak MB | +0 s MB | +10 s MB | Retained | Probe before p50/p99 | Probe +0 s | Probe +10 s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 17,949 | 8.1 | 22.3 | 22.3 | 22.3 | **100.0%** | 0.18 / 0.96 | 0.15 / 0.24 | 0.10 / 0.41 |
| `go-nethttp-pg` | 18,998 | 17.2 | 48.8 | 48.8 | 48.8 | **100.2%** | 0.12 / 0.33 | 0.14 / 0.24 | 0.13 / 0.35 |
| `python-fastapi-pg` | 6,803 | 699.7 | 721.1 | 721.1 | 721.1 | **100.0%** | 0.21 / 0.66 | 0.36 / 0.89 | 0.21 / 0.58 |
| `python-fastapi-1w-pg` | 2,154 | 65.1 | 75.2 | 75.2 | 75.2 | **100.0%** | 0.22 / 0.61 | 0.23 / 0.39 | 0.23 / 0.63 |

## Per-scenario detail

### `health`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 178,758 | 0.31 | 0.65 | 1.25 | 3.93 | 38.24 | 4.01× | 12.4 | 0 | 19.2 | 34% | 0 (0.00%) |
| `go-nethttp-pg` | 144,253 | 0.38 | 0.96 | 1.74 | 3.54 | 10.70 | 4.60× | 29.9 | 0 | 33.5 | 47% | 0 (0.00%) |
| `python-fastapi-pg` | 79,314 | 0.54 | 2.41 | 6.25 | 13.01 | 32.55 | 11.57× | 712.9 | 1 | 85.6 | 67% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 33,947 | 1.86 | 1.96 | 3.66 | 3.85 | 61.53 | 1.97× | 68.3 | 2 | 29.4 | 10% | 0 (0.00%) |

### `get`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 43,310 | 1.46 | 1.61 | 1.80 | 3.72 | 9.35 | 1.23× | 11.7 | 0 | 76.1 | 33% | 0 (0.00%) |
| `go-nethttp-pg` | 66,167 | 0.93 | 1.32 | 1.65 | 2.22 | 6.92 | 1.78× | 31.2 | 1 | 66.2 | 43% | 0 (0.00%) |
| `python-fastapi-pg` | 25,725 | 1.66 | 6.08 | 10.09 | 17.06 | 121.77 | 6.07× | 711.1 | 6 | 262.7 | 67% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 14,468 | 4.43 | 6.85 | 7.46 | 11.72 | 28.72 | 1.68× | 67.4 | 1 | 69.1 | 10% | 0 (0.00%) |

### `list`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 18,371 | 3.29 | 4.44 | 6.53 | 14.97 | 51.76 | 1.98× | 14.4 | 0 | 315.9 | 58% | 0 (0.00%) |
| `go-nethttp-pg` | 14,961 | 4.17 | 5.70 | 6.77 | 8.67 | 23.02 | 1.63× | 38.1 | 7 | 355.2 | 53% | 0 (0.00%) |
| `python-fastapi-pg` | 5,820 | 11.79 | 23.03 | 33.92 | 51.56 | 88.75 | 2.88× | 713.5 | 82 | 1,364.1 | 79% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 2,185 | 29.09 | 36.65 | 78.94 | 256.13 | 621.01 | 2.71× | 69.8 | 5 | 459.3 | 10% | 0 (0.00%) |

### `create`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 37,416 | 1.68 | 1.94 | 2.39 | 4.36 | 26.63 | 1.42× | 11.9 | 0 | 83.8 | 31% | 0 (0.00%) |
| `go-nethttp-pg` | 47,235 | 1.29 | 1.89 | 2.50 | 4.42 | 17.65 | 1.93× | 30.9 | 1 | 70.2 | 33% | 0 (0.00%) |
| `python-fastapi-pg` | 19,227 | 2.43 | 8.45 | 14.06 | 23.60 | 75.78 | 5.79× | 711.8 | 5 | 328.7 | 63% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 11,435 | 5.62 | 6.04 | 6.33 | 10.94 | 24.46 | 1.13× | 67.7 | 2 | 86.9 | 10% | 0 (0.00%) |

### `cpu`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 23,267 | 2.64 | 4.66 | 5.79 | 8.19 | 33.88 | 2.20× | 11.4 | 1 | 374.3 | 87% | 0 (0.00%) |
| `go-nethttp-pg` | 10,147 | 1.85 | 25.46 | 41.64 | 65.19 | 112.40 | 22.46× | 41.6 | 48 | 680.1 | 69% | 0 (0.00%) |
| `python-fastapi-pg` | 3,262 | 16.60 | 43.79 | 102.07 | 140.66 | 158.19 | 6.15× | 719.4 | 42 | 2,946.2 | 96% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 979 | 65.13 | 67.23 | 71.25 | 370.82 | 485.46 | 1.09× | 70.2 | 5 | 1,040.0 | 10% | 0 (0.00%) |

### `io`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 5,182 | 12.39 | 13.26 | 13.56 | 14.38 | 14.63 | 1.09× | 11.3 | 2 | 30.5 | 2% | 0 (0.00%) |
| `go-nethttp-pg` | 5,572 | 11.47 | 12.25 | 12.75 | 20.42 | 22.08 | 1.11× | 28.5 | 16 | 58.9 | 3% | 0 (0.00%) |
| `python-fastapi-pg` | 5,660 | 11.26 | 12.28 | 12.70 | 21.85 | 28.00 | 1.13× | 708.1 | 59 | 136.5 | 8% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 5,461 | 11.75 | 12.80 | 13.58 | 20.93 | 22.82 | 1.16× | 67.6 | 8 | 64.0 | 4% | 0 (0.00%) |

### `mixed`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 37,066 | 1.71 | 1.92 | 2.08 | 2.68 | 8.47 | 1.22× | 11.9 | 0 | 98.5 | 36% | 0 (0.00%) |
| `go-nethttp-pg` | 53,887 | 1.10 | 1.88 | 2.48 | 4.45 | 20.98 | 2.26× | 34.8 | 4 | 91.0 | 49% | 0 (0.00%) |
| `python-fastapi-pg` | 18,392 | 3.25 | 6.87 | 10.04 | 17.11 | 59.08 | 3.09× | 711.1 | 9 | 390.8 | 72% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 7,853 | 7.69 | 12.64 | 18.93 | 35.27 | 51.57 | 2.46× | 67.4 | 3 | 125.7 | 10% | 0 (0.00%) |

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

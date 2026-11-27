# API Performance Lab — results `20261127-002947`

*2026-11-27T05:29:47+00:00* · Apple M5 (10 cores) · macOS-26.5-arm64-arm-64bit-Mach-O  
Load: oha 1.17.0, concurrency **64**, **10 s** per scenario after **3 s** warm-up, fresh process per scenario. Load generator and services share the machine; read the numbers as relative.

## Implementations and implementation complexity

LOC is non-blank, non-comment lines for the identical contract. Deps is every third-party package shipped (transitive). Cold start is process launch to first `200` from `/health`, median of 5 starts.

| Implementation | Toolchain | Contract | LOC | Deps | Build (s) | Artifact (MB) | Cold start ms (min–max) | Idle RSS (MB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | rustc 1.98.0 | pass | 256 | 207 | – | – | 24 (21–33) | 8.1 |
| `go-nethttp-pg` | go1.27.4 | pass | 283 | 15 | – | – | 10 (10–28) | 17.1 |
| `python-fastapi-pg` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | pass | 129 | 22 | – | – | 333 (293–398) | 699.6 |
| `python-fastapi-1w-pg` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | pass | 129 | 22 | – | – | 156 (156–161) | 65.2 |

## Throughput (requests/s)

| Scenario | `rust-axum-pg` | `go-nethttp-pg` | `python-fastapi-pg` | `python-fastapi-1w-pg` |
|---|---:|---:|---:|---:|
| health | 173,523 | 143,143 | 77,310 | 32,680 |
| get | 40,456 | 66,303 | 22,553 | 13,746 |
| list | 17,088 | 15,008 | 4,654 | 2,177 |
| create | 33,814 | 48,564 | 17,790 | 10,720 |
| cpu | 20,525 | 10,669 | 3,006 | 979 |
| io | 5,227 | 5,637 | 5,630 | 5,468 |
| mixed | 35,892 | 54,990 | 16,830 | 8,550 |

## Latency: p50 / p95 / p99 (ms)

| Scenario | `rust-axum-pg` | `go-nethttp-pg` | `python-fastapi-pg` | `python-fastapi-1w-pg` |
|---|---:|---:|---:|---:|
| health | 0.35 / 0.53 / 0.79 | 0.37 / 1.01 / 1.87 | 0.62 / 2.21 / 4.45 | 1.90 / 2.06 / 3.80 |
| get | 1.56 / 1.75 / 2.11 | 0.92 / 1.34 / 1.76 | 2.22 / 6.74 / 11.48 | 4.64 / 7.18 / 8.02 |
| list | 3.62 / 4.45 / 6.17 | 4.15 / 5.70 / 6.88 | 12.56 / 29.64 / 51.17 | 29.09 / 38.33 / 77.15 |
| create | 1.88 / 2.11 / 2.23 | 1.26 / 1.84 / 2.40 | 3.18 / 8.37 / 13.23 | 5.74 / 6.93 / 10.57 |
| cpu | 3.04 / 5.09 / 6.20 | 1.77 / 23.92 / 39.56 | 18.98 / 42.46 / 59.22 | 65.27 / 67.03 / 80.04 |
| io | 12.21 / 13.14 / 13.42 | 11.34 / 12.12 / 12.60 | 11.33 / 12.44 / 12.86 | 11.72 / 12.81 / 13.44 |
| mixed | 1.78 / 2.08 / 2.20 | 1.08 / 1.84 / 2.39 | 2.52 / 10.21 / 16.46 | 7.51 / 11.80 / 12.42 |

## Peak RSS during load (MB, whole process tree)

| Scenario | `rust-axum-pg` | `go-nethttp-pg` | `python-fastapi-pg` | `python-fastapi-1w-pg` |
|---|---:|---:|---:|---:|
| health | 12.4 | 29.7 | 711.8 | 68.7 |
| get | 11.8 | 31.5 | 712.2 | 67.4 |
| list | 14.5 | 38.3 | 716.8 | 69.7 |
| create | 11.9 | 31.2 | 711.5 | 67.5 |
| cpu | 11.3 | 40.9 | 719.8 | 70.0 |
| io | 11.4 | 28.5 | 707.7 | 67.4 |
| mixed | 11.8 | 33.5 | 710.5 | 67.6 |

## CPU per 1,000 requests (server CPU-ms)

Lower is better: compute each request actually consumed, independent of how saturated the machine was. Two implementations with equal req/s but 3× different CPU/1k do not have equal performance; one has 3× the headroom.

| Scenario | `rust-axum-pg` | `go-nethttp-pg` | `python-fastapi-pg` | `python-fastapi-1w-pg` |
|---|---:|---:|---:|---:|
| health | 21.4 | 33.2 | 86.3 | 30.5 |
| get | 79.7 | 65.0 | 275.0 | 72.7 |
| list | 341.2 | 350.7 | 1,466.6 | 461.4 |
| create | 91.7 | 68.3 | 345.9 | 92.0 |
| cpu | 433.4 | 654.9 | 3,085.6 | 1,040.5 |
| io | 32.0 | 66.2 | 128.7 | 64.4 |
| mixed | 103.0 | 90.2 | 415.8 | 117.0 |

## Error rate under saturation

Concurrency far above the normal runs, with a per-request timeout; every timeout, refused or reset connection and non-2xx counts as an error. macOS `kern.ipc.somaxconn` here is 128, so connection bursts above that queue in the kernel for every implementation alike.

### `sat-get` — `/items/42` at concurrency 1000, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 36,838 | 27.66 | 29.91 | 183.35 | **0.00%** | 0 | 51.2 | – |
| `go-nethttp-pg` | 61,628 | 15.35 | 28.68 | 236.41 | **0.00%** | 0 | 73.6 | – |
| `python-fastapi-pg` | 23,036 | 37.27 | 153.44 | 440.28 | **0.00%** | 0 | 736.1 | – |
| `python-fastapi-1w-pg` | 12,952 | 76.64 | 202.79 | 574.71 | **0.00%** | 0 | 93.3 | – |

### `sat-cpu` — `/compute/hash?n=20000` at concurrency 500, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 4,037 | 113.25 | 345.37 | 511.68 | **0.00%** | 0 | 28.7 | – |
| `go-nethttp-pg` | 3,589 | 29.30 | 786.38 | 1,000.03 | **0.51%** | 181 | 78.0 | timeout: 181 |
| `python-fastapi-pg` | 973 | 490.79 | 949.76 | 999.99 | **3.37%** | 311 | 751.2 | timeout: 311 |
| `python-fastapi-1w-pg` | 619 | 145.65 | 948.56 | 993.93 | **75.68%** | 4310 | 85.2 | timeout: 4310 |

## Memory per open connection

1000 keep-alive connections opened, one request each, then held idle for 1 s. Per-connection cost is what bounds long-lived streaming/WebSocket/SSE fan-out.

| Implementation | Opened | Failed | Idle RSS MB | Held RSS MB | KB / connection | After close MB |
|---|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 1000 | 0 | 8.0 | 40.4 | **31.6** | 40.4 |
| `go-nethttp-pg` | 1000 | 0 | 17.2 | 39.1 | **21.4** | 39.3 |
| `python-fastapi-pg` | 1000 | 0 | 700.0 | 718.9 | **18.4** | 718.9 |
| `python-fastapi-1w-pg` | 1000 | 0 | 65.1 | 77.3 | **11.9** | 76.2 |

## Recovery after a load spike

Probe: sequential keep-alive requests to `/items/42` from one client. Spike: `/items?limit=200` at concurrency 256 for 5 s. Then probe again immediately and after 10 s idle. *Retained* is how much of the spike's RSS growth was still held after settling: it shows whether the runtime gives memory back to the OS.

| Implementation | Spike req/s | Idle MB | Peak MB | +0 s MB | +10 s MB | Retained | Probe before p50/p99 | Probe +0 s | Probe +10 s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 17,775 | 8.1 | 22.5 | 22.5 | 22.5 | **100.0%** | 0.18 / 0.98 | 0.15 / 0.30 | 0.15 / 0.35 |
| `go-nethttp-pg` | 17,993 | 17.2 | 51.7 | 51.7 | 51.9 | **100.4%** | 0.12 / 0.35 | 0.14 / 0.25 | 0.12 / 0.27 |
| `python-fastapi-pg` | 6,437 | 698.9 | 720.3 | 720.3 | 720.3 | **100.0%** | 0.22 / 0.82 | 0.39 / 1.53 | 0.22 / 0.68 |
| `python-fastapi-1w-pg` | 2,123 | 65.1 | 75.3 | 75.3 | 75.3 | **100.0%** | 0.22 / 0.58 | 0.21 / 11.97 | 0.21 / 0.43 |

## Per-scenario detail

### `health`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 173,523 | 0.35 | 0.53 | 0.79 | 1.91 | 13.45 | 2.22× | 12.4 | 0 | 21.4 | 37% | 0 (0.00%) |
| `go-nethttp-pg` | 143,143 | 0.37 | 1.01 | 1.87 | 4.13 | 26.85 | 5.02× | 29.7 | 1 | 33.2 | 47% | 0 (0.00%) |
| `python-fastapi-pg` | 77,310 | 0.62 | 2.21 | 4.45 | 8.21 | 126.27 | 7.22× | 711.8 | 1 | 86.3 | 66% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 32,680 | 1.90 | 2.06 | 3.80 | 4.39 | 63.12 | 2.00× | 68.7 | 2 | 30.5 | 10% | 0 (0.00%) |

### `get`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 40,456 | 1.56 | 1.75 | 2.11 | 3.88 | 20.16 | 1.36× | 11.8 | 0 | 79.7 | 32% | 0 (0.00%) |
| `go-nethttp-pg` | 66,303 | 0.92 | 1.34 | 1.76 | 3.27 | 15.33 | 1.91× | 31.5 | 1 | 65.0 | 43% | 0 (0.00%) |
| `python-fastapi-pg` | 22,553 | 2.22 | 6.74 | 11.48 | 38.27 | 137.28 | 5.17× | 712.2 | 14 | 275.0 | 62% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 13,746 | 4.64 | 7.18 | 8.02 | 12.95 | 21.00 | 1.73× | 67.4 | 1 | 72.7 | 10% | 0 (0.00%) |

### `list`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 17,088 | 3.62 | 4.45 | 6.17 | 11.96 | 32.15 | 1.71× | 14.5 | 1 | 341.2 | 58% | 0 (0.00%) |
| `go-nethttp-pg` | 15,008 | 4.15 | 5.70 | 6.88 | 9.40 | 20.38 | 1.66× | 38.3 | 7 | 350.7 | 52% | 0 (0.00%) |
| `python-fastapi-pg` | 4,654 | 12.56 | 29.64 | 51.17 | 118.93 | 264.28 | 4.07× | 716.8 | 90 | 1,466.6 | 68% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 2,177 | 29.09 | 38.33 | 77.15 | 193.77 | 501.89 | 2.65× | 69.7 | 5 | 461.4 | 10% | 0 (0.00%) |

### `create`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 33,814 | 1.88 | 2.11 | 2.23 | 2.58 | 6.28 | 1.18× | 11.9 | 1 | 91.7 | 31% | 0 (0.00%) |
| `go-nethttp-pg` | 48,564 | 1.26 | 1.84 | 2.40 | 4.42 | 9.85 | 1.91× | 31.2 | 2 | 68.3 | 33% | 0 (0.00%) |
| `python-fastapi-pg` | 17,790 | 3.18 | 8.37 | 13.23 | 24.48 | 88.92 | 4.16× | 711.5 | 21 | 345.9 | 61% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 10,720 | 5.74 | 6.93 | 10.57 | 19.62 | 41.54 | 1.84× | 67.5 | 0 | 92.0 | 10% | 0 (0.00%) |

### `cpu`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 20,525 | 3.04 | 5.09 | 6.20 | 8.83 | 32.93 | 2.04× | 11.3 | 0 | 433.4 | 89% | 0 (0.00%) |
| `go-nethttp-pg` | 10,669 | 1.77 | 23.92 | 39.56 | 61.85 | 91.02 | 22.40× | 40.9 | 35 | 654.9 | 70% | 0 (0.00%) |
| `python-fastapi-pg` | 3,006 | 18.98 | 42.46 | 59.22 | 90.81 | 151.66 | 3.12× | 719.8 | 22 | 3,085.6 | 92% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 979 | 65.27 | 67.03 | 80.04 | 360.32 | 474.48 | 1.23× | 70.0 | 34 | 1,040.5 | 10% | 0 (0.00%) |

### `io`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 5,227 | 12.21 | 13.14 | 13.42 | 23.68 | 24.07 | 1.10× | 11.4 | 5 | 32.0 | 2% | 0 (0.00%) |
| `go-nethttp-pg` | 5,637 | 11.34 | 12.12 | 12.60 | 14.44 | 19.55 | 1.11× | 28.5 | 14 | 66.2 | 4% | 0 (0.00%) |
| `python-fastapi-pg` | 5,630 | 11.33 | 12.44 | 12.86 | 20.90 | 26.95 | 1.14× | 707.7 | 38 | 128.7 | 7% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 5,468 | 11.72 | 12.81 | 13.44 | 20.77 | 23.92 | 1.15× | 67.4 | 7 | 64.4 | 4% | 0 (0.00%) |

### `mixed`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum-pg` | 35,892 | 1.78 | 2.08 | 2.20 | 2.43 | 5.28 | 1.24× | 11.8 | 0 | 103.0 | 37% | 0 (0.00%) |
| `go-nethttp-pg` | 54,990 | 1.08 | 1.84 | 2.39 | 3.67 | 17.61 | 2.22× | 33.5 | 1 | 90.2 | 49% | 0 (0.00%) |
| `python-fastapi-pg` | 16,830 | 2.52 | 10.21 | 16.46 | 25.97 | 58.62 | 6.53× | 710.5 | 28 | 415.8 | 70% | 0 (0.00%) |
| `python-fastapi-1w-pg` | 8,550 | 7.51 | 11.80 | 12.42 | 20.04 | 50.99 | 1.65× | 67.6 | 2 | 117.0 | 10% | 0 (0.00%) |

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

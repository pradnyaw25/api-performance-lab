# API Performance Lab — results `20261126-223757`

*2026-11-27T03:37:57+00:00* · Apple M5 (10 cores) · macOS-26.5-arm64-arm-64bit-Mach-O  
Load: oha 1.17.0, concurrency **64**, **10 s** per scenario after **3 s** warm-up, fresh process per scenario. Load generator and services share the machine; read the numbers as relative.

## Implementations and implementation complexity

LOC is non-blank, non-comment lines for the identical contract. Deps is every third-party package shipped (transitive). Cold start is process launch to first `200` from `/health`, median of 5 starts.

| Implementation | Toolchain | Contract | LOC | Deps | Build (s) | Artifact (MB) | Cold start ms (min–max) | Idle RSS (MB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | rustc 1.98.0 | pass | 177 | 93 | – | – | 9 (9–12) | 9.9 |
| `go-nethttp` | go1.27.4 | pass | 182 | 0 | – | – | 14 (11–17) | 13.4 |
| `python-fastapi` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | pass | 93 | 32 | – | – | 416 (392–418) | 711.0 |
| `python-fastapi-1w` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | pass | 93 | 32 | – | – | 175 (157–175) | 66.1 |

## Throughput (requests/s)

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 142,018 | 146,876 | 67,349 | 29,944 |
| get | 143,023 | 142,837 | 62,437 | 27,152 |
| list | 52,864 | 48,906 | 34,371 | 14,543 |
| create | 140,689 | 124,894 | 35,244 | 19,388 |
| cpu | 19,246 | 10,012 | 2,220 | 875 |
| io | 5,226 | 5,553 | 5,757 | 5,455 |
| mixed | 8,609 | 10,857 | 10,119 | 9,942 |

## Latency: p50 / p95 / p99 (ms)

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 0.43 / 0.64 / 1.12 | 0.35 / 0.95 / 2.00 | 0.59 / 2.79 / 6.74 | 2.09 / 2.37 / 4.10 |
| get | 0.43 / 0.63 / 0.99 | 0.36 / 1.02 / 2.23 | 0.70 / 2.94 / 6.10 | 2.29 / 2.57 / 4.55 |
| list | 1.16 / 2.00 / 2.82 | 0.93 / 3.92 / 6.67 | 1.32 / 5.04 / 9.24 | 4.30 / 4.68 / 8.58 |
| create | 0.44 / 0.62 / 0.85 | 0.40 / 1.09 / 2.77 | 1.46 / 4.44 / 8.20 | 3.21 / 3.58 / 6.38 |
| cpu | 3.25 / 5.38 / 6.48 | 1.81 / 24.95 / 39.70 | 26.27 / 62.95 / 79.74 | 73.23 / 78.64 / 81.85 |
| io | 12.23 / 13.14 / 13.43 | 11.50 / 12.41 / 12.93 | 11.10 / 11.92 / 12.01 | 11.75 / 12.89 / 14.23 |
| mixed | 7.47 / 8.70 / 9.18 | 5.76 / 7.13 / 8.07 | 6.32 / 7.55 / 8.20 | 6.37 / 7.18 / 8.06 |

## Peak RSS during load (MB, whole process tree)

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 12.7 | 30.6 | 722.3 | 69.3 |
| get | 13.4 | 30.0 | 720.4 | 67.6 |
| list | 15.1 | 30.3 | 720.2 | 67.6 |
| create | 840.2 | 692.1 | 686.0 | 204.3 |
| cpu | 13.3 | 39.3 | 731.4 | 71.7 |
| io | 13.2 | 26.6 | 718.6 | 67.9 |
| mixed | 13.4 | 27.2 | 720.1 | 67.8 |

## CPU per 1,000 requests (server CPU-ms)

Lower is better: compute each request actually consumed, independent of how saturated the machine was. Two implementations with equal req/s but 3× different CPU/1k do not have equal performance; one has 3× the headroom.

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 23.5 | 31.7 | 90.5 | 33.3 |
| get | 24.2 | 31.5 | 104.8 | 36.8 |
| list | 134.6 | 134.6 | 207.3 | 68.7 |
| create | 28.3 | 38.0 | 169.5 | 51.5 |
| cpu | 456.6 | 713.8 | 3,428.5 | 1,173.0 |
| io | 32.6 | 63.4 | 69.5 | 63.1 |
| mixed | 74.9 | 96.3 | 168.6 | 83.1 |

## Error rate under saturation

Concurrency far above the normal runs, with a per-request timeout; every timeout, refused or reset connection and non-2xx counts as an error. macOS `kern.ipc.somaxconn` here is 128, so connection bursts above that queue in the kernel for every implementation alike.

### `sat-get` — `/items/42` at concurrency 1000, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 169,244 | 5.84 | 14.70 | 206.98 | **0.00%** | 0 | 63.0 | – |
| `go-nethttp` | 155,255 | 4.62 | 28.82 | 134.54 | **0.00%** | 0 | 61.8 | – |
| `python-fastapi` | 38,623 | 20.78 | 115.60 | 909.22 | **0.00%** | 0 | 731.1 | – |
| `python-fastapi-1w` | 26,057 | 11.30 | 18.45 | 998.17 | **2.48%** | 6427 | 75.1 | timeout: 6427 |

### `sat-cpu` — `/compute/hash?n=20000` at concurrency 500, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 6,160 | 73.83 | 209.91 | 336.72 | **0.00%** | 0 | 30.6 | – |
| `go-nethttp` | 3,698 | 74.81 | 715.64 | 994.77 | **0.26%** | 94 | 67.3 | timeout: 94 |
| `python-fastapi` | 734 | 626.81 | 986.83 | 1,000.53 | **21.47%** | 1469 | 765.9 | timeout: 1469 |
| `python-fastapi-1w` | 606 | 165.72 | 951.98 | 998.94 | **77.35%** | 4306 | 88.5 | timeout: 4306 |

## Memory per open connection

1000 keep-alive connections opened, one request each, then held idle for 1 s. Per-connection cost is what bounds long-lived streaming/WebSocket/SSE fan-out.

| Implementation | Opened | Failed | Idle RSS MB | Held RSS MB | KB / connection | After close MB |
|---|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 1000 | 0 | 10.0 | 42.4 | **31.6** | 42.4 |
| `go-nethttp` | 1000 | 0 | 13.5 | 36.7 | **22.7** | 37.3 |
| `python-fastapi` | 1000 | 0 | 710.8 | 729.5 | **18.3** | 729.5 |
| `python-fastapi-1w` | 1000 | 0 | 66.0 | 78.1 | **11.8** | 78.1 |

## Recovery after a load spike

Probe: sequential keep-alive requests to `/items/42` from one client. Spike: `/items?limit=200` at concurrency 256 for 5 s. Then probe again immediately and after 10 s idle. *Retained* is how much of the spike's RSS growth was still held after settling: it shows whether the runtime gives memory back to the OS.

| Implementation | Spike req/s | Idle MB | Peak MB | +0 s MB | +10 s MB | Retained | Probe before p50/p99 | Probe +0 s | Probe +10 s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 68,463 | 9.9 | 22.8 | 22.8 | 22.8 | **100.0%** | 0.09 / 0.15 | 0.05 / 0.11 | 0.09 / 0.15 |
| `go-nethttp` | 60,895 | 13.5 | 35.9 | 35.9 | 35.9 | **100.0%** | 0.09 / 0.21 | 0.08 / 0.17 | 0.09 / 0.18 |
| `python-fastapi` | 30,868 | 711.0 | 722.4 | 722.4 | 427.1 | **-2489.9%** | 0.14 / 0.33 | 0.18 / 0.29 | 0.13 / 0.32 |
| `python-fastapi-1w` | 14,227 | 65.8 | 69.6 | 69.6 | 64.8 | **-25.4%** | 0.13 / 0.33 | 0.09 / 0.15 | 0.12 / 0.28 |

## Where Rust's advantage is, relative to each alternative

Every ratio is *alternative ÷ Rust* for cost metrics (latency, CPU, RSS) and *Rust ÷ alternative* for throughput, so **> 1 means Rust is better**, ≈ 1 means the language did not matter for that workload, and < 1 means the alternative won.

| Scenario | Metric | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---|---:|---:|---:|
| **health** | throughput | 0.97× | 2.11× | 4.74× |
|  | p99 latency | 1.78× | 6.01× | 3.66× |
|  | CPU / 1k req | 1.35× | 3.86× | 1.42× |
|  | peak RSS | 2.42× | 57.03× | 5.47× |
| **get** | throughput | 1.00× | 2.29× | 5.27× |
|  | p99 latency | 2.26× | 6.16× | 4.60× |
|  | CPU / 1k req | 1.30× | 4.32× | 1.52× |
|  | peak RSS | 2.24× | 53.75× | 5.04× |
| **list** | throughput | 1.08× | 1.54× | 3.64× |
|  | p99 latency | 2.36× | 3.27× | 3.04× |
|  | CPU / 1k req | 1.00× | 1.54× | 0.51× |
|  | peak RSS | 2.00× | 47.63× | 4.47× |
| **create** | throughput | 1.13× | 3.99× | 7.26× |
|  | p99 latency | 3.27× | 9.67× | 7.52× |
|  | CPU / 1k req | 1.34× | 6.00× | 1.82× |
|  | peak RSS | 0.82× | 0.82× | 0.24× |
| **cpu** | throughput | 1.92× | 8.67× | 22.00× |
|  | p99 latency | 6.13× | 12.31× | 12.64× |
|  | CPU / 1k req | 1.56× | 7.51× | 2.57× |
|  | peak RSS | 2.95× | 54.91× | 5.38× |
| **io** | throughput | 0.94× | 0.91× | 0.96× |
|  | p99 latency | 0.96× | 0.89× | 1.06× |
|  | CPU / 1k req | 1.95× | 2.14× | 1.94× |
|  | peak RSS | 2.02× | 54.55× | 5.15× |
| **mixed** | throughput | 0.79× | 0.85× | 0.87× |
|  | p99 latency | 0.88× | 0.89× | 0.88× |
|  | CPU / 1k req | 1.28× | 2.25× | 1.11× |
|  | peak RSS | 2.03× | 53.79× | 5.06× |

## Per-scenario detail

### `health`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 142,018 | 0.43 | 0.64 | 1.12 | 3.34 | 23.56 | 2.62× | 12.7 | 0 | 23.5 | 33% | 0 (0.00%) |
| `go-nethttp` | 146,876 | 0.35 | 0.95 | 2.00 | 5.41 | 102.61 | 5.66× | 30.6 | 1 | 31.7 | 46% | 0 (0.00%) |
| `python-fastapi` | 67,349 | 0.59 | 2.79 | 6.74 | 15.69 | 129.41 | 11.32× | 722.3 | 1 | 90.5 | 60% | 0 (0.00%) |
| `python-fastapi-1w` | 29,944 | 2.09 | 2.37 | 4.10 | 4.63 | 68.94 | 1.96× | 69.3 | 2 | 33.3 | 10% | 0 (0.00%) |

### `get`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 143,023 | 0.43 | 0.63 | 0.99 | 3.09 | 50.18 | 2.32× | 13.4 | 0 | 24.2 | 34% | 0 (0.00%) |
| `go-nethttp` | 142,837 | 0.36 | 1.02 | 2.23 | 6.13 | 23.04 | 6.23× | 30.0 | 2 | 31.5 | 44% | 0 (0.00%) |
| `python-fastapi` | 62,437 | 0.70 | 2.94 | 6.10 | 13.43 | 132.29 | 8.71× | 720.4 | 1 | 104.8 | 65% | 0 (0.00%) |
| `python-fastapi-1w` | 27,152 | 2.29 | 2.57 | 4.55 | 5.01 | 76.88 | 1.99× | 67.6 | 2 | 36.8 | 10% | 0 (0.00%) |

### `list`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 52,864 | 1.16 | 2.00 | 2.82 | 6.46 | 35.99 | 2.43× | 15.1 | 0 | 134.6 | 70% | 0 (0.00%) |
| `go-nethttp` | 48,906 | 0.93 | 3.92 | 6.67 | 10.65 | 23.29 | 7.19× | 30.3 | 3 | 134.6 | 65% | 0 (0.00%) |
| `python-fastapi` | 34,371 | 1.32 | 5.04 | 9.24 | 22.09 | 133.09 | 6.97× | 720.2 | 10 | 207.3 | 71% | 0 (0.00%) |
| `python-fastapi-1w` | 14,543 | 4.30 | 4.68 | 8.58 | 9.33 | 139.63 | 2.00× | 67.6 | 5 | 68.7 | 10% | 0 (0.00%) |

### `create`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 140,689 | 0.44 | 0.62 | 0.85 | 1.75 | 73.81 | 1.94× | 840.2 | 404 | 28.3 | 39% | 0 (0.00%) |
| `go-nethttp` | 124,894 | 0.40 | 1.09 | 2.77 | 10.83 | 95.94 | 7.02× | 692.1 | 417 | 38.0 | 46% | 0 (0.00%) |
| `python-fastapi` | 35,244 | 1.46 | 4.44 | 8.20 | 19.97 | 129.48 | 5.61× | 686.0 | 452 | 169.5 | 59% | 0 (0.00%) |
| `python-fastapi-1w` | 19,388 | 3.21 | 3.58 | 6.38 | 7.42 | 103.41 | 1.99× | 204.3 | 540 | 51.5 | 10% | 0 (0.00%) |

### `cpu`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 19,246 | 3.25 | 5.38 | 6.48 | 8.08 | 27.68 | 2.00× | 13.3 | 0 | 456.6 | 88% | 0 (0.00%) |
| `go-nethttp` | 10,012 | 1.81 | 24.95 | 39.70 | 60.12 | 115.23 | 21.96× | 39.3 | 13 | 713.8 | 71% | 0 (0.00%) |
| `python-fastapi` | 2,220 | 26.27 | 62.95 | 79.74 | 102.86 | 149.31 | 3.04× | 731.4 | 95 | 3,428.5 | 76% | 0 (0.00%) |
| `python-fastapi-1w` | 875 | 73.23 | 78.64 | 81.85 | 119.74 | 127.36 | 1.12× | 71.7 | 77 | 1,173.0 | 10% | 0 (0.00%) |

### `io`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 5,226 | 12.23 | 13.14 | 13.43 | 13.72 | 13.93 | 1.10× | 13.2 | 3 | 32.6 | 2% | 0 (0.00%) |
| `go-nethttp` | 5,553 | 11.50 | 12.41 | 12.93 | 13.75 | 14.19 | 1.12× | 26.6 | 16 | 63.4 | 4% | 0 (0.00%) |
| `python-fastapi` | 5,757 | 11.10 | 11.92 | 12.01 | 13.19 | 15.85 | 1.08× | 718.6 | 6 | 69.5 | 4% | 0 (0.00%) |
| `python-fastapi-1w` | 5,455 | 11.75 | 12.89 | 14.23 | 21.83 | 25.85 | 1.21× | 67.9 | 0 | 63.1 | 3% | 0 (0.00%) |

### `mixed`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 8,609 | 7.47 | 8.70 | 9.18 | 9.93 | 11.18 | 1.23× | 13.4 | 2 | 74.9 | 6% | 0 (0.00%) |
| `go-nethttp` | 10,857 | 5.76 | 7.13 | 8.07 | 11.13 | 19.70 | 1.40× | 27.2 | 4 | 96.3 | 10% | 0 (0.00%) |
| `python-fastapi` | 10,119 | 6.32 | 7.55 | 8.20 | 8.93 | 11.32 | 1.30× | 720.1 | 4 | 168.6 | 17% | 0 (0.00%) |
| `python-fastapi-1w` | 9,942 | 6.37 | 7.18 | 8.06 | 13.73 | 18.45 | 1.26× | 67.8 | 2 | 83.1 | 8% | 0 (0.00%) |

## Behaviour that differs despite the shared contract

Recorded by the contract test (not asserted). Same inputs, framework-chosen responses.

- `rust-axum`
  - non-numeric id -> 400 'Invalid URL: Cannot parse `not-a-number` to a `u64`'
  - malformed json -> 400 'Failed to parse the request body as JSON: key must be a string at line 1 column 2'
  - wrong types -> 422 'Failed to deserialize the JSON body into the target type: name: invalid type: integer `123`, expected a string at line 1 column 12'
- `go-nethttp`
  - non-numeric id -> 400 {'error': 'invalid id'}
  - malformed json -> 400 {'error': 'invalid json'}
  - wrong types -> 400 {'error': 'invalid json'}
- `python-fastapi`
  - non-numeric id -> 422 b'{"detail":[{"type":"int_parsing","loc":["path","item_id"],"msg":"Input should be a valid integer, unable to parse string'
  - create-then-get across workers -> 0/10 hits (state is per-process; a real deployment needs a shared store)
  - malformed json -> 422 b'{"detail":[{"type":"json_invalid","loc":["body",1],"msg":"JSON decode error","input":{},"ctx":{"error":"Expecting proper'
  - wrong types -> 422 b'{"detail":[{"type":"string_type","loc":["body","name"],"msg":"Input should be a valid string","input":123},{"type":"float_parsing","loc":["body","price"],"msg":'
- `python-fastapi-1w`
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

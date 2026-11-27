# API Performance Lab — results `20261126-224731`

*2026-11-27T03:47:31+00:00* · Apple M5 (10 cores) · macOS-26.5-arm64-arm-64bit-Mach-O  
Load: oha 1.17.0, concurrency **64**, **10 s** per scenario after **3 s** warm-up, fresh process per scenario. Load generator and services share the machine; read the numbers as relative.

## Implementations and implementation complexity

LOC is non-blank, non-comment lines for the identical contract. Deps is every third-party package shipped (transitive). Cold start is process launch to first `200` from `/health`, median of 5 starts.

| Implementation | Toolchain | Contract | LOC | Deps | Build (s) | Artifact (MB) | Cold start ms (min–max) | Idle RSS (MB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | rustc 1.98.0 | pass | 177 | 93 | – | – | 10 (9–13) | 9.9 |
| `go-nethttp` | go1.27.4 | pass | 182 | 0 | – | – | 12 (12–17) | 13.4 |
| `python-fastapi` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | pass | 93 | 32 | – | – | 433 (345–450) | 710.8 |
| `python-fastapi-1w` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | pass | 93 | 32 | – | – | 172 (146–174) | 66.0 |

## Throughput (requests/s)

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 140,094 | 162,471 | 68,325 | 34,787 |
| get | 138,742 | 166,065 | 80,664 | 30,804 |
| list | 49,643 | 56,720 | 36,399 | 15,461 |
| create | 135,309 | 148,023 | 50,191 | 21,005 |
| cpu | 19,521 | 12,249 | 3,448 | 981 |
| io | 5,176 | 5,611 | 5,318 | 4,930 |
| mixed | 8,769 | 10,935 | 9,966 | 8,680 |

## Latency: p50 / p95 / p99 (ms)

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 0.38 / 0.89 / 2.05 | 0.30 / 0.92 / 2.02 | 0.61 / 2.67 / 5.44 | 1.78 / 1.96 / 3.58 |
| get | 0.38 / 0.89 / 2.04 | 0.30 / 0.87 / 1.83 | 0.52 / 2.36 / 4.29 | 2.02 / 2.23 / 4.01 |
| list | 1.25 / 2.13 / 2.79 | 0.77 / 3.50 / 5.84 | 1.45 / 3.73 / 6.76 | 4.00 / 4.41 / 7.94 |
| create | 0.39 / 0.93 / 1.93 | 0.35 / 0.88 / 2.09 | 0.85 / 3.62 / 6.65 | 2.96 / 3.46 / 5.90 |
| cpu | 3.19 / 5.41 / 6.78 | 1.41 / 21.41 / 33.89 | 15.82 / 39.18 / 51.22 | 65.26 / 66.30 / 75.47 |
| io | 12.42 / 13.26 / 13.57 | 11.39 / 12.16 / 12.53 | 12.04 / 13.36 / 14.00 | 13.01 / 14.32 / 15.65 |
| mixed | 7.36 / 8.61 / 9.22 | 5.72 / 7.05 / 7.79 | 6.34 / 7.66 / 7.95 | 7.00 / 8.28 / 11.14 |

## Peak RSS during load (MB, whole process tree)

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 11.5 | 30.2 | 722.1 | 69.2 |
| get | 9.9 | 28.9 | 719.1 | 67.6 |
| list | 15.2 | 30.1 | 514.9 | 67.6 |
| create | 441.2 | 799.7 | 928.1 | 203.8 |
| cpu | 13.4 | 41.0 | 732.6 | 71.1 |
| io | 13.2 | 26.4 | 719.6 | 67.4 |
| mixed | 13.7 | 27.2 | 720.5 | 67.8 |

## CPU per 1,000 requests (server CPU-ms)

Lower is better: compute each request actually consumed, independent of how saturated the machine was. Two implementations with equal req/s but 3× different CPU/1k do not have equal performance; one has 3× the headroom.

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 21.6 | 29.3 | 81.6 | 28.6 |
| get | 21.7 | 29.4 | 88.9 | 32.4 |
| list | 139.8 | 119.2 | 170.1 | 64.7 |
| create | 24.9 | 33.4 | 135.1 | 47.5 |
| cpu | 414.2 | 598.5 | 2,569.6 | 1,037.1 |
| io | 30.7 | 67.2 | 144.1 | 66.4 |
| mixed | 61.0 | 109.3 | 128.2 | 88.2 |

## Error rate under saturation

Concurrency far above the normal runs, with a per-request timeout; every timeout, refused or reset connection and non-2xx counts as an error. macOS `kern.ipc.somaxconn` here is 128, so connection bursts above that queue in the kernel for every implementation alike.

### `sat-get` — `/items/42` at concurrency 1000, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 172,174 | 5.55 | 18.78 | 235.83 | **0.00%** | 0 | 66.3 | – |
| `go-nethttp` | 175,902 | 3.44 | 29.87 | 105.73 | **0.00%** | 0 | 63.4 | – |
| `python-fastapi` | 78,300 | 11.72 | 30.12 | 458.88 | **0.00%** | 0 | 732.7 | – |
| `python-fastapi-1w` | 29,158 | 10.79 | 13.41 | 999.26 | **2.14%** | 6224 | 75.5 | timeout: 6224 |

### `sat-cpu` — `/compute/hash?n=20000` at concurrency 500, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 7,567 | 61.25 | 174.20 | 239.04 | **0.00%** | 0 | 30.8 | – |
| `go-nethttp` | 4,276 | 64.41 | 653.82 | 992.35 | **0.12%** | 53 | 70.1 | timeout: 53 |
| `python-fastapi` | 1,160 | 419.59 | 880.73 | 998.91 | **0.45%** | 50 | 760.8 | timeout: 50 |
| `python-fastapi-1w` | 677 | 270.77 | 364.12 | 958.40 | **62.11%** | 3897 | 71.0 | timeout: 3897 |

## Memory per open connection

1000 keep-alive connections opened, one request each, then held idle for 1 s. Per-connection cost is what bounds long-lived streaming/WebSocket/SSE fan-out.

| Implementation | Opened | Failed | Idle RSS MB | Held RSS MB | KB / connection | After close MB |
|---|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 1000 | 0 | 9.9 | 42.4 | **31.7** | 42.4 |
| `go-nethttp` | 1000 | 0 | 13.4 | 36.9 | **23.0** | 37.0 |
| `python-fastapi` | 1000 | 0 | 710.1 | 729.3 | **18.7** | 729.3 |
| `python-fastapi-1w` | 1000 | 0 | 66.0 | 78.1 | **11.8** | 77.1 |

## Recovery after a load spike

Probe: sequential keep-alive requests to `/items/42` from one client. Spike: `/items?limit=200` at concurrency 256 for 5 s. Then probe again immediately and after 10 s idle. *Retained* is how much of the spike's RSS growth was still held after settling: it shows whether the runtime gives memory back to the OS.

| Implementation | Spike req/s | Idle MB | Peak MB | +0 s MB | +10 s MB | Retained | Probe before p50/p99 | Probe +0 s | Probe +10 s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 65,768 | 9.9 | 22.9 | 22.9 | 16.4 | **49.9%** | 0.09 / 0.18 | 0.04 / 0.11 | 0.08 / 0.18 |
| `go-nethttp` | 65,800 | 13.5 | 35.3 | 35.7 | 35.7 | **101.9%** | 0.08 / 0.16 | 0.05 / 0.09 | 0.09 / 0.19 |
| `python-fastapi` | 47,769 | 710.8 | 722.0 | 722.0 | 722.0 | **100.0%** | 0.12 / 0.28 | 0.11 / 0.21 | 0.12 / 0.30 |
| `python-fastapi-1w` | 14,341 | 66.0 | 69.8 | 69.8 | 65.4 | **-15.4%** | 0.12 / 0.26 | 0.08 / 0.14 | 0.12 / 0.28 |

## Where Rust's advantage is, relative to each alternative

Every ratio is *alternative ÷ Rust* for cost metrics (latency, CPU, RSS) and *Rust ÷ alternative* for throughput, so **> 1 means Rust is better**, ≈ 1 means the language did not matter for that workload, and < 1 means the alternative won.

| Scenario | Metric | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---|---:|---:|---:|
| **health** | throughput | 0.86× | 2.05× | 4.03× |
|  | p99 latency | 0.99× | 2.65× | 1.75× |
|  | CPU / 1k req | 1.36× | 3.79× | 1.33× |
|  | peak RSS | 2.64× | 63.05× | 6.04× |
| **get** | throughput | 0.84× | 1.72× | 4.50× |
|  | p99 latency | 0.90× | 2.10× | 1.96× |
|  | CPU / 1k req | 1.35× | 4.09× | 1.49× |
|  | peak RSS | 2.93× | 72.91× | 6.85× |
| **list** | throughput | 0.88× | 1.36× | 3.21× |
|  | p99 latency | 2.10× | 2.43× | 2.85× |
|  | CPU / 1k req | 0.85× | 1.22× | 0.46× |
|  | peak RSS | 1.98× | 33.97× | 4.46× |
| **create** | throughput | 0.91× | 2.70× | 6.44× |
|  | p99 latency | 1.08× | 3.45× | 3.06× |
|  | CPU / 1k req | 1.34× | 5.43× | 1.91× |
|  | peak RSS | 1.81× | 2.10× | 0.46× |
| **cpu** | throughput | 1.59× | 5.66× | 19.90× |
|  | p99 latency | 5.00× | 7.56× | 11.13× |
|  | CPU / 1k req | 1.44× | 6.20× | 2.50× |
|  | peak RSS | 3.07× | 54.86× | 5.32× |
| **io** | throughput | 0.92× | 0.97× | 1.05× |
|  | p99 latency | 0.92× | 1.03× | 1.15× |
|  | CPU / 1k req | 2.19× | 4.69× | 2.16× |
|  | peak RSS | 2.01× | 54.70× | 5.12× |
| **mixed** | throughput | 0.80× | 0.88× | 1.01× |
|  | p99 latency | 0.85× | 0.86× | 1.21× |
|  | CPU / 1k req | 1.79× | 2.10× | 1.44× |
|  | peak RSS | 1.98× | 52.48× | 4.94× |

## Per-scenario detail

### `health`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 140,094 | 0.38 | 0.89 | 2.05 | 6.15 | 61.82 | 5.43× | 11.5 | 1 | 21.6 | 30% | 0 (0.00%) |
| `go-nethttp` | 162,471 | 0.30 | 0.92 | 2.02 | 4.93 | 58.42 | 6.72× | 30.2 | 0 | 29.3 | 47% | 0 (0.00%) |
| `python-fastapi` | 68,325 | 0.61 | 2.67 | 5.44 | 16.42 | 168.60 | 8.93× | 722.1 | 2 | 81.6 | 55% | 0 (0.00%) |
| `python-fastapi-1w` | 34,787 | 1.78 | 1.96 | 3.58 | 5.03 | 60.14 | 2.01× | 69.2 | 2 | 28.6 | 10% | 0 (0.00%) |

### `get`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 138,742 | 0.38 | 0.89 | 2.04 | 7.69 | 39.01 | 5.40× | 9.9 | 1 | 21.7 | 29% | 0 (0.00%) |
| `go-nethttp` | 166,065 | 0.30 | 0.87 | 1.83 | 4.75 | 13.84 | 6.01× | 28.9 | 0 | 29.4 | 48% | 0 (0.00%) |
| `python-fastapi` | 80,664 | 0.52 | 2.36 | 4.29 | 7.52 | 131.50 | 8.33× | 719.1 | 3 | 88.9 | 71% | 0 (0.00%) |
| `python-fastapi-1w` | 30,804 | 2.02 | 2.23 | 4.01 | 4.34 | 65.67 | 1.99× | 67.6 | 2 | 32.4 | 10% | 0 (0.00%) |

### `list`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 49,643 | 1.25 | 2.13 | 2.79 | 6.00 | 28.37 | 2.23× | 15.2 | 0 | 139.8 | 69% | 0 (0.00%) |
| `go-nethttp` | 56,720 | 0.77 | 3.50 | 5.84 | 9.44 | 18.38 | 7.55× | 30.1 | 1 | 119.2 | 67% | 0 (0.00%) |
| `python-fastapi` | 36,399 | 1.45 | 3.73 | 6.76 | 19.45 | 135.60 | 4.68× | 514.9 | 0 | 170.1 | 62% | 0 (0.00%) |
| `python-fastapi-1w` | 15,461 | 4.00 | 4.41 | 7.94 | 8.71 | 139.93 | 1.98× | 67.6 | 4 | 64.7 | 10% | 0 (0.00%) |

### `create`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 135,309 | 0.39 | 0.93 | 1.93 | 6.62 | 58.57 | 5.01× | 441.2 | 219 | 24.9 | 33% | 0 (0.00%) |
| `go-nethttp` | 148,023 | 0.35 | 0.88 | 2.09 | 8.11 | 101.42 | 6.03× | 799.7 | 375 | 33.4 | 48% | 0 (0.00%) |
| `python-fastapi` | 50,191 | 0.85 | 3.62 | 6.65 | 13.00 | 136.16 | 7.83× | 928.1 | 255 | 135.1 | 67% | 0 (0.00%) |
| `python-fastapi-1w` | 21,005 | 2.96 | 3.46 | 5.90 | 7.77 | 98.43 | 1.99× | 203.8 | 494 | 47.5 | 10% | 0 (0.00%) |

### `cpu`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 19,521 | 3.19 | 5.41 | 6.78 | 9.47 | 43.69 | 2.12× | 13.4 | 1 | 414.2 | 80% | 0 (0.00%) |
| `go-nethttp` | 12,249 | 1.41 | 21.41 | 33.89 | 52.30 | 82.67 | 24.07× | 41.0 | 45 | 598.5 | 73% | 0 (0.00%) |
| `python-fastapi` | 3,448 | 15.82 | 39.18 | 51.22 | 64.40 | 86.39 | 3.24× | 732.6 | 58 | 2,569.6 | 88% | 0 (0.00%) |
| `python-fastapi-1w` | 981 | 65.26 | 66.30 | 75.47 | 254.70 | 358.05 | 1.16× | 71.1 | 40 | 1,037.1 | 10% | 0 (0.00%) |

### `io`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 5,176 | 12.42 | 13.26 | 13.57 | 17.85 | 20.27 | 1.09× | 13.2 | 4 | 30.7 | 2% | 0 (0.00%) |
| `go-nethttp` | 5,611 | 11.39 | 12.16 | 12.53 | 13.27 | 14.57 | 1.10× | 26.4 | 25 | 67.2 | 4% | 0 (0.00%) |
| `python-fastapi` | 5,318 | 12.04 | 13.36 | 14.00 | 15.19 | 16.49 | 1.16× | 719.6 | 55 | 144.1 | 8% | 0 (0.00%) |
| `python-fastapi-1w` | 4,930 | 13.01 | 14.32 | 15.65 | 22.69 | 24.89 | 1.20× | 67.4 | 0 | 66.4 | 3% | 0 (0.00%) |

### `mixed`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 8,769 | 7.36 | 8.61 | 9.22 | 10.07 | 10.94 | 1.25× | 13.7 | 5 | 61.0 | 5% | 0 (0.00%) |
| `go-nethttp` | 10,935 | 5.72 | 7.05 | 7.79 | 9.15 | 15.15 | 1.36× | 27.2 | 5 | 109.3 | 12% | 0 (0.00%) |
| `python-fastapi` | 9,966 | 6.34 | 7.66 | 7.95 | 8.80 | 13.74 | 1.25× | 720.5 | 25 | 128.2 | 13% | 0 (0.00%) |
| `python-fastapi-1w` | 8,680 | 7.00 | 8.28 | 11.14 | 16.97 | 31.50 | 1.59× | 67.8 | 3 | 88.2 | 8% | 0 (0.00%) |

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
  - create-then-get across workers -> 1/10 hits (state is per-process; a real deployment needs a shared store)
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

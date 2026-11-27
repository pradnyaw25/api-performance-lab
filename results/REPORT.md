# API Performance Lab — results `20261126-221219`

*2026-11-27T03:12:19+00:00* · Apple M5 (10 cores) · macOS-26.5-arm64-arm-64bit-Mach-O  
Load: oha 1.17.0, concurrency **64**, **10 s** per scenario after **3 s** warm-up, fresh process per scenario. Load generator and services share the machine; read the numbers as relative.

## Implementations and implementation complexity

LOC is non-blank, non-comment lines for the identical contract. Deps is every third-party package shipped (transitive). Cold start is process launch to first `200` from `/health`, median of 5 starts.

| Implementation | Toolchain | Contract | LOC | Deps | Build (s) | Artifact (MB) | Cold start ms (min–max) | Idle RSS (MB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | rustc 1.98.0 | pass | 177 | 93 | 13.7 (cold) | 1.3 | 12 (9–177) | 9.9 |
| `go-nethttp` | go1.27.4 | pass | 182 | 0 | 3.2 (cold) | 9.3 | 12 (11–271) | 13.5 |
| `python-fastapi` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | pass | 93 | 21 | – | – | 417 (332–458) | 710.6 |
| `python-fastapi-1w` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | pass | 93 | 21 | – | – | 170 (148–178) | 66.0 |

## Throughput (requests/s)

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 187,430 | 172,913 | 86,031 | 33,295 |
| get | 184,152 | 168,017 | 77,025 | 30,141 |
| list | 67,633 | 56,036 | 42,376 | 15,344 |
| create | 180,059 | 141,524 | 55,025 | 20,088 |
| cpu | 23,733 | 11,482 | 3,221 | 979 |
| io | 5,207 | 5,617 | 5,653 | 5,450 |
| mixed | 8,673 | 11,027 | 10,230 | 9,896 |

## Latency: p50 / p95 / p99 (ms)

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 0.33 / 0.48 / 0.65 | 0.28 / 0.90 / 1.92 | 0.51 / 2.05 / 4.19 | 1.88 / 2.01 / 3.76 |
| get | 0.33 / 0.51 / 0.71 | 0.30 / 0.87 / 1.83 | 0.54 / 2.36 / 5.87 | 2.08 / 2.22 / 4.15 |
| list | 0.94 / 1.52 / 1.84 | 0.79 / 3.50 / 5.93 | 1.34 / 3.66 / 5.61 | 4.13 / 4.35 / 8.00 |
| create | 0.34 / 0.54 / 0.76 | 0.39 / 0.87 / 1.80 | 0.93 / 2.58 / 4.45 | 3.05 / 3.56 / 6.19 |
| cpu | 2.61 / 4.50 / 5.54 | 1.52 / 22.95 / 37.02 | 18.51 / 37.70 / 50.80 | 65.38 / 66.77 / 67.58 |
| io | 12.28 / 13.17 / 13.64 | 11.37 / 12.09 / 12.50 | 11.30 / 12.23 / 12.86 | 11.76 / 12.85 / 13.48 |
| mixed | 7.42 / 8.62 / 9.12 | 5.71 / 6.85 / 7.62 | 6.12 / 7.87 / 8.38 | 6.43 / 7.00 / 7.91 |

## Peak RSS during load (MB, whole process tree)

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 13.7 | 29.8 | 722.3 | 69.2 |
| get | 13.4 | 29.6 | 718.7 | 67.7 |
| list | 15.2 | 30.9 | 713.2 | 67.7 |
| create | 809.6 | 781.1 | 1,130.6 | 201.7 |
| cpu | 13.3 | 37.7 | 732.5 | 70.8 |
| io | 13.1 | 26.7 | 719.5 | 67.8 |
| mixed | 13.5 | 27.5 | 720.5 | 68.0 |

## CPU per 1,000 requests (server CPU-ms)

Lower is better: compute each request actually consumed, independent of how saturated the machine was. Two implementations with equal req/s but 3× different CPU/1k do not have equal performance; one has 3× the headroom.

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 20.6 | 28.1 | 78.2 | 29.9 |
| get | 21.6 | 29.5 | 93.3 | 33.2 |
| list | 120.0 | 123.2 | 179.0 | 65.2 |
| create | 23.6 | 36.3 | 136.6 | 49.6 |
| cpu | 375.9 | 642.0 | 2,976.7 | 1,039.0 |
| io | 31.1 | 65.0 | 126.2 | 63.2 |
| mixed | 75.0 | 103.7 | 105.6 | 83.7 |

## Error rate under saturation

Concurrency far above the normal runs, with a per-request timeout; every timeout, refused or reset connection and non-2xx counts as an error. macOS `kern.ipc.somaxconn` here is 128, so connection bursts above that queue in the kernel for every implementation alike.

### `sat-get` — `/items/42` at concurrency 1000, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 187,735 | 4.09 | 25.96 | 232.91 | **0.00%** | 0 | 68.0 | – |
| `go-nethttp` | 170,735 | 3.77 | 29.34 | 224.94 | **0.00%** | 0 | 59.5 | – |
| `python-fastapi` | 69,450 | 12.94 | 38.23 | 272.70 | **0.00%** | 0 | 734.6 | – |
| `python-fastapi-1w` | 29,424 | 10.74 | 13.03 | 1,000.77 | **2.11%** | 6200 | 76.2 | timeout: 6200 |

### `sat-cpu` — `/compute/hash?n=20000` at concurrency 500, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 8,956 | 50.96 | 145.00 | 204.49 | **0.00%** | 0 | 30.7 | – |
| `go-nethttp` | 4,150 | 21.05 | 698.01 | 996.52 | **0.20%** | 83 | 69.4 | timeout: 83 |
| `python-fastapi` | 991 | 484.62 | 955.58 | 999.67 | **2.10%** | 198 | 762.2 | timeout: 198 |
| `python-fastapi-1w` | 667 | 310.34 | 406.55 | 965.04 | **62.71%** | 3870 | 71.6 | timeout: 3870 |

## Memory per open connection

1000 keep-alive connections opened, one request each, then held idle for 1 s. Per-connection cost is what bounds long-lived streaming/WebSocket/SSE fan-out.

| Implementation | Opened | Failed | Idle RSS MB | Held RSS MB | KB / connection | After close MB |
|---|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 1000 | 0 | 9.9 | 42.3 | **31.6** | 42.3 |
| `go-nethttp` | 1000 | 0 | 13.4 | 37.1 | **23.2** | 37.5 |
| `python-fastapi` | 1000 | 0 | 710.5 | 729.4 | **18.5** | 729.4 |
| `python-fastapi-1w` | 1000 | 0 | 65.9 | 78.0 | **11.8** | 77.0 |

## Recovery after a load spike

Probe: sequential keep-alive requests to `/items/42` from one client. Spike: `/items?limit=200` at concurrency 256 for 5 s. Then probe again immediately and after 10 s idle. *Retained* is how much of the spike's RSS growth was still held after settling: it shows whether the runtime gives memory back to the OS.

| Implementation | Spike req/s | Idle MB | Peak MB | +0 s MB | +10 s MB | Retained | Probe before p50/p99 | Probe +0 s | Probe +10 s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 76,575 | 9.9 | 23.0 | 23.0 | 23.0 | **100.0%** | 0.08 / 0.15 | 0.04 / 0.07 | 0.09 / 0.17 |
| `go-nethttp` | 64,684 | 13.5 | 36.9 | 36.9 | 30.4 | **72.4%** | 0.09 / 0.19 | 0.05 / 0.10 | 0.09 / 0.22 |
| `python-fastapi` | 48,676 | 710.2 | 721.6 | 721.6 | 721.6 | **100.1%** | 0.13 / 0.33 | 0.13 / 0.28 | 0.12 / 0.31 |
| `python-fastapi-1w` | 14,900 | 66.1 | 69.8 | 69.8 | 69.8 | **100.0%** | 0.13 / 0.27 | 0.07 / 0.12 | 0.12 / 0.28 |

## Where Rust's advantage is, relative to each alternative

Every ratio is *alternative ÷ Rust* for cost metrics (latency, CPU, RSS) and *Rust ÷ alternative* for throughput, so **> 1 means Rust is better**, ≈ 1 means the language did not matter for that workload, and < 1 means the alternative won.

| Scenario | Metric | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---|---:|---:|---:|
| **health** | throughput | 1.08× | 2.18× | 5.63× |
|  | p99 latency | 2.97× | 6.48× | 5.82× |
|  | CPU / 1k req | 1.36× | 3.78× | 1.45× |
|  | peak RSS | 2.17× | 52.73× | 5.05× |
| **get** | throughput | 1.10× | 2.39× | 6.11× |
|  | p99 latency | 2.59× | 8.31× | 5.87× |
|  | CPU / 1k req | 1.37× | 4.33× | 1.54× |
|  | peak RSS | 2.20× | 53.56× | 5.05× |
| **list** | throughput | 1.21× | 1.60× | 4.41× |
|  | p99 latency | 3.22× | 3.05× | 4.34× |
|  | CPU / 1k req | 1.03× | 1.49× | 0.54× |
|  | peak RSS | 2.03× | 46.96× | 4.46× |
| **create** | throughput | 1.27× | 3.27× | 8.96× |
|  | p99 latency | 2.39× | 5.88× | 8.19× |
|  | CPU / 1k req | 1.54× | 5.80× | 2.10× |
|  | peak RSS | 0.96× | 1.40× | 0.25× |
| **cpu** | throughput | 2.07× | 7.37× | 24.24× |
|  | p99 latency | 6.68× | 9.17× | 12.19× |
|  | CPU / 1k req | 1.71× | 7.92× | 2.76× |
|  | peak RSS | 2.82× | 54.92× | 5.31× |
| **io** | throughput | 0.93× | 0.92× | 0.96× |
|  | p99 latency | 0.92× | 0.94× | 0.99× |
|  | CPU / 1k req | 2.09× | 4.05× | 2.03× |
|  | peak RSS | 2.03× | 54.75× | 5.16× |
| **mixed** | throughput | 0.79× | 0.85× | 0.88× |
|  | p99 latency | 0.84× | 0.92× | 0.87× |
|  | CPU / 1k req | 1.38× | 1.41× | 1.12× |
|  | peak RSS | 2.04× | 53.30× | 5.03× |

## Per-scenario detail

### `health`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 187,430 | 0.33 | 0.48 | 0.65 | 1.12 | 6.47 | 1.96× | 13.7 | 0 | 20.6 | 38% | 0 (0.00%) |
| `go-nethttp` | 172,913 | 0.28 | 0.90 | 1.92 | 4.35 | 10.63 | 6.88× | 29.8 | 0 | 28.1 | 48% | 0 (0.00%) |
| `python-fastapi` | 86,031 | 0.51 | 2.05 | 4.19 | 7.81 | 130.74 | 8.23× | 722.3 | 2 | 78.2 | 66% | 0 (0.00%) |
| `python-fastapi-1w` | 33,295 | 1.88 | 2.01 | 3.76 | 5.92 | 60.48 | 2.00× | 69.2 | 2 | 29.9 | 10% | 0 (0.00%) |

### `get`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 184,152 | 0.33 | 0.51 | 0.71 | 1.40 | 10.38 | 2.12× | 13.4 | 0 | 21.6 | 39% | 0 (0.00%) |
| `go-nethttp` | 168,017 | 0.30 | 0.87 | 1.83 | 4.39 | 9.42 | 6.10× | 29.6 | 1 | 29.5 | 49% | 0 (0.00%) |
| `python-fastapi` | 77,025 | 0.54 | 2.36 | 5.87 | 12.08 | 127.98 | 10.79× | 718.7 | 3 | 93.3 | 71% | 0 (0.00%) |
| `python-fastapi-1w` | 30,141 | 2.08 | 2.22 | 4.15 | 4.39 | 66.38 | 1.99× | 67.7 | 2 | 33.2 | 10% | 0 (0.00%) |

### `list`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 67,633 | 0.94 | 1.52 | 1.84 | 2.54 | 49.64 | 1.96× | 15.2 | 0 | 120.0 | 80% | 0 (0.00%) |
| `go-nethttp` | 56,036 | 0.79 | 3.50 | 5.93 | 9.60 | 18.40 | 7.52× | 30.9 | 4 | 123.2 | 68% | 0 (0.00%) |
| `python-fastapi` | 42,376 | 1.34 | 3.66 | 5.61 | 10.96 | 129.12 | 4.17× | 713.2 | 8 | 179.0 | 75% | 0 (0.00%) |
| `python-fastapi-1w` | 15,344 | 4.13 | 4.35 | 8.00 | 8.64 | 125.58 | 1.93× | 67.7 | 4 | 65.2 | 10% | 0 (0.00%) |

### `create`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 180,059 | 0.34 | 0.54 | 0.76 | 1.53 | 70.20 | 2.26× | 809.6 | 292 | 23.6 | 42% | 0 (0.00%) |
| `go-nethttp` | 141,524 | 0.39 | 0.87 | 1.80 | 5.92 | 70.19 | 4.59× | 781.1 | 390 | 36.3 | 50% | 0 (0.00%) |
| `python-fastapi` | 55,025 | 0.93 | 2.58 | 4.45 | 7.83 | 159.34 | 4.79× | 1,130.6 | 584 | 136.6 | 74% | 0 (0.00%) |
| `python-fastapi-1w` | 20,088 | 3.05 | 3.56 | 6.19 | 13.79 | 96.87 | 2.03× | 201.7 | 506 | 49.6 | 10% | 0 (0.00%) |

### `cpu`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 23,733 | 2.61 | 4.50 | 5.54 | 10.25 | 91.77 | 2.13× | 13.3 | 1 | 375.9 | 89% | 0 (0.00%) |
| `go-nethttp` | 11,482 | 1.52 | 22.95 | 37.02 | 56.11 | 96.44 | 24.32× | 37.7 | 11 | 642.0 | 74% | 0 (0.00%) |
| `python-fastapi` | 3,221 | 18.51 | 37.70 | 50.80 | 73.40 | 123.28 | 2.74× | 732.5 | 38 | 2,976.7 | 96% | 0 (0.00%) |
| `python-fastapi-1w` | 979 | 65.38 | 66.77 | 67.58 | 363.70 | 489.87 | 1.03× | 70.8 | 12 | 1,039.0 | 10% | 0 (0.00%) |

### `io`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 5,207 | 12.28 | 13.17 | 13.64 | 23.17 | 23.61 | 1.11× | 13.1 | 2 | 31.1 | 2% | 0 (0.00%) |
| `go-nethttp` | 5,617 | 11.37 | 12.09 | 12.50 | 17.31 | 17.80 | 1.10× | 26.7 | 16 | 65.0 | 4% | 0 (0.00%) |
| `python-fastapi` | 5,653 | 11.30 | 12.23 | 12.86 | 13.57 | 15.07 | 1.14× | 719.5 | 51 | 126.2 | 7% | 0 (0.00%) |
| `python-fastapi-1w` | 5,450 | 11.76 | 12.85 | 13.48 | 21.53 | 23.43 | 1.15× | 67.8 | 4 | 63.2 | 3% | 0 (0.00%) |

### `mixed`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 8,673 | 7.42 | 8.62 | 9.12 | 9.57 | 9.90 | 1.23× | 13.5 | 2 | 75.0 | 6% | 0 (0.00%) |
| `go-nethttp` | 11,027 | 5.71 | 6.85 | 7.62 | 8.86 | 13.27 | 1.33× | 27.5 | 9 | 103.7 | 11% | 0 (0.00%) |
| `python-fastapi` | 10,230 | 6.12 | 7.87 | 8.38 | 9.64 | 15.14 | 1.37× | 720.5 | 22 | 105.6 | 11% | 0 (0.00%) |
| `python-fastapi-1w` | 9,896 | 6.43 | 7.00 | 7.91 | 11.97 | 14.29 | 1.23× | 68.0 | 2 | 83.7 | 8% | 0 (0.00%) |

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

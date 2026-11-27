# API Performance Lab — results `20261126-222824`

*2026-11-27T03:28:24+00:00* · Apple M5 (10 cores) · macOS-26.5-arm64-arm-64bit-Mach-O  
Load: oha 1.17.0, concurrency **64**, **10 s** per scenario after **3 s** warm-up, fresh process per scenario. Load generator and services share the machine; read the numbers as relative.

## Implementations and implementation complexity

LOC is non-blank, non-comment lines for the identical contract. Deps is every third-party package shipped (transitive). Cold start is process launch to first `200` from `/health`, median of 5 starts.

| Implementation | Toolchain | Contract | LOC | Deps | Build (s) | Artifact (MB) | Cold start ms (min–max) | Idle RSS (MB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | rustc 1.98.0 | pass | 177 | 93 | – | – | 9 (9–10) | 9.9 |
| `go-nethttp` | go1.27.4 | pass | 182 | 0 | – | – | 14 (12–19) | 13.5 |
| `python-fastapi` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | pass | 93 | 32 | – | – | 415 (390–447) | 710.7 |
| `python-fastapi-1w` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | pass | 93 | 32 | – | – | 178 (176–203) | 65.9 |

## Throughput (requests/s)

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 187,340 | 171,372 | 79,964 | 29,207 |
| get | 186,485 | 166,279 | 69,871 | 27,476 |
| list | 68,250 | 52,094 | 38,618 | 13,164 |
| create | 180,464 | 139,461 | 48,168 | 18,161 |
| cpu | 21,415 | 10,468 | 3,049 | 872 |
| io | 5,176 | 5,586 | 5,670 | 5,440 |
| mixed | 8,583 | 10,945 | 10,361 | 9,864 |

## Latency: p50 / p95 / p99 (ms)

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 0.32 / 0.53 / 0.91 | 0.27 / 0.94 / 2.18 | 0.53 / 2.34 / 6.50 | 2.06 / 2.56 / 4.28 |
| get | 0.32 / 0.54 / 0.83 | 0.29 / 0.92 / 2.12 | 0.70 / 2.29 / 4.73 | 2.27 / 2.54 / 4.54 |
| list | 0.93 / 1.51 / 1.89 | 0.83 / 3.77 / 6.41 | 0.83 / 5.58 / 9.49 | 4.54 / 6.45 / 10.52 |
| create | 0.33 / 0.55 / 0.82 | 0.38 / 0.93 / 2.18 | 1.02 / 3.44 / 5.81 | 3.37 / 4.30 / 6.78 |
| cpu | 2.92 / 4.89 / 5.84 | 1.68 / 24.46 / 39.30 | 19.99 / 43.11 / 56.45 | 71.74 / 81.62 / 110.33 |
| io | 12.44 / 13.32 / 14.06 | 11.39 / 12.23 / 12.86 | 11.32 / 12.28 / 12.73 | 11.72 / 12.91 / 14.93 |
| mixed | 7.48 / 8.76 / 9.48 | 5.71 / 6.94 / 7.83 | 6.13 / 7.38 / 7.88 | 6.37 / 7.24 / 8.35 |

## Peak RSS during load (MB, whole process tree)

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 13.7 | 29.4 | 722.2 | 69.1 |
| get | 13.3 | 29.9 | 719.5 | 67.3 |
| list | 15.3 | 29.9 | 720.3 | 67.7 |
| create | 1,007.1 | 773.5 | 1,046.2 | 197.3 |
| cpu | 13.3 | 42.3 | 732.5 | 71.0 |
| io | 13.2 | 26.3 | 720.4 | 67.8 |
| mixed | 13.8 | 27.4 | 720.4 | 68.2 |

## CPU per 1,000 requests (server CPU-ms)

Lower is better: compute each request actually consumed, independent of how saturated the machine was. Two implementations with equal req/s but 3× different CPU/1k do not have equal performance; one has 3× the headroom.

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 19.9 | 27.9 | 84.4 | 33.9 |
| get | 20.4 | 28.8 | 99.5 | 36.3 |
| list | 115.1 | 122.5 | 193.9 | 74.9 |
| create | 23.4 | 35.5 | 150.4 | 54.7 |
| cpu | 422.3 | 658.4 | 3,074.4 | 1,163.7 |
| io | 29.6 | 53.2 | 93.2 | 64.8 |
| mixed | 68.2 | 102.0 | 106.2 | 83.4 |

## Error rate under saturation

Concurrency far above the normal runs, with a per-request timeout; every timeout, refused or reset connection and non-2xx counts as an error. macOS `kern.ipc.somaxconn` here is 128, so connection bursts above that queue in the kernel for every implementation alike.

### `sat-get` — `/items/42` at concurrency 1000, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 187,421 | 3.92 | 26.05 | 168.93 | **0.00%** | 0 | 67.2 | – |
| `go-nethttp` | 155,196 | 4.43 | 31.43 | 174.60 | **0.00%** | 0 | 60.5 | – |
| `python-fastapi` | 53,050 | 15.55 | 73.14 | 220.20 | **0.00%** | 0 | 733.1 | – |
| `python-fastapi-1w` | 24,427 | 11.66 | 23.91 | 992.61 | **2.61%** | 6364 | 74.3 | timeout: 6364 |

### `sat-cpu` — `/compute/hash?n=20000` at concurrency 500, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 7,907 | 57.31 | 173.16 | 304.02 | **0.00%** | 0 | 30.8 | – |
| `go-nethttp` | 3,744 | 73.86 | 730.69 | 1,000.34 | **0.23%** | 83 | 71.4 | timeout: 83 |
| `python-fastapi` | 811 | 555.33 | 981.00 | 1,000.83 | **13.80%** | 1050 | 762.7 | timeout: 1050 |
| `python-fastapi-1w` | 657 | 318.77 | 404.54 | 971.51 | **63.89%** | 3879 | 71.3 | timeout: 3879 |

## Memory per open connection

1000 keep-alive connections opened, one request each, then held idle for 1 s. Per-connection cost is what bounds long-lived streaming/WebSocket/SSE fan-out.

| Implementation | Opened | Failed | Idle RSS MB | Held RSS MB | KB / connection | After close MB |
|---|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 1000 | 0 | 9.9 | 42.3 | **31.6** | 42.3 |
| `go-nethttp` | 1000 | 0 | 13.5 | 36.8 | **22.7** | 37.1 |
| `python-fastapi` | 1000 | 0 | 710.9 | 729.9 | **18.5** | 729.9 |
| `python-fastapi-1w` | 1000 | 0 | 66.0 | 78.0 | **11.8** | 78.0 |

## Recovery after a load spike

Probe: sequential keep-alive requests to `/items/42` from one client. Spike: `/items?limit=200` at concurrency 256 for 5 s. Then probe again immediately and after 10 s idle. *Retained* is how much of the spike's RSS growth was still held after settling: it shows whether the runtime gives memory back to the OS.

| Implementation | Spike req/s | Idle MB | Peak MB | +0 s MB | +10 s MB | Retained | Probe before p50/p99 | Probe +0 s | Probe +10 s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 67,459 | 9.9 | 22.9 | 22.9 | 17.5 | **58.4%** | 0.09 / 0.17 | 0.04 / 0.13 | 0.08 / 0.14 |
| `go-nethttp` | 57,939 | 13.4 | 36.5 | 36.5 | 35.3 | **95.0%** | 0.06 / 0.12 | 0.07 / 0.17 | 0.09 / 0.18 |
| `python-fastapi` | 38,487 | 710.9 | 722.4 | 722.4 | 722.4 | **100.0%** | 0.12 / 0.35 | 0.17 / 0.45 | 0.13 / 0.28 |
| `python-fastapi-1w` | 14,259 | 66.0 | 69.8 | 69.8 | 65.3 | **-18.4%** | 0.12 / 0.31 | 0.08 / 0.13 | 0.13 / 0.30 |

## Where Rust's advantage is, relative to each alternative

Every ratio is *alternative ÷ Rust* for cost metrics (latency, CPU, RSS) and *Rust ÷ alternative* for throughput, so **> 1 means Rust is better**, ≈ 1 means the language did not matter for that workload, and < 1 means the alternative won.

| Scenario | Metric | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---|---:|---:|---:|
| **health** | throughput | 1.09× | 2.34× | 6.41× |
|  | p99 latency | 2.39× | 7.14× | 4.70× |
|  | CPU / 1k req | 1.41× | 4.25× | 1.71× |
|  | peak RSS | 2.14× | 52.54× | 5.03× |
| **get** | throughput | 1.12× | 2.67× | 6.79× |
|  | p99 latency | 2.55× | 5.69× | 5.47× |
|  | CPU / 1k req | 1.41× | 4.88× | 1.78× |
|  | peak RSS | 2.25× | 53.95× | 5.05× |
| **list** | throughput | 1.31× | 1.77× | 5.18× |
|  | p99 latency | 3.39× | 5.02× | 5.56× |
|  | CPU / 1k req | 1.06× | 1.68× | 0.65× |
|  | peak RSS | 1.96× | 47.17× | 4.43× |
| **create** | throughput | 1.29× | 3.75× | 9.94× |
|  | p99 latency | 2.66× | 7.09× | 8.27× |
|  | CPU / 1k req | 1.52× | 6.42× | 2.34× |
|  | peak RSS | 0.77× | 1.04× | 0.20× |
| **cpu** | throughput | 2.05× | 7.02× | 24.55× |
|  | p99 latency | 6.72× | 9.66× | 18.88× |
|  | CPU / 1k req | 1.56× | 7.28× | 2.76× |
|  | peak RSS | 3.17× | 54.99× | 5.33× |
| **io** | throughput | 0.93× | 0.91× | 0.95× |
|  | p99 latency | 0.91× | 0.91× | 1.06× |
|  | CPU / 1k req | 1.80× | 3.15× | 2.19× |
|  | peak RSS | 2.00× | 54.62× | 5.14× |
| **mixed** | throughput | 0.78× | 0.83× | 0.87× |
|  | p99 latency | 0.83× | 0.83× | 0.88× |
|  | CPU / 1k req | 1.50× | 1.56× | 1.22× |
|  | peak RSS | 1.99× | 52.16× | 4.94× |

## Per-scenario detail

### `health`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 187,340 | 0.32 | 0.53 | 0.91 | 2.60 | 44.24 | 2.87× | 13.7 | 0 | 19.9 | 36% | 0 (0.00%) |
| `go-nethttp` | 171,372 | 0.27 | 0.94 | 2.18 | 4.79 | 31.36 | 8.03× | 29.4 | 1 | 27.9 | 47% | 0 (0.00%) |
| `python-fastapi` | 79,964 | 0.53 | 2.34 | 6.50 | 14.61 | 129.44 | 12.38× | 722.2 | 1 | 84.4 | 67% | 0 (0.00%) |
| `python-fastapi-1w` | 29,207 | 2.06 | 2.56 | 4.28 | 7.76 | 77.27 | 2.07× | 69.1 | 2 | 33.9 | 10% | 0 (0.00%) |

### `get`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 186,485 | 0.32 | 0.54 | 0.83 | 1.78 | 28.89 | 2.58× | 13.3 | 0 | 20.4 | 37% | 0 (0.00%) |
| `go-nethttp` | 166,279 | 0.29 | 0.92 | 2.12 | 5.26 | 38.20 | 7.40× | 29.9 | 1 | 28.8 | 47% | 0 (0.00%) |
| `python-fastapi` | 69,871 | 0.70 | 2.29 | 4.73 | 9.42 | 134.76 | 6.74× | 719.5 | 1 | 99.5 | 69% | 0 (0.00%) |
| `python-fastapi-1w` | 27,476 | 2.27 | 2.54 | 4.54 | 6.26 | 79.94 | 2.00× | 67.3 | 3 | 36.3 | 10% | 0 (0.00%) |

### `list`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 68,250 | 0.93 | 1.51 | 1.89 | 3.21 | 41.02 | 2.04× | 15.3 | 0 | 115.1 | 78% | 0 (0.00%) |
| `go-nethttp` | 52,094 | 0.83 | 3.77 | 6.41 | 11.87 | 42.30 | 7.74× | 29.9 | 4 | 122.5 | 63% | 0 (0.00%) |
| `python-fastapi` | 38,618 | 0.83 | 5.58 | 9.49 | 15.79 | 133.23 | 11.46× | 720.3 | 13 | 193.9 | 74% | 0 (0.00%) |
| `python-fastapi-1w` | 13,164 | 4.54 | 6.45 | 10.52 | 22.02 | 138.28 | 2.32× | 67.7 | 5 | 74.9 | 10% | 0 (0.00%) |

### `create`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 180,464 | 0.33 | 0.55 | 0.82 | 1.89 | 47.63 | 2.47× | 1,007.1 | 400 | 23.4 | 41% | 0 (0.00%) |
| `go-nethttp` | 139,461 | 0.38 | 0.93 | 2.18 | 8.17 | 121.39 | 5.79× | 773.5 | 405 | 35.5 | 49% | 0 (0.00%) |
| `python-fastapi` | 48,168 | 1.02 | 3.44 | 5.81 | 11.11 | 192.91 | 5.67× | 1,046.2 | 521 | 150.4 | 72% | 0 (0.00%) |
| `python-fastapi-1w` | 18,161 | 3.37 | 4.30 | 6.78 | 11.09 | 91.43 | 2.01× | 197.3 | 534 | 54.7 | 10% | 0 (0.00%) |

### `cpu`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 21,415 | 2.92 | 4.89 | 5.84 | 7.22 | 27.64 | 2.00× | 13.3 | 1 | 422.3 | 90% | 0 (0.00%) |
| `go-nethttp` | 10,468 | 1.68 | 24.46 | 39.30 | 62.10 | 95.82 | 23.34× | 42.3 | 24 | 658.4 | 69% | 0 (0.00%) |
| `python-fastapi` | 3,049 | 19.99 | 43.11 | 56.45 | 75.05 | 114.00 | 2.82× | 732.5 | 183 | 3,074.4 | 93% | 0 (0.00%) |
| `python-fastapi-1w` | 872 | 71.74 | 81.62 | 110.33 | 412.16 | 526.66 | 1.54× | 71.0 | 72 | 1,163.7 | 10% | 0 (0.00%) |

### `io`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 5,176 | 12.44 | 13.32 | 14.06 | 15.33 | 16.70 | 1.13× | 13.2 | 1 | 29.6 | 2% | 0 (0.00%) |
| `go-nethttp` | 5,586 | 11.39 | 12.23 | 12.86 | 24.13 | 32.94 | 1.13× | 26.3 | 15 | 53.2 | 3% | 0 (0.00%) |
| `python-fastapi` | 5,670 | 11.32 | 12.28 | 12.73 | 17.12 | 21.43 | 1.12× | 720.4 | 70 | 93.2 | 5% | 0 (0.00%) |
| `python-fastapi-1w` | 5,440 | 11.72 | 12.91 | 14.93 | 23.89 | 27.19 | 1.27× | 67.8 | 0 | 64.8 | 4% | 0 (0.00%) |

### `mixed`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 8,583 | 7.48 | 8.76 | 9.48 | 10.61 | 11.25 | 1.27× | 13.8 | 5 | 68.2 | 6% | 0 (0.00%) |
| `go-nethttp` | 10,945 | 5.71 | 6.94 | 7.83 | 9.68 | 29.17 | 1.37× | 27.4 | 10 | 102.0 | 11% | 0 (0.00%) |
| `python-fastapi` | 10,361 | 6.13 | 7.38 | 7.88 | 8.39 | 10.44 | 1.29× | 720.4 | 35 | 106.2 | 11% | 0 (0.00%) |
| `python-fastapi-1w` | 9,864 | 6.37 | 7.24 | 8.35 | 18.07 | 59.96 | 1.31× | 68.2 | 2 | 83.4 | 8% | 0 (0.00%) |

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

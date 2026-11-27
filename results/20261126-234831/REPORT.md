# API Performance Lab — results `20261126-234831`

*2026-11-27T04:48:31+00:00* · Apple M5 (10 cores) · macOS-26.5-arm64-arm-64bit-Mach-O  
Load: oha 1.17.0, concurrency **64**, **10 s** per scenario after **3 s** warm-up, fresh process per scenario. Load generator and services share the machine; read the numbers as relative.

## Implementations and implementation complexity

LOC is non-blank, non-comment lines for the identical contract. Deps is every third-party package shipped (transitive). Cold start is process launch to first `200` from `/health`, median of 1 starts.

| Implementation | Toolchain | Contract | LOC | Deps | Build (s) | Artifact (MB) | Cold start ms (min–max) | Idle RSS (MB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `go-nethttp` | go1.27.4 | pass | 182 | 0 | – | – | 14 (14–14) | 13.3 |
| `go-nethttp-nogc` | go1.27.4 | pass | 182 | 0 | – | – | 12 (12–12) | 13.5 |

## Throughput (requests/s)

| Scenario | `go-nethttp` | `go-nethttp-nogc` |
|---|---:|---:|
| get | 132,590 | 90,514 |
| list | 49,958 | 46,827 |
| cpu | 11,476 | 9,626 |

## Latency: p50 / p95 / p99 (ms)

| Scenario | `go-nethttp` | `go-nethttp-nogc` |
|---|---:|---:|
| get | 0.25 / 1.42 / 5.13 | 0.24 / 1.75 / 7.53 |
| list | 0.82 / 4.21 / 7.61 | 0.90 / 3.71 / 8.61 |
| cpu | 1.59 / 22.91 / 37.40 | 4.64 / 17.61 / 38.41 |

## Peak RSS during load (MB, whole process tree)

| Scenario | `go-nethttp` | `go-nethttp-nogc` |
|---|---:|---:|
| get | 30.5 | 1,048.1 |
| list | 31.0 | 2,078.1 |
| cpu | 41.7 | 1,934.3 |

## CPU per 1,000 requests (server CPU-ms)

Lower is better: compute each request actually consumed, independent of how saturated the machine was. Two implementations with equal req/s but 3× different CPU/1k do not have equal performance; one has 3× the headroom.

| Scenario | `go-nethttp` | `go-nethttp-nogc` |
|---|---:|---:|
| get | 24.6 | 26.4 |
| list | 117.1 | 119.6 |
| cpu | 593.0 | 546.3 |

## Error rate under saturation

Concurrency far above the normal runs, with a per-request timeout; every timeout, refused or reset connection and non-2xx counts as an error. macOS `kern.ipc.somaxconn` here is 128, so connection bursts above that queue in the kernel for every implementation alike.

### `sat-cpu` — `/compute/hash?n=20000` at concurrency 500, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `go-nethttp` | 3,391 | 77.69 | 764.81 | 1,000.21 | **0.39%** | 130 | 80.6 | timeout: 130 |
| `go-nethttp-nogc` | 2,614 | 140.74 | 885.87 | 1,002.71 | **1.14%** | 292 | 9,608.7 | timeout: 292 |

## Per-scenario detail

### `get`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `go-nethttp` | 132,590 | 0.25 | 1.42 | 5.13 | 10.50 | 73.02 | 20.34× | 30.5 | 2 | 24.6 | 32% | 0 (0.00%) |
| `go-nethttp-nogc` | 90,514 | 0.24 | 1.75 | 7.53 | 53.44 | 367.26 | 31.79× | 1,048.1 | 165 | 26.4 | 24% | 0 (0.00%) |

### `list`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `go-nethttp` | 49,958 | 0.82 | 4.21 | 7.61 | 12.96 | 67.64 | 9.28× | 31.0 | 4 | 117.1 | 58% | 0 (0.00%) |
| `go-nethttp-nogc` | 46,827 | 0.90 | 3.71 | 8.61 | 21.56 | 180.12 | 9.52× | 2,078.1 | 3,057 | 119.6 | 56% | 0 (0.00%) |

### `cpu`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `go-nethttp` | 11,476 | 1.59 | 22.91 | 37.40 | 58.58 | 96.46 | 23.47× | 41.7 | 19 | 593.0 | 68% | 0 (0.00%) |
| `go-nethttp-nogc` | 9,626 | 4.64 | 17.61 | 38.41 | 124.49 | 242.82 | 8.27× | 1,934.3 | 5,928 | 546.3 | 52% | 0 (0.00%) |

## Behaviour that differs despite the shared contract

Recorded by the contract test (not asserted). Same inputs, framework-chosen responses.

- `go-nethttp`
  - non-numeric id -> 400 {'error': 'invalid id'}
  - malformed json -> 400 {'error': 'invalid json'}
  - wrong types -> 400 {'error': 'invalid json'}
- `go-nethttp-nogc`
  - non-numeric id -> 400 {'error': 'invalid id'}
  - malformed json -> 400 {'error': 'invalid json'}
  - wrong types -> 400 {'error': 'invalid json'}

## Reading the numbers

- **p99/p50** is the tail-flatness ratio. GC pauses and the GIL show up here, not in the median.
- **CPU ms/1k** is the cost side of throughput. Equal req/s at 3× the CPU is not equal performance; it is 3× less headroom.
- **CPU util** is server CPU over all cores. Near 100% means the service was the bottleneck; well below means the load generator or the scenario's I/O wait was.
- **ΔRSS/req** is memory growth per request over the run. It only means something for `create`, where it is the per-item cost of the in-memory store; elsewhere it should be ~0.
- `io` and `mixed` are latency-bound by design: with concurrency *c* and wait *w*, throughput cannot exceed *c / w*. Converging numbers there are the expected result; the interesting columns are CPU/1k, RSS and tail latency.
- The Python rows are the same code; `python-fastapi` runs one Uvicorn worker per core, `python-fastapi-1w` runs one. The gap between them is the cost of the GIL; the gap between `python-fastapi` and Go is the cost of multi-process vs. multi-thread.

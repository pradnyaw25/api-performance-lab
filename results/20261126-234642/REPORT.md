# API Performance Lab — results `20261126-234642`

*2026-11-27T04:46:42+00:00* · Apple M5 (10 cores) · macOS-26.5-arm64-arm-64bit-Mach-O  
Load: oha 1.17.0, concurrency **64**, **10 s** per scenario after **3 s** warm-up, fresh process per scenario. Load generator and services share the machine; read the numbers as relative.

## Implementations and implementation complexity

LOC is non-blank, non-comment lines for the identical contract. Deps is every third-party package shipped (transitive). Cold start is process launch to first `200` from `/health`, median of 1 starts.

| Implementation | Toolchain | Contract | LOC | Deps | Build (s) | Artifact (MB) | Cold start ms (min–max) | Idle RSS (MB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `go-nethttp` | go1.27.4 | pass | 182 | 0 | – | – | 31 (31–31) | 13.5 |
| `go-nethttp-nogc` | go1.27.4 | pass | 182 | 0 | – | – | 6 (6–6) | 13.5 |

## Throughput (requests/s)

| Scenario | `go-nethttp` | `go-nethttp-nogc` |
|---|---:|---:|
| get | 176,618 | 175,643 |
| list | 61,859 | 70,791 |
| cpu | 14,241 | 12,983 |

## Latency: p50 / p95 / p99 (ms)

| Scenario | `go-nethttp` | `go-nethttp-nogc` |
|---|---:|---:|
| get | 0.24 / 0.95 / 2.62 | 0.23 / 0.86 / 3.03 |
| list | 0.68 / 3.28 / 5.91 | 0.66 / 2.37 / 4.43 |
| cpu | 1.24 / 18.82 / 30.72 | 3.58 / 12.40 / 25.38 |

## Peak RSS during load (MB, whole process tree)

| Scenario | `go-nethttp` | `go-nethttp-nogc` |
|---|---:|---:|
| get | 28.3 | 716.6 |
| list | 28.7 | 1,993.6 |
| cpu | 40.7 | 2,317.8 |

## CPU per 1,000 requests (server CPU-ms)

Lower is better: compute each request actually consumed, independent of how saturated the machine was. Two implementations with equal req/s but 3× different CPU/1k do not have equal performance; one has 3× the headroom.

| Scenario | `go-nethttp` | `go-nethttp-nogc` |
|---|---:|---:|
| get | 26.2 | 26.2 |
| list | 103.2 | 97.2 |
| cpu | 495.2 | 453.2 |

## Error rate under saturation

Concurrency far above the normal runs, with a per-request timeout; every timeout, refused or reset connection and non-2xx counts as an error. macOS `kern.ipc.somaxconn` here is 128, so connection bursts above that queue in the kernel for every implementation alike.

### `sat-cpu` — `/compute/hash?n=20000` at concurrency 500, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `go-nethttp` | 4,581 | 63.88 | 618.83 | 999.38 | **0.08%** | 36 | 73.7 | timeout: 36 |
| `go-nethttp-nogc` | 2,404 | 175.19 | 860.13 | 1,009.26 | **0.32%** | 76 | 6,078.3 | timeout: 76 |

## Per-scenario detail

### `get`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `go-nethttp` | 176,618 | 0.24 | 0.95 | 2.62 | 5.99 | 38.63 | 11.01× | 28.3 | 1 | 26.2 | 45% | 0 (0.00%) |
| `go-nethttp-nogc` | 175,643 | 0.23 | 0.86 | 3.03 | 10.60 | 116.38 | 13.47× | 716.6 | 82 | 26.2 | 45% | 0 (0.00%) |

### `list`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `go-nethttp` | 61,859 | 0.68 | 3.28 | 5.91 | 10.21 | 33.52 | 8.67× | 28.7 | 1 | 103.2 | 63% | 0 (0.00%) |
| `go-nethttp-nogc` | 70,791 | 0.66 | 2.37 | 4.43 | 9.71 | 159.27 | 6.75× | 1,993.6 | 1,119 | 97.2 | 68% | 0 (0.00%) |

### `cpu`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `go-nethttp` | 14,241 | 1.24 | 18.82 | 30.72 | 47.64 | 82.21 | 24.77× | 40.7 | 8 | 495.2 | 70% | 0 (0.00%) |
| `go-nethttp-nogc` | 12,983 | 3.58 | 12.40 | 25.38 | 91.17 | 157.51 | 7.09× | 2,317.8 | 7,377 | 453.2 | 57% | 0 (0.00%) |

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

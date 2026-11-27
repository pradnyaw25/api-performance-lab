# API Performance Lab — results `20261126-215740`

*2026-11-27T02:57:40+00:00* · Apple M5 (10 cores) · macOS-26.5-arm64-arm-64bit-Mach-O  
Load: oha 1.17.0, concurrency **64**, **10 s** per scenario after **3 s** warm-up. Load generator and services share the machine; read the numbers as relative.

## Implementations

| Implementation | Toolchain | Contract | LOC | Build (s) | Artifact | Startup (s) | Idle RSS (MB) |
|---|---|---|---:|---:|---:|---:|---:|
| `rust-axum` | rustc 1.98.0 (88d9e12ae 2026-08-18) | pass | 177 | – | – | 0.01 | 9.9 |
| `go-nethttp` | go version go1.27.4 darwin/arm64 | pass | 182 | – | – | 0.11 | 13.5 |
| `python-fastapi` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | pass | 93 | – | – | 0.30 | 710.6 |
| `python-fastapi-1w` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | pass | 93 | – | – | 0.21 | 65.9 |

## Throughput (requests/s)

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 190,358 | 171,232 | 89,421 | 31,337 |
| get | 188,756 | 173,935 | 70,476 | 24,377 |
| list | 73,246 | 61,961 | 5,150 | 1,175 |
| create | 180,924 | 165,940 | 59,084 | 21,400 |
| cpu | 8,388 | 14,699 | 4,110 | 969 |
| io | 5,182 | 5,585 | 5,671 | 5,392 |
| mixed | 8,050 | 10,500 | 10,333 | 9,019 |

## Latency p99 (ms)

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 0.77 | 2.33 | 5.37 | 3.99 |
| get | 0.76 | 1.97 | 4.20 | 5.09 |
| list | 1.72 | 5.63 | 36.06 | 107.97 |
| create | 0.86 | 2.00 | 4.38 | 5.76 |
| cpu | 14.88 | 33.57 | 53.83 | 85.51 |
| io | 13.70 | 12.79 | 12.67 | 13.92 |
| mixed | 10.58 | 10.96 | 7.48 | 9.89 |

## Peak RSS during load (MB, whole process tree)

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 13.8 | 31.4 | 722.5 | 69.1 |
| get | 13.8 | 31.8 | 723.7 | 69.8 |
| list | 14.1 | 32.3 | 725.5 | 70.0 |
| create | 788.2 | 1,031.2 | 1,122.5 | 216.0 |
| cpu | 784.1 | 1,206.2 | 1,071.6 | 220.7 |
| io | 784.2 | 1,205.7 | 997.1 | 220.7 |
| mixed | 719.8 | 1,136.5 | 977.0 | 220.7 |

## CPU cost (server CPU-ms per request)

Lower is better: how much CPU each request actually consumed, independent of how saturated the machine was.

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 0.0204 | 0.0263 | 0.0787 | 0.0317 |
| get | 0.0208 | 0.0278 | 0.1016 | 0.0409 |
| list | 0.1092 | 0.1083 | 1.7028 | 0.8570 |
| create | 0.0231 | 0.0303 | 0.1221 | 0.0467 |
| cpu | 1.0937 | 0.6082 | 2.2510 | 1.0508 |
| io | 0.0305 | 0.0597 | 0.1308 | 0.0692 |
| mixed | 0.1281 | 0.1088 | 0.1140 | 0.0934 |

## Where Rust's advantage is, relative to each alternative

Throughput and CPU ratios > 1 mean Rust does better; p99 and RSS ratios > 1 mean the alternative is worse (Rust lower).

| Scenario | Metric | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---|---:|---:|---:|
| **health** | throughput | 1.11× | 2.13× | 6.07× |
|  | p99 latency | 3.03× | 6.99× | 5.19× |
|  | p99.9 latency | 3.17× | 7.87× | 4.11× |
|  | CPU/req | 1.29× | 3.86× | 1.55× |
|  | peak RSS | 2.28× | 52.50× | 5.02× |
| **get** | throughput | 1.09× | 2.68× | 7.74× |
|  | p99 latency | 2.59× | 5.51× | 6.68× |
|  | p99.9 latency | 3.43× | 6.02× | 4.29× |
|  | CPU/req | 1.34× | 4.88× | 1.97× |
|  | peak RSS | 2.30× | 52.46× | 5.06× |
| **list** | throughput | 1.18× | 14.22× | 62.33× |
|  | p99 latency | 3.27× | 20.93× | 62.66× |
|  | p99.9 latency | 3.07× | 19.94× | 390.09× |
|  | CPU/req | 0.99× | 15.59× | 7.85× |
|  | peak RSS | 2.29× | 51.43× | 4.96× |
| **create** | throughput | 1.09× | 3.06× | 8.45× |
|  | p99 latency | 2.34× | 5.12× | 6.73× |
|  | p99.9 latency | 3.56× | 5.93× | 2.98× |
|  | CPU/req | 1.31× | 5.29× | 2.02× |
|  | peak RSS | 1.31× | 1.42× | 0.27× |
| **cpu** | throughput | 0.57× | 2.04× | 8.65× |
|  | p99 latency | 2.26× | 3.62× | 5.75× |
|  | p99.9 latency | 1.86× | 3.31× | 11.55× |
|  | CPU/req | 0.56× | 2.06× | 0.96× |
|  | peak RSS | 1.54× | 1.37× | 0.28× |
| **io** | throughput | 0.93× | 0.91× | 0.96× |
|  | p99 latency | 0.93× | 0.93× | 1.02× |
|  | p99.9 latency | 0.73× | 0.70× | 2.96× |
|  | CPU/req | 1.96× | 4.29× | 2.27× |
|  | peak RSS | 1.54× | 1.27× | 0.28× |
| **mixed** | throughput | 0.77× | 0.78× | 0.89× |
|  | p99 latency | 1.04× | 0.71× | 0.94× |
|  | p99.9 latency | 1.81× | 0.74× | 3.16× |
|  | CPU/req | 0.85× | 0.89× | 0.73× |
|  | peak RSS | 1.58× | 1.36× | 0.31× |

## Per-scenario detail

### `health`

| Implementation | req/s | p50 | p90 | p99 | p99.9 | max | p99/p50 | peak RSS MB | CPU ms/req | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 190,358 | 0.32 | 0.44 | 0.77 | 1.62 | 13.15 | 2.42× | 13.8 | 0.0204 | 38% | 0 (0.00%) |
| `go-nethttp` | 171,232 | 0.26 | 0.66 | 2.33 | 5.14 | 71.70 | 9.00× | 31.4 | 0.0263 | 44% | 0 (0.00%) |
| `python-fastapi` | 89,421 | 0.44 | 1.40 | 5.37 | 12.78 | 43.10 | 12.33× | 722.5 | 0.0787 | 70% | 0 (0.00%) |
| `python-fastapi-1w` | 31,337 | 1.96 | 2.12 | 3.99 | 6.67 | 65.98 | 2.03× | 69.1 | 0.0317 | 10% | 0 (0.00%) |

### `get`

| Implementation | req/s | p50 | p90 | p99 | p99.9 | max | p99/p50 | peak RSS MB | CPU ms/req | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 188,756 | 0.32 | 0.44 | 0.76 | 1.50 | 22.16 | 2.37× | 13.8 | 0.0208 | 38% | 0 (0.00%) |
| `go-nethttp` | 173,935 | 0.28 | 0.61 | 1.97 | 5.14 | 40.62 | 7.14× | 31.8 | 0.0278 | 48% | 0 (0.00%) |
| `python-fastapi` | 70,476 | 0.61 | 1.72 | 4.20 | 9.04 | 133.59 | 6.87× | 723.7 | 0.1016 | 71% | 0 (0.00%) |
| `python-fastapi-1w` | 24,377 | 2.55 | 2.71 | 5.09 | 6.43 | 83.76 | 2.00× | 69.8 | 0.0409 | 10% | 0 (0.00%) |

### `list`

| Implementation | req/s | p50 | p90 | p99 | p99.9 | max | p99/p50 | peak RSS MB | CPU ms/req | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 73,246 | 0.86 | 1.27 | 1.72 | 3.16 | 47.79 | 2.00× | 14.1 | 0.1092 | 79% | 0 (0.00%) |
| `go-nethttp` | 61,961 | 0.69 | 2.22 | 5.63 | 9.70 | 27.60 | 8.13× | 32.3 | 0.1083 | 67% | 0 (0.00%) |
| `python-fastapi` | 5,150 | 9.66 | 25.78 | 36.06 | 63.09 | 75.75 | 3.73× | 725.5 | 1.7028 | 87% | 0 (0.00%) |
| `python-fastapi-1w` | 1,175 | 53.42 | 55.16 | 107.97 | 1,233.85 | 1,772.69 | 2.02× | 70.0 | 0.8570 | 10% | 0 (0.00%) |

### `create`

| Implementation | req/s | p50 | p90 | p99 | p99.9 | max | p99/p50 | peak RSS MB | CPU ms/req | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 180,924 | 0.33 | 0.48 | 0.86 | 2.17 | 64.29 | 2.60× | 788.2 | 0.0231 | 41% | 0 (0.00%) |
| `go-nethttp` | 165,940 | 0.29 | 0.62 | 2.00 | 7.74 | 142.48 | 6.99× | 1,031.2 | 0.0303 | 49% | 0 (0.00%) |
| `python-fastapi` | 59,084 | 0.92 | 2.07 | 4.38 | 12.89 | 152.52 | 4.78× | 1,122.5 | 0.1221 | 72% | 0 (0.00%) |
| `python-fastapi-1w` | 21,400 | 2.93 | 3.10 | 5.76 | 6.48 | 91.02 | 1.97× | 216.0 | 0.0467 | 10% | 0 (0.00%) |

### `cpu`

| Implementation | req/s | p50 | p90 | p99 | p99.9 | max | p99/p50 | peak RSS MB | CPU ms/req | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 8,388 | 7.50 | 11.16 | 14.88 | 32.03 | 94.93 | 1.98× | 784.1 | 1.0937 | 92% | 0 (0.00%) |
| `go-nethttp` | 14,699 | 2.42 | 9.53 | 33.57 | 59.64 | 132.94 | 13.86× | 1,206.2 | 0.6082 | 89% | 0 (0.00%) |
| `python-fastapi` | 4,110 | 12.41 | 31.54 | 53.83 | 106.17 | 142.55 | 4.34× | 1,071.6 | 2.2510 | 92% | 0 (0.00%) |
| `python-fastapi-1w` | 969 | 65.71 | 67.00 | 85.51 | 369.97 | 496.48 | 1.30× | 220.7 | 1.0508 | 10% | 0 (0.00%) |

### `io`

| Implementation | req/s | p50 | p90 | p99 | p99.9 | max | p99/p50 | peak RSS MB | CPU ms/req | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 5,182 | 12.37 | 13.04 | 13.70 | 18.78 | 19.57 | 1.11× | 784.2 | 0.0305 | 2% | 0 (0.00%) |
| `go-nethttp` | 5,585 | 11.43 | 12.06 | 12.79 | 13.80 | 14.53 | 1.12× | 1,205.7 | 0.0597 | 3% | 0 (0.00%) |
| `python-fastapi` | 5,671 | 11.27 | 12.05 | 12.67 | 13.07 | 14.85 | 1.12× | 997.1 | 0.1308 | 7% | 0 (0.00%) |
| `python-fastapi-1w` | 5,392 | 11.72 | 12.46 | 13.92 | 55.54 | 63.25 | 1.19× | 220.7 | 0.0692 | 4% | 0 (0.00%) |

### `mixed`

| Implementation | req/s | p50 | p90 | p99 | p99.9 | max | p99/p50 | peak RSS MB | CPU ms/req | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 8,050 | 7.83 | 9.61 | 10.58 | 11.75 | 12.54 | 1.35× | 719.8 | 0.1281 | 10% | 0 (0.00%) |
| `go-nethttp` | 10,500 | 5.93 | 6.80 | 10.96 | 21.30 | 22.20 | 1.85× | 1,136.5 | 0.1088 | 11% | 0 (0.00%) |
| `python-fastapi` | 10,333 | 6.14 | 7.12 | 7.48 | 8.67 | 12.53 | 1.22× | 977.0 | 0.1140 | 12% | 0 (0.00%) |
| `python-fastapi-1w` | 9,019 | 7.00 | 7.37 | 9.89 | 37.17 | 40.27 | 1.41× | 220.7 | 0.0934 | 8% | 0 (0.00%) |

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
- **CPU ms/req** is the cost side of throughput. Two implementations with equal req/s but 3× different CPU/req do not have equal performance; one has 3× the headroom.
- **CPU util** is server CPU over all cores. Near 100% means the service was the bottleneck; well below means the load generator or the scenario's I/O wait was.
- `io` and `mixed` are latency-bound by design: with concurrency *c* and wait *w*, throughput cannot exceed *c / w*. Converging numbers there are the expected result, and the interesting columns are RSS and tail latency.
- The Python rows are the same code; `python-fastapi` runs one Uvicorn worker per core, `python-fastapi-1w` runs one. The gap between them is the cost of the GIL; the gap between `python-fastapi` and Go is the cost of multi-process vs. multi-thread.

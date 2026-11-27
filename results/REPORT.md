# API Performance Lab — results `aggregate of 4 runs`

*2026-11-27T03:12:19+00:00* · Apple M5 (10 cores) · macOS-26.5-arm64-arm-64bit-Mach-O  
**Median of 4 runs** (`20261126-221219`, `20261126-222824`, `20261126-223757`, `20261126-224731`); throughput and p99 tables show min–max across runs.  
Load: oha 1.17.0, concurrency **64**, **10 s** per scenario after **3 s** warm-up, fresh process per scenario. Load generator and services share the machine; read the numbers as relative.

## Implementations and implementation complexity

LOC is non-blank, non-comment lines for the identical contract. Deps is every third-party package shipped (transitive). Cold start is process launch to first `200` from `/health`, median of 5 starts.

| Implementation | Toolchain | Contract | LOC | Deps | Build (s) | Artifact (MB) | Cold start ms (min–max) | Idle RSS (MB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | rustc 1.98.0 | pass | 177 | 93 | 13.7 (cold) | 1.3 | 10 (9–177) | 9.9 |
| `go-nethttp` | go1.27.4 | pass | 182 | 0 | 3.2 (cold) | 9.3 | 13 (11–271) | 13.4 |
| `python-fastapi` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | pass | 93 | 21 | – | – | 416 (332–458) | 710.7 |
| `python-fastapi-1w` | Python 3.14.6, FastAPI 0.165.0, Uvicorn 0.54.0 | pass | 93 | 21 | – | – | 173 (146–203) | 66.0 |

## Throughput (requests/s)

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 164,679 <sub>(140,094–187,430)</sub> | 166,922 <sub>(146,876–172,913)</sub> | 74,144 <sub>(67,349–86,031)</sub> | 31,620 <sub>(29,207–34,787)</sub> |
| get | 163,587 <sub>(138,742–186,485)</sub> | 166,172 <sub>(142,837–168,017)</sub> | 73,448 <sub>(62,437–80,664)</sub> | 28,809 <sub>(27,152–30,804)</sub> |
| list | 60,248 <sub>(49,643–68,250)</sub> | 54,065 <sub>(48,906–56,720)</sub> | 37,508 <sub>(34,371–42,376)</sub> | 14,943 <sub>(13,164–15,461)</sub> |
| create | 160,374 <sub>(135,309–180,464)</sub> | 140,492 <sub>(124,894–148,023)</sub> | 49,180 <sub>(35,244–55,025)</sub> | 19,738 <sub>(18,161–21,005)</sub> |
| cpu | 20,468 <sub>(19,246–23,733)</sub> | 10,975 <sub>(10,012–12,249)</sub> | 3,135 <sub>(2,220–3,448)</sub> | 927 <sub>(872–981)</sub> |
| io | 5,192 <sub>(5,176–5,226)</sub> | 5,598 <sub>(5,553–5,617)</sub> | 5,662 <sub>(5,318–5,757)</sub> | 5,445 <sub>(4,930–5,455)</sub> |
| mixed | 8,641 <sub>(8,583–8,769)</sub> | 10,940 <sub>(10,857–11,027)</sub> | 10,174 <sub>(9,966–10,361)</sub> | 9,880 <sub>(8,680–9,942)</sub> |

## Latency: p50 / p95 / p99 (ms)

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 0.35 / 0.59 / 1.02 <sub>(0.65–2.05)</sub> | 0.29 / 0.93 / 2.01 <sub>(1.92–2.18)</sub> | 0.56 / 2.50 / 5.97 <sub>(4.19–6.74)</sub> | 1.97 / 2.19 / 3.93 <sub>(3.58–4.28)</sub> |
| get | 0.36 / 0.58 / 0.91 <sub>(0.71–2.04)</sub> | 0.30 / 0.89 / 1.98 <sub>(1.83–2.23)</sub> | 0.62 / 2.36 / 5.30 <sub>(4.29–6.10)</sub> | 2.18 / 2.39 / 4.35 <sub>(4.01–4.55)</sub> |
| list | 1.05 / 1.76 / 2.34 <sub>(1.84–2.82)</sub> | 0.81 / 3.64 / 6.17 <sub>(5.84–6.67)</sub> | 1.33 / 4.39 / 8.00 <sub>(5.61–9.49)</sub> | 4.22 / 4.54 / 8.29 <sub>(7.94–10.52)</sub> |
| create | 0.36 / 0.59 / 0.83 <sub>(0.76–1.93)</sub> | 0.39 / 0.91 / 2.13 <sub>(1.80–2.77)</sub> | 0.98 / 3.53 / 6.23 <sub>(4.45–8.20)</sub> | 3.13 / 3.57 / 6.29 <sub>(5.90–6.78)</sub> |
| cpu | 3.06 / 5.13 / 6.16 <sub>(5.54–6.78)</sub> | 1.60 / 23.70 / 38.16 <sub>(33.89–39.70)</sub> | 19.25 / 41.15 / 53.84 <sub>(50.80–79.74)</sub> | 68.56 / 72.70 / 78.66 <sub>(67.58–110.33)</sub> |
| io | 12.35 / 13.22 / 13.60 <sub>(13.43–14.06)</sub> | 11.39 / 12.19 / 12.70 <sub>(12.50–12.93)</sub> | 11.31 / 12.26 / 12.79 <sub>(12.01–14.00)</sub> | 11.75 / 12.90 / 14.58 <sub>(13.48–15.65)</sub> |
| mixed | 7.44 / 8.66 / 9.20 <sub>(9.12–9.48)</sub> | 5.72 / 7.00 / 7.81 <sub>(7.62–8.07)</sub> | 6.22 / 7.61 / 8.07 <sub>(7.88–8.38)</sub> | 6.40 / 7.21 / 8.20 <sub>(7.91–11.14)</sub> |

## Peak RSS during load (MB, whole process tree)

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 13.2 | 30.0 | 722.2 | 69.2 |
| get | 13.4 | 29.8 | 719.3 | 67.6 |
| list | 15.2 | 30.2 | 716.7 | 67.7 |
| create | 824.9 | 777.3 | 987.1 | 202.8 |
| cpu | 13.3 | 40.1 | 732.5 | 71.0 |
| io | 13.2 | 26.5 | 719.5 | 67.8 |
| mixed | 13.6 | 27.3 | 720.5 | 67.9 |

## CPU per 1,000 requests (server CPU-ms)

Lower is better: compute each request actually consumed, independent of how saturated the machine was. Two implementations with equal req/s but 3× different CPU/1k do not have equal performance; one has 3× the headroom.

| Scenario | `rust-axum` | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---:|---:|---:|---:|
| health | 21.1 | 28.7 | 83.0 | 31.6 |
| get | 21.6 | 29.4 | 96.4 | 34.7 |
| list | 127.3 | 122.9 | 186.4 | 66.9 |
| create | 24.2 | 35.9 | 143.5 | 50.6 |
| cpu | 418.3 | 650.2 | 3,025.5 | 1,101.3 |
| io | 30.9 | 64.2 | 109.7 | 64.0 |
| mixed | 71.6 | 102.8 | 117.2 | 83.5 |

## Error rate under saturation

Concurrency far above the normal runs, with a per-request timeout; every timeout, refused or reset connection and non-2xx counts as an error. macOS `kern.ipc.somaxconn` here is 128, so connection bursts above that queue in the kernel for every implementation alike.

### `sat-get` — `/items/42` at concurrency 1000, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 179,798 | 4.82 | 22.37 | 219.95 | **0.00%** | 0 | 66.7 | – |
| `go-nethttp` | 162,995 | 4.10 | 29.61 | 154.57 | **0.00%** | 0 | 61.1 | – |
| `python-fastapi` | 61,250 | 14.24 | 55.68 | 365.79 | **0.00%** | 0 | 732.9 | – |
| `python-fastapi-1w` | 27,608 | 11.05 | 15.93 | 998.72 | **2.31%** | 6294 | 75.3 | timeout: 6294 |

### `sat-cpu` — `/compute/hash?n=20000` at concurrency 500, timeout 1 s

| Implementation | req/s | p50 | p99 | max (ms) | Error rate | Errors | Peak RSS MB | Error kinds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 7,737 | 59.28 | 173.68 | 271.53 | **0.00%** | 0 | 30.7 | – |
| `go-nethttp` | 3,947 | 69.13 | 706.83 | 995.65 | **0.21%** | 83 | 69.7 | timeout: 83 |
| `python-fastapi` | 901 | 519.98 | 968.29 | 1,000.10 | **7.95%** | 624 | 762.4 | timeout: 624 |
| `python-fastapi-1w` | 662 | 290.56 | 405.54 | 968.28 | **63.30%** | 3888 | 71.5 | timeout: 3888 |

## Memory per open connection

1000 keep-alive connections opened, one request each, then held idle for 1 s. Per-connection cost is what bounds long-lived streaming/WebSocket/SSE fan-out.

| Implementation | Opened | Failed | Idle RSS MB | Held RSS MB | KB / connection | After close MB |
|---|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 1000 | 0 | 9.9 | 42.3 | **31.6** | 42.4 |
| `go-nethttp` | 1000 | 0 | 13.4 | 36.8 | **22.9** | 37.2 |
| `python-fastapi` | 1000 | 0 | 710.6 | 729.4 | **18.5** | 729.4 |
| `python-fastapi-1w` | 1000 | 0 | 66.0 | 78.0 | **11.8** | 77.6 |

## Recovery after a load spike

Probe: sequential keep-alive requests to `/items/42` from one client. Spike: `/items?limit=200` at concurrency 256 for 5 s. Then probe again immediately and after 10 s idle. *Retained* is how much of the spike's RSS growth was still held after settling: it shows whether the runtime gives memory back to the OS.

| Implementation | Spike req/s | Idle MB | Peak MB | +0 s MB | +10 s MB | Retained | Probe before p50/p99 | Probe +0 s | Probe +10 s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 67,961 | 9.9 | 22.9 | 22.9 | 20.1 | **79.2%** | 0.09 / 0.16 | 0.04 / 0.11 | 0.09 / 0.16 |
| `go-nethttp` | 62,789 | 13.5 | 36.2 | 36.2 | 35.5 | **97.5%** | 0.08 / 0.18 | 0.06 / 0.13 | 0.09 / 0.19 |
| `python-fastapi` | 43,128 | 710.8 | 722.2 | 722.2 | 721.8 | **100.0%** | 0.12 / 0.33 | 0.15 / 0.28 | 0.12 / 0.31 |
| `python-fastapi-1w` | 14,300 | 66.0 | 69.8 | 69.8 | 65.3 | **-16.9%** | 0.12 / 0.29 | 0.08 / 0.13 | 0.12 / 0.28 |

## Where Rust's advantage is, relative to each alternative

Every ratio is *alternative ÷ Rust* for cost metrics (latency, CPU, RSS) and *Rust ÷ alternative* for throughput, so **> 1 means Rust is better**, ≈ 1 means the language did not matter for that workload, and < 1 means the alternative won.

| Scenario | Metric | `go-nethttp` | `python-fastapi` | `python-fastapi-1w` |
|---|---|---:|---:|---:|
| **health** | throughput | 0.99× | 2.22× | 5.21× |
|  | p99 latency | 1.98× | 5.88× | 3.87× |
|  | CPU / 1k req | 1.36× | 3.93× | 1.50× |
|  | peak RSS | 2.28× | 54.79× | 5.25× |
| **get** | throughput | 0.98× | 2.23× | 5.68× |
|  | p99 latency | 2.17× | 5.82× | 4.77× |
|  | CPU / 1k req | 1.36× | 4.45× | 1.60× |
|  | peak RSS | 2.23× | 53.80× | 5.06× |
| **list** | throughput | 1.11× | 1.61× | 4.03× |
|  | p99 latency | 2.64× | 3.42× | 3.54× |
|  | CPU / 1k req | 0.97× | 1.46× | 0.53× |
|  | peak RSS | 1.99× | 47.24× | 4.46× |
| **create** | throughput | 1.14× | 3.26× | 8.13× |
|  | p99 latency | 2.56× | 7.47× | 7.54× |
|  | CPU / 1k req | 1.48× | 5.92× | 2.09× |
|  | peak RSS | 0.94× | 1.20× | 0.25× |
| **cpu** | throughput | 1.86× | 6.53× | 22.08× |
|  | p99 latency | 6.19× | 8.74× | 12.77× |
|  | CPU / 1k req | 1.55× | 7.23× | 2.63× |
|  | peak RSS | 3.01× | 54.96× | 5.33× |
| **io** | throughput | 0.93× | 0.92× | 0.95× |
|  | p99 latency | 0.93× | 0.94× | 1.07× |
|  | CPU / 1k req | 2.08× | 3.55× | 2.07× |
|  | peak RSS | 2.01× | 54.66× | 5.15× |
| **mixed** | throughput | 0.79× | 0.85× | 0.87× |
|  | p99 latency | 0.85× | 0.88× | 0.89× |
|  | CPU / 1k req | 1.44× | 1.64× | 1.17× |
|  | peak RSS | 2.01× | 52.88× | 4.98× |

## Per-scenario detail

### `health`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 164,679 | 0.35 | 0.59 | 1.02 | 2.97 | 33.90 | 2.88× | 13.2 | 0 | 21.1 | 34% | 0 (0.00%) |
| `go-nethttp` | 166,922 | 0.29 | 0.93 | 2.01 | 4.86 | 44.89 | 6.93× | 30.0 | 0 | 28.7 | 47% | 0 (0.00%) |
| `python-fastapi` | 74,144 | 0.56 | 2.50 | 5.97 | 15.15 | 130.09 | 10.66× | 722.2 | 1 | 83.0 | 63% | 0 (0.00%) |
| `python-fastapi-1w` | 31,620 | 1.97 | 2.19 | 3.93 | 5.48 | 64.71 | 1.99× | 69.2 | 2 | 31.6 | 10% | 0 (0.00%) |

### `get`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 163,587 | 0.36 | 0.58 | 0.91 | 2.44 | 33.95 | 2.56× | 13.4 | 0 | 21.6 | 36% | 0 (0.00%) |
| `go-nethttp` | 166,172 | 0.30 | 0.89 | 1.98 | 5.01 | 18.44 | 6.54× | 29.8 | 1 | 29.4 | 47% | 0 (0.00%) |
| `python-fastapi` | 73,448 | 0.62 | 2.36 | 5.30 | 10.75 | 131.90 | 8.52× | 719.3 | 2 | 96.4 | 70% | 0 (0.00%) |
| `python-fastapi-1w` | 28,809 | 2.18 | 2.39 | 4.35 | 4.70 | 71.63 | 1.99× | 67.6 | 2 | 34.7 | 10% | 0 (0.00%) |

### `list`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 60,248 | 1.05 | 1.76 | 2.34 | 4.60 | 38.51 | 2.23× | 15.2 | 0 | 127.3 | 74% | 0 (0.00%) |
| `go-nethttp` | 54,065 | 0.81 | 3.64 | 6.17 | 10.12 | 20.84 | 7.63× | 30.2 | 3 | 122.9 | 66% | 0 (0.00%) |
| `python-fastapi` | 37,508 | 1.33 | 4.39 | 8.00 | 17.62 | 133.16 | 6.00× | 716.7 | 9 | 186.4 | 72% | 0 (0.00%) |
| `python-fastapi-1w` | 14,943 | 4.22 | 4.54 | 8.29 | 9.02 | 138.96 | 1.97× | 67.7 | 4 | 66.9 | 10% | 0 (0.00%) |

### `create`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 160,374 | 0.36 | 0.59 | 0.83 | 1.82 | 64.39 | 2.32× | 824.9 | 346 | 24.2 | 40% | 0 (0.00%) |
| `go-nethttp` | 140,492 | 0.39 | 0.91 | 2.13 | 8.14 | 98.68 | 5.54× | 777.3 | 397 | 35.9 | 48% | 0 (0.00%) |
| `python-fastapi` | 49,180 | 0.98 | 3.53 | 6.23 | 12.05 | 147.75 | 6.38× | 987.1 | 486 | 143.5 | 69% | 0 (0.00%) |
| `python-fastapi-1w` | 19,738 | 3.13 | 3.57 | 6.29 | 9.43 | 97.65 | 2.01× | 202.8 | 520 | 50.6 | 10% | 0 (0.00%) |

### `cpu`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 20,468 | 3.06 | 5.13 | 6.16 | 8.78 | 35.68 | 2.01× | 13.3 | 1 | 418.3 | 88% | 0 (0.00%) |
| `go-nethttp` | 10,975 | 1.60 | 23.70 | 38.16 | 58.11 | 96.13 | 23.81× | 40.1 | 18 | 650.2 | 72% | 0 (0.00%) |
| `python-fastapi` | 3,135 | 19.25 | 41.15 | 53.84 | 74.22 | 118.64 | 2.80× | 732.5 | 76 | 3,025.5 | 91% | 0 (0.00%) |
| `python-fastapi-1w` | 927 | 68.56 | 72.70 | 78.66 | 309.20 | 423.96 | 1.15× | 71.0 | 56 | 1,101.3 | 10% | 0 (0.00%) |

### `io`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 5,192 | 12.35 | 13.22 | 13.60 | 16.59 | 18.49 | 1.10× | 13.2 | 2 | 30.9 | 2% | 0 (0.00%) |
| `go-nethttp` | 5,598 | 11.39 | 12.19 | 12.70 | 15.53 | 16.18 | 1.11× | 26.5 | 16 | 64.2 | 4% | 0 (0.00%) |
| `python-fastapi` | 5,662 | 11.31 | 12.26 | 12.79 | 14.38 | 16.17 | 1.13× | 719.5 | 53 | 109.7 | 6% | 0 (0.00%) |
| `python-fastapi-1w` | 5,445 | 11.75 | 12.90 | 14.58 | 22.26 | 25.37 | 1.24× | 67.8 | 0 | 64.0 | 3% | 0 (0.00%) |

### `mixed`

| Implementation | req/s | p50 | p95 | p99 | p99.9 | max | p99/p50 | peak RSS MB | ΔRSS/req B | CPU ms/1k | CPU util | errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rust-axum` | 8,641 | 7.44 | 8.66 | 9.20 | 10.00 | 11.06 | 1.24× | 13.6 | 3 | 71.6 | 6% | 0 (0.00%) |
| `go-nethttp` | 10,940 | 5.72 | 7.00 | 7.81 | 9.42 | 17.43 | 1.37× | 27.3 | 7 | 102.8 | 11% | 0 (0.00%) |
| `python-fastapi` | 10,174 | 6.22 | 7.61 | 8.07 | 8.87 | 12.53 | 1.30× | 720.5 | 23 | 117.2 | 12% | 0 (0.00%) |
| `python-fastapi-1w` | 9,880 | 6.40 | 7.21 | 8.20 | 15.35 | 24.97 | 1.28× | 67.9 | 2 | 83.5 | 8% | 0 (0.00%) |

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

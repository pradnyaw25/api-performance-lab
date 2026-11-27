# API Performance Lab

A comparative engineering study of **Rust**, **Go** and **Python** for
high-performance API services.

The question is not "is Rust faster than Python?" (it is). The question is
**where does the difference actually matter for an API service, by how much,
and what does it cost to get it?**

## Study design

The same HTTP service is implemented three times with each ecosystem's
production-grade stack:

| Implementation      | Stack                                            | Dir                        |
|---------------------|--------------------------------------------------|----------------------------|
| `rust-axum`         | Rust, Axum 0.8 on Tokio, serde_json              | `services/rust-axum`       |
| `go-nethttp`        | Go, standard library `net/http` (1.22+ routing)  | `services/go-nethttp`      |
| `python-fastapi`    | Python 3, FastAPI + Uvicorn (uvloop/httptools), orjson, N workers | `services/python-fastapi` |
| `python-fastapi-1w` | Same code, a single Uvicorn worker               | (same)                     |

Every implementation serves the identical contract in [`docs/API.md`](docs/API.md),
verified by one shared contract test (`tests/contract_test.py`) that runs
against all of them. If the contract test does not pass, the benchmark numbers
are not comparable and the harness refuses to run.

### Workload dimensions

Each endpoint isolates one thing an API service spends time on, so the
results tell you *which kind* of work benefits from which runtime:

| Scenario   | Endpoint                 | What it isolates                                   |
|------------|--------------------------|----------------------------------------------------|
| `health`   | `GET /health`            | Framework + HTTP stack floor                       |
| `get`      | `GET /items/{id}`        | Routing, shared-state read, small JSON encode      |
| `list`     | `GET /items?limit=200`   | Large JSON serialization (200 objects)             |
| `create`   | `POST /items`            | JSON decode, validation, write under a lock        |
| `cpu`      | `GET /compute/hash?n=`   | Pure CPU work (chained SHA-256), no I/O            |
| `io`       | `GET /io/wait?ms=10`     | Pure I/O wait, concurrency handling, no CPU        |
| `mixed`    | `GET /mixed`             | Realistic request: 5 ms "DB" wait + small CPU + JSON |

### What we measure

| Metric | Why it matters | How the harness measures it |
|---|---|---|
| Requests per second | Maximum sustainable throughput | `oha` at fixed concurrency for a fixed window, after warm-up, fresh process per scenario |
| p50 / p95 / p99 latency | Predictability under load | `oha` latency percentiles; p99.9 and max in the detail tables; p99/p50 as the tail-flatness ratio |
| Peak memory (RSS) | Infrastructure footprint | Process-tree RSS sampled 4×/s during each run (summed over workers, which is what multi-worker Python actually costs) |
| CPU per 1,000 requests | Compute efficiency | Process-tree CPU time delta across the run ÷ completed requests. Equal req/s at 3× the CPU is 3× less headroom |
| Cold start time | Autoscaling performance | Process launch → first `200` from `/health`, polled every 2 ms, median of 5 starts |
| Error rate under saturation | Resilience | Dedicated runs at 1000 and 500 concurrency with a 1 s per-request timeout; timeouts, resets, refused connections and non-2xx all count |
| Memory per open connection | Streaming scalability | 1000 keep-alive connections opened and held idle; (RSS held − RSS idle) ÷ connections |
| Recovery after load spikes | Runtime behaviour | Probe latency → 5 s spike at 256 concurrency → probe again → 10 s idle → probe again; how much of the spike's RSS is retained (does the runtime return memory to the OS) |
| Implementation complexity | Developer productivity | Lines of code for the identical contract, transitive dependency count, cold build time, artifact size, and behaviour that differs despite the shared contract |

### Hypotheses (written before running anything)

1. **CPU-bound work** (`cpu`): Rust and Go are an order of magnitude ahead of
   Python; Rust leads Go by a smaller, constant factor. Multi-worker Python
   scales linearly with cores but never closes the gap.
2. **I/O-bound work** (`io`): all three are limited by the sleep, not the
   runtime. Throughput converges; the differences are in memory and tail
   latency, not in requests/second. This is where "Python is slow" is least
   true.
3. **Serialization** (`list`): Rust > Go > Python, but orjson narrows the
   Python gap much more than people expect.
4. **Tail latency** (`get`, `mixed`): Rust has the flattest p99/p50 ratio (no
   GC pauses, no GIL). Go's p99.9 shows GC. Python's p99 degrades fastest
   under rising concurrency.
5. **Memory**: Rust < Go << Python×N workers. The ratio, not the absolute
   numbers, is what matters for density.
6. **Engineering cost**: Rust costs the most lines and the longest build; the
   question is whether the runtime advantages above pay for that in a given
   service.

The point of writing hypotheses first is to find out which ones are wrong.

## Quick start

Prerequisites: Rust toolchain, Go 1.22+, Python 3.11+, [`oha`](https://github.com/hatoo/oha)
(`brew install go oha`).

```bash
make setup      # python venv + deps
make build      # release builds for rust and go
make contract   # start each service, run the shared contract test, stop it
make bench      # full benchmark -> results/REPORT.md (~12 min)
```

`bench/run.py --clean` cleans before building so the build-time column is a
cold build. `--skip saturation`, `--skip recovery`, `--skip connections`,
`--skip coldstart` and `--impl`/`--scenario` narrow a run.

Tune the run in `bench/config.json` (duration, concurrency, which scenarios,
which implementations). Results land in `results/` as raw oha JSON per run plus
a rendered `REPORT.md`.

## Methodology notes and known limits

- Load generator and services run on the same machine. This understates
  absolute numbers for every implementation equally, but it means the load
  generator competes for CPU with the service. Treat results as *relative*.
- Each scenario gets a warm-up before measurement.
- Python runs with `workers = CPU count`; that is the production deployment
  model, and the single-worker row is kept so the scaling cost is visible.
- The in-memory store deliberately replaces a database. Phase 2 is the same
  contract backed by PostgreSQL, where driver and connection-pool quality
  starts to dominate and the language gap narrows again.
- The CPU endpoint runs inline on the request path in every implementation.
  That is a realistic default, and it is what makes the Python GIL visible.
- **Multi-worker Python has no shared memory.** Each Uvicorn worker is a
  separate process with its own copy of the in-memory store, so an item
  created on one worker is a 404 on the other nine. The contract test records
  this (`--process-local-state`) instead of failing, because it is one of the
  study's findings: Python's route to using all cores costs you shared state,
  and a real deployment pays for that with Redis or a database round-trip that
  Rust and Go do not need for the same feature.

## Layout

```
docs/API.md                 the contract all three implement
services/rust-axum/         Rust implementation
services/go-nethttp/        Go implementation
services/python-fastapi/    Python implementation
tests/contract_test.py      shared behavioural test (stdlib only)
bench/config.json           scenarios, concurrency, duration, implementations
bench/run.py                orchestrator: build, start, warm, measure, stop
bench/report.py             renders results/REPORT.md from results/summary.json
results/                    raw and rendered results (one subdir per run)
```

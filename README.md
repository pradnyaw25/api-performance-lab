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

## Results (medians of 4 runs, Apple M5, 10 cores, macOS)

Full tables with min–max spread per cell: [`results/aggregate/REPORT.md`](results/aggregate/REPORT.md)
(also copied to [`results/REPORT.md`](results/REPORT.md)). The four runs are
`20261126-221219`, `222824`, `223757` and `224731`. The untuned baseline that
preceded them is kept in [`results/20261126-215740/`](results/20261126-215740/REPORT.md)
because the difference between it and the final numbers is itself a result.
Publication drafts and charts built from the aggregate are in [`content/`](content/).

### Hypotheses, scored

| # | Hypothesis | Verdict |
|---|---|---|
| 1 | CPU-bound: Rust and Go an order of magnitude ahead of Python; Rust leads Go by a small constant | **Mostly right, with a twist.** Rust 20.5k req/s, Go 11.0k, Python×10 3.1k, Python×1 927. Rust leads Go by **1.9×**, not a small constant, but only after enabling the `sha2` crate's `asm` feature. With the crate's default software SHA-256, Rust was **slower than Go** (8.4k vs 14.7k in the baseline) because Go's standard library uses the ARM SHA-2 instructions out of the box. The language sets the ceiling; the library decides whether you reach it. |
| 2 | I/O-bound: all three converge; differences are memory and tail, not req/s | **Confirmed, and Rust was the slowest.** `io` throughput spans 5.2k–5.7k req/s (9%); p99 spans 12.7–14.6 ms. Rust is last because Tokio's `sleep(10 ms)` completes in 12.3 ms even at concurrency 1 on this macOS build, while Go and uvloop sleep 11.3 ms. What Rust wins while waiting is cost: **31 ms CPU per 1k requests vs 64 (Go) and 110 (Python×10)**, at 13 MB vs 27 MB vs 720 MB. |
| 3 | Serialization: Rust > Go > Python, but orjson narrows the gap more than expected | **Confirmed, dramatically.** Baseline Python `list` was **14× slower** than Rust and burned 1.7 ms CPU per request. Returning `ORJSONResponse` directly, so FastAPI skips its pure-Python `jsonable_encoder` pass, took that to **1.6×** (60.2k vs 37.5k req/s). Rust over Go on serialization: 1.1×. Serialization alone is not a reason to choose Rust; knowing your framework's hot path is worth 7× in Python. |
| 4 | Tail latency: Rust flattest p99/p50; Go's tail shows GC; Python degrades fastest | **Confirmed.** On `get`, p99/p50 is **2.6× Rust, 6.5× Go, 8.5× Python×10**. Absolute p99: 0.91 / 1.98 / 5.30 ms (Rust's ranged 0.71–2.04 ms across runs; the comparison holds at its worst run). Under CPU saturation Go's p99/p50 reaches **24×** while Rust stays at 2×. Go's p95 is where its GC and scheduler become visible. |
| 5 | Memory: Rust < Go << Python×N; the ratio matters for density | **Confirmed at the baseline, wrong per connection.** Idle RSS: **9.9 MB Rust, 13.4 MB Go, 66 MB Python×1, 711 MB Python×10** (72× Rust). Per *idle connection* the order inverts: **Rust 31.6 KB, Go 22.9 KB, Python 18.5 KB**; hyper's per-connection buffers are the largest of the three. At 100k connections that is 3.2 GB vs 2.3 GB vs 1.9 GB, so the fixed cost, not the per-connection cost, is the story. |
| 6 | Engineering cost: Rust costs the most lines and the longest build | **Half right.** LOC: **Rust 177, Go 182, Python 93**. Rust ships **93 transitive crates**; Go **0**; Python 21 packages. Cold build 13.7 s Rust (LTO) vs 3.2 s Go. Cold start **10 ms Rust, 13 ms Go, 173 ms Python×1, 416 ms Python×10**. Rust and Go cost the same lines; Rust's cost is the dependency graph and the build. |

### Findings that were not hypotheses

- **On ordinary endpoints, Go ties Rust on throughput.** Across four runs the
  lookup medians are 166k (Go) vs 164k (Rust) req/s, within 10% on `list` and
  `create`. Rust's throughput on those endpoints swung 139k–186k run to run
  (laptop noise), which is why everything here is a median with its range in
  the report. Rust's edge over Go is in p99 (2.2×), CPU per request (1.4×) and
  memory (2.2×), not in requests per second.
- **Multi-worker Python has no shared memory.** The contract test found that
  an item created on one Uvicorn worker is a 404 on the other nine (1 hit in
  10). Python's only route to all ten cores is ten processes, which means ten
  copies of every in-memory structure (711 MB idle for a 10k-item seed) and no
  shared state without Redis or a database round-trip that Rust and Go do not
  need for the same feature. Ten workers gave 3.4× one worker on CPU-bound
  work, not 10×.
- **Graceful degradation under CPU overload is where Rust is most clearly
  ahead.** `sat-cpu` (500 concurrent, 20k hash rounds, 1 s timeout):
  **Rust 0 timeouts in every run, p99 174 ms; Go 0.21%, p99 707 ms; Python×10
  7.95% at the median (0.45–21.5% run to run), p99 968 ms; Python×1 63%.** Go's
  median (69 ms) is close to Rust's (59 ms) while its p99 is 4× worse: its
  scheduler lets a tail of requests wait out the deadline, Tokio's work-stealing
  spreads the delay evenly. Under connection overload (`sat-get`, 1000
  concurrent) Rust, Go and Python×10 served every request; Python×1 timed out
  2.3%.
- **Nobody has a latency hangover; memory retention is too noisy to rank.**
  Probe p99 after a 5 s spike at 256 concurrency returned to the pre-spike
  level for all four in the first probe. Retained RSS after 10 s idle swung run
  to run by more than the differences between runtimes (medians: Rust 79%, Go
  98%, Python×10 100%, Python×1 below its starting point), so this harness
  cannot rank them on it. The growth was small in all cases (13 MB Rust, 23 MB
  Go, 11 MB Python×10).
- **Per-item storage cost** (`create`, RSS growth per inserted item): Rust 346 B,
  Go 397 B, Python×10 486 B, Python×1 520 B.
- **Python's per-request CPU is close to Go's; its scaling is the cost.**
  Single-worker Python spends 32 ms CPU per 1k `health` requests, Go 29, Rust
  21. At ten workers the same code costs 83 ms per 1k, because ten processes
  plus the load generator contend for ten cores.
- **Same contract, different error shapes.** A non-numeric path id is a 400
  with a plain-text message from Axum, a 400 JSON `{"error"}` we wrote in Go,
  and a 422 with a Pydantic error array from FastAPI. Go is the only one where
  every byte of the error surface is yours.

### So where does Rust give a meaningful advantage?

1. **CPU on the request path**: 1.9× Go, 6.5× Python×10, and the only one that
   met a 1 s deadline for every request under 500-way CPU overload, in every run.
2. **Tail latency at the floor**: sub-millisecond p99 where Go is 2× and
   Python 6×, and a p99/p50 that stays near 2–3× when the others widen to
   6–24×. If you have an SLO on p99 rather than on the median, Rust is the
   only one that is flat.
3. **Density**: 10–15 MB and 21 ms CPU per 1k requests, vs 27–40 MB / 29 ms
   for Go and 711 MB / 83 ms for Python×10. Across a fleet that is the bill.

And where it does not:

4. **Throughput on ordinary endpoints**: a tie with Go.
5. **I/O-bound endpoints** (`io`, `mixed`): throughput and p99 equal to or
   slightly behind Go and Python; the win is 2–3.5× less CPU *while waiting*.
6. **Serialization**: 1.1× Go, 1.6× tuned Python.
7. **Per-connection memory**: Rust is the heaviest of the three.

### Context

This experiment was inspired by Anthropic's
[Migrating our Messages API to Rust](https://www.anthropic.com/research/migrating-api-to-rust)
(25 Nov 2026), which reports about 70% less CPU per request and more than 80%
less memory per request after moving the Messages API from Python to Rust.
Those are production numbers from a very large service. This lab is one laptop,
synthetic endpoints and seconds of load: it is not production-level load and
does not predict what such a migration yields. What it can do is isolate where
the differences come from.

### Caveats

- One machine, load generator and service sharing 10 cores, 10 s windows.
  Four runs; medians with min–max in the report.
- macOS: `kern.ipc.somaxconn` is 128 and Tokio's timer behaviour differs from
  Linux. Production numbers would come from a Linux box with a separate load
  generator.
- In-memory store. Phase 2 is the same contract on PostgreSQL, where driver and
  pool quality start to dominate and the gaps narrow again.
- RSS is sampled from `ps` four times a second, so short spikes can be missed.

## Quick start

Prerequisites: Rust toolchain, Go 1.22+, Python 3.11+, [`oha`](https://github.com/hatoo/oha)
(`brew install go oha`).

```bash
make setup      # python venv + deps
make build      # release builds for rust and go
make contract   # start each service, run the shared contract test, stop it
make bench      # full benchmark -> results/REPORT.md (~12 min)
```

`bench/aggregate.py results/<a> results/<b> ... -o results/aggregate` folds
several runs into medians with spread; `bench/charts.py results/aggregate`
renders the PNG and GIF charts; `bench/fill_numbers.py results/aggregate`
fills the publication drafts in `content/templates/` with those numbers.
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

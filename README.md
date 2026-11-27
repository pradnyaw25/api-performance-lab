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

## Results (run `20261126-221219`, Apple M5, 10 cores, macOS)

Full tables: [`results/REPORT.md`](results/REPORT.md). The untuned baseline
that preceded it is kept in [`results/20261126-215740/`](results/20261126-215740/REPORT.md)
because the difference between the two runs is itself a result.

### Hypotheses, scored

| # | Hypothesis | Verdict |
|---|---|---|
| 1 | CPU-bound: Rust and Go an order of magnitude ahead of Python; Rust leads Go by a small constant | **Mostly right, with a twist.** Rust 23.7k req/s, Go 11.5k, Python×10 3.2k, Python×1 979. Rust leads Go by **2.07×**, not a small constant, but only after enabling the `sha2` crate's `asm` feature. With the crate's default software SHA-256, Rust was **slower than Go** (8.4k vs 14.7k in the baseline) because Go's standard library uses the ARM SHA-2 instructions out of the box. The language sets the ceiling; the library decides whether you reach it. |
| 2 | I/O-bound: all three converge; differences are memory and tail, not req/s | **Confirmed, and Rust was the slowest.** `io` throughput spans 5,207–5,653 req/s (8%); p99 spans 12.5–13.6 ms. Rust is last on both because Tokio's `sleep(10 ms)` completes in 12.3 ms even at concurrency 1 on this macOS build (timer-wheel slack), while Go and uvloop sleep 11.3 ms. What Rust wins while waiting is cost: **31 ms CPU per 1k requests vs 65 (Go) and 126 (Python×10)**, at 13 MB vs 27 MB vs 720 MB. |
| 3 | Serialization: Rust > Go > Python, but orjson narrows the gap more than expected | **Confirmed, dramatically.** Baseline Python `list` was **14× slower** than Rust and burned 1.7 ms CPU per request. Returning `ORJSONResponse` directly, so FastAPI skips its pure-Python `jsonable_encoder` pass, took that to **1.6×** (67.6k vs 42.4k req/s) and 1.5× the CPU. Rust over Go on serialization: 1.2×. Serialization alone is not a reason to choose Rust; knowing your framework's hot path is worth 8× in Python. |
| 4 | Tail latency: Rust flattest p99/p50; Go's tail shows GC; Python degrades fastest | **Confirmed.** On `get`, p99/p50 is **2.2× Rust, 6.1× Go, 10.9× Python×10**. Absolute p99: 0.71 / 1.83 / 5.87 ms. Under CPU saturation (`cpu`) Go's p99/p50 reaches **24×** (1.5 ms median, 37 ms p99) while Rust stays at 2.1× (2.6 → 5.5 ms). Go's p95 is where its GC and scheduler become visible. |
| 5 | Memory: Rust < Go << Python×N; the ratio matters for density | **Confirmed at the baseline, wrong per connection.** Idle RSS: **9.9 MB Rust, 13.5 MB Go, 66 MB Python×1, 710 MB Python×10**. Under load Rust holds 13–15 MB where Go holds 27–38 MB (2–2.8×) and Python×10 holds 720 MB (53×). But per *idle connection* the order inverts: **Rust 31.6 KB, Go 23.2 KB, Python 18.5 KB** (hyper's per-connection buffers are the largest of the three). For a 100k-connection streaming fan-out that is 3.2 GB vs 2.3 GB vs 1.9 GB, so none of them is the bottleneck; the fixed cost is. |
| 6 | Engineering cost: Rust costs the most lines and the longest build | **Half right.** LOC for the identical contract: **Rust 177, Go 182, Python 93**. Rust ships **93 transitive crates**; Go ships **0**; Python 21 packages. Cold build 13.7 s Rust vs 3.2 s Go (LTO on, small project; the gap widens with size). Artifact 1.3 MB vs 9.3 MB. Cold start **12 ms Rust, 12 ms Go, 170 ms Python×1, 417 ms Python×10**. Rust and Go cost the same lines; Rust's cost is the dependency graph and the build, Python's is the deployment model (next row). |

### Findings that were not hypotheses

- **Multi-worker Python does not share memory.** The contract test found that
  an item created on one Uvicorn worker is a 404 on the other nine (1 hit in
  10). Python's only route to all ten cores is ten processes, which means ten
  copies of every in-memory structure (710 MB idle for a 10k-item seed) and
  no shared state without Redis or a database round-trip that Rust and Go do
  not need for the same feature. This is the largest practical difference in
  the study and it is architectural, not a benchmark number.
- **Graceful degradation under CPU overload is where Rust is most clearly
  ahead.** `sat-cpu` (500 concurrent, 20k hash rounds, 1 s timeout):
  **Rust 0 timeouts, p99 145 ms; Go 0.2% timeouts, p99 698 ms; Python×10 2.1%,
  p99 956 ms; Python×1 62.7%.** Go's median (21 ms) beats Rust's (51 ms) while
  its p99 is 5× worse: under overload Go serves some requests fast and lets
  others wait out the deadline, Tokio's work-stealing spreads the pain evenly.
  Under connection overload (`sat-get`, 1000 concurrent) Rust, Go and
  Python×10 all served every request; single-worker Python timed out 2.1%.
- **Nobody has a latency hangover after a spike.** Probe p99 after a 5 s
  spike at 256 concurrency returned to the pre-spike level for all four in the
  first probe. Memory is a different story: Rust and Python retained **100%**
  of the spike's RSS growth after 10 s idle (allocators keep their pages), Go
  returned 28% (its scavenger ran). In absolute terms the growth was 13 MB
  Rust, 23 MB Go, 11 MB Python×10, so this matters for density, not for
  correctness.
- **Per-item storage cost** (`create`, RSS growth per inserted item): Rust
  292 B, Go 390 B, Python×10
  584 B, Python×1 506 B.
  Rust's `String` + `Vec<String>` per item is the leanest; Python's dict per
  item costs about 2.0×.
- **Python's per-request CPU is close to Go's; its scaling is the cost.**
  Single-worker Python spends 30 ms CPU per 1k `health` requests, Go 28, Rust
  21: uvloop, httptools and orjson are C, and the Python in the request path is
  thin. At ten workers the same code costs 78 ms per 1k, because ten processes
  plus the load generator contend for ten cores. The CPU-per-request columns
  for saturated runs include that contention for every implementation.
- **Same contract, different error shapes.** A non-numeric path id is a 400
  with a plain-text message from Axum, a 400 JSON `{"error"}` we wrote in Go,
  and a 422 with a Pydantic error array from FastAPI. Wrong field types: Axum
  422 (text), Go 400, FastAPI 422 (JSON). Go is the only one where every
  byte of the error surface is yours; the other two give you a framework's
  shape unless you override it.

### So where does Rust give a meaningful advantage?

1. **CPU on the request path**: 2× Go, 7× Python×10, and the only one that
   met a 1 s deadline for every request under 500-way CPU overload. If the
   service computes (hashing, compression, parsing, scoring), this is decisive.
2. **Tail latency at the floor**: sub-millisecond p99 where Go is 2–3× and
   Python 6–8×, and a p99/p50 that stays near 2× when the others widen to
   6–24×. If you have an SLO on p99 rather than on the median, Rust is the
   only one that is flat.
3. **Density**: 10–15 MB and 21 ms CPU per 1k requests, vs 27–38 MB / 28 ms
   for Go and 720 MB / 78 ms for Python×10. Across a fleet that is the bill.

And where it does not:

4. **I/O-bound endpoints** (`io`, `mixed`): throughput and p99 equal to or
   slightly behind Go and Python; the win is 2–4× less CPU *while waiting*. If
   the service is "call the database and return it", Rust buys you cost, not
   speed.
5. **Serialization**: 1.2× Go, 1.6× tuned Python.
6. **Per-connection memory**: Rust is the heaviest of the three.

Go reaches within 10–25% of Rust on everything except CPU-bound work and tail
latency, with zero dependencies, a 3 s build and the same line count. That is
the honest competitor in this study, and the reason to pick Rust over Go is
items 1 and 2, not item 3.

### Caveats

- One machine, load generator and service sharing 10 cores, 10 s windows, one
  run per cell. No variance estimate yet; repeat runs are the obvious next step.
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

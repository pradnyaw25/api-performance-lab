# X thread

Each tweet is under 280 characters (URLs count as 23). Attach the image named in brackets; the first tweet carries the social card. Post 1 is the hook; the last carries the links.

---

**1/** [attach charts/00-social-card.png]

I built the same API in Rust, Go and Python, with each one's production stack, and benchmarked 7 workloads on 9 metrics.

"Rust is faster than Python" is true and useless. Here's *where* it's faster, by how much, and what it costs. 🧵

---

**2/**

Setup: Axum/Tokio vs Go net/http vs FastAPI on Uvicorn (uvloop + httptools + orjson, ×10 workers and ×1).

Same contract, verified by a shared test that refuses to benchmark anything that behaves differently. oha, 64 conns, 10 s per cell, fresh process per scenario, M5 10-core.

---

**3/** [attach charts/01-where-rust-wins.png]

The whole study in one chart. Each cell is a ratio against Rust. Blue = Rust better. Grey = the language didn't matter.

Look at the bottom two rows. When the request is *waiting* on something, the language doesn't decide speed. It decides what you pay while you wait.

---

**4/** [attach charts/06-overload.png]

Where Rust wins, #1: CPU on the request path.

SHA-256 ×5000 per request: Rust 23.7k rps, Go 11.5k, Python×10 3.2k.

Under overload (500 clients, 1 s timeout): Rust missed 0 deadlines, p99 145 ms. Go missed 0.2% at 698 ms. Python×10 2.1%. Python×1 63%.

---

**5/**

The detail I keep thinking about: under overload Go's *median* (21 ms) beat Rust's (51 ms) while its p99 was 5× worse.

Go serves some requests fast and lets others wait out the deadline. Tokio's work-stealing spreads the delay evenly. If you have an SLO, evenly is what you want.

---

**6/** [attach charts/03-tail-latency.png]

Where Rust wins, #2: the tail.

Simple lookup, p99: Rust 0.71 ms (2× its median). Go 1.83 ms (6×). Python×10 5.87 ms (11×).

Under CPU load Go's p99 opens to 24× its median. Rust stays at 2×. If your SLO is on p99 and not the median, this is the whole argument.

---

**7/** [attach charts/05-memory.png]

Where Rust wins, #3: density.

Idle RSS: Rust 9.9 MB, Go 13.5, Python×1 66, Python×10 710.
CPU per 1k lookups: Rust 22 ms, Go 30, Python×10 93.

Across a fleet, that's the bill.

Surprise: per *connection* Rust is heaviest (31.6 KB vs Go 23, Python 18). Hyper buffers big.

---

**8/**

Where Rust does NOT win: anything I/O-bound.

10 ms async wait: all four within 8% on throughput and 1 ms on p99. Rust is last (Tokio's sleep(10ms) takes 12.3 ms; Go and uvloop 11.3).

"Call the DB, return it" services: Rust buys 2–4× less CPU while waiting. Not speed.

---

**9/** [attach charts/08-tuning.png]

Two one-line changes moved the numbers more than the language choice did.

FastAPI: returning a dict runs jsonable_encoder (pure Python) before orjson gets it. `return ORJSONResponse(...)` took Python's list endpoint from 14× behind Rust to 1.6×.

---

**10/**

Rust's sha2 crate defaults to software SHA-256. Go's stdlib uses the ARM SHA-2 instructions.

In the baseline, Rust was *slower than Go* on hashing. `features = ["asm"]` tripled it, same digest.

The language sets the ceiling. The library decides if you reach it.

---

**11/**

The finding that isn't a benchmark number: ten-worker Python has no shared memory.

An item POSTed to one Uvicorn worker is a 404 on the other nine. Python's only route to all cores is 10 processes = 10 copies of everything, and Redis for what Rust and Go get from a mutex.

---

**12/** [attach charts/07-complexity.png]

Cost side: Rust 177 LOC / 93 crates / 13.7 s build. Go 182 LOC / 0 deps / 3.2 s. Python 93 LOC / 21 pkgs.

Go gets within 10–25% of Rust on everything except CPU-bound work and the tail, with zero dependencies. It's the honest competitor.

---

**13/**

Caveats: one machine, load gen shares the cores, macOS, in-memory store, medians of 4 runs. Phase 2 is the same contract on Postgres.

Everything's open: harness, raw oha JSON, both runs, contract test.

github.com/pradnyaw25/api-performance-lab

Write-up: [link to post]

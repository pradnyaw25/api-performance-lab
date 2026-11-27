# Benchmarking API Performance: Python vs Go vs Rust

<!-- Medium: upload the six PNGs from content/charts/simple/ at each image marker; Medium does not play GIFs reliably. Cover image: content/charts/00-social-card.png -->

### Same API, three production stacks, nine metrics. Where Rust actually matters, and where it doesn't. A small experiment inspired by Anthropic's Rust migration.

![Rust vs Go vs Python for API services](charts/00-social-card.png)

Last week Anthropic published [Migrating our Messages API to Rust](https://www.anthropic.com/research/migrating-api-to-rust): about 70% less CPU per request and more than 80% less memory after rewriting their API from Python to Rust. Those are production numbers from a very large service.

I wanted to know the *shape* of that gain. Which requests get faster? By how much? Which parts are the language, which are the runtime, and which are a library choice? Those questions can be answered on one laptop, with everything else held constant.

So I built the same API three times: Rust with Axum, Go with the standard library, Python with FastAPI on Uvicorn (uvloop, httptools, orjson). Python runs two ways: one worker, which has the same one-process, one-store, one-lock semantics as Rust and Go and is the like-for-like comparison, and ten workers, which is how it is actually deployed and which has ten separate stores. Seven endpoints, each isolating one kind of work. A shared test that refuses to benchmark anything that behaves differently. Nine metrics, {{n_runs}} full runs, medians below.

**One thing first:** this is a lab benchmark on a laptop, not production traffic. It cannot tell you what a migration like Anthropic's would yield. It can tell you *where* the differences come from.

## The experiment in one chart

![The experiment in one chart: who is fastest depends on the workload](charts/simple/s1-rust-advantage.png)

Each group is one workload; each bar is that language's throughput as a share of the fastest on that workload, with the real requests per second on it. On CPU-bound work Rust is well ahead. On a simple lookup Rust and Go are tied. On a request that is *waiting* on something, all three are within 9% and Rust is last. The language does not decide how fast a waiting request goes. It decides what it costs while it waits.

## Where Rust wins

**CPU on the request path.** 5,000 rounds of SHA-256 per request: Rust {{rps_cpu_rust}} req/s, Go {{rps_cpu_go}}, Python with ten workers {{rps_cpu_py10}}. That is {{r_go_cpu_rps}}× Go and {{r_py10_cpu_rps}}× Python.

![Under CPU overload, only Rust met the deadline for every request](charts/simple/s2-overload.png)

Push past saturation and it stops being a factor and becomes a behaviour. With 500 clients and a 1-second timeout, Rust missed the deadline on **zero** requests in every run. Go missed {{satcpu_err_go}}%, ten-worker Python {{satcpu_err_py10}}% (anywhere from {{satcpu_errrange_py10}}% run to run), single-worker Python {{satcpu_err_py1}}%. Go's median is close to Rust's but its p99 is four times worse: its scheduler lets a tail of requests wait out the deadline, while Tokio spreads the delay evenly. If you have an SLO, evenly is what you want.

**Tail latency.** On a simple lookup, Rust's p99 is {{p99_get_rust}} ms and about {{tail_get_rust}}× its median. Go's is {{p99_get_go}} ms at {{tail_get_go}}×. Python's is {{p99_get_py10}} ms at {{tail_get_py10}}×. Under CPU load Go's p99 opens to {{tail_cpu_go}}× its median; Rust's stays at {{tail_cpu_rust}}×.

![On a simple lookup, Rust's p99 is under a millisecond](charts/simple/s3-tail-latency.png)

![Idle memory: ten Python workers are ten copies of everything](charts/simple/s5-memory.png)

**Density.** Idle memory: Rust {{idle_rust}} MB, Go {{idle_go}} MB, ten Python workers {{idle_py10}} MB. CPU per 1,000 lookups: Rust {{cpu1k_get_rust}} ms, Go {{cpu1k_get_go}}, Python {{cpu1k_get_py10}}. Across a fleet, that is the bill, and it is the number Anthropic's 70% is made of.

## Where it does not

![When the request is waiting on I/O, the language barely matters](charts/simple/s4-io-bound.png)

- **Anything I/O-bound.** On a 10 ms wait all four land within {{io_spread_pct}}% on throughput and within a millisecond on p99. Rust is last, because Tokio's sleep overshoots by about 2 ms on macOS. Rust buys you {{r_cpu_io_go}} to {{r_cpu_io_py10}} less CPU *while waiting*. Not speed.
- **Serialization.** {{r_go_list_rps}}× Go, {{r_py10_list_rps}}× tuned Python on a 200-item list. Not a reason on its own.
- **Memory per connection.** Rust is the heaviest of the three ({{conn_rust}} KB per idle connection vs Go {{conn_go}}, Python {{conn_py10}}). My hypothesis had that backwards.

## Two one-line changes moved the numbers more than the language did

![Two one-line changes moved the numbers more than the language did](charts/simple/s6-tuning.png)

I kept the first run, with every framework at its defaults, on purpose.

**FastAPI:** returning a dict from a handler runs its pure-Python `jsonable_encoder` over the response before orjson gets it. On 200 items that made Python **{{b_ratio_list}}× slower** than Rust. Returning `ORJSONResponse(...)` directly took the gap to **{{r_py10_list_rps}}×**. If you run FastAPI in production, check which path your responses take.

**Rust:** in the first run, Rust was *slower than Go* on hashing. Go's standard library uses the ARM SHA-2 instructions out of the box; Rust's `sha2` crate defaults to software. One feature flag ({{tune_rust}}×, same digest). The language sets the ceiling; the library decides whether you reach it.

## The finding that is not a benchmark number

Ten-worker Python has no shared memory. The contract test caught it: an item created on one Uvicorn worker is a 404 on the other nine. Python's only route to all your cores is ten processes, which means ten copies of everything and Redis for what Rust and Go get from a mutex. It also means the ten-worker write numbers are not the same guarantee as the others; compare the single-worker row for like-for-like.

## What it costs

Rust and Go took the same number of lines ({{loc_rust}} and {{loc_go}}); Python {{loc_py10}}. Rust ships {{deps_rust}} crates, Go {{deps_go}}, Python {{deps_py10}} packages. Clean build: {{build_rust}} s Rust, {{build_go}} s Go. Cold start: {{cold_rust}} ms Rust, {{cold_go}} ms Go, {{cold_py10}} ms for ten Python workers.

On ordinary endpoints Go's throughput is a tie with Rust ({{rps_get_go}} vs {{rps_get_rust}} req/s on the lookup). Its gaps are CPU-bound work ({{r_rps_cpu_go}}), the p99 ({{r_p99_get_go}}), and per-request CPU and memory ({{r_cpu_get_go}}, {{r_peak_get_go}}), all with zero dependencies. It is the honest competitor.

## So what should you pick?

- **You compute on the request path:** Rust.
- **Your SLO is on p99:** Rust.
- **You mostly wait on a database:** the language does not decide your latency. Pick for the team, then pay the bill: about 2× memory and CPU for Go, {{r_py10_idle}}× memory for ten-worker Python.
- **You need shared state across cores:** Rust or Go.
- **You want most of Rust's density without its dependency graph:** Go.

## Caveats

One laptop with the load generator on the same cores, 10-second windows, macOS, an in-memory store, medians of {{n_runs}} runs with the ranges in the repo (Rust's lookup throughput swung {{rpsrange_get_rust}} req/s run to run, so Rust vs Go on ordinary endpoints is a tie, not a win). Small scale, not the production load of a large service. Phase 2 is the same contract on PostgreSQL.

Everything is open, including the raw `oha` output, the untuned baseline, and the contract test: [github.com/pradnyaw25/api-performance-lab](https://github.com/pradnyaw25/api-performance-lab). The long version with every number and the methodology is on [pradnya.dev](https://pradnya.dev/blog/api-performance-lab/). If a configuration is unfair to your favourite language, open an issue.

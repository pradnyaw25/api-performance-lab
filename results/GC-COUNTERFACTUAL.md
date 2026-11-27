# Counterfactual: Go with the garbage collector off

The posts originally attributed Go's wider tail to its garbage collector.
That was a hypothesis, not a measurement. The cheapest test is to run the
same Go binary with `GOGC=off` (no collection at all) and see whether the
tail flattens. Runs: `20261126-234642`, `20261126-234831`; config `bench/config-gc.json`.

| Run | Implementation | Scenario | req/s | p50 ms | p95 ms | p99 ms | p99.9 ms | peak RSS MB |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `20261126-234642` | `go-nethttp` | get | 176,618 | 0.24 | 0.95 | 2.62 | 6.0 | 28 |
| `20261126-234642` | `go-nethttp` | list | 61,859 | 0.68 | 3.28 | 5.91 | 10.2 | 29 |
| `20261126-234642` | `go-nethttp` | cpu | 14,241 | 1.24 | 18.82 | 30.72 | 47.6 | 41 |
| `20261126-234642` | `go-nethttp` | sat-cpu | 4,581 | 64 | 403 | 619 | 876 | 74 |
| `20261126-234642` | `go-nethttp-nogc` | get | 175,643 | 0.23 | 0.86 | 3.03 | 10.6 | 717 |
| `20261126-234642` | `go-nethttp-nogc` | list | 70,791 | 0.66 | 2.37 | 4.43 | 9.7 | 1,994 |
| `20261126-234642` | `go-nethttp-nogc` | cpu | 12,983 | 3.58 | 12.40 | 25.38 | 91.2 | 2,318 |
| `20261126-234642` | `go-nethttp-nogc` | sat-cpu | 2,404 | 175 | 536 | 860 | 980 | 6,078 |
| `20261126-234831` | `go-nethttp` | get | 132,590 | 0.25 | 1.42 | 5.13 | 10.5 | 30 |
| `20261126-234831` | `go-nethttp` | list | 49,958 | 0.82 | 4.21 | 7.61 | 13.0 | 31 |
| `20261126-234831` | `go-nethttp` | cpu | 11,476 | 1.59 | 22.91 | 37.40 | 58.6 | 42 |
| `20261126-234831` | `go-nethttp` | sat-cpu | 3,391 | 78 | 521 | 765 | 953 | 81 |
| `20261126-234831` | `go-nethttp-nogc` | get | 90,514 | 0.24 | 1.75 | 7.53 | 53.4 | 1,048 |
| `20261126-234831` | `go-nethttp-nogc` | list | 46,827 | 0.90 | 3.71 | 8.61 | 21.6 | 2,078 |
| `20261126-234831` | `go-nethttp-nogc` | cpu | 9,626 | 4.64 | 17.61 | 38.41 | 124.5 | 1,934 |
| `20261126-234831` | `go-nethttp-nogc` | sat-cpu | 2,614 | 141 | 471 | 886 | 988 | 9,609 |

## Reading

- On the lookup, p99 did **not** improve with the collector off; it got worse
  in both runs. On the list it moved both ways. On the CPU endpoint, p95 fell by
  roughly a quarter in both runs while the median tripled and p99 barely moved.
- So the garbage collector is at most a minor contributor to Go's tail on these
  workloads. The tail persists without it, which means it comes from somewhere
  this harness cannot see: scheduler behaviour, netpoll and syscall timing, lock
  contention, or allocation without reuse (with `GOGC=off` the heap grew to
  1–2 GB, which changes allocation behaviour and is itself a confound).
- The two runs of the baseline Go service differ by 25% on lookup throughput,
  the same laptop noise seen in the main runs. Direction is consistent across
  both runs; magnitudes are not.
- The proper tools are `pprof`, the execution tracer and `runtime/metrics`
  for Go, and Tokio's runtime metrics for Rust. Until that is done, every
  explanation of *why* a tail is shaped the way it is stays a hypothesis.

#!/usr/bin/env python3
"""Render results/<run>/summary.json into a Markdown report.

Usage: bench/report.py results/<run-id>/summary.json  (prints Markdown)
"""

import json
import sys


def mb(b):
    return "–" if b is None else f"{b / 1e6:,.1f}"


def ms(v):
    return "–" if v is None else f"{v:,.2f}"


def num(v, d=0):
    return "–" if v is None else f"{v:,.{d}f}"


def ratio(a, b):
    if a is None or b is None or b == 0:
        return "–"
    return f"{a / b:.2f}×"


def render(summary):
    impls = summary["implementations"]
    names = [n for n in impls if impls[n].get("scenarios")]
    failed = [n for n in impls if not impls[n].get("scenarios")]
    scenarios = [s["name"] for s in summary["scenarios"]]
    st = summary["settings"]
    m = summary["machine"]
    L = []
    L.append(f"# API Performance Lab — results `{summary['run_id']}`\n")
    L.append(f"*{summary['started_at']}* · {m['cpu']} ({m['cpus']} cores) · {m['platform']}  ")
    L.append(f"Load: {st['load_generator']}, concurrency **{st['concurrency']}**, "
             f"**{st['duration_s']} s** per scenario after **{st['warmup_s']} s** warm-up. "
             f"Load generator and services share the machine; read the numbers as relative.\n")

    L.append("## Implementations\n")
    L.append("| Implementation | Toolchain | Contract | LOC | Build (s) | Artifact | Startup (s) | Idle RSS (MB) |")
    L.append("|---|---|---|---:|---:|---:|---:|---:|")
    for n, e in impls.items():
        build = "–" if e.get("build_s") is None else f"{e['build_s']:.1f}{' cold' if e.get('cold') else ''}"
        art = mb(e.get("artifact_bytes"))
        contract = e.get("contract", e.get("error", "–"))
        L.append(f"| `{n}` | {e.get('toolchain','–')} | {contract} | {e.get('loc','–')} | {build} | {art} "
                 f"| {num(e.get('startup_s'), 2)} | {mb(e.get('idle_rss_bytes'))} |")
    if failed:
        L.append("")
        for n in failed:
            L.append(f"- `{n}` produced no results: {impls[n].get('error') or 'contract test failed'}")
    L.append("")

    L.append("## Throughput (requests/s)\n")
    L.append("| Scenario | " + " | ".join(f"`{n}`" for n in names) + " |")
    L.append("|---|" + "---:|" * len(names))
    for sc in scenarios:
        L.append(f"| {sc} | " + " | ".join(num(impls[n]["scenarios"].get(sc, {}).get("rps")) for n in names) + " |")
    L.append("")

    L.append("## Latency p99 (ms)\n")
    L.append("| Scenario | " + " | ".join(f"`{n}`" for n in names) + " |")
    L.append("|---|" + "---:|" * len(names))
    for sc in scenarios:
        L.append(f"| {sc} | " + " | ".join(ms(impls[n]["scenarios"].get(sc, {}).get("p99_ms")) for n in names) + " |")
    L.append("")

    L.append("## Peak RSS during load (MB, whole process tree)\n")
    L.append("| Scenario | " + " | ".join(f"`{n}`" for n in names) + " |")
    L.append("|---|" + "---:|" * len(names))
    for sc in scenarios:
        L.append(f"| {sc} | " + " | ".join(mb(impls[n]["scenarios"].get(sc, {}).get("peak_rss_bytes")) for n in names) + " |")
    L.append("")

    L.append("## CPU cost (server CPU-ms per request)\n")
    L.append("Lower is better: how much CPU each request actually consumed, independent of how saturated the machine was.\n")
    L.append("| Scenario | " + " | ".join(f"`{n}`" for n in names) + " |")
    L.append("|---|" + "---:|" * len(names))
    for sc in scenarios:
        L.append(f"| {sc} | " + " | ".join(num(impls[n]["scenarios"].get(sc, {}).get("cpu_ms_per_req"), 4) for n in names) + " |")
    L.append("")

    if "rust-axum" in names:
        L.append("## Where Rust's advantage is, relative to each alternative\n")
        L.append("Throughput and CPU ratios > 1 mean Rust does better; p99 and RSS ratios > 1 mean the alternative is worse (Rust lower).\n")
        others = [n for n in names if n != "rust-axum"]
        L.append("| Scenario | Metric | " + " | ".join(f"`{n}`" for n in others) + " |")
        L.append("|---|---|" + "---:|" * len(others))
        r = impls["rust-axum"]["scenarios"]
        for sc in scenarios:
            rs = r.get(sc, {})
            rows = [
                ("throughput", lambda o: ratio(rs.get("rps"), o.get("rps"))),
                ("p99 latency", lambda o: ratio(o.get("p99_ms"), rs.get("p99_ms"))),
                ("p99.9 latency", lambda o: ratio(o.get("p999_ms"), rs.get("p999_ms"))),
                ("CPU/req", lambda o: ratio(o.get("cpu_ms_per_req"), rs.get("cpu_ms_per_req"))),
                ("peak RSS", lambda o: ratio(o.get("peak_rss_bytes"), rs.get("peak_rss_bytes"))),
            ]
            for i, (label, f) in enumerate(rows):
                first = f"**{sc}**" if i == 0 else ""
                L.append(f"| {first} | {label} | " + " | ".join(f(impls[n]["scenarios"].get(sc, {})) for n in others) + " |")
        L.append("")

    L.append("## Per-scenario detail\n")
    for sc in scenarios:
        L.append(f"### `{sc}`\n")
        L.append("| Implementation | req/s | p50 | p90 | p99 | p99.9 | max | p99/p50 | peak RSS MB | CPU ms/req | CPU util | errors |")
        L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for n in names:
            s = impls[n]["scenarios"].get(sc)
            if not s:
                continue
            tail = ratio(s.get("p99_ms"), s.get("p50_ms"))
            util = "–" if s.get("server_cpu_util") is None else f"{100*s['server_cpu_util']:.0f}%"
            L.append(f"| `{n}` | {num(s['rps'])} | {ms(s['p50_ms'])} | {ms(s['p90_ms'])} | {ms(s['p99_ms'])} | "
                     f"{ms(s['p999_ms'])} | {ms(s['max_ms'])} | {tail} | {mb(s['peak_rss_bytes'])} | "
                     f"{num(s['cpu_ms_per_req'], 4)} | {util} | {s['errors']} ({num(s['error_pct'], 2)}%) |")
        L.append("")

    notes = {n: impls[n].get("contract_notes") for n in impls if impls[n].get("contract_notes")}
    if notes:
        L.append("## Behaviour that differs despite the shared contract\n")
        L.append("Recorded by the contract test (not asserted). Same inputs, framework-chosen responses.\n")
        for n, ns in notes.items():
            L.append(f"- `{n}`")
            for x in ns:
                L.append(f"  - {x}")
        L.append("")

    L.append("## Reading the numbers\n")
    L.append("- **p99/p50** is the tail-flatness ratio. GC pauses and the GIL show up here, not in the median.")
    L.append("- **CPU ms/req** is the cost side of throughput. Two implementations with equal req/s but 3× different CPU/req do not have equal performance; one has 3× the headroom.")
    L.append("- **CPU util** is server CPU over all cores. Near 100% means the service was the bottleneck; well below means the load generator or the scenario's I/O wait was.")
    L.append("- `io` and `mixed` are latency-bound by design: with concurrency *c* and wait *w*, throughput cannot exceed *c / w*. Converging numbers there are the expected result, and the interesting columns are RSS and tail latency.")
    L.append("- The Python rows are the same code; `python-fastapi` runs one Uvicorn worker per core, `python-fastapi-1w` runs one. The gap between them is the cost of the GIL; the gap between `python-fastapi` and Go is the cost of multi-process vs. multi-thread.")
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(render(json.loads(open(sys.argv[1]).read())))

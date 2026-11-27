#!/usr/bin/env python3
"""Render results/<run>/summary.json into a Markdown report.

Usage: bench/report.py results/<run-id>/summary.json  (prints Markdown)
"""

import json
import sys


def mb(b):
    return "–" if b is None else f"{b / 1e6:,.1f}"


def kb(b):
    return "–" if b is None else f"{b / 1024:,.1f}"


def ms(v):
    return "–" if v is None else f"{v:,.2f}"


def num(v, d=0):
    return "–" if v is None else f"{v:,.{d}f}"


def ratio(a, b):
    if a is None or b is None or b == 0:
        return "–"
    return f"{a / b:.2f}×"


def table(L, header, rows):
    L.append("| " + " | ".join(header) + " |")
    L.append("|" + "|".join("---:" if i else "---" for i in range(len(header))) + "|")
    for r in rows:
        L.append("| " + " | ".join(str(c) for c in r) + " |")
    L.append("")


def render(summary, spread=None):
    spread = spread or {}
    impls = summary["implementations"]
    names = [n for n in impls if impls[n].get("scenarios")]
    failed = [n for n in impls if not impls[n].get("scenarios")]
    scenarios = [s["name"] for s in summary["scenarios"]]
    st = summary["settings"]
    m = summary["machine"]
    cols = [f"`{n}`" for n in names]
    L = []
    L.append(f"# API Performance Lab — results `{summary['run_id']}`\n")
    L.append(f"*{summary['started_at']}* · {m['cpu']} ({m['cpus']} cores) · {m['platform']}  ")
    if st.get("runs"):
        L.append(f"**Median of {len(st['runs'])} runs** ({', '.join(f'`{r}`' for r in st['runs'])}); throughput and p99 tables show min–max across runs.  ")
    L.append(f"Load: {st['load_generator']}, concurrency **{st['concurrency']}**, "
             f"**{st['duration_s']} s** per scenario after **{st['warmup_s']} s** warm-up, fresh process per scenario. "
             f"Load generator and services share the machine; read the numbers as relative.\n")

    # ------------------------------------------------------------ complexity
    L.append("## Implementations and implementation complexity\n")
    L.append("LOC is non-blank, non-comment lines for the identical contract. Deps is every third-party package shipped (transitive). "
             "Cold start is process launch to first `200` from `/health`, median of "
             f"{st.get('cold_start_runs', '?')} starts.\n")
    rows = []
    for n, e in impls.items():
        build = "–" if e.get("build_s") is None else f"{e['build_s']:.1f}{' (cold)' if e.get('cold') else ''}"
        cs = e.get("cold_start_ms") or []
        cs_txt = "–" if not cs else f"{e.get('cold_start_median_ms', cs[0]):,.0f} ({min(cs):,.0f}–{max(cs):,.0f})"
        rows.append([f"`{n}`", e.get("toolchain", "–"), e.get("contract", e.get("error", "–")), e.get("loc", "–"),
                     num(e.get("deps")), build, mb(e.get("artifact_bytes")), cs_txt, mb(e.get("idle_rss_bytes"))])
    table(L, ["Implementation", "Toolchain", "Contract", "LOC", "Deps", "Build (s)", "Artifact (MB)", "Cold start ms (min–max)", "Idle RSS (MB)"], rows)
    if failed:
        for n in failed:
            L.append(f"- `{n}` produced no results: {impls[n].get('error') or 'contract test failed'}")
        L.append("")

    def sc_get(n, sc, key):
        return impls[n]["scenarios"].get(sc, {}).get(key)

    # ------------------------------------------------------------ throughput
    L.append("## Throughput (requests/s)\n")
    def with_spread(n, sc, key, fmt):
        v = fmt(sc_get(n, sc, key))
        sp = spread.get(f"{n}/scenarios/{sc}/{key}")
        if sp and sp["n"] > 1:
            v += f" <sub>({fmt(sp['min'])}–{fmt(sp['max'])})</sub>"
        return v

    table(L, ["Scenario"] + cols, [[sc] + [with_spread(n, sc, "rps", num) for n in names] for sc in scenarios])

    # --------------------------------------------------------------- latency
    L.append("## Latency: p50 / p95 / p99 (ms)\n")
    table(L, ["Scenario"] + cols,
          [[sc] + [f"{ms(sc_get(n, sc, 'p50_ms'))} / {ms(sc_get(n, sc, 'p95_ms'))} / {with_spread(n, sc, 'p99_ms', ms)}" for n in names]
           for sc in scenarios])

    # ---------------------------------------------------------------- memory
    L.append("## Peak RSS during load (MB, whole process tree)\n")
    table(L, ["Scenario"] + cols, [[sc] + [mb(sc_get(n, sc, "peak_rss_bytes")) for n in names] for sc in scenarios])

    # ------------------------------------------------------------------- cpu
    L.append("## CPU per 1,000 requests (server CPU-ms)\n")
    L.append("Lower is better: compute each request actually consumed, independent of how saturated the machine was. "
             "Two implementations with equal req/s but 3× different CPU/1k do not have equal performance; one has 3× the headroom.\n")
    table(L, ["Scenario"] + cols, [[sc] + [num(sc_get(n, sc, "cpu_ms_per_1k_req"), 1) for n in names] for sc in scenarios])

    # ------------------------------------------------------------ saturation
    sats = [s["name"] for s in summary.get("saturation", [])]
    if sats and any(impls[n].get("saturation") for n in names):
        L.append("## Error rate under saturation\n")
        L.append(f"Concurrency far above the normal runs, with a per-request timeout; every timeout, refused or reset connection and non-2xx counts as an error. "
                 f"macOS `kern.ipc.somaxconn` here is {m.get('somaxconn', '?')}, so connection bursts above that queue in the kernel for every implementation alike.\n")
        for sat in sats:
            cfg = next(s for s in summary["saturation"] if s["name"] == sat)
            L.append(f"### `{sat}` — `{cfg['path']}` at concurrency {cfg['concurrency']}, timeout {cfg.get('timeout_s', '∞')} s\n")
            rows = []
            for n in names:
                s = impls[n].get("saturation", {}).get(sat)
                if not s:
                    continue
                kinds = ", ".join(f"{k}: {v}" for k, v in list(s["error_kinds"].items())[:3]) or "–"
                non2xx = {k: v for k, v in s["status_codes"].items() if not str(k).startswith("2")}
                if non2xx:
                    kinds = (kinds + "; " if kinds != "–" else "") + ", ".join(f"HTTP {k}: {v}" for k, v in non2xx.items())
                rows.append([f"`{n}`", num(s["rps"]), ms(s["p50_ms"]), ms(s["p99_ms"]), ms(s["max_ms"]),
                             f"**{num(s['error_pct'], 2)}%**", s["errors"], mb(s["peak_rss_bytes"]), kinds])
            table(L, ["Implementation", "req/s", "p50", "p99", "max (ms)", "Error rate", "Errors", "Peak RSS MB", "Error kinds"], rows)

    # ----------------------------------------------------------- connections
    if any(impls[n].get("connections") for n in names):
        c = st.get("connections") or {}
        L.append("## Memory per open connection\n")
        L.append(f"{c.get('count', '?')} keep-alive connections opened, one request each, then held idle for {c.get('hold_s', 1)} s. "
                 "Per-connection cost is what bounds long-lived streaming/WebSocket/SSE fan-out.\n")
        rows = []
        for n in names:
            e = impls[n].get("connections")
            if not e:
                continue
            rows.append([f"`{n}`", e["connections"], e["failed"], mb(e["idle_rss_bytes"]), mb(e["held_rss_bytes"]),
                         f"**{kb(e['bytes_per_conn'])}**", mb(e["after_close_rss_bytes"])])
        table(L, ["Implementation", "Opened", "Failed", "Idle RSS MB", "Held RSS MB", "KB / connection", "After close MB"], rows)

    # -------------------------------------------------------------- recovery
    if any(impls[n].get("recovery") for n in names):
        r0 = next(impls[n]["recovery"] for n in names if impls[n].get("recovery"))
        sp = r0["spike"]
        L.append("## Recovery after a load spike\n")
        L.append(f"Probe: sequential keep-alive requests to `/items/42` from one client. Spike: `{sp['path']}` at concurrency {sp['concurrency']} for {sp['seconds']} s. "
                 f"Then probe again immediately and after {r0['settle_s']} s idle. *Retained* is how much of the spike's RSS growth was still held after settling: "
                 "it shows whether the runtime gives memory back to the OS.\n")
        rows = []
        for n in names:
            r = impls[n].get("recovery")
            if not r:
                continue
            rows.append([f"`{n}`", num(r["spike"]["rps"]), mb(r["idle_rss_bytes"]), mb(r["peak_rss_bytes"]), mb(r["rss_after_spike_bytes"]),
                         mb(r["rss_after_settle_bytes"]), f"**{r['retained_pct']}%**",
                         f"{ms(r['probe_pre']['p50_ms'])} / {ms(r['probe_pre']['p99_ms'])}",
                         f"{ms(r['probe_after_spike']['p50_ms'])} / {ms(r['probe_after_spike']['p99_ms'])}",
                         f"{ms(r['probe_after_settle']['p50_ms'])} / {ms(r['probe_after_settle']['p99_ms'])}"])
        table(L, ["Implementation", "Spike req/s", "Idle MB", "Peak MB", "+0 s MB", f"+{r0['settle_s']} s MB", "Retained",
                  "Probe before p50/p99", "Probe +0 s", f"Probe +{r0['settle_s']} s"], rows)

    # ------------------------------------------------------------ rust ratio
    if "rust-axum" in names:
        L.append("## Where Rust's advantage is, relative to each alternative\n")
        L.append("Every ratio is *alternative ÷ Rust* for cost metrics (latency, CPU, RSS) and *Rust ÷ alternative* for throughput, so **> 1 means Rust is better**, "
                 "≈ 1 means the language did not matter for that workload, and < 1 means the alternative won.\n")
        others = [n for n in names if n != "rust-axum"]
        r = impls["rust-axum"]["scenarios"]
        rows = []
        for sc in scenarios:
            rs = r.get(sc, {})
            metrics = [
                ("throughput", lambda o: ratio(rs.get("rps"), o.get("rps"))),
                ("p99 latency", lambda o: ratio(o.get("p99_ms"), rs.get("p99_ms"))),
                ("CPU / 1k req", lambda o: ratio(o.get("cpu_ms_per_1k_req"), rs.get("cpu_ms_per_1k_req"))),
                ("peak RSS", lambda o: ratio(o.get("peak_rss_bytes"), rs.get("peak_rss_bytes"))),
            ]
            for i, (label, f) in enumerate(metrics):
                rows.append([f"**{sc}**" if i == 0 else "", label] + [f(impls[n]["scenarios"].get(sc, {})) for n in others])
        L.append("| Scenario | Metric | " + " | ".join(f"`{n}`" for n in others) + " |")
        L.append("|---|---|" + "---:|" * len(others))
        for row in rows:
            L.append("| " + " | ".join(row) + " |")
        L.append("")

    # ---------------------------------------------------------------- detail
    L.append("## Per-scenario detail\n")
    for sc in scenarios:
        L.append(f"### `{sc}`\n")
        rows = []
        for n in names:
            s = impls[n]["scenarios"].get(sc)
            if not s:
                continue
            util = "–" if s.get("server_cpu_util") is None else f"{100 * s['server_cpu_util']:.0f}%"
            rows.append([f"`{n}`", num(s["rps"]), ms(s["p50_ms"]), ms(s["p95_ms"]), ms(s["p99_ms"]), ms(s["p999_ms"]), ms(s["max_ms"]),
                         ratio(s.get("p99_ms"), s.get("p50_ms")), mb(s["peak_rss_bytes"]), num(s.get("rss_growth_per_req_bytes")),
                         num(s["cpu_ms_per_1k_req"], 1), util, f"{s['errors']} ({num(s['error_pct'], 2)}%)"])
        table(L, ["Implementation", "req/s", "p50", "p95", "p99", "p99.9", "max", "p99/p50", "peak RSS MB", "ΔRSS/req B", "CPU ms/1k", "CPU util", "errors"], rows)

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
    L.append("- **CPU ms/1k** is the cost side of throughput. Equal req/s at 3× the CPU is not equal performance; it is 3× less headroom.")
    L.append("- **CPU util** is server CPU over all cores. Near 100% means the service was the bottleneck; well below means the load generator or the scenario's I/O wait was.")
    L.append("- **ΔRSS/req** is memory growth per request over the run. It only means something for `create`, where it is the per-item cost of the in-memory store; elsewhere it should be ~0.")
    L.append("- `io` and `mixed` are latency-bound by design: with concurrency *c* and wait *w*, throughput cannot exceed *c / w*. Converging numbers there are the expected result; the interesting columns are CPU/1k, RSS and tail latency.")
    L.append("- The Python rows are the same code; `python-fastapi` runs one Uvicorn worker per core, `python-fastapi-1w` runs one. The gap between them is the cost of the GIL; the gap between `python-fastapi` and Go is the cost of multi-process vs. multi-thread.")
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(render(json.loads(open(sys.argv[1]).read())))

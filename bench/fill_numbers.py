#!/usr/bin/env python3
"""Fill {{placeholders}} in content/templates/* from a run's summary.json.

Usage: bench/fill_numbers.py results/aggregate [--baseline results/20261126-215740] [--list]

Every number in the published drafts comes from here, so a re-run of the
benchmark re-renders the prose with one command and nothing is hand-edited.
Unknown placeholders are an error (it lists them), so typos cannot ship.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMPL = {"rust": "rust-axum", "go": "go-nethttp", "py10": "python-fastapi", "py1": "python-fastapi-1w"}
SCEN = ["health", "get", "list", "create", "cpu", "io", "mixed"]


def k(v):
    if v is None:
        return "–"
    if v >= 10000:
        return f"{v/1000:,.1f}k".replace(".0k", "k")
    if v >= 1000:
        return f"{v/1000:,.1f}k"
    return f"{v:,.0f}"


def n0(v):
    return "–" if v is None else f"{v:,.0f}"


def n1(v):
    return "–" if v is None else f"{v:,.1f}"


def n2(v):
    return "–" if v is None else f"{v:,.2f}"


def x1(v):
    return "–" if v is None else f"{v:.1f}×"


def values(summary, spread, baseline):
    V = {}
    I = summary["implementations"]
    V["n_runs"] = str(len(summary["settings"].get("runs", [summary["run_id"]])))
    V["run_ids"] = ", ".join(summary["settings"].get("runs", [summary["run_id"]]))
    V["cpu_brand"] = summary["machine"]["cpu"]
    V["cpus"] = str(summary["machine"]["cpus"])
    rust = I["rust-axum"]
    for short, name in IMPL.items():
        e = I[name]
        s = e["scenarios"]
        for sc in SCEN:
            r = s[sc]
            V[f"rps_{sc}_{short}"] = k(r["rps"])
            V[f"rpsfull_{sc}_{short}"] = n0(r["rps"])
            sp = spread.get(f"{name}/scenarios/{sc}/rps")
            V[f"rpsrange_{sc}_{short}"] = f"{k(sp['min'])}–{k(sp['max'])}" if sp and sp["n"] > 1 else k(r["rps"])
            V[f"p50_{sc}_{short}"] = n2(r["p50_ms"])
            V[f"p95_{sc}_{short}"] = n2(r["p95_ms"])
            V[f"p99_{sc}_{short}"] = n2(r["p99_ms"])
            V[f"p99r_{sc}_{short}"] = n1(r["p99_ms"])
            V[f"tail_{sc}_{short}"] = n1(r["p99_ms"] / r["p50_ms"])
            V[f"cpu1k_{sc}_{short}"] = n0(r["cpu_ms_per_1k_req"])
            V[f"peak_{sc}_{short}"] = n1(r["peak_rss_bytes"] / 1e6)
            rr = rust["scenarios"][sc]
            V[f"r_rps_{sc}_{short}"] = x1(rr["rps"] / r["rps"])
            V[f"r_p99_{sc}_{short}"] = x1(r["p99_ms"] / rr["p99_ms"])
            V[f"r_cpu_{sc}_{short}"] = x1(r["cpu_ms_per_1k_req"] / rr["cpu_ms_per_1k_req"])
            V[f"r_peak_{sc}_{short}"] = x1(r["peak_rss_bytes"] / rr["peak_rss_bytes"])
        V[f"peritem_{short}"] = n0(s["create"]["rss_growth_per_req_bytes"])
        V[f"idle_{short}"] = n1(e["idle_rss_bytes"] / 1e6)
        V[f"r_idle_{short}"] = x1(e["idle_rss_bytes"] / rust["idle_rss_bytes"])
        V[f"conn_{short}"] = n1(e["connections"]["bytes_per_conn"] / 1024)
        V[f"conn100k_{short}"] = n1(e["connections"]["bytes_per_conn"] * 100_000 / 1e9)
        V[f"cold_{short}"] = n0(e["cold_start_median_ms"])
        V[f"coldrange_{short}"] = f"{min(e['cold_start_ms']):,.0f}–{max(e['cold_start_ms']):,.0f}"
        V[f"loc_{short}"] = str(e["loc"])
        V[f"deps_{short}"] = str(e["deps"])
        V[f"build_{short}"] = n1(e["build_s"]) if e.get("build_s") else "–"
        V[f"artifact_{short}"] = n1(e["artifact_bytes"] / 1e6) if e.get("artifact_bytes") else "–"
        for sat in ("sat-cpu", "sat-get"):
            t = e["saturation"][sat]
            key = sat.replace("-", "")
            V[f"{key}_err_{short}"] = n2(t["error_pct"])
            V[f"{key}_errn_{short}"] = n0(t["errors"])
            V[f"{key}_p50_{short}"] = n0(t["p50_ms"])
            V[f"{key}_p99_{short}"] = n0(t["p99_ms"])
            V[f"{key}_rps_{short}"] = k(t["rps"])
        rec = e["recovery"]
        V[f"ret_{short}"] = n0(rec["retained_pct"])
        V[f"growth_{short}"] = n1((rec["peak_rss_bytes"] - rec["idle_rss_bytes"]) / 1e6)
        V[f"recpre_{short}"] = n2(rec["probe_pre"]["p99_ms"])
        V[f"recpost_{short}"] = n2(rec["probe_after_spike"]["p99_ms"])
    io = [I[n]["scenarios"]["io"] for n in IMPL.values()]
    lo, hi = min(r["rps"] for r in io), max(r["rps"] for r in io)
    V["io_rps_lo"], V["io_rps_hi"], V["io_spread_pct"] = k(lo), k(hi), n0(100 * (hi - lo) / lo)
    V["io_p99_lo"], V["io_p99_hi"] = n1(min(r["p99_ms"] for r in io)), n1(max(r["p99_ms"] for r in io))
    V["r_go_cpu_rps"] = n1(rust["scenarios"]["cpu"]["rps"] / I["go-nethttp"]["scenarios"]["cpu"]["rps"])
    V["r_py10_cpu_rps"] = n1(rust["scenarios"]["cpu"]["rps"] / I["python-fastapi"]["scenarios"]["cpu"]["rps"])
    V["r_py1_cpu_rps"] = n0(rust["scenarios"]["cpu"]["rps"] / I["python-fastapi-1w"]["scenarios"]["cpu"]["rps"])
    V["r_py10_list_rps"] = n1(rust["scenarios"]["list"]["rps"] / I["python-fastapi"]["scenarios"]["list"]["rps"])
    V["r_go_list_rps"] = n1(rust["scenarios"]["list"]["rps"] / I["go-nethttp"]["scenarios"]["list"]["rps"])
    V["r_py10_idle"] = n0(I["python-fastapi"]["idle_rss_bytes"] / rust["idle_rss_bytes"])
    V["py_scale_cpu"] = n1(I["python-fastapi"]["scenarios"]["cpu"]["rps"] / I["python-fastapi-1w"]["scenarios"]["cpu"]["rps"])
    V["py_scale_get"] = n1(I["python-fastapi"]["scenarios"]["get"]["rps"] / I["python-fastapi-1w"]["scenarios"]["get"]["rps"])
    sp = spread.get("rust-axum/scenarios/get/p99_ms")
    V["p99range_get_rust"] = f"{n2(sp['min'])}–{n2(sp['max'])}" if sp and sp["n"] > 1 else V["p99_get_rust"]
    sp = spread.get("python-fastapi/saturation/sat-cpu/error_pct")
    V["satcpu_errrange_py10"] = f"{n2(sp['min'])}–{n2(sp['max'])}" if sp and sp["n"] > 1 else V["satcpu_err_py10"]
    if baseline:
        B = baseline["implementations"]
        V["b_rps_list_py10"] = k(B["python-fastapi"]["scenarios"]["list"]["rps"])
        V["b_rps_list_py1"] = k(B["python-fastapi-1w"]["scenarios"]["list"]["rps"])
        V["b_cpu_list_py10"] = n1(B["python-fastapi"]["scenarios"]["list"]["cpu_ms_per_req"])
        V["b_ratio_list"] = n0(B["rust-axum"]["scenarios"]["list"]["rps"] / B["python-fastapi"]["scenarios"]["list"]["rps"])
        V["b_rps_cpu_rust"] = k(B["rust-axum"]["scenarios"]["cpu"]["rps"])
        V["b_rps_cpu_go"] = k(B["go-nethttp"]["scenarios"]["cpu"]["rps"])
        V["tune_py"] = n1(I["python-fastapi"]["scenarios"]["list"]["rps"] / B["python-fastapi"]["scenarios"]["list"]["rps"])
        V["tune_rust"] = n1(I["rust-axum"]["scenarios"]["cpu"]["rps"] / B["rust-axum"]["scenarios"]["cpu"]["rps"])
    return V


def pg_values(pg, mem):
    """pg_* placeholders from the Phase 2 aggregate, plus pgshare_* (pg ÷ in-memory)."""
    V = {}
    P, M = pg["implementations"], mem["implementations"]
    V["pg_n_runs"] = str(len(pg["settings"].get("runs", [pg["run_id"]])))
    for short, name in IMPL.items():
        e = P.get(name + "-pg")
        if not e:
            continue
        s, ms_ = e["scenarios"], M[name]["scenarios"]
        for sc in SCEN:
            r = s[sc]
            V[f"pg_rps_{sc}_{short}"] = k(r["rps"])
            V[f"pg_rpsfull_{sc}_{short}"] = n0(r["rps"])
            V[f"pg_p50_{sc}_{short}"] = n2(r["p50_ms"])
            V[f"pg_p99_{sc}_{short}"] = n2(r["p99_ms"])
            V[f"pg_cpu1k_{sc}_{short}"] = n0(r["cpu_ms_per_1k_req"])
            V[f"pg_peak_{sc}_{short}"] = n1(r["peak_rss_bytes"] / 1e6)
            V[f"pgshare_{sc}_{short}"] = n0(100 * r["rps"] / ms_[sc]["rps"])
        V[f"pg_idle_{short}"] = n1(e["idle_rss_bytes"] / 1e6)
        V[f"pg_cold_{short}"] = n0(e["cold_start_median_ms"])
        t = e["saturation"]["sat-get"]
        V[f"pg_satget_err_{short}"] = n2(t["error_pct"])
        V[f"pg_satget_p99_{short}"] = n0(t["p99_ms"])
        V[f"pg_satget_rps_{short}"] = k(t["rps"])
    rust = P["rust-axum-pg"]["scenarios"]
    for sc in ("get", "list", "create", "mixed"):
        for short in ("go", "py10", "py1"):
            o = P[IMPL[short] + "-pg"]["scenarios"][sc]
            V[f"pg_r_rps_{sc}_{short}"] = x1(rust[sc]["rps"] / o["rps"])
            V[f"pg_r_p99_{sc}_{short}"] = x1(o["p99_ms"] / rust[sc]["p99_ms"])
            V[f"pg_r_cpu_{sc}_{short}"] = x1(o["cpu_ms_per_1k_req"] / rust[sc]["cpu_ms_per_1k_req"])
    return V


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--baseline", default=str(ROOT / "results" / "20261126-215740"))
    ap.add_argument("--templates", default=str(ROOT / "content" / "templates"))
    ap.add_argument("-o", "--out", default=str(ROOT / "content"))
    ap.add_argument("--list", action="store_true", help="print every placeholder name and value")
    ap.add_argument("--pg", default=str(ROOT / "results" / "aggregate-pg"), help="Phase 2 (PostgreSQL) aggregate dir; adds pg_* placeholders when present")
    args = ap.parse_args()
    run = Path(args.run_dir)
    summary = json.loads((run / "summary.json").read_text())
    spread = json.loads((run / "spread.json").read_text()) if (run / "spread.json").exists() else {}
    bpath = Path(args.baseline) / "summary.json"
    baseline = json.loads(bpath.read_text()) if bpath.exists() else None
    V = values(summary, spread, baseline)
    pgp = Path(args.pg) / "summary.json"
    if pgp.exists():
        V.update(pg_values(json.loads(pgp.read_text()), summary))
    if args.list:
        for kk in sorted(V):
            print(f"{kk:28s} {V[kk]}")
        return 0
    out = Path(args.out)
    rc = 0
    for tpl in sorted(Path(args.templates).iterdir()):
        if tpl.name.startswith("."):
            continue
        text = tpl.read_text()
        missing = sorted(set(re.findall(r"\{\{(\w+)\}\}", text)) - set(V))
        if missing:
            print(f"{tpl.name}: unknown placeholders: {', '.join(missing)}", file=sys.stderr)
            rc = 1
            continue
        rendered = re.sub(r"\{\{(\w+)\}\}", lambda m: V[m.group(1)], text)
        target = out / tpl.name if not tpl.name.startswith("blog") else out / "blog" / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered)
        print(f"{tpl.name} -> {target.relative_to(ROOT)} ({len(re.findall(r'{{', text))} numbers)")
    return rc


if __name__ == "__main__":
    sys.exit(main())

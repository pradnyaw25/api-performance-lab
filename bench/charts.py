#!/usr/bin/env python3
"""Render publication charts as PNG (2400 px) and animated GIF (1200 px) from a
summary.json (+ optional spread.json).

Usage: bench/charts.py results/aggregate [-o content/charts] [--no-gif]

Every chart is a function of t in [0, 1]: the still is t = 1, the GIF eases t
from 0 to 1 (bars grow, dumbbells extend, heatmap rows reveal) and holds.

Colors follow a validated four-slot categorical palette (blue, orange, aqua,
yellow) assigned in fixed order to rust-axum, go-nethttp, python-fastapi,
python-fastapi-1w; the ratio heatmap uses a blue/orange diverging ramp with a
neutral midpoint at 1×. Text is always ink, never series color.
"""

import argparse
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

SURFACE, INK, INK2, INK3, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1"
SERIES = {"rust-axum": "#2a78d6", "go-nethttp": "#eb6834", "python-fastapi": "#1baf7a", "python-fastapi-1w": "#eda100"}
LABEL = {"rust-axum": "Rust · Axum", "go-nethttp": "Go · net/http", "python-fastapi": "Python · FastAPI ×10 workers",
         "python-fastapi-1w": "Python · FastAPI ×1 worker"}
SHORT = {"rust-axum": "Rust", "go-nethttp": "Go", "python-fastapi": "Python ×10", "python-fastapi-1w": "Python ×1"}
SCEN_LABEL = {"health": "health  ·  GET /health", "get": "get  ·  GET /items/{id}", "list": "list  ·  GET /items?limit=200",
              "create": "create  ·  POST /items", "cpu": "cpu  ·  SHA-256 ×5000", "io": "io  ·  10 ms async wait",
              "mixed": "mixed  ·  5 ms wait + hash + JSON"}
ORDER = ["rust-axum", "go-nethttp", "python-fastapi", "python-fastapi-1w"]
FOOT_SETUP = "Apple M5, 10 cores, macOS; oha, 64 concurrent, 10 s per cell, medians of 4 runs; load generator shares the machine, so read relatively."

plt.rcParams.update({
    "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 11, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.titlecolor": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.grid": False, "legend.frameon": False, "legend.fontsize": 10,
})


# ------------------------------------------------------------------ helpers


def ease(t):
    return 1 - (1 - t) ** 3


def fmt_num(v):
    if v is None:
        return "–"
    if v >= 10000:
        return f"{v/1000:,.0f}k"
    if v >= 1000:
        return f"{v/1000:,.1f}k"
    if v >= 100:
        return f"{v:,.0f}"
    if v >= 10:
        return f"{v:,.1f}"
    return f"{v:,.2f}"


def title(fig, text, sub=None):
    h = fig.get_figheight()
    fig.text(0.02, 1 - 0.18 / h, text, fontsize=17, fontweight="bold", color=INK, va="top", ha="left")
    if sub:
        fig.text(0.02, 1 - 0.52 / h, sub, fontsize=11, color=INK2, va="top", ha="left")


def footer(fig, text):
    fig.text(0.02, 0.012, text, fontsize=8.5, color=INK3, ha="left", va="bottom")


def legend(fig, names):
    y = 1 - 0.78 / fig.get_figheight()
    handles = [plt.Line2D([], [], marker="s", linestyle="", markersize=9, color=SERIES[n], label=LABEL[n]) for n in names]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.015, y), ncol=4, handletextpad=0.4, columnspacing=1.6)


def bar_panel(ax, names, vals, t, fmt, spread_keys=None, spread=None, pad=24, ttl=None, unit=None, xmax=None):
    """Horizontal bars for one panel, grown to fraction t."""
    y = list(range(len(names)))[::-1]
    shown = [(v or 0) * t for v in vals]
    full = [(v or 0) for v in vals]
    ax.barh(y, shown, height=0.55, color=[SERIES[n] for n in names], edgecolor=SURFACE, linewidth=2)
    top = xmax or (max(full) if any(full) else 1)
    for i, (n, yy, v) in enumerate(zip(names, y, vals)):
        sp = spread.get(spread_keys[i]) if spread and spread_keys else None
        if sp and sp["n"] > 1 and t >= 1:
            ax.plot([sp["min"], sp["max"]], [yy, yy], color=INK, linewidth=1.2)
            ax.plot([sp["min"]] * 2, [yy - 0.14, yy + 0.14], color=INK, linewidth=1.2)
            ax.plot([sp["max"]] * 2, [yy - 0.14, yy + 0.14], color=INK, linewidth=1.2)
            top = max(top, sp["max"])
        label_x = (sp["max"] if (sp and sp["n"] > 1 and t >= 1) else shown[i])
        ax.text(label_x + top * 0.02, yy, "–" if v is None else fmt(v * t if t < 1 else v), va="center", ha="left", fontsize=10, color=INK)
    ax.set_yticks(y)
    ax.set_yticklabels([SHORT[n] for n in names], fontsize=10)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=0, labelsize=8.5, colors=INK3)
    ax.set_xlim(0, top * 1.3)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["bottom"].set_visible(False)
    if ttl:
        ax.set_title(ttl, fontsize=12, loc="left", color=INK, pad=pad)
    if unit:
        ax.text(0, 1.03, unit, transform=ax.transAxes, fontsize=9.5, color=INK2)


# ------------------------------------------------------------------- charts


def chart_small_multiples(summary, spread, metric, ttl, sub, unit, higher_better, fmt=fmt_num):
    impls = summary["implementations"]
    names = [n for n in ORDER if impls.get(n, {}).get("scenarios")]
    scenarios = [s["name"] for s in summary["scenarios"]]
    ncol, nrow = 4, math.ceil(len(scenarios) / 4)

    def draw(t, dpi):
        fig, axes = plt.subplots(nrow, ncol, figsize=(16, 2.0 + 2.4 * nrow), dpi=dpi)
        axes = axes.flatten()
        for ax, sc in zip(axes, scenarios):
            vals = [impls[n]["scenarios"].get(sc, {}).get(metric) for n in names]
            bar_panel(ax, names, vals, t, fmt, [f"{n}/scenarios/{sc}/{metric}" for n in names], spread, pad=6,
                      ttl=SCEN_LABEL.get(sc, sc))
            for lab in ax.get_xticklabels():
                lab.set_visible(False)
        for ax in axes[len(scenarios):]:
            ax.axis("off")
        title(fig, ttl, sub)
        legend(fig, names)
        footer(fig, f"{unit}. {'Higher' if higher_better else 'Lower'} is better. Whiskers: min–max across 4 runs. {FOOT_SETUP}")
        fig.subplots_adjust(left=0.05, right=0.985, top=1 - 1.7 / fig.get_figheight(), bottom=0.07, hspace=0.5, wspace=0.35)
        return fig
    return draw


def chart_tail(summary, t, dpi):
    impls = summary["implementations"]
    names = [n for n in ORDER if impls.get(n, {}).get("scenarios")]
    scenarios = ["health", "get", "list", "create", "cpu", "mixed"]
    fig, axes = plt.subplots(2, 3, figsize=(16, 8.0), dpi=dpi)
    for ax, sc in zip(axes.flatten(), scenarios):
        y = list(range(len(names)))[::-1]
        xmax = 0
        for n, yy in zip(names, y):
            s = impls[n]["scenarios"].get(sc, {})
            p50, p99 = s.get("p50_ms"), s.get("p99_ms")
            if p50 is None:
                continue
            end = p50 + (p99 - p50) * t
            ax.plot([p50, end], [yy, yy], color=SERIES[n], linewidth=3, solid_capstyle="round", zorder=2)
            ax.plot(p50, yy, "o", color=SERIES[n], markersize=9, markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=3)
            ax.plot(end, yy, "o", color=SERIES[n], markersize=9, markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=3)
            if t >= 1:
                ax.text(p99 * 1.04 + 0.02, yy, f"p99 {fmt_num(p99)} ms  ·  {p99/p50:.1f}× p50", va="center", fontsize=9.5, color=INK)
            xmax = max(xmax, p99)
        ax.set_yticks(y)
        ax.set_yticklabels([SHORT[n] for n in names], fontsize=10)
        ax.tick_params(axis="y", length=0)
        ax.set_xlim(0, xmax * 1.9)
        ax.xaxis.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", labelsize=8.5, colors=INK3, length=0)
        ax.set_xlabel("ms", fontsize=9, color=INK3, loc="right")
        ax.spines["bottom"].set_color(GRID)
        ax.set_title(SCEN_LABEL.get(sc, sc), fontsize=11, loc="left", color=INK, pad=6)
    title(fig, "Tail latency: median to p99",
          "Left dot is p50, right dot is p99. A short bar is a predictable service; a long one is a service whose median lies to you.")
    legend(fig, names)
    footer(fig, f"io omitted: all four sit at 11–14 ms by construction. {FOOT_SETUP}")
    fig.subplots_adjust(left=0.05, right=0.985, top=1 - 1.7 / fig.get_figheight(), bottom=0.09, hspace=0.6, wspace=0.28)
    return fig


def chart_memory(summary, t, dpi):
    impls = summary["implementations"]
    names = [n for n in ORDER if impls.get(n, {}).get("scenarios")]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.0), dpi=dpi)
    panels = [
        ("Idle RSS", "process tree, MB", [impls[n]["idle_rss_bytes"] / 1e6 for n in names]),
        ("Peak RSS under load (get)", "MB", [impls[n]["scenarios"]["get"]["peak_rss_bytes"] / 1e6 for n in names]),
        ("Memory per idle connection", "KB, 1000 held connections", [(impls[n].get("connections") or {}).get("bytes_per_conn", 0) / 1024 for n in names]),
    ]
    for ax, (ttl, unit, vals) in zip(axes, panels):
        bar_panel(ax, names, vals, t, lambda v: f"{v:,.1f}", ttl=ttl, unit=unit)
    title(fig, "Memory: the fixed cost is the story, not the per-connection cost",
          "Ten Python workers are ten copies of the interpreter and the data. Per connection, Rust (hyper) buffers the most.")
    footer(fig, "RSS summed over the process tree, sampled from ps, medians of 4 runs. Lower is better.")
    fig.subplots_adjust(left=0.06, right=0.985, top=1 - 1.45 / fig.get_figheight(), bottom=0.08, wspace=0.42)
    return fig


def chart_saturation(summary, t, dpi):
    impls = summary["implementations"]
    names = [n for n in ORDER if impls.get(n, {}).get("saturation")]
    sat = "sat-cpu"
    cfg = next(s for s in summary["saturation"] if s["name"] == sat)
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2), dpi=dpi)
    panels = [
        ("Requests that missed the 1 s deadline", "% of requests", [impls[n]["saturation"][sat]["error_pct"] for n in names], lambda v: f"{v:.2f}%"),
        ("p99 latency", "ms (timeout at 1,000)", [impls[n]["saturation"][sat]["p99_ms"] for n in names], lambda v: f"{v:,.0f}"),
        ("Throughput while overloaded", "requests/s", [impls[n]["saturation"][sat]["rps"] for n in names], lambda v: f"{v:,.0f}"),
    ]
    for ax, (ttl, unit, vals, f) in zip(axes, panels):
        bar_panel(ax, names, vals, t, f, ttl=ttl, unit=unit)
    title(fig, "Under CPU overload, only Rust met the deadline for every request",
          f"{cfg['concurrency']} concurrent clients hammering {cfg['path']} for {cfg.get('duration_s', 10)} s with a {cfg['timeout_s']} s per-request timeout.")
    footer(fig, "Same hardware for all four, medians of 4 runs. Go's median is close to Rust's; its tail waits out the deadline. Tokio's work-stealing spreads the delay evenly.")
    fig.subplots_adjust(left=0.06, right=0.985, top=1 - 1.45 / fig.get_figheight(), bottom=0.08, wspace=0.42)
    return fig


def chart_complexity(summary, t, dpi):
    impls = summary["implementations"]
    names = [n for n in ORDER if impls.get(n)]
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.8), dpi=dpi)
    panels = [
        ("Lines of code", "same contract", [impls[n]["loc"] for n in names], lambda v: f"{v:,.0f}"),
        ("Dependencies shipped", "transitive packages", [impls[n].get("deps") for n in names], lambda v: f"{v:,.0f}"),
        ("Cold start", "ms to first healthy response, median", [impls[n].get("cold_start_median_ms") for n in names], lambda v: f"{v:,.0f}"),
        ("Clean build", "seconds (Python: no build step)", [impls[n].get("build_s") for n in names], lambda v: f"{v:,.1f}"),
    ]
    for ax, (ttl, unit, vals, f) in zip(axes, panels):
        bar_panel(ax, names, vals, t, f, ttl=ttl, unit=unit)
    title(fig, "What each implementation costs to write, ship and start",
          "Rust and Go took the same number of lines; Python half. Go ships zero third-party packages.")
    footer(fig, "LOC: non-blank, non-comment. Deps: Cargo.lock / go.mod / pip freeze. Build: cargo --release with LTO; go build; cold caches.")
    fig.subplots_adjust(left=0.06, right=0.985, top=1 - 1.45 / fig.get_figheight(), bottom=0.08, wspace=0.5)
    return fig


def chart_tuning(baseline, tuned):
    b, tt = baseline["implementations"], tuned["implementations"]
    rows = [
        ("Python · list (200 items)\nreturn dict → return ORJSONResponse", "python-fastapi", "list"),
        ("Python ×1 · list", "python-fastapi-1w", "list"),
        ("Rust · cpu (SHA-256 ×5000)\nsha2 default → sha2 `asm` feature", "rust-axum", "cpu"),
    ]

    def draw(t, dpi):
        fig, ax = plt.subplots(figsize=(16, 4.6), dpi=dpi)
        y = list(range(len(rows)))[::-1]
        for (lab, n, sc), yy in zip(rows, y):
            before = b[n]["scenarios"][sc]["rps"]
            after = tt[n]["scenarios"][sc]["rps"]
            pos = before + (after - before) * t
            ax.plot([before, pos], [yy, yy], color=SERIES[n], linewidth=3, solid_capstyle="round", zorder=2)
            ax.plot(before, yy, "o", color=SURFACE, markersize=11, markeredgecolor=SERIES[n], markeredgewidth=2.5, zorder=3)
            ax.plot(pos, yy, "o", color=SERIES[n], markersize=11, markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=3)
            ax.text(before, yy + 0.22, f"{fmt_num(before)} req/s", ha="center", fontsize=9.5, color=INK2)
            if t >= 1:
                ax.text(after, yy + 0.22, f"{fmt_num(after)} req/s", ha="center", fontsize=10, color=INK, fontweight="bold")
                ax.text(after + 1500, yy - 0.02, f"{after/before:.1f}×", va="center", fontsize=12, color=INK, fontweight="bold")
        ax.set_yticks(y)
        ax.set_yticklabels([r[0] for r in rows], fontsize=10.5)
        ax.tick_params(axis="y", length=0)
        ax.set_xlim(0, 80000)
        ax.xaxis.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", length=0, labelsize=9, colors=INK3)
        ax.set_xlabel("requests / s", fontsize=9.5, color=INK3, loc="right")
        ax.spines["bottom"].set_color(GRID)
        ax.set_ylim(-0.6, len(rows) - 0.3)
        title(fig, "Two one-line changes moved the results more than the language choice did",
              "Hollow dot: framework default (first run). Filled dot: after the change (medians of 4 runs). Same code otherwise, same machine, same load.")
        footer(fig, "FastAPI's default path runs jsonable_encoder (pure Python) over the response before orjson serializes it. "
               "Rust's sha2 crate defaults to software SHA-256; Go's crypto/sha256 uses the ARM SHA-2 instructions out of the box.")
        fig.subplots_adjust(left=0.24, right=0.97, top=1 - 0.95 / fig.get_figheight(), bottom=0.14)
        return fig
    return draw


def chart_social(summary, out):
    """1600×900 cover: the finding itself as two mini bar groups, not number tiles."""
    I = summary["implementations"]
    impls = ["rust-axum", "go-nethttp", "python-fastapi"]
    dark = {"rust-axum": "#3987e5", "go-nethttp": "#e8633a", "python-fastapi": "#22b37e"}
    names = {"rust-axum": "Rust", "go-nethttp": "Go", "python-fastapi": "Python"}
    bg, ink, ink2, ink3 = "#0b0b0b", "#f0efec", "#c3c2b7", "#8a8984"
    fig = plt.figure(figsize=(16, 9), dpi=100)
    fig.patch.set_facecolor(bg)
    fig.text(0.06, 0.90, "Benchmarking API performance", fontsize=40, fontweight="bold", color=ink, va="top")
    fig.text(0.06, 0.80, "Python vs Go vs Rust", fontsize=40, fontweight="bold", color=ink, va="top")
    fig.text(0.06, 0.695, "Same API, three production stacks, one laptop. Who is fastest depends on the workload.", fontsize=19, color=ink2, va="top")

    groups = [("CPU-bound request", "cpu", 0.06), ("I/O-bound request", "io", 0.53)]
    for head, sc, x0 in groups:
        vals = {n: I[n]["scenarios"][sc]["rps"] for n in impls}
        best = max(vals.values())
        fig.text(x0, 0.585, head, fontsize=21, fontweight="bold", color=ink, va="center")
        width = 0.24
        for i, n in enumerate(impls):
            y = 0.50 - i * 0.095
            w = width * vals[n] / best
            fig.patches.append(plt.Rectangle((x0 + 0.085, y - 0.03), w, 0.06, transform=fig.transFigure, facecolor=dark[n], edgecolor="none"))
            fig.text(x0 + 0.075, y, names[n], fontsize=18, color=ink2, ha="right", va="center")
            fig.text(x0 + 0.085 + w + 0.008, y, f"{vals[n]:,.0f} req/s", fontsize=17, color=ink if vals[n] == best else ink2,
                     fontweight="bold" if vals[n] == best else "normal", ha="left", va="center")
    fig.text(0.06, 0.19, "Rust wins when the request computes. When it waits, the language barely matters.", fontsize=19, color=ink, va="center")
    fig.text(0.06, 0.09, "7 workloads · 9 metrics · medians of 4 runs · github.com/pradnyaw25/api-performance-lab", fontsize=14, color=ink3, va="center")
    fig.savefig(out, facecolor=bg)
    plt.close(fig)

# ------------------------------------------------- simplified set (Medium)
# One message per chart, at most four bars, big type, no axes to read.

SIMPLE_LABEL = {"rust-axum": "Rust", "go-nethttp": "Go", "python-fastapi": "Python\n10 workers", "python-fastapi-1w": "Python\n1 worker"}


def simple_canvas(ttl, sub, left=0.17, bottom=0.10):
    fig, ax = plt.subplots(figsize=(16, 9), dpi=100)
    fig.text(0.05, 0.94, ttl, fontsize=30, fontweight="bold", color=INK, va="top", ha="left", wrap=True)
    fig.text(0.05, 0.845, sub, fontsize=17, color=INK2, va="top", ha="left")
    fig.subplots_adjust(left=left, right=0.90, top=0.76, bottom=bottom)
    ax.set_xticks([])
    ax.tick_params(axis="y", length=0, labelsize=21, colors=INK)
    for sp in ax.spines.values():
        sp.set_visible(False)
    return fig, ax


def simple_bars(ax, names, vals, labels, xmax=None):
    y = list(range(len(names)))[::-1]
    ax.barh(y, vals, height=0.62, color=[SERIES[n] for n in names], edgecolor=SURFACE, linewidth=2)
    top = xmax or max(vals)
    for yy, v, lab in zip(y, vals, labels):
        ax.text(v + top * 0.015, yy, lab, va="center", ha="left", fontsize=24, color=INK, fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels([SIMPLE_LABEL[n] for n in names])
    ax.set_xlim(0, top * 1.22)
    ax.set_ylim(-0.6, len(names) - 0.4)


def simple_footer(fig, text):
    fig.text(0.05, 0.03, text, fontsize=13, color=INK3, ha="left", va="bottom")


def simple_advantage(summary, out):
    """All three languages on four workloads; bars are throughput as a share of
    the fastest on that workload, labelled with the real requests per second."""
    I = summary["implementations"]
    impls = ["rust-axum", "go-nethttp", "python-fastapi"]
    rows = [("CPU-bound request  (SHA-256 ×5000 per request)", "cpu"), ("Simple lookup  (GET /items/{id})", "get"),
            ("200-item list  (GET /items?limit=200)", "list"), ("I/O-bound request  (10 ms async wait)", "io")]
    fig, ax = plt.subplots(figsize=(16, 11), dpi=100)
    fig.text(0.05, 0.95, "The experiment in one chart: who is fastest depends on the workload",
             fontsize=30, fontweight="bold", color=INK, va="top", ha="left")
    fig.text(0.05, 0.875, "Throughput per workload, each bar as a share of the fastest implementation on that workload. "
             "Same API, same machine, 64 connections.", fontsize=17, color=INK2, va="top", ha="left")
    fig.subplots_adjust(left=0.16, right=0.86, top=0.80, bottom=0.07)
    gap = 1.4
    yt, ylab = [], []
    y = 0.0
    for lab, sc in reversed(rows):
        vals = {n: I[n]["scenarios"][sc]["rps"] for n in impls}
        best = max(vals.values())
        for n in reversed(impls):
            v = vals[n]
            ax.barh(y, v / best, height=0.72, color=SERIES[n], edgecolor=SURFACE, linewidth=2)
            tag = f"{v:,.0f} req/s" + ("   fastest" if v == best else f"   {v / best:.0%} of fastest")
            ax.text(v / best + 0.012, y, tag, va="center", fontsize=19, color=INK, fontweight="bold" if v == best else "normal")
            yt.append(y); ylab.append({"rust-axum": "Rust", "go-nethttp": "Go", "python-fastapi": "Python ×10"}[n])
            y += 1
        ax.text(-0.01, y - 0.25, lab, ha="left", va="bottom", fontsize=20, fontweight="bold", color=INK, transform=ax.get_yaxis_transform())
        y += gap
    ax.set_yticks(yt)
    ax.set_yticklabels(ylab, fontsize=19)
    ax.tick_params(axis="y", length=0, colors=INK)
    ax.set_xticks([])
    ax.set_xlim(0, 1.5)
    ax.set_ylim(-0.6, y - gap + 0.9)
    for sp in ax.spines.values():
        sp.set_visible(False)
    simple_footer(fig, "Medians of 4 runs, Apple M5. Python ×10 is FastAPI on Uvicorn with ten workers. On the I/O-bound request all three are within 9%: the language barely matters while waiting.")
    fig.savefig(out)
    plt.close(fig)


def simple_overload(summary, out):
    I = summary["implementations"]
    names = [n for n in ORDER if I[n].get("saturation")]
    vals = [I[n]["saturation"]["sat-cpu"]["error_pct"] for n in names]
    fig, ax = simple_canvas("Under CPU overload, only Rust met the deadline for every request",
                            "500 concurrent clients, a 1-second timeout per request. Share of requests that timed out.")
    simple_bars(ax, names, vals, [("0%" if v == 0 else f"{v:.1f}%" if v < 10 else f"{v:.0f}%") + (" timed out" if i == 0 else "") for i, v in enumerate(vals)], xmax=70)
    simple_footer(fig, "Rust's p99 under this load: {:,.0f} ms. Go: {:,.0f} ms. Python ×10: {:,.0f} ms. Medians of 4 runs.".format(
        *[I[n]["saturation"]["sat-cpu"]["p99_ms"] for n in names[:3]]))
    fig.savefig(out)
    plt.close(fig)


def simple_tail(summary, out):
    I = summary["implementations"]
    names = [n for n in ORDER if I[n].get("scenarios")]
    fig, ax = simple_canvas("On a simple lookup, Rust's p99 is under a millisecond",
                            "Left dot: median latency. Right dot: p99. A short line is a predictable service.")
    y = list(range(len(names)))[::-1]
    for n, yy in zip(names, y):
        s = I[n]["scenarios"]["get"]
        p50, p99 = s["p50_ms"], s["p99_ms"]
        ax.plot([p50, p99], [yy, yy], color=SERIES[n], linewidth=7, solid_capstyle="round", zorder=2)
        ax.plot([p50, p99], [yy, yy], "o", color=SERIES[n], markersize=22, markeredgecolor=SURFACE, markeredgewidth=3, zorder=3)
        ax.text(p99 + 0.15, yy, f"p99 {p99:.2f} ms   ({p99 / p50:.0f}× the median)", va="center", fontsize=22, color=INK, fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels([SIMPLE_LABEL[n] for n in names])
    ax.set_xlim(0, 9.5)
    ax.set_ylim(-0.6, len(names) - 0.4)
    simple_footer(fig, "GET /items/{id}, 64 concurrent connections, medians of 4 runs. Rust's p99 ranged 0.71–2.04 ms across runs; Go's 1.83–2.23 ms.")
    fig.savefig(out)
    plt.close(fig)


def simple_io(summary, out):
    I = summary["implementations"]
    names = [n for n in ORDER if I[n].get("scenarios")]
    vals = [I[n]["scenarios"]["io"]["rps"] for n in names]
    fig, ax = simple_canvas("When the request is waiting on I/O, the language barely matters",
                            "Requests per second on a 10 ms async wait, 64 connections. All four within 9% of each other; Rust is last.")
    simple_bars(ax, names, vals, [f"{v:,.0f} req/s" for v in vals], xmax=6400)
    ax.axvline(6400, color=INK3, linewidth=1.5, linestyle=(0, (4, 4)))
    ax.text(6400, len(names) - 0.35, "ceiling: 64 ÷ 10 ms", ha="right", va="bottom", fontsize=14, color=INK3)
    ax.set_xlim(0, 6400 * 1.28)
    cpu = [I[n]["scenarios"]["io"]["cpu_ms_per_1k_req"] for n in names]
    simple_footer(fig, f"What differs is the cost of waiting: CPU per 1,000 requests is {cpu[0]:.0f} ms for Rust, {cpu[1]:.0f} ms for Go, {cpu[2]:.0f} ms for Python ×10.")
    fig.savefig(out)
    plt.close(fig)


def simple_memory(summary, out):
    I = summary["implementations"]
    names = [n for n in ORDER if I[n].get("scenarios")]
    vals = [I[n]["idle_rss_bytes"] / 1e6 for n in names]
    fig, ax = simple_canvas("Idle memory: ten Python workers are ten copies of everything",
                            "Resident memory of the whole process tree before any load, in MB. Rust and Go fit in the width of the first bar's label.")
    simple_bars(ax, names, vals, [f"{v:,.0f} MB" for v in vals])
    simple_footer(fig, "Each Uvicorn worker is a separate process with its own interpreter and its own copy of the data; they share nothing in memory.")
    fig.savefig(out)
    plt.close(fig)


def simple_tuning(baseline, tuned, out):
    b, t = baseline["implementations"], tuned["implementations"]
    rows = [("Python, 200-item list\nreturn ORJSONResponse directly\ninstead of a dict", "python-fastapi", "list"),
            ("Rust, SHA-256 endpoint\nsha2 crate with the asm feature\ninstead of the default", "rust-axum", "cpu")]
    fig, ax = simple_canvas("Two one-line changes moved the numbers more than the language did",
                            "Hollow dot: framework default. Filled dot: after the change. Requests per second.", left=0.3)
    y = list(range(len(rows)))[::-1]
    for (lab, n, sc), yy in zip(rows, y):
        before, after = b[n]["scenarios"][sc]["rps"], t[n]["scenarios"][sc]["rps"]
        ax.plot([before, after], [yy, yy], color=SERIES[n], linewidth=7, solid_capstyle="round", zorder=2)
        ax.plot(before, yy, "o", color=SURFACE, markersize=24, markeredgecolor=SERIES[n], markeredgewidth=4, zorder=3)
        ax.plot(after, yy, "o", color=SERIES[n], markersize=24, markeredgecolor=SURFACE, markeredgewidth=3, zorder=3)
        ax.text(before, yy + 0.2, f"{fmt_num(before)}", ha="center", fontsize=18, color=INK2)
        ax.text(after, yy + 0.2, f"{fmt_num(after)}", ha="center", fontsize=18, color=INK)
        ax.text(after + 1800, yy, f"{after / before:.1f}× faster", va="center", fontsize=24, color=INK, fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=18)
    ax.set_xlim(0, 52000)
    ax.set_ylim(-0.6, len(rows) - 0.3)
    simple_footer(fig, "FastAPI's default path runs a pure-Python encoder before orjson. Rust's sha2 crate defaults to software SHA-256; Go's standard library uses the hardware instructions.")
    fig.savefig(out)
    plt.close(fig)


def render_simple(summary, baseline, out):
    out.mkdir(parents=True, exist_ok=True)
    simple_advantage(summary, out / "s1-rust-advantage.png")
    simple_overload(summary, out / "s2-overload.png")
    simple_tail(summary, out / "s3-tail-latency.png")
    simple_io(summary, out / "s4-io-bound.png")
    simple_memory(summary, out / "s5-memory.png")
    if baseline:
        simple_tuning(baseline, summary, out / "s6-tuning.png")


# ------------------------------------------------------------------ render


def fig_to_image(fig):
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())
    return Image.fromarray(buf[..., :3].copy())


def render(draw, out_dir, stem, gif=True, grow_frames=26, frame_ms=40, start_hold_ms=500, end_hold_ms=2800):
    fig = draw(1.0, 150)
    fig.savefig(out_dir / f"{stem}.png")
    plt.close(fig)
    if not gif:
        return
    frames = []
    for i in range(grow_frames + 1):
        fig = draw(ease(i / grow_frames), 75)
        frames.append(fig_to_image(fig))
        plt.close(fig)
    pal = frames[-1].quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    durations = [frame_ms] * len(q)
    durations[0], durations[-1] = start_hold_ms, end_hold_ms
    q[0].save(out_dir / f"{stem}.gif", save_all=True, append_images=q[1:], duration=durations, loop=0, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("-o", "--out", default=str(ROOT / "content" / "charts"))
    ap.add_argument("--baseline", default=str(ROOT / "results" / "20261126-215740"))
    ap.add_argument("--no-gif", action="store_true")
    ap.add_argument("--simple-only", action="store_true", help="render only the simplified PNG set")
    args = ap.parse_args()
    run = Path(args.run_dir)
    summary = json.loads((run / "summary.json").read_text())
    spread = json.loads((run / "spread.json").read_text()) if (run / "spread.json").exists() else {}
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    gif = not args.no_gif
    base = Path(args.baseline)
    if args.simple_only:
        render_simple(summary, json.loads((base / "summary.json").read_text()) if (base / "summary.json").exists() else None, out / "simple")
        return

    render(chart_small_multiples(summary, spread, "rps", "Throughput by workload",
                                 "Requests per second at 64 concurrent connections. Each panel has its own scale; the question is the gap within a panel, not across panels.",
                                 "requests/s", True), out, "02-throughput", gif)
    render(lambda t, dpi: chart_tail(summary, t, dpi), out, "03-tail-latency", gif)
    render(chart_small_multiples(summary, spread, "cpu_ms_per_1k_req", "CPU cost per 1,000 requests",
                                 "Server CPU-milliseconds consumed per 1,000 requests. Equal throughput at 3× the CPU is 3× less headroom.",
                                 "CPU-ms per 1k requests", False, fmt=lambda v: "–" if v is None else f"{v:,.0f}"), out, "04-cpu-per-1k", gif)
    render(lambda t, dpi: chart_memory(summary, t, dpi), out, "05-memory", gif)
    render(lambda t, dpi: chart_saturation(summary, t, dpi), out, "06-overload", gif)
    render(lambda t, dpi: chart_complexity(summary, t, dpi), out, "07-complexity", gif)
    if (base / "summary.json").exists():
        render(chart_tuning(json.loads((base / "summary.json").read_text()), summary), out, "08-tuning", gif)
    chart_social(summary, out / "00-social-card.png")
    render_simple(summary, json.loads((base / "summary.json").read_text()) if (base / "summary.json").exists() else None, out / "simple")
    for f in sorted(out.iterdir()):
        if f.is_dir():
            continue
        print(f"{f.name:28s} {f.stat().st_size/1e6:5.2f} MB")


if __name__ == "__main__":
    main()

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
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402
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


def chart_ratios(summary, t, dpi):
    impls = summary["implementations"]
    others = [n for n in ORDER[1:] if impls.get(n, {}).get("scenarios")]
    scenarios = [s["name"] for s in summary["scenarios"]]
    r = impls["rust-axum"]["scenarios"]
    panels = [
        ("Throughput", "Rust ÷ alternative", lambda rs, o: (rs.get("rps") or 0) / (o.get("rps") or 1)),
        ("p99 latency", "alternative ÷ Rust", lambda rs, o: (o.get("p99_ms") or 0) / (rs.get("p99_ms") or 1)),
        ("CPU per 1k requests", "alternative ÷ Rust", lambda rs, o: (o.get("cpu_ms_per_1k_req") or 0) / (rs.get("cpu_ms_per_1k_req") or 1)),
        ("Peak memory", "alternative ÷ Rust", lambda rs, o: (o.get("peak_rss_bytes") or 0) / (rs.get("peak_rss_bytes") or 1)),
    ]
    cmap = LinearSegmentedColormap.from_list("div", ["#eb6834", "#f6c9b5", "#ebebe8", "#b7d3f6", "#2a78d6"])
    norm = TwoSlopeNorm(vmin=math.log10(1 / 4), vcenter=0, vmax=math.log10(16))
    rows_shown = math.ceil(t * len(scenarios) - 1e-9)
    fig, axes = plt.subplots(1, len(panels), figsize=(16, 6.6), dpi=dpi)
    for ax, (ttl, sub, f) in zip(axes, panels):
        grid = [[f(r.get(sc, {}), impls[o]["scenarios"].get(sc, {})) for o in others] for sc in scenarios]
        logs = [[math.log10(max(v, 1e-9)) for v in row] for row in grid]
        ax.imshow(logs, cmap=cmap, norm=norm, aspect="auto")
        for i, row in enumerate(grid):
            for j, v in enumerate(row):
                if i >= rows_shown:
                    continue
                lum = norm(math.log10(max(v, 1e-9)))
                col = SURFACE if (lum > 0.78 or lum < 0.18) else INK
                txt = f"{v:.1f}×" if v < 10 else f"{v:.0f}×"
                ax.text(j, i, txt, ha="center", va="center", fontsize=11, color=col, fontweight="bold" if abs(math.log10(v)) > 0.3 else "normal")
        if rows_shown < len(scenarios):  # hide unrevealed rows
            ax.add_patch(plt.Rectangle((-0.5, rows_shown - 0.5), len(others), len(scenarios) - rows_shown, color=SURFACE, zorder=5))
        ax.set_xticks(range(len(others)))
        ax.set_xticklabels([SHORT[o] for o in others], fontsize=10)
        ax.set_yticks(range(len(scenarios)))
        ax.set_yticklabels(scenarios if ax is axes[0] else [""] * len(scenarios), fontsize=10.5)
        ax.tick_params(length=0)
        ax.set_title(f"{ttl}\n", fontsize=12.5, loc="left", color=INK, pad=2)
        ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=9.5, color=INK2, va="bottom")
        for s in ax.spines.values():
            s.set_visible(False)
        for k in range(len(others) + 1):
            ax.axvline(k - 0.5, color=SURFACE, linewidth=3, zorder=6)
        for k in range(len(scenarios) + 1):
            ax.axhline(k - 0.5, color=SURFACE, linewidth=3, zorder=6)
    title(fig, "Where Rust's advantage actually is",
          "Every cell is a ratio against the Rust implementation on the same workload. Blue: Rust is better by that factor. Orange: the alternative won. "
          "Grey: the language did not matter.")
    footer(fig, "Same contract, same machine (Apple M5, 10 cores, macOS), oha at 64 concurrent connections, 10 s per cell, medians of 4 runs. "
           "io and mixed are bound by their 10 ms / 5 ms waits by design: throughput cannot exceed 64 ÷ wait.")
    fig.subplots_adjust(left=0.065, right=0.99, top=0.76, bottom=0.07, wspace=0.14)
    return fig


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
    impls = summary["implementations"]
    r, g, p = impls["rust-axum"]["scenarios"], impls["go-nethttp"]["scenarios"], impls["python-fastapi"]["scenarios"]
    fig = plt.figure(figsize=(16, 9), dpi=100)
    fig.patch.set_facecolor("#0b0b0b")
    fig.text(0.06, 0.86, "Benchmarking API performance: Python vs Go vs Rust", fontsize=36, fontweight="bold", color="#f0efec", va="top")
    fig.text(0.06, 0.745, "Same API, three production stacks, nine metrics. Where does Rust actually matter?", fontsize=20, color="#c3c2b7", va="top")
    tiles = [
        (f"{r['cpu']['rps']/g['cpu']['rps']:.1f}×", "faster than Go", "on CPU-bound requests", "#3987e5"),
        (f"{r['get']['p99_ms']:.2f} ms", "p99 latency", f"Go {g['get']['p99_ms']:.1f} ms · Python {p['get']['p99_ms']:.1f} ms", "#3987e5"),
        ("≈ equal", "throughput when I/O-bound", f"Python {p['io']['rps']/r['io']['rps']:.2f}× Rust · Go {g['io']['rps']/r['io']['rps']:.2f}×", "#d95926"),
    ]
    for i, (big, lab, sub, col) in enumerate(tiles):
        x = 0.06 + i * 0.31
        fig.patches.append(plt.Rectangle((x, 0.26), 0.27, 0.4, transform=fig.transFigure, facecolor="#1a1a19", edgecolor="none", zorder=0))
        fig.text(x + 0.02, 0.57, big, fontsize=52, fontweight="bold", color=col, va="center")
        fig.text(x + 0.02, 0.43, lab, fontsize=19, color="#f0efec", va="center")
        fig.text(x + 0.02, 0.36, sub, fontsize=14, color="#c3c2b7", va="center")
    fig.text(0.06, 0.14, "API Performance Lab · github.com/pradnyaw25/api-performance-lab", fontsize=16, color="#8a8984")
    fig.savefig(out, facecolor=fig.get_facecolor())
    plt.close(fig)


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
    args = ap.parse_args()
    run = Path(args.run_dir)
    summary = json.loads((run / "summary.json").read_text())
    spread = json.loads((run / "spread.json").read_text()) if (run / "spread.json").exists() else {}
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    gif = not args.no_gif

    render(lambda t, dpi: chart_ratios(summary, t, dpi), out, "01-where-rust-wins", gif, grow_frames=14, frame_ms=110)
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
    base = Path(args.baseline)
    if (base / "summary.json").exists():
        render(chart_tuning(json.loads((base / "summary.json").read_text()), summary), out, "08-tuning", gif)
    chart_social(summary, out / "00-social-card.png")
    for f in sorted(out.iterdir()):
        print(f"{f.name:28s} {f.stat().st_size/1e6:5.2f} MB")


if __name__ == "__main__":
    main()

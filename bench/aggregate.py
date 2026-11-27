#!/usr/bin/env python3
"""Aggregate several runs into medians with min–max spread.

Usage: bench/aggregate.py results/<run-a> results/<run-b> ... [-o results/aggregate]

Writes <out>/summary.json (same shape as a single run's summary.json, every
numeric leaf replaced by its median across runs, so report.py and charts.py
read it unchanged), <out>/spread.json ({"impl/section/.../metric": {min, max,
values}}), and <out>/REPORT.md rendered with "median of N runs" noted.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bench"))
import report  # noqa: E402


def leaves(obj, path=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from leaves(v, path + (str(k),))
    elif isinstance(obj, list) and obj and all(isinstance(x, (int, float)) for x in obj):
        yield path, list(obj)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        yield path, obj


def set_path(obj, path, value):
    for k in path[:-1]:
        obj = obj[k]
    obj[path[-1]] = value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("-o", "--out", default=str(ROOT / "results" / "aggregate"))
    args = ap.parse_args()

    summaries = [json.loads((Path(r) / "summary.json").read_text()) for r in args.runs]
    base = json.loads(json.dumps(summaries[0]))  # deep copy; medians written in place
    spread = {}
    skip_roots = {"scenarios", "saturation"}  # the scenario definitions, not results

    for path, _ in leaves(summaries[0]["implementations"]):
        full = ("implementations",) + path
        vals = []
        for s in summaries:
            try:
                v = s
                for k in full:
                    v = v[k]
            except (KeyError, TypeError):
                continue
            if isinstance(v, list):
                vals.extend(v)
            elif isinstance(v, (int, float)):
                vals.append(v)
        if not vals:
            continue
        key = "/".join(path)
        if isinstance(vals[0], float) or any(isinstance(v, float) for v in vals):
            med = statistics.median(vals)
            med = round(med, 4)
        else:
            med = int(statistics.median(vals))
        if path[-1] == "cold_start_ms":
            set_path(base, full, vals)  # keep all samples
            set_path(base, full[:-1] + ("cold_start_median_ms",), round(statistics.median(vals), 1))
        else:
            set_path(base, full, med)
        spread[key] = {"min": min(vals), "max": max(vals), "n": len(vals), "values": vals}

    base["run_id"] = f"aggregate of {len(summaries)} runs"
    base["settings"]["runs"] = [s["run_id"] for s in summaries]
    base["settings"]["aggregate"] = f"median of {len(summaries)} runs; spread in spread.json"

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(base, indent=2))
    (out / "spread.json").write_text(json.dumps(spread, indent=1))
    md = report.render(base, spread=spread)
    (out / "REPORT.md").write_text(md)
    print(f"aggregated {len(summaries)} runs -> {out.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()

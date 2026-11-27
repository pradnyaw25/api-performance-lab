#!/usr/bin/env python3
"""Benchmark orchestrator for API Performance Lab.

For each implementation: build, start, wait for /health, run the shared
contract test (refuse to benchmark an implementation that fails it), warm up,
then run every scenario with `oha` while sampling process-tree RSS and CPU
time. Writes results/<run-id>/{raw/*.json, summary.json, REPORT.md} and copies
the report to results/REPORT.md.

Usage:
  bench/run.py                       # full run from bench/config.json
  bench/run.py --contract-only       # start each impl, run contract test, stop
  bench/run.py --impl rust-axum --scenario cpu --duration 5
  bench/run.py --clean               # clean before build so build time is a cold build
"""

import argparse
import datetime as dt
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bench"))
import report  # noqa: E402

CPUS = os.cpu_count() or 1


def log(msg):
    print(f"[bench] {msg}", flush=True)


# ---------------------------------------------------------------- process tree


def _ps_snapshot():
    """pid -> (ppid, rss_kb, cpu_seconds) for every process."""
    out = subprocess.run(
        ["ps", "-axo", "pid=,ppid=,rss=,cputime="], capture_output=True, text=True
    ).stdout
    snap = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        try:
            pid, ppid, rss = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            continue
        snap[pid] = (ppid, rss, _parse_cputime(parts[3]))
    return snap


def _parse_cputime(s):
    # "0:01.23" or "1:02:03.45" or "3-01:02:03"
    days = 0
    if "-" in s:
        d, s = s.split("-", 1)
        days = int(d)
    parts = s.split(":")
    secs = 0.0
    for p in parts:
        secs = secs * 60 + float(p)
    return days * 86400 + secs


def tree_stats(root_pid):
    """(total_rss_bytes, total_cpu_seconds) over root_pid and its descendants."""
    snap = _ps_snapshot()
    children = {}
    for pid, (ppid, _, _) in snap.items():
        children.setdefault(ppid, []).append(pid)
    rss = cpu = 0.0
    stack = [root_pid]
    while stack:
        pid = stack.pop()
        if pid not in snap:
            continue
        _, r, c = snap[pid]
        rss += r * 1024
        cpu += c
        stack.extend(children.get(pid, []))
    return rss, cpu


class Sampler(threading.Thread):
    def __init__(self, pid, interval=0.25):
        super().__init__(daemon=True)
        self.pid, self.interval = pid, interval
        self.peak_rss = 0
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            rss, _ = tree_stats(self.pid)
            self.peak_rss = max(self.peak_rss, rss)
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()
        self.join()
        return self.peak_rss


# ------------------------------------------------------------------- services


def port_free(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def wait_healthy(port, timeout=60):
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.1)
    return False


def start_impl(impl):
    port = impl["port"]
    if not port_free(port):
        raise RuntimeError(f"port {port} already in use; stop whatever is on it")
    cwd = ROOT / impl["cwd"]
    cmd = [c.format(port=port, cpus=CPUS) for c in impl["cmd"]]
    env = dict(os.environ, PORT=str(port))
    log(f"starting {impl['name']}: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd, cwd=cwd, env=env, start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    t0 = time.time()
    if not wait_healthy(port):
        stop_impl(proc)
        err = proc.stderr.read()[-2000:] if proc.stderr else ""
        raise RuntimeError(f"{impl['name']} never became healthy\n{err}")
    startup_s = time.time() - t0
    time.sleep(0.5)  # let workers settle before the idle measurement
    return proc, startup_s


def stop_impl(proc):
    try:
        os.killpg(os.getpgid(proc.pid), 15)
        proc.wait(timeout=10)
    except Exception:
        try:
            os.killpg(os.getpgid(proc.pid), 9)
        except Exception:
            pass


def build_impl(impl, clean):
    if not impl.get("build"):
        return {"build_s": None, "artifact_bytes": None, "cold": None}
    cwd = ROOT / impl["cwd"]
    if clean and impl.get("clean"):
        subprocess.run(impl["clean"], cwd=cwd, check=True, capture_output=True)
    log(f"building {impl['name']}{' (clean)' if clean else ''}")
    t0 = time.time()
    subprocess.run(impl["build"], cwd=cwd, check=True, capture_output=True)
    build_s = time.time() - t0
    art = cwd / impl["artifact"]
    return {"build_s": round(build_s, 2), "artifact_bytes": art.stat().st_size, "cold": clean}


def loc(impl):
    n = 0
    for f in impl["src"]:
        for line in (ROOT / impl["cwd"] / f).read_text().splitlines():
            s = line.strip()
            if s and not s.startswith(("//", "#", "///", "//!")):
                n += 1
    return n


# ------------------------------------------------------------------------ oha


def run_oha(url, scenario, duration, concurrency):
    cmd = ["oha", "-z", f"{duration}s", "-c", str(concurrency), "--no-tui", "--output-format", "json"]
    if scenario.get("method", "GET") != "GET":
        cmd += ["-m", scenario["method"]]
    if "body" in scenario:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(scenario["body"])]
    cmd.append(url)
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"oha failed: {out.stderr[-500:]}")
    return json.loads(out.stdout)


def summarize_oha(j):
    s = j.get("summary", {})
    pct = j.get("latencyPercentiles", {})
    codes = j.get("statusCodeDistribution", {})
    errors = j.get("errorDistribution", {})
    # summary.total is the elapsed time, not a count; count completed responses.
    # "aborted due to deadline" is oha cancelling in-flight requests at the end
    # of the window, not a server error.
    errors = {k: v for k, v in errors.items() if "deadline" not in k}
    completed = sum(codes.values())
    ok = sum(v for k, v in codes.items() if str(k).startswith("2"))
    total = completed + sum(errors.values())
    err_count = total - ok

    def ms(key):
        v = pct.get(key)
        return None if v is None else round(v * 1000, 3)

    return {
        "rps": round(s.get("requestsPerSec", 0.0), 1),
        "total": total,
        "errors": err_count,
        "error_pct": round(100.0 * err_count / total, 3) if total else None,
        "p50_ms": ms("p50"),
        "p90_ms": ms("p90"),
        "p99_ms": ms("p99"),
        "p999_ms": ms("p99.9"),
        "max_ms": round(s.get("slowest", 0.0) * 1000, 3),
        "mean_ms": round(s.get("average", 0.0) * 1000, 3),
        "status_codes": codes,
        "error_kinds": errors,
    }


# ----------------------------------------------------------------------- main


def contract_ok(impl):
    cmd = [sys.executable, str(ROOT / "tests" / "contract_test.py")]
    if impl.get("process_local_state"):
        cmd.append("--process-local-state")
    cmd.append(f"http://127.0.0.1:{impl['port']}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout, end="")
    return r.returncode == 0, r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "bench" / "config.json"))
    ap.add_argument("--impl", action="append", help="limit to implementation name(s)")
    ap.add_argument("--scenario", action="append", help="limit to scenario name(s)")
    ap.add_argument("--duration", type=int)
    ap.add_argument("--concurrency", type=int)
    ap.add_argument("--warmup", type=int)
    ap.add_argument("--clean", action="store_true", help="clean before build (cold build time)")
    ap.add_argument("--contract-only", action="store_true")
    ap.add_argument("--no-build", action="store_true")
    args = ap.parse_args()

    if not shutil.which("oha") and not args.contract_only:
        sys.exit("oha not found: brew install oha")

    cfg = json.loads(Path(args.config).read_text())
    duration = args.duration or cfg["duration_s"]
    concurrency = args.concurrency or cfg["concurrency"]
    warmup = args.warmup if args.warmup is not None else cfg["warmup_s"]
    impls = [i for i in cfg["implementations"] if not args.impl or i["name"] in args.impl]
    scenarios = [s for s in cfg["scenarios"] if not args.scenario or s["name"] in args.scenario]

    run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = ROOT / "results" / run_id
    raw_dir = out_dir / "raw"

    summary = {
        "run_id": run_id,
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "machine": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpus": CPUS,
            "cpu": _cpu_brand(),
        },
        "settings": {"duration_s": duration, "warmup_s": warmup, "concurrency": concurrency,
                     "load_generator": _oha_version()},
        "scenarios": scenarios,
        "implementations": {},
    }

    exit_code = 0
    for impl in impls:
        name = impl["name"]
        entry = {"port": impl["port"], "loc": loc(impl), "toolchain": _toolchain(impl)}
        try:
            if not args.no_build:
                entry.update(build_impl(impl, args.clean))
            proc, startup_s = start_impl(impl)
        except Exception as e:
            log(f"{name}: FAILED to build/start: {e}")
            entry["error"] = str(e)
            summary["implementations"][name] = entry
            exit_code = 1
            continue
        try:
            entry["startup_s"] = round(startup_s, 3)
            entry["idle_rss_bytes"], _ = tree_stats(proc.pid)
            ok, text = contract_ok(impl)
            entry["contract"] = "pass" if ok else "fail"
            entry["contract_notes"] = [l.strip()[6:] for l in text.splitlines() if l.strip().startswith("note:")]
            if not ok:
                log(f"{name}: contract test FAILED, not benchmarking")
                exit_code = 1
                continue
            if args.contract_only:
                continue

            entry["scenarios"] = {}
            base = f"http://127.0.0.1:{impl['port']}"
            for sc in scenarios:
                url = base + sc["path"]
                if warmup:
                    run_oha(url, sc, warmup, concurrency)
                _, cpu0 = tree_stats(proc.pid)
                sampler = Sampler(proc.pid)
                sampler.start()
                t0 = time.time()
                j = run_oha(url, sc, duration, concurrency)
                wall = time.time() - t0
                peak_rss = sampler.stop()
                _, cpu1 = tree_stats(proc.pid)
                raw_dir.mkdir(parents=True, exist_ok=True)
                (raw_dir / f"{name}-{sc['name']}.json").write_text(json.dumps(j, indent=1))
                res = summarize_oha(j)
                cpu_s = max(cpu1 - cpu0, 0.0)
                res["peak_rss_bytes"] = peak_rss
                res["cpu_seconds"] = round(cpu_s, 3)
                res["cpu_ms_per_req"] = round(1000 * cpu_s / res["total"], 4) if res["total"] else None
                res["server_cpu_util"] = round(cpu_s / wall / CPUS, 3)  # fraction of all cores
                entry["scenarios"][sc["name"]] = res
                log(f"{name:18s} {sc['name']:7s} {res['rps']:>10.0f} rps  p50 {res['p50_ms']:>8.2f}ms  "
                    f"p99 {res['p99_ms']:>8.2f}ms  peak {peak_rss/1e6:>7.1f}MB  cpu/req {res['cpu_ms_per_req']}ms  err {res['errors']}")
        finally:
            stop_impl(proc)
            summary["implementations"][name] = entry

    if args.contract_only:
        return exit_code

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    md = report.render(summary)
    (out_dir / "REPORT.md").write_text(md)
    (ROOT / "results" / "REPORT.md").write_text(md)
    log(f"wrote {out_dir.relative_to(ROOT)}/REPORT.md and results/REPORT.md")
    return exit_code


def _cpu_brand():
    try:
        return subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
    except Exception:
        return platform.processor()


def _oha_version():
    try:
        return subprocess.run(["oha", "--version"], capture_output=True, text=True).stdout.strip()
    except Exception:
        return "oha (unknown)"


def _toolchain(impl):
    try:
        if impl["name"].startswith("rust"):
            return subprocess.run(["rustc", "--version"], capture_output=True, text=True).stdout.strip()
        if impl["name"].startswith("go"):
            return subprocess.run(["go", "version"], capture_output=True, text=True).stdout.strip()
        py = ROOT / impl["cwd"] / ".venv" / "bin" / "python"
        v = subprocess.run([str(py), "-c",
                            "import sys,fastapi,uvicorn;print(f'Python {sys.version.split()[0]}, FastAPI {fastapi.__version__}, Uvicorn {uvicorn.__version__}')"],
                           capture_output=True, text=True).stdout.strip()
        return v or "python (venv missing: make setup)"
    except Exception as e:
        return f"unknown ({e})"


if __name__ == "__main__":
    sys.exit(main())

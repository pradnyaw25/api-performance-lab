#!/usr/bin/env python3
"""Benchmark orchestrator for API Performance Lab.

For each implementation:
  1. build (cold with --clean), count dependencies and lines of code
  2. cold start: start/stop N times, median time to first healthy /health
  3. run the shared contract test; refuse to benchmark on failure
  4. scenarios: fresh process each, warm-up, then `oha` at fixed concurrency
     while sampling process-tree RSS and CPU time
  5. saturation: high concurrency with a per-request timeout -> error rate
  6. memory per open connection: hold N idle keep-alive connections
  7. recovery: probe latency, spike, probe again, settle, probe again

Writes results/<run-id>/{raw/*.json, summary.json, REPORT.md} and copies the
report to results/REPORT.md.

Usage:
  bench/run.py                       # full run from bench/config.json
  bench/run.py --contract-only       # start each impl, run contract test, stop
  bench/run.py --impl rust-axum --scenario cpu --duration 5
  bench/run.py --clean               # clean before build so build time is a cold build
  bench/run.py --skip saturation --skip recovery
"""

import argparse
import datetime as dt
import http.client
import json
import os
import platform
import resource
import shutil
import socket
import statistics
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


def ensure_fd_limit(want=65536):
    """Raise the open-files soft limit; children (services, oha) inherit it."""
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    cap = want if hard == resource.RLIM_INFINITY else min(want, hard)
    if soft < cap:
        resource.setrlimit(resource.RLIMIT_NOFILE, (cap, hard))
    return resource.getrlimit(resource.RLIMIT_NOFILE)[0]


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
    secs = 0.0
    for p in s.split(":"):
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
    """Seconds until GET /health returns 200, or None. Polls every 2 ms."""
    t0 = time.perf_counter()
    deadline = t0 + timeout
    url = f"http://127.0.0.1:{port}/health"
    while time.perf_counter() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return time.perf_counter() - t0
        except Exception:
            time.sleep(0.002)
    return None


def start_impl(impl, quiet=False):
    port = impl["port"]
    if not port_free(port):
        raise RuntimeError(f"port {port} already in use; stop whatever is on it")
    cwd = ROOT / impl["cwd"]
    cmd = [c.format(port=port, cpus=CPUS) for c in impl["cmd"]]
    env = dict(os.environ, PORT=str(port), **{k: str(v) for k, v in impl.get("env", {}).items()})
    if not quiet:
        log(f"starting {impl['name']}: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd, cwd=cwd, env=env, start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    startup = wait_healthy(port)
    if startup is None:
        stop_impl(proc)
        err = proc.stderr.read()[-2000:] if proc.stderr else ""
        raise RuntimeError(f"{impl['name']} never became healthy\n{err}")
    return proc, startup


def stop_impl(proc):
    try:
        os.killpg(os.getpgid(proc.pid), 15)
        proc.wait(timeout=10)
    except Exception:
        try:
            os.killpg(os.getpgid(proc.pid), 9)
        except Exception:
            pass


def restart(impl, proc):
    stop_impl(proc)
    deadline = time.time() + 5
    while not port_free(impl["port"]) and time.time() < deadline:
        time.sleep(0.01)
    time.sleep(0.2)
    proc, _ = start_impl(impl, quiet=True)
    time.sleep(0.5)  # let workers settle before idle measurements
    return proc


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


def dep_count(impl):
    """Direct + transitive third-party packages the service ships with."""
    cwd = ROOT / impl["cwd"]
    try:
        if impl.get("deps") == "cargo":
            lock = (cwd / "Cargo.lock").read_text()
            return lock.count("[[package]]") - 1
        if impl.get("deps") == "go":
            out = subprocess.run(["go", "list", "-m", "all"], cwd=cwd, capture_output=True, text=True).stdout
            return max(len(out.strip().splitlines()) - 1, 0)
        if impl.get("deps") == "pip":
            out = subprocess.run([str(cwd / ".venv/bin/pip"), "freeze"], capture_output=True, text=True).stdout
            return len(out.strip().splitlines())
    except Exception:
        pass
    return None


# ------------------------------------------------------------------------ oha


def run_oha(url, scenario, duration, concurrency, timeout_s=None):
    cmd = ["oha", "-z", f"{duration}s", "-c", str(concurrency), "--no-tui", "--output-format", "json"]
    if timeout_s:
        cmd += ["-t", f"{timeout_s}s"]
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
        "p95_ms": ms("p95"),
        "p99_ms": ms("p99"),
        "p999_ms": ms("p99.9"),
        "max_ms": round(s.get("slowest", 0.0) * 1000, 3),
        "mean_ms": round(s.get("average", 0.0) * 1000, 3),
        "status_codes": codes,
        "error_kinds": errors,
    }


def measured_run(proc, url, sc, duration, concurrency, timeout_s=None):
    """One oha run with RSS sampling and CPU accounting around it."""
    idle_rss, cpu0 = tree_stats(proc.pid)
    sampler = Sampler(proc.pid)
    sampler.start()
    t0 = time.time()
    j = run_oha(url, sc, duration, concurrency, timeout_s)
    wall = time.time() - t0
    peak_rss = sampler.stop()
    _, cpu1 = tree_stats(proc.pid)
    res = summarize_oha(j)
    cpu_s = max(cpu1 - cpu0, 0.0)
    res["concurrency"] = concurrency
    res["peak_rss_bytes"] = peak_rss
    res["idle_rss_bytes"] = idle_rss
    res["rss_growth_per_req_bytes"] = round((peak_rss - idle_rss) / res["total"]) if res["total"] else None
    res["cpu_seconds"] = round(cpu_s, 3)
    res["cpu_ms_per_1k_req"] = round(1000 * 1000 * cpu_s / res["total"], 2) if res["total"] else None
    res["server_cpu_util"] = round(cpu_s / wall / CPUS, 3)  # fraction of all cores
    return res, j


# ------------------------------------------------------------- other probes


def probe_latency(port, path, n):
    """Sequential keep-alive requests from one connection; p50/p99 in ms."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    lat = []
    for _ in range(n):
        t = time.perf_counter()
        conn.request("GET", path)
        r = conn.getresponse()
        r.read()
        lat.append((time.perf_counter() - t) * 1000)
    conn.close()
    lat.sort()
    return {"p50_ms": round(lat[len(lat) // 2], 3), "p99_ms": round(lat[min(len(lat) - 1, int(len(lat) * 0.99))], 3)}


def connections_test(proc, port, n, hold_s):
    """Open n keep-alive connections, one request each, hold them idle, measure RSS."""
    idle, _ = tree_stats(proc.pid)
    socks, failed = [], 0
    req = b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: keep-alive\r\n\r\n"
    for _ in range(n):
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=5)
            s.sendall(req)
            socks.append(s)
        except OSError:
            failed += 1
    for s in socks:
        s.settimeout(5)
        try:
            s.recv(4096)
        except OSError:
            pass
    time.sleep(hold_s)
    held, _ = tree_stats(proc.pid)
    for s in socks:
        s.close()
    time.sleep(1.0)
    after, _ = tree_stats(proc.pid)
    opened = len(socks)
    return {
        "connections": opened,
        "failed": failed,
        "idle_rss_bytes": idle,
        "held_rss_bytes": held,
        "after_close_rss_bytes": after,
        "bytes_per_conn": round((held - idle) / opened) if opened else None,
    }


def recovery_test(proc, port, cfg):
    """Latency probe -> spike -> probe -> settle -> probe. RSS at each point."""
    probe_path, n = cfg.get("probe_path", "/items/42"), cfg.get("probe_requests", 300)
    idle, _ = tree_stats(proc.pid)
    pre = probe_latency(port, probe_path, n)
    sampler = Sampler(proc.pid, interval=0.1)
    sampler.start()
    spike = run_oha(f"http://127.0.0.1:{port}{cfg['spike_path']}", {}, cfg["spike_s"], cfg["spike_concurrency"])
    peak = sampler.stop()
    rss_after, _ = tree_stats(proc.pid)
    post = probe_latency(port, probe_path, n)
    time.sleep(cfg["settle_s"])
    rss_settled, _ = tree_stats(proc.pid)
    settled = probe_latency(port, probe_path, n)
    grown = max(peak - idle, 1)
    return {
        "spike": {"path": cfg["spike_path"], "concurrency": cfg["spike_concurrency"], "seconds": cfg["spike_s"],
                  "rps": round(spike["summary"]["requestsPerSec"]), "errors": summarize_oha(spike)["errors"]},
        "idle_rss_bytes": idle,
        "peak_rss_bytes": peak,
        "rss_after_spike_bytes": rss_after,
        "rss_after_settle_bytes": rss_settled,
        "settle_s": cfg["settle_s"],
        "retained_pct": round(100 * (rss_settled - idle) / grown, 1),
        "probe_pre": pre,
        "probe_after_spike": post,
        "probe_after_settle": settled,
    }


def cold_start(impl, runs):
    """Start/stop `runs` times; return times and the last process still running."""
    times = []
    proc = None
    for i in range(runs):
        if proc is not None:
            stop_impl(proc)
            deadline = time.time() + 5
            while not port_free(impl["port"]) and time.time() < deadline:
                time.sleep(0.01)
            time.sleep(0.2)
        proc, t = start_impl(impl, quiet=i > 0)
        times.append(round(t * 1000, 1))
    time.sleep(0.5)
    return proc, times


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
    ap.add_argument("--skip", action="append", default=[], choices=["scenarios", "saturation", "connections", "recovery", "coldstart"])
    ap.add_argument("--duration", type=int)
    ap.add_argument("--concurrency", type=int)
    ap.add_argument("--warmup", type=int)
    ap.add_argument("--clean", action="store_true", help="clean before build (cold build time)")
    ap.add_argument("--contract-only", action="store_true")
    ap.add_argument("--no-build", action="store_true")
    args = ap.parse_args()

    if not shutil.which("oha") and not args.contract_only:
        sys.exit("oha not found: brew install oha")
    fd_limit = ensure_fd_limit()

    cfg = json.loads(Path(args.config).read_text())
    duration = args.duration or cfg["duration_s"]
    concurrency = args.concurrency or cfg["concurrency"]
    warmup = args.warmup if args.warmup is not None else cfg["warmup_s"]
    impls = [i for i in cfg["implementations"] if not args.impl or i["name"] in args.impl]
    scenarios = [s for s in cfg["scenarios"] if not args.scenario or s["name"] in args.scenario]
    saturation = cfg.get("saturation", [])
    cold_runs = cfg.get("cold_start_runs", 5)

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
            "fd_limit": fd_limit,
            "somaxconn": _sysctl("kern.ipc.somaxconn"),
        },
        "settings": {"duration_s": duration, "warmup_s": warmup, "concurrency": concurrency,
                     "cold_start_runs": cold_runs, "load_generator": _oha_version(),
                     "connections": cfg.get("connections"), "recovery": cfg.get("recovery")},
        "scenarios": scenarios,
        "saturation": saturation,
        "implementations": {},
    }

    exit_code = 0
    for impl in impls:
        name = impl["name"]
        port = impl["port"]
        base = f"http://127.0.0.1:{port}"
        entry = {"port": port, "loc": loc(impl), "deps": dep_count(impl), "toolchain": _toolchain(impl)}
        proc = None
        try:
            if not args.no_build:
                entry.update(build_impl(impl, args.clean))
            if "coldstart" in args.skip or args.contract_only:
                proc, t = start_impl(impl)
                entry["cold_start_ms"] = [round(t * 1000, 1)]
            else:
                proc, entry["cold_start_ms"] = cold_start(impl, cold_runs)
            entry["cold_start_median_ms"] = round(statistics.median(entry["cold_start_ms"]), 1)
        except Exception as e:
            log(f"{name}: FAILED to build/start: {e}")
            entry["error"] = str(e)
            summary["implementations"][name] = entry
            exit_code = 1
            if proc:
                stop_impl(proc)
            continue
        try:
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
            raw_dir.mkdir(parents=True, exist_ok=True)

            if "scenarios" not in args.skip:
                entry["scenarios"] = {}
                for i, sc in enumerate(scenarios):
                    if cfg.get("restart_per_scenario", True) and i > 0:
                        proc = restart(impl, proc)
                    url = base + sc["path"]
                    if warmup:
                        run_oha(url, sc, warmup, concurrency)
                    res, raw = measured_run(proc, url, sc, duration, concurrency)
                    (raw_dir / f"{name}-{sc['name']}.json").write_text(json.dumps(raw, indent=1))
                    entry["scenarios"][sc["name"]] = res
                    log(f"{name:18s} {sc['name']:8s} {res['rps']:>9.0f} rps  p50 {res['p50_ms']:>7.2f}  p95 {res['p95_ms']:>7.2f}  "
                        f"p99 {res['p99_ms']:>7.2f} ms  peak {res['peak_rss_bytes']/1e6:>7.1f} MB  cpu/1k {res['cpu_ms_per_1k_req']:>8.2f} ms  err {res['errors']}")

            if "saturation" not in args.skip and saturation:
                entry["saturation"] = {}
                for sc in saturation:
                    proc = restart(impl, proc)
                    res, raw = measured_run(proc, base + sc["path"], sc, sc.get("duration_s", duration),
                                            sc["concurrency"], sc.get("timeout_s"))
                    (raw_dir / f"{name}-{sc['name']}.json").write_text(json.dumps(raw, indent=1))
                    entry["saturation"][sc["name"]] = res
                    log(f"{name:18s} {sc['name']:8s} c={sc['concurrency']:<5d} {res['rps']:>9.0f} rps  p99 {res['p99_ms']:>8.2f} ms  "
                        f"errors {res['errors']} ({res['error_pct']}%) {dict(list(res['error_kinds'].items())[:3])}")

            if "connections" not in args.skip and cfg.get("connections"):
                proc = restart(impl, proc)
                c = cfg["connections"]
                entry["connections"] = connections_test(proc, port, c["count"], c.get("hold_s", 1))
                e = entry["connections"]
                log(f"{name:18s} conns    {e['connections']} open: idle {e['idle_rss_bytes']/1e6:.1f} MB -> held {e['held_rss_bytes']/1e6:.1f} MB  "
                    f"= {e['bytes_per_conn']/1024:.1f} KB/conn  (failed {e['failed']})")

            if "recovery" not in args.skip and cfg.get("recovery"):
                proc = restart(impl, proc)
                entry["recovery"] = recovery_test(proc, port, cfg["recovery"])
                r = entry["recovery"]
                log(f"{name:18s} recover  idle {r['idle_rss_bytes']/1e6:.1f} -> peak {r['peak_rss_bytes']/1e6:.1f} -> +0s {r['rss_after_spike_bytes']/1e6:.1f} "
                    f"-> +{r['settle_s']}s {r['rss_after_settle_bytes']/1e6:.1f} MB (retained {r['retained_pct']}%)  "
                    f"probe p99 {r['probe_pre']['p99_ms']} -> {r['probe_after_spike']['p99_ms']} -> {r['probe_after_settle']['p99_ms']} ms")
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


def _sysctl(key):
    try:
        return subprocess.run(["sysctl", "-n", key], capture_output=True, text=True).stdout.strip()
    except Exception:
        return None


def _cpu_brand():
    return _sysctl("machdep.cpu.brand_string") or platform.processor()


def _oha_version():
    try:
        return subprocess.run(["oha", "--version"], capture_output=True, text=True).stdout.strip()
    except Exception:
        return "oha (unknown)"


def _toolchain(impl):
    try:
        if impl["name"].startswith("rust"):
            return subprocess.run(["rustc", "--version"], capture_output=True, text=True).stdout.strip().replace(" (", " (").split(" (")[0]
        if impl["name"].startswith("go"):
            return subprocess.run(["go", "version"], capture_output=True, text=True).stdout.strip().replace("go version ", "").split()[0]
        py = ROOT / impl["cwd"] / ".venv" / "bin" / "python"
        v = subprocess.run([str(py), "-c",
                            "import sys,fastapi,uvicorn;print(f'Python {sys.version.split()[0]}, FastAPI {fastapi.__version__}, Uvicorn {uvicorn.__version__}')"],
                           capture_output=True, text=True).stdout.strip()
        return v or "python (venv missing: make setup)"
    except Exception as e:
        return f"unknown ({e})"


if __name__ == "__main__":
    sys.exit(main())

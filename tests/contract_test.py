#!/usr/bin/env python3
"""Shared contract test for every implementation (stdlib only).

Usage: contract_test.py [--process-local-state] http://127.0.0.1:8001 [more base urls...]

--process-local-state: the implementation runs several worker processes with
in-memory state, so a created item is only visible on the worker that created
it. Recorded as a finding instead of a failure.

Asserts the behaviour in docs/API.md. Framework-specific behaviour (malformed
path ids, structurally invalid JSON) is recorded and printed, not asserted,
because that is itself a finding of the study.
"""

import hashlib
import json
import sys
import urllib.error
import urllib.request


def chained_sha256(seed_str: str, rounds: int) -> str:
    buf = seed_str.encode()
    for _ in range(rounds):
        buf = hashlib.sha256(buf).digest()
    return buf.hex()


def call(base, method, path, body=None):
    data = None
    headers = {}
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
            return r.status, raw, dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def parse(raw):
    try:
        return json.loads(raw)
    except Exception:
        return raw.decode(errors="replace")


def seed_item(i):
    return {
        "id": i,
        "name": f"item-{i}",
        "price": (i % 1000) + 0.99,
        "tags": [f"tag-{i % 7}", f"tag-{i % 13}"],
        "created_at": "2026-01-01T00:00:00Z",
    }


def header(h, name):
    for k, v in h.items():
        if k.lower() == name.lower():
            return v
    return ""


def run(base, process_local_state=False):
    failures = []
    notes = []

    def check(name, cond, detail=""):
        if not cond:
            failures.append(f"{name}: {detail}")

    s, raw, h = call(base, "GET", "/health")
    check("health status", s == 200, s)
    check("health body", parse(raw) == {"status": "ok"}, raw[:200])
    check("health content-type", "application/json" in header(h, "Content-Type").lower(), header(h, "Content-Type"))

    s, raw, _ = call(base, "GET", "/items/42")
    check("get status", s == 200, s)
    check("get body", parse(raw) == seed_item(42), raw[:300])

    s, raw, _ = call(base, "GET", "/items/999999")
    check("get 404 status", s == 404, s)
    check("get 404 body", parse(raw) == {"error": "not found"}, raw[:200])

    s, raw, _ = call(base, "GET", "/items/not-a-number")
    notes.append(f"non-numeric id -> {s} {parse(raw) if len(raw) < 120 else raw[:120]!r}")
    check("non-numeric id is 4xx", 400 <= s < 500, s)

    s, raw, _ = call(base, "GET", "/items?limit=5")
    b = parse(raw)
    check("list status", s == 200, s)
    check("list count", isinstance(b, dict) and b.get("count") == 5, b if not isinstance(b, dict) else b.get("count"))
    check("list items", isinstance(b, dict) and b.get("items") == [seed_item(i) for i in range(1, 6)], "items mismatch")

    s, raw, _ = call(base, "GET", "/items")
    b = parse(raw)
    check("list default 20", isinstance(b, dict) and b.get("count") == 20, b.get("count") if isinstance(b, dict) else b)

    s, raw, _ = call(base, "GET", "/items?limit=5000")
    b = parse(raw)
    check("list clamp 1000", isinstance(b, dict) and b.get("count") == 1000, b.get("count") if isinstance(b, dict) else b)

    s, raw, _ = call(base, "POST", "/items", {"name": "widget", "price": 9.5, "tags": ["a", "b"]})
    b = parse(raw)
    check("create status", s == 201, s)
    check("create fields", isinstance(b, dict) and b.get("name") == "widget" and b.get("price") == 9.5 and b.get("tags") == ["a", "b"], b)
    check("create id", isinstance(b, dict) and isinstance(b.get("id"), int) and b["id"] > 10000, b.get("id") if isinstance(b, dict) else b)
    check("create created_at", isinstance(b, dict) and isinstance(b.get("created_at"), str) and b["created_at"].endswith("Z"), b.get("created_at") if isinstance(b, dict) else b)
    new_id = b["id"] if isinstance(b, dict) and "id" in b else None

    if new_id:
        # With one process this must be 200. With several worker processes and
        # in-memory state, the GET may land on a worker that never saw the POST:
        # that is a real property of the deployment, recorded when declared.
        hits = 0
        for _ in range(10):
            s, raw, _ = call(base, "GET", f"/items/{new_id}")
            hits += int(s == 200 and parse(raw) == b)
        if process_local_state:
            notes.append(f"create-then-get across workers -> {hits}/10 hits (state is per-process; a real deployment needs a shared store)")
        else:
            check("create then get", hits == 10, f"{hits}/10")

    s, raw, _ = call(base, "POST", "/items", {"name": "no-tags", "price": 1})
    b = parse(raw)
    check("create default tags", s == 201 and isinstance(b, dict) and b.get("tags") == [], b)

    s, raw, _ = call(base, "POST", "/items", {"name": "   ", "price": 1})
    check("create blank name 400", s == 400, s)
    check("create blank name body", isinstance(parse(raw), dict) and "error" in parse(raw), raw[:200])

    s, raw, _ = call(base, "POST", "/items", {"name": "x", "price": -1})
    check("create negative price 400", s == 400, s)

    s, raw, _ = call(base, "POST", "/items", b"{not json")
    notes.append(f"malformed json -> {s} {parse(raw) if len(raw) < 120 else raw[:120]!r}")
    check("malformed json is 4xx", 400 <= s < 500, s)

    s, raw, _ = call(base, "POST", "/items", {"name": 123, "price": "cheap"})
    notes.append(f"wrong types -> {s} {parse(raw) if len(raw) < 160 else raw[:160]!r}")
    check("wrong types is 4xx", 400 <= s < 500, s)

    for n in (1, 7, 1000):
        s, raw, _ = call(base, "GET", f"/compute/hash?n={n}")
        b = parse(raw)
        check(f"hash n={n}", s == 200 and b == {"n": n, "digest": chained_sha256(str(n), n)}, b)
    s, raw, _ = call(base, "GET", "/compute/hash")
    check("hash default", parse(raw) == {"n": 1000, "digest": chained_sha256("1000", 1000)}, raw[:120])

    s, raw, _ = call(base, "GET", "/io/wait?ms=3")
    check("wait", s == 200 and parse(raw) == {"waited_ms": 3}, raw[:100])
    s, raw, _ = call(base, "GET", "/io/wait")
    check("wait default", parse(raw) == {"waited_ms": 10}, raw[:100])

    s, raw, _ = call(base, "GET", "/mixed?id=42")
    b = parse(raw)
    check("mixed", s == 200 and b == {"item": seed_item(42), "digest": chained_sha256("42", 200)}, b)
    s, raw, _ = call(base, "GET", "/mixed")
    b = parse(raw)
    check("mixed default", s == 200 and isinstance(b, dict) and b.get("item") == seed_item(1), b)
    s, raw, _ = call(base, "GET", "/mixed?id=999999")
    check("mixed 404", s == 404 and parse(raw) == {"error": "not found"}, s)

    return failures, notes


def main(argv):
    process_local = "--process-local-state" in argv
    bases = [a for a in argv[1:] if not a.startswith("--")]
    if not bases:
        print(__doc__)
        return 2
    rc = 0
    for base in bases:
        base = base.rstrip("/")
        try:
            failures, notes = run(base, process_local)
        except Exception as e:  # connection refused etc.
            print(f"[{base}] ERROR: {e}")
            rc = 1
            continue
        status = "PASS" if not failures else "FAIL"
        print(f"[{base}] {status}")
        for n in notes:
            print(f"    note: {n}")
        for f in failures:
            print(f"    FAIL: {f}")
        if failures:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))

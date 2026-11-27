"""API Performance Lab — Python implementation (FastAPI on Uvicorn).

Implements the contract in docs/API.md.

Run: uvicorn app.main:app --port 8003 --workers <N> --loop uvloop --http httptools
"""

import asyncio
import hashlib
import itertools
import threading
from datetime import datetime, timezone

from fastapi import FastAPI, Query
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel

SEED_COUNT = 10_000
SEED_CREATED_AT = "2026-01-01T00:00:00Z"

app = FastAPI(title="api-lab-python", default_response_class=ORJSONResponse)


class Item(BaseModel):
    id: int
    name: str
    price: float
    tags: list[str]
    created_at: str


class NewItem(BaseModel):
    name: str
    price: float
    tags: list[str] = []


def seed() -> dict[int, dict]:
    return {
        i: {
            "id": i,
            "name": f"item-{i}",
            "price": (i % 1000) + 0.99,
            "tags": [f"tag-{i % 7}", f"tag-{i % 13}"],
            "created_at": SEED_CREATED_AT,
        }
        for i in range(1, SEED_COUNT + 1)
    }


# Plain dicts are stored (not pydantic models) so the hot read path is a dict
# lookup + orjson dump, which is how a tuned FastAPI service is actually written.
ITEMS: dict[int, dict] = seed()
_ids = itertools.count(SEED_COUNT + 1)
_write_lock = threading.Lock()


def chained_sha256(seed_str: str, rounds: int) -> str:
    buf = seed_str.encode()
    for _ in range(rounds):
        buf = hashlib.sha256(buf).digest()
    return buf.hex()


def error(status: int, msg: str) -> ORJSONResponse:
    return ORJSONResponse({"error": msg}, status_code=status)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/items/{item_id}")
async def get_item(item_id: int):
    item = ITEMS.get(item_id)
    if item is None:
        return error(404, "not found")
    return item


@app.get("/items")
async def list_items(limit: int = Query(20)):
    limit = max(1, min(limit, 1000))
    out = [ITEMS[i] for i in range(1, limit + 1) if i in ITEMS]
    return {"count": len(out), "items": out}


@app.post("/items", status_code=201)
async def create_item(body: NewItem):
    if not body.name.strip():
        return error(400, "name must not be empty")
    if body.price < 0:
        return error(400, "price must be >= 0")
    with _write_lock:
        item_id = next(_ids)
        item = {
            "id": item_id,
            "name": body.name,
            "price": body.price,
            "tags": body.tags,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        ITEMS[item_id] = item
    return ORJSONResponse(item, status_code=201)


@app.get("/compute/hash")
def compute_hash(n: int = Query(1000)):
    # Sync `def` endpoint: FastAPI runs it in the threadpool, which is the
    # idiomatic way to keep CPU work off the event loop. The GIL still applies.
    n = max(1, min(n, 1_000_000))
    return {"n": n, "digest": chained_sha256(str(n), n)}


@app.get("/io/wait")
async def io_wait(ms: int = Query(10)):
    ms = max(0, min(ms, 5000))
    await asyncio.sleep(ms / 1000)
    return {"waited_ms": ms}


@app.get("/mixed")
async def mixed(id: int = Query(1)):
    await asyncio.sleep(0.005)
    item = ITEMS.get(id)
    if item is None:
        return error(404, "not found")
    return {"item": item, "digest": chained_sha256(str(id), 200)}

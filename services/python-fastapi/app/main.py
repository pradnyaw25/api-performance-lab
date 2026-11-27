"""API Performance Lab — Python implementation (FastAPI on Uvicorn).

Implements the contract in docs/API.md. With DATABASE_URL set, the item
endpoints go to PostgreSQL through an asyncpg pool (Phase 2, one pool per
worker process); otherwise an in-memory dict (Phase 1).

Run: uvicorn app.main:app --port 8003 --workers <N> --loop uvloop --http httptools
"""

import asyncio
import contextlib
import hashlib
import itertools
import os
import threading

import asyncpg
from fastapi import FastAPI, Query
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel

SEED_COUNT = 10_000
SEED_CREATED_AT = "2026-01-01T00:00:00Z"
DATABASE_URL = os.environ.get("DATABASE_URL") or None
DB_POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "16"))
SELECT_COLS = "id, name, price, tags, created_at"

POOL: asyncpg.Pool | None = None


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    global POOL
    if DATABASE_URL:
        POOL = await asyncpg.create_pool(DATABASE_URL, min_size=DB_POOL_SIZE, max_size=DB_POOL_SIZE)
    yield
    if POOL:
        await POOL.close()


app = FastAPI(title="api-lab-python", default_response_class=ORJSONResponse, lifespan=lifespan)


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
#
# Handlers return ORJSONResponse(...) directly instead of a dict. A returned
# dict goes through FastAPI's pure-Python `jsonable_encoder` before the response
# class serializes it, which on a 200-item list cost ~1.6 ms of CPU per request
# in the baseline run (results/20261126-215740). Returning the response object
# skips that pass. Both forms are common in production code; the difference is
# one of the study's findings.
ITEMS: dict[int, dict] = {} if DATABASE_URL else seed()
_ids = itertools.count(SEED_COUNT + 1)
_write_lock = threading.Lock()


def row_to_item(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "price": row["price"],
        "tags": list(row["tags"] or []),
        "created_at": row["created_at"].strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


async def fetch_item(item_id: int) -> dict | None:
    if POOL is None:
        return ITEMS.get(item_id)
    row = await POOL.fetchrow(f"SELECT {SELECT_COLS} FROM items WHERE id = $1", item_id)
    return row_to_item(row) if row else None


def chained_sha256(seed_str: str, rounds: int) -> str:
    buf = seed_str.encode()
    for _ in range(rounds):
        buf = hashlib.sha256(buf).digest()
    return buf.hex()


def error(status: int, msg: str) -> ORJSONResponse:
    return ORJSONResponse({"error": msg}, status_code=status)


@app.get("/health")
async def health():
    return ORJSONResponse({"status": "ok"})


@app.get("/items/{item_id}")
async def get_item(item_id: int):
    item = await fetch_item(item_id)
    if item is None:
        return error(404, "not found")
    return ORJSONResponse(item)


@app.get("/items")
async def list_items(limit: int = Query(20)):
    limit = max(1, min(limit, 1000))
    if POOL is None:
        out = [ITEMS[i] for i in range(1, limit + 1) if i in ITEMS]
    else:
        rows = await POOL.fetch(f"SELECT {SELECT_COLS} FROM items WHERE id <= $1 ORDER BY id", limit)
        out = [row_to_item(r) for r in rows]
    return ORJSONResponse({"count": len(out), "items": out})


@app.post("/items", status_code=201)
async def create_item(body: NewItem):
    if not body.name.strip():
        return error(400, "name must not be empty")
    if body.price < 0:
        return error(400, "price must be >= 0")
    if POOL is None:
        from datetime import datetime, timezone
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
    else:
        row = await POOL.fetchrow(
            f"INSERT INTO items (name, price, tags) VALUES ($1, $2, $3) RETURNING {SELECT_COLS}",
            body.name, body.price, body.tags,
        )
        item = row_to_item(row)
    return ORJSONResponse(item, status_code=201)


@app.get("/compute/hash")
def compute_hash(n: int = Query(1000)):
    # Sync `def` endpoint: FastAPI runs it in the threadpool, which is the
    # idiomatic way to keep CPU work off the event loop. The GIL still applies.
    n = max(1, min(n, 1_000_000))
    return ORJSONResponse({"n": n, "digest": chained_sha256(str(n), n)})


@app.get("/io/wait")
async def io_wait(ms: int = Query(10)):
    ms = max(0, min(ms, 5000))
    await asyncio.sleep(ms / 1000)
    return ORJSONResponse({"waited_ms": ms})


@app.get("/mixed")
async def mixed(id: int = Query(1)):
    # In-memory mode simulates a 5 ms database wait; in Postgres mode the
    # round-trip is the I/O.
    if POOL is None:
        await asyncio.sleep(0.005)
    item = await fetch_item(id)
    if item is None:
        return error(404, "not found")
    return ORJSONResponse({"item": item, "digest": chained_sha256(str(id), 200)})

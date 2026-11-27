//! API Performance Lab — Rust implementation (Axum on Tokio).
//! Implements the contract in docs/API.md.

use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::get,
    Json, Router,
};
use serde::{Deserialize, Serialize};
use serde_json::json;
use sha2::{Digest, Sha256};
use std::{
    collections::HashMap,
    net::SocketAddr,
    sync::{
        atomic::{AtomicU64, Ordering},
        Arc, RwLock,
    },
    time::Duration,
};

const SEED_COUNT: u64 = 10_000;
const SEED_CREATED_AT: &str = "2026-01-01T00:00:00Z";

#[derive(Clone, Serialize)]
struct Item {
    id: u64,
    name: String,
    price: f64,
    tags: Vec<String>,
    created_at: String,
}

#[derive(Deserialize)]
struct NewItem {
    name: String,
    price: f64,
    #[serde(default)]
    tags: Vec<String>,
}

struct AppState {
    items: RwLock<HashMap<u64, Item>>,
    next_id: AtomicU64,
}

type Shared = Arc<AppState>;

fn seed() -> HashMap<u64, Item> {
    (1..=SEED_COUNT)
        .map(|i| {
            (
                i,
                Item {
                    id: i,
                    name: format!("item-{i}"),
                    price: (i % 1000) as f64 + 0.99,
                    tags: vec![format!("tag-{}", i % 7), format!("tag-{}", i % 13)],
                    created_at: SEED_CREATED_AT.to_string(),
                },
            )
        })
        .collect()
}

fn chained_sha256(seed: &str, rounds: u32) -> String {
    let mut buf: Vec<u8> = seed.as_bytes().to_vec();
    for _ in 0..rounds {
        buf = Sha256::digest(&buf).to_vec();
    }
    hex::encode(buf)
}

fn error(status: StatusCode, msg: &str) -> Response {
    (status, Json(json!({ "error": msg }))).into_response()
}

async fn health() -> impl IntoResponse {
    Json(json!({ "status": "ok" }))
}

async fn get_item(State(s): State<Shared>, Path(id): Path<u64>) -> Response {
    let items = s.items.read().unwrap();
    match items.get(&id) {
        Some(item) => Json(item.clone()).into_response(),
        None => error(StatusCode::NOT_FOUND, "not found"),
    }
}

#[derive(Deserialize)]
struct ListQuery {
    limit: Option<usize>,
}

#[derive(Serialize)]
struct ListResponse {
    count: usize,
    items: Vec<Item>,
}

async fn list_items(State(s): State<Shared>, Query(q): Query<ListQuery>) -> impl IntoResponse {
    let limit = q.limit.unwrap_or(20).clamp(1, 1000);
    let items = s.items.read().unwrap();
    let out: Vec<Item> = (1..=limit as u64)
        .filter_map(|i| items.get(&i).cloned())
        .collect();
    Json(ListResponse { count: out.len(), items: out })
}

async fn create_item(State(s): State<Shared>, Json(body): Json<NewItem>) -> Response {
    if body.name.trim().is_empty() {
        return error(StatusCode::BAD_REQUEST, "name must not be empty");
    }
    if body.price < 0.0 {
        return error(StatusCode::BAD_REQUEST, "price must be >= 0");
    }
    let id = s.next_id.fetch_add(1, Ordering::Relaxed);
    let item = Item {
        id,
        name: body.name,
        price: body.price,
        tags: body.tags,
        created_at: chrono::Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string(),
    };
    s.items.write().unwrap().insert(id, item.clone());
    (StatusCode::CREATED, Json(item)).into_response()
}

#[derive(Deserialize)]
struct HashQuery {
    n: Option<u32>,
}

async fn compute_hash(Query(q): Query<HashQuery>) -> impl IntoResponse {
    let n = q.n.unwrap_or(1000).clamp(1, 1_000_000);
    let digest = chained_sha256(&n.to_string(), n);
    Json(json!({ "n": n, "digest": digest }))
}

#[derive(Deserialize)]
struct WaitQuery {
    ms: Option<u64>,
}

async fn io_wait(Query(q): Query<WaitQuery>) -> impl IntoResponse {
    let ms = q.ms.unwrap_or(10).min(5000);
    tokio::time::sleep(Duration::from_millis(ms)).await;
    Json(json!({ "waited_ms": ms }))
}

#[derive(Deserialize)]
struct MixedQuery {
    id: Option<u64>,
}

async fn mixed(State(s): State<Shared>, Query(q): Query<MixedQuery>) -> Response {
    let id = q.id.unwrap_or(1);
    tokio::time::sleep(Duration::from_millis(5)).await;
    let item = {
        let items = s.items.read().unwrap();
        items.get(&id).cloned()
    };
    let Some(item) = item else {
        return error(StatusCode::NOT_FOUND, "not found");
    };
    let digest = chained_sha256(&id.to_string(), 200);
    Json(json!({ "item": item, "digest": digest })).into_response()
}

#[tokio::main]
async fn main() {
    let port: u16 = std::env::var("PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8001);

    let state: Shared = Arc::new(AppState {
        items: RwLock::new(seed()),
        next_id: AtomicU64::new(SEED_COUNT + 1),
    });

    let app = Router::new()
        .route("/health", get(health))
        .route("/items", get(list_items).post(create_item))
        .route("/items/{id}", get(get_item))
        .route("/compute/hash", get(compute_hash))
        .route("/io/wait", get(io_wait))
        .route("/mixed", get(mixed))
        .with_state(state);

    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    let listener = tokio::net::TcpListener::bind(addr).await.expect("bind");
    eprintln!("rust-axum listening on http://{addr}");
    axum::serve(listener, app).await.expect("serve");
}

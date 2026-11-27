// API Performance Lab — Go implementation (standard library net/http).
// Implements the contract in docs/API.md. With DATABASE_URL set, the item
// endpoints go to PostgreSQL through a pgx pool (Phase 2); otherwise an
// in-memory map behind a RWMutex (Phase 1).
package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"sync"
	"sync/atomic"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

const (
	seedCount     = 10000
	seedCreatedAt = "2026-01-01T00:00:00Z"
	selectCols    = "id, name, price, tags, created_at"
)

type Item struct {
	ID        uint64   `json:"id"`
	Name      string   `json:"name"`
	Price     float64  `json:"price"`
	Tags      []string `json:"tags"`
	CreatedAt string   `json:"created_at"`
}

type NewItem struct {
	Name  string   `json:"name"`
	Price float64  `json:"price"`
	Tags  []string `json:"tags"`
}

// Store is either the in-memory map or a Postgres pool.
type Store struct {
	mu     sync.RWMutex
	items  map[uint64]*Item
	nextID atomic.Uint64
	pool   *pgxpool.Pool
}

func newMemoryStore() *Store {
	s := &Store{items: make(map[uint64]*Item, seedCount)}
	for i := uint64(1); i <= seedCount; i++ {
		s.items[i] = &Item{
			ID:        i,
			Name:      fmt.Sprintf("item-%d", i),
			Price:     float64(i%1000) + 0.99,
			Tags:      []string{fmt.Sprintf("tag-%d", i%7), fmt.Sprintf("tag-%d", i%13)},
			CreatedAt: seedCreatedAt,
		}
	}
	s.nextID.Store(seedCount + 1)
	return s
}

func newPgStore(url string, size int32) *Store {
	cfg, err := pgxpool.ParseConfig(url)
	if err != nil {
		log.Fatalf("DATABASE_URL: %v", err)
	}
	cfg.MaxConns = size
	cfg.MinConns = size
	pool, err := pgxpool.NewWithConfig(context.Background(), cfg)
	if err != nil {
		log.Fatalf("pgxpool: %v", err)
	}
	if err := pool.Ping(context.Background()); err != nil {
		log.Fatalf("postgres ping: %v", err)
	}
	log.Printf("go-nethttp: postgres mode, pool size %d", size)
	return &Store{pool: pool}
}

type scanner interface {
	Scan(dest ...any) error
}

func scanItem(row scanner) (*Item, error) {
	var it Item
	var id int64
	var created time.Time
	if err := row.Scan(&id, &it.Name, &it.Price, &it.Tags, &created); err != nil {
		return nil, err
	}
	it.ID = uint64(id)
	if it.Tags == nil {
		it.Tags = []string{}
	}
	it.CreatedAt = created.UTC().Format("2006-01-02T15:04:05Z")
	return &it, nil
}

func (s *Store) get(ctx context.Context, id uint64) (*Item, bool, error) {
	if s.pool == nil {
		s.mu.RLock()
		it, ok := s.items[id]
		s.mu.RUnlock()
		return it, ok, nil
	}
	it, err := scanItem(s.pool.QueryRow(ctx, "SELECT "+selectCols+" FROM items WHERE id = $1", int64(id)))
	if err != nil {
		if err.Error() == "no rows in result set" {
			return nil, false, nil
		}
		return nil, false, err
	}
	return it, true, nil
}

func chainedSHA256(seed string, rounds int) string {
	buf := []byte(seed)
	for i := 0; i < rounds; i++ {
		sum := sha256.Sum256(buf)
		buf = sum[:]
	}
	return hex.EncodeToString(buf)
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}

func dbError(w http.ResponseWriter, err error) {
	writeError(w, 500, "database error: "+err.Error())
}

func queryInt(r *http.Request, key string, def, lo, hi int) int {
	v := r.URL.Query().Get(key)
	if v == "" {
		return def
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return def
	}
	if n < lo {
		return lo
	}
	if n > hi {
		return hi
	}
	return n
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8002"
	}
	var store *Store
	if url := os.Getenv("DATABASE_URL"); url != "" {
		size := 16
		if v, err := strconv.Atoi(os.Getenv("DB_POOL_SIZE")); err == nil && v > 0 {
			size = v
		}
		store = newPgStore(url, int32(size))
	} else {
		store = newMemoryStore()
	}
	mux := http.NewServeMux()

	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, 200, map[string]string{"status": "ok"})
	})

	mux.HandleFunc("GET /items/{id}", func(w http.ResponseWriter, r *http.Request) {
		id, err := strconv.ParseUint(r.PathValue("id"), 10, 64)
		if err != nil {
			writeError(w, 400, "invalid id")
			return
		}
		item, ok, err := store.get(r.Context(), id)
		if err != nil {
			dbError(w, err)
			return
		}
		if !ok {
			writeError(w, 404, "not found")
			return
		}
		writeJSON(w, 200, item)
	})

	mux.HandleFunc("GET /items", func(w http.ResponseWriter, r *http.Request) {
		limit := queryInt(r, "limit", 20, 1, 1000)
		out := make([]*Item, 0, limit)
		if store.pool == nil {
			store.mu.RLock()
			for i := uint64(1); i <= uint64(limit); i++ {
				if it, ok := store.items[i]; ok {
					out = append(out, it)
				}
			}
			store.mu.RUnlock()
		} else {
			rows, err := store.pool.Query(r.Context(), "SELECT "+selectCols+" FROM items WHERE id <= $1 ORDER BY id", int64(limit))
			if err != nil {
				dbError(w, err)
				return
			}
			defer rows.Close()
			for rows.Next() {
				it, err := scanItem(rows)
				if err != nil {
					dbError(w, err)
					return
				}
				out = append(out, it)
			}
		}
		writeJSON(w, 200, map[string]any{"count": len(out), "items": out})
	})

	mux.HandleFunc("POST /items", func(w http.ResponseWriter, r *http.Request) {
		var body NewItem
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			writeError(w, 400, "invalid json")
			return
		}
		if isBlank(body.Name) {
			writeError(w, 400, "name must not be empty")
			return
		}
		if body.Price < 0 {
			writeError(w, 400, "price must be >= 0")
			return
		}
		if body.Tags == nil {
			body.Tags = []string{}
		}
		var item *Item
		if store.pool == nil {
			item = &Item{
				ID:        store.nextID.Add(1) - 1,
				Name:      body.Name,
				Price:     body.Price,
				Tags:      body.Tags,
				CreatedAt: time.Now().UTC().Format("2006-01-02T15:04:05Z"),
			}
			store.mu.Lock()
			store.items[item.ID] = item
			store.mu.Unlock()
		} else {
			var err error
			item, err = scanItem(store.pool.QueryRow(r.Context(),
				"INSERT INTO items (name, price, tags) VALUES ($1, $2, $3) RETURNING "+selectCols,
				body.Name, body.Price, body.Tags))
			if err != nil {
				dbError(w, err)
				return
			}
		}
		writeJSON(w, 201, item)
	})

	mux.HandleFunc("GET /compute/hash", func(w http.ResponseWriter, r *http.Request) {
		n := queryInt(r, "n", 1000, 1, 1_000_000)
		writeJSON(w, 200, map[string]any{"n": n, "digest": chainedSHA256(strconv.Itoa(n), n)})
	})

	mux.HandleFunc("GET /io/wait", func(w http.ResponseWriter, r *http.Request) {
		ms := queryInt(r, "ms", 10, 0, 5000)
		time.Sleep(time.Duration(ms) * time.Millisecond)
		writeJSON(w, 200, map[string]int{"waited_ms": ms})
	})

	mux.HandleFunc("GET /mixed", func(w http.ResponseWriter, r *http.Request) {
		id := uint64(queryInt(r, "id", 1, 1, 1<<31))
		// In-memory mode simulates a 5 ms database wait; in Postgres mode the
		// round-trip is the I/O.
		if store.pool == nil {
			time.Sleep(5 * time.Millisecond)
		}
		item, ok, err := store.get(r.Context(), id)
		if err != nil {
			dbError(w, err)
			return
		}
		if !ok {
			writeError(w, 404, "not found")
			return
		}
		writeJSON(w, 200, map[string]any{"item": item, "digest": chainedSHA256(strconv.FormatUint(id, 10), 200)})
	})

	addr := "127.0.0.1:" + port
	log.Printf("go-nethttp listening on http://%s", addr)
	srv := &http.Server{Addr: addr, Handler: mux, ReadHeaderTimeout: 10 * time.Second}
	log.Fatal(srv.ListenAndServe())
}

func isBlank(s string) bool {
	for _, c := range s {
		if c != ' ' && c != '\t' && c != '\n' && c != '\r' {
			return false
		}
	}
	return true
}

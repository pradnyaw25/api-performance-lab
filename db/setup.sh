#!/usr/bin/env bash
# Start the Homebrew postgresql@17 cluster on its own port (5433 by default, so
# it never contends with another project's PostgreSQL on 5432) and create the
# apilab role and database if missing. Idempotent. Usage: db/setup.sh
set -euo pipefail
PGPORT="${PGPORT:-5433}"
PGBIN="$(brew --prefix postgresql@17 2>/dev/null)/bin"
PGDATA="$(brew --prefix)/var/postgresql@17"
PGLOG="$(brew --prefix)/var/log/postgresql@17-apilab.log"
export PATH="$PGBIN:$PATH"
# macOS: without a valid locale the postmaster aborts with "became multithreaded during startup".
export LC_ALL="${LC_ALL:-en_US.UTF-8}"
if ! brew list --versions postgresql@17 >/dev/null 2>&1; then
  echo "installing postgresql@17 via Homebrew"; brew install postgresql@17
fi
if [ ! -f "$PGDATA/PG_VERSION" ]; then
  initdb -D "$PGDATA" >/dev/null
fi
if ! pg_isready -h 127.0.0.1 -p "$PGPORT" -q; then
  pg_ctl -D "$PGDATA" -o "-p $PGPORT -c listen_addresses=127.0.0.1" -l "$PGLOG" start >/dev/null
  for _ in $(seq 1 60); do pg_isready -h 127.0.0.1 -p "$PGPORT" -q && break; sleep 0.5; done
fi
pg_isready -h 127.0.0.1 -p "$PGPORT"
psql -h 127.0.0.1 -p "$PGPORT" -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='apilab'" | grep -q 1 \
  || psql -h 127.0.0.1 -p "$PGPORT" -d postgres -q -c "CREATE ROLE apilab LOGIN PASSWORD 'apilab'"
psql -h 127.0.0.1 -p "$PGPORT" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='apilab'" | grep -q 1 \
  || createdb -h 127.0.0.1 -p "$PGPORT" -O apilab apilab
echo "DATABASE_URL=postgres://apilab:apilab@127.0.0.1:$PGPORT/apilab"
echo "stop with: pg_ctl -D $PGDATA stop"

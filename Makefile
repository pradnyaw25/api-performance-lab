.PHONY: setup build contract bench bench-quick aggregate charts drafts clean

PY_DIR := services/python-fastapi

setup:
	python3 -m venv $(PY_DIR)/.venv
	$(PY_DIR)/.venv/bin/pip install -q -r $(PY_DIR)/requirements.txt

build:
	cd services/rust-axum && cargo build --release
	cd services/go-nethttp && go build -o bin/api-lab-go .

contract:
	python3 bench/run.py --contract-only

bench:
	python3 bench/run.py

bench-quick:
	python3 bench/run.py --duration 3 --warmup 1

# Chart tooling lives in its own venv so it never changes the service's dependency count.
.venv-bench:
	python3 -m venv .venv-bench && .venv-bench/bin/pip install -q matplotlib

aggregate:
	python3 bench/aggregate.py $(RUNS) -o results/aggregate

charts: .venv-bench
	.venv-bench/bin/python bench/charts.py results/aggregate -o content/charts

drafts:
	python3 bench/fill_numbers.py results/aggregate

clean:
	cd services/rust-axum && cargo clean
	rm -rf services/go-nethttp/bin $(PY_DIR)/.venv .venv-bench
	find . -name __pycache__ -type d -exec rm -rf {} +

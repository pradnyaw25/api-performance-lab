.PHONY: setup build contract bench bench-quick clean

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

clean:
	cd services/rust-axum && cargo clean
	rm -rf services/go-nethttp/bin $(PY_DIR)/.venv
	find . -name __pycache__ -type d -exec rm -rf {} +

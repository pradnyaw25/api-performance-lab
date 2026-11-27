# X posts

Two posts, one graphic. Attach `charts/01-where-rust-wins.gif` to the first; X plays GIFs inline. Each is under 280 characters (URLs count as 23).

---

**Post 1** [attach charts/01-where-rust-wins.gif]

Benchmarking API performance: Python vs Go vs Rust.

Same API built 3×, 7 workloads, 9 metrics. Inspired by Anthropic's Rust migration.

Rust: 1.9× Go, 6.5× Python on CPU-bound requests, and the only flat p99. When the request is waiting on I/O, the language barely matters.

---

**Post 2** (reply)

Small scale: one laptop, synthetic endpoints, medians of 4 runs. Not production load, but it isolates where the gains come from. Two one-line library changes moved the numbers more than the language did.

Write-up: https://pradnya.dev/blog/api-performance-lab/
Code: github.com/pradnyaw25/api-performance-lab

# AGENTS.md — dundercode

Durable notes for coding agents working on this repo. Terse by design.
Add an entry only when a lesson is generalisable beyond the current
task. Do not duplicate what the code or tests already express.

## Tracing

- Tracing is wired via **ddkypy** (`from .dd import ddclient`), a custom
  ddtrace fork pinned in `setup.py`. `DDConfig` requires `env` to be
  set — pass `DD_ENV=dev` when running locally.
- To add tags inside a `@ddclient.traced()` function, get the current
  span with `ddtrace.tracer.current_span()`. Example in
  `dundercode/data.py::find_lines`. String values land in the span's
  `meta` dict, numeric values in `metrics` (ddtrace convention).
- The test agent at `localhost:8126` receives traces; use Leash
  (`/leash/api/traces?app=dundercode`) to inspect them.

## Search (`dundercode.data.find_lines`)

- Search is **tokenised**: the query is split on whitespace and every
  token must appear (case-insensitive) in the line body or in a
  speaker name. No regex interpretation — literal substrings only.
- Span tags emitted per call: `leash.search.query` (meta),
  `leash.search.strategy` (meta), `leash.search.tokens` (metrics),
  `leash.search.match_count` (metrics).

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

## HTML rendering (`dundercode.html.Html`)

- Attribute values are HTML-escaped with `quote=True` (so `"` inside an
  `og:title` stays valid). Text content is HTML-escaped by default.
- **Exception:** text inside `<script>` and `<style>` elements is
  rendered *raw* — the renderer opts those tag types out of text
  escaping (browsers don't decode entities there; escaping would break
  JS/CSS). See `_RAW_TEXT_ELEMENTS` in `html.py`. If you add other
  raw-text-content elements (e.g. `<template>`), add them to that set.

## Open Graph unfurls (`/quote/{id}`)

- The quote text is the **`og:description`** (and `twitter:description`).
  `og:image` is intentionally omitted so Slack renders a compact
  text-only unfurl instead of a grey placeholder box. `twitter:card`
  is `summary` for the same reason.
- Span tags emitted: `leash.unfurl.view` (meta),
  `leash.unfurl.og_title` (meta), `leash.unfurl.has_og_image` (meta),
  `leash.unfurl.og_description_len` (metrics).
- Slack caches unfurls per URL; when testing, use an unseen path
  (e.g. a different quote id) or have Slack re-fetch.

## AI scene context (`dundercode.ai.scene_context`)

- `/quote/{id}` renders a 1-2 sentence summary above the quote so
  newcomers to The Office have enough context to get the joke. The
  summary is generated from the surrounding scene's lines.
- Requires `OPENAI_API_KEY`. Without it (or on API failure) the call
  returns `None` and the page renders without the blurb — never raise.
- Persistent on-disk cache keyed by `(season, episode, scene)` lives at
  `DUNDERCODE_SCENE_CACHE` (default `cache/scene_context.json`). The
  transcript is static, so each scene is summarised at most once.
- Model is `DUNDERCODE_OPENAI_MODEL` (default `gpt-4o-mini`).
- The blurb is **only** rendered in the page body. `og:description`
  stays as the quote so Slack unfurls don't depend on OpenAI.
- Wrapped with `@ddclient.workflow(name="scene_context")` (LLM Obs).
  The OpenAI call is auto-instrumented by ddtrace's openai integration
  as a child `llm` span when LLM Obs is enabled.
- Manual span tags emitted on the parent APM span:
  `leash.ai.scene_context.cache_hit` (meta),
  `leash.ai.scene_context.scene` (meta),
  `leash.ai.scene_context.model` (meta),
  `leash.ai.scene_context.prompt_tokens` /
  `leash.ai.scene_context.completion_tokens` (metrics),
  `leash.ai.scene_context.error` (meta, on failure).

## LLM Observability

- Enabled via `DDConfig(llmobs_enabled=True, llmobs_ml_app="dundercode")`
  in `dd.py`. Requires ddkypy ≥ the SHA that ships ddtrace 4.8 + the
  `LLMObs`-on-`DDClient` API.
- Use the decorators directly off the client:
  `@ddclient.workflow`, `@ddclient.llm`, `@ddclient.task`,
  `@ddclient.tool`, `@ddclient.retrieval`, `@ddclient.embedding`,
  `@ddclient.llm_agent` (named to avoid clashing with the Datadog
  Agent runner). Annotate with `ddclient.annotate(...)`.
- Traces flow through the local agent at `localhost:8126` like other
  APM traces. Set `DD_LLMOBS_AGENTLESS_ENABLED=1` to send directly to
  Datadog instead.

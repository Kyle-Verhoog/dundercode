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

- **The quote leads `og:title`**, formatted `“quote” — Speaker, S1E2`.
  This is deliberate: iMessage and Google Messages render only the
  title and image. Apple's LinkPresentation has no description field at
  all (`LPLinkMetadata` is title/url/icon/image/video), and Google
  Messages dropped the description snippet in its Nov 2025 preview
  redesign. Putting the quote only in `og:description` — as this page
  used to — means neither platform ever shows it.
- The quote is truncated to 90 chars for the title (word boundary +
  ellipsis); 78% of transcript lines are ≤80 chars, so most survive
  whole. When it *is* truncated, `og:description` carries the full line;
  otherwise the description is the AI scene context, falling back to
  `The Office — S{season}E{episode}`.
- `og:image` is a **generated quote card** (see below), so `twitter:card`
  is now `summary_large_image`. The earlier no-image/compact-Slack-card
  choice traded away both mobile platforms; a typeset text card gets the
  quote in front of every client without the grey placeholder box.
- Span tags emitted: `leash.unfurl.view` (meta),
  `leash.unfurl.og_title` (meta), `leash.unfurl.has_og_image` (meta),
  `leash.unfurl.og_title_truncated` (meta),
  `leash.unfurl.og_title_len` / `leash.unfurl.og_description_len`
  (metrics).
- Keep exactly one `<meta name="description">` per page — pass it to
  `views._add_base_meta(h, description=...)`. Emitting a second one
  leaves crawlers that take the first match with the site name.
- Slack caches unfurls per URL; when testing, use an unseen path
  (e.g. a different quote id) or have Slack re-fetch.

## Quote cards (`dundercode.ogimage`, `/og/quote/{id}.png`)

- 1200x630 PNG with the quote typeset over a cream background plus an
  attribution footer. Font size is chosen by fitting: the largest of
  `_QUOTE_SIZES` whose wrapped text fits the box wins, and text that
  overflows even at the smallest size is clipped with an ellipsis.
- Fonts are resolved from a candidate list — Georgia on macOS, DejaVu
  in the Docker image (`fonts-dejavu-core`, installed and *kept* in the
  Dockerfile), Pillow's bundled default as a last resort. A missing font
  must never take the route down.
- Rendering costs ~37ms and is memoised in-process
  (`cached_quote_card`, 256 entries), so repeat hits are instant and
  editing the module clears the cache with the reloader.
- Responses are served `Cache-Control: no-store` **on purpose** while
  the layout is being iterated on: a card cached by a browser, Slack or
  Apple is keyed by URL and can't be re-checked. Once the design
  settles, switch back to `public, max-age=604800, immutable` — the
  transcript is static, so a card never changes.
- The route rejects negative line numbers; `data.get_line(-5)` would
  otherwise wrap to the tail of the transcript and serve a card for an
  unrelated line.
- Card text comes straight from the transcript, so data-level garbage
  shows up as tofu boxes. The U+FFFD mojibake was fixed at the source
  (see below) rather than patched in the renderer.

## Transcript data (`transcript`, `transcript.csv`)

- `transcript` is the Fernet-encrypted CSV that ships; `transcript.csv`
  is the plaintext and is **gitignored**. Editing the data means
  decrypt → edit → `KEY=... python -m scripts.encrypt` (which reads
  `transcript.csv` and overwrites `transcript`). A plaintext edit that
  never gets re-encrypted is invisible to the app — that is exactly how
  the repo ended up with a repaired `transcript.csv` sitting next to an
  unrepaired `transcript` for two years.
- The file is CRLF-terminated with a trailing CRLF; keep it that way
  when rewriting. `data._read_data` splits on `\n`, so the stray `\r`
  lands in the unused `deleted` field.
- Line numbers are positional (`enumerate` over the file), and `/quote/{id}`
  URLs are those indices — **never add or remove lines**, or every
  shared link points at a different quote.
- Speaker names are normalised to one spelling per character. A single
  speaker is a bare name; multiple speakers are joined with **` and `**
  (`Jim and Pam`, `Andy and Creed and Kevin and Kelly`) — not `/`, `&`
  or comma lists, none of which the parser understands. Keep it that way
  when adding data.
- `data._read_data` splits on `" and "` **with** its spaces. A bare
  `"and"` also matches inside Brandon, Randy, Rolando, Amanda and Prince
  Grandfather, which used to split those speakers into fragments.
- Qualified in-scene variants (`Video Michael`, `Michael [on phone]`,
  screen names like `JIM9334` and `Receptionitis15`) are merged into the
  character. Deliberate exceptions, kept separate because they are *not*
  that character: `Fake Jim` (S9E3, an impostor Jim hires),
  `Fake Stanley`, relatives (`Pam's Mom`, `Jim's Dad`), and devices
  (`Kevin's computer`, `Erin's Cell Phone`, `DunMiff/sys`).
- **Main cast go by first name** (`Michael`, `Jim`, `Ryan`, `Nellie`,
  `Jan`, …). **Recurring non-main characters go by full name**:
  `David Wallace`, `Robert California`, `Jo Bennett`, `Carol Stills`,
  `Bob Vance`, `Senator Lipton`, `Diane Kelly`, `Merv Bronte`,
  `Phil Maguire`, `Barbara Allen`, `Fred Henry`, `Paul Faust`,
  `Teddy Wallace`, `Carla Fern`, `Concierge Marie`.
- A first name that means **different people in different episodes** is
  renamed per-episode, not globally: `Robert` is Robert California only
  from S7E24 on (S7E11's Robert is someone else), and `Carla` is Carla
  Fern only in S9E19 (S7E7's Carla is a nurse). Same trap in
  `Walter` (Andy's father) vs `Walter Jr` (his brother), `Julius` vs
  `Julius Irving`, `Professor` (Monaghan) vs `Professor Powell`,
  `Donna` (Newton) vs `Donna Muraski`, and the celebrity cameos
  (`Jessica` vs `Jessica Alba`, `Mark` vs `Mark McGrath`, `Christian` vs
  `Christian Slater`). Check episode overlap before merging any pair.

## AI scene context (`dundercode.ai.scene_context`)

- `/quote/{id}` renders a 1-2 sentence summary above the quote so
  newcomers to The Office have enough context to get the joke. The
  summary is generated from the surrounding scene's lines.
- Requires `OPENAI_API_KEY`. Without it (or on API failure) the call
  returns `None` and the page renders without the blurb — never raise.
- Persistent on-disk cache keyed by `(season, episode, scene)` lives at
  `DUNDERCODE_SCENE_CACHE` (default `cache/scene_context.json`). The
  transcript is static, so each scene is summarised at most once.
- The blurb doubles as `og:description` when the quote fits in
  `og:title` untruncated. Unfurls never *depend* on it: a missing blurb
  falls back to `The Office — S{season}E{episode}`, and the quote itself
  is carried by the title and the card image regardless.
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

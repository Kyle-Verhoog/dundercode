# AGENTS.md — dundercode

Durable notes for coding agents working on this repo. Terse by design.
Add an entry only when a lesson is generalisable beyond the current
task. Do not duplicate what the code or tests already express.

Write everything else that way too — replies, commit messages, PR
bodies. State the finding, not the investigation that produced it.

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
- Keep exactly one `<meta name="description">` per page: crawlers that
  fall back to it take the first one they see.
- Slack caches unfurls per URL; when testing, use an unseen path
  (e.g. a different quote id) or have Slack re-fetch.

## Quote cards (`/og/quote/{id}.png`)

- 1200x630 PNG with the quote typeset over a cream background plus an
  attribution footer. Long quotes shrink to fit and are clipped with an
  ellipsis once even the smallest size overflows.
- Fonts come from a candidate list ending in a bundled fallback, so a
  missing font can't take the route down. The Docker image ships
  `fonts-dejavu-core` for this — keep it installed.
- Cards are served `Cache-Control: no-store` **on purpose** while the
  layout is being iterated on: a card cached by a browser, Slack or
  Apple is keyed by URL and can't be re-checked. Restore the long
  immutable cache once the design settles — the transcript is static,
  so a card never changes.

## Transcript data (`transcript`, `transcript.csv`)

- Line numbers are positional and `/quote/{id}` URLs are those indices —
  **never add or remove lines**, or every shared link points at a
  different quote.
- Speaker names are normalised to one spelling per character. A single
  speaker is a bare name; multiple speakers are joined with **` and `**
  (`Jim and Pam`, `Andy and Creed and Kevin and Kelly`) — never `/`, `&`
  or comma lists.
- The separator is ` and ` **with its spaces**: a bare `and` also occurs
  inside names like Brandon, Randy, Rolando, Amanda and Prince
  Grandfather.
- Names carry their own casing (`AJ`, `David Wallace`) and matching is
  case-insensitive, so never case-fold the data.
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

## Deploys and versioning

- Prod is one container on `verhoog.ca` behind nginx, served at
  `dc.verhoog.ca`. See `.claude/skills/deploy/SKILL.md` for the
  procedure; `scripts/validate_prod.sh` is the smoke test and is
  runnable standalone. `scripts/validate_monitoring.sh` checks the
  service is still observable in Datadog (needs ssh).
- Prod telemetry is queryable through the **Datadog MCP**
  (`service:dundercode env:prod`). Generate traffic first — an idle
  service looks exactly like a broken tracer, in both the MCP and the
  agent's own one-minute stat windows.
- Live spans carry `version:<sha6>`, so comparing that against the
  deployed image tag closes the loop from git commit to running code.
- The APM metric is `trace.asgi.request.hits` — named for the ASGI
  integration, not the app.
- **The app ships its own logs** via `ddclient.LogHandler` (`app.py`),
  with version and trace correlation; `StreamHandler` writes the same
  records to stderr purely for `docker logs`. So dundercode must **not**
  carry a `com.datadoghq.ad.logs` label — that makes the agent tail the
  stderr copy too, landing every line twice with the second copy having
  no version, no trace correlation, and `status:error`.
- Consequently the agent's log-source list says nothing about this
  service: it lists no source for dundercode while logs flow fine.
  Only a backend query settles whether logs are landing.
- Log collection is opt-in per container via the
  `com.datadoghq.ad.logs` label in the compose file — container-collect-all
  is off, so a service without the label ships no logs at all.
- Images are tagged with the **6-char commit SHA prefix**, which is the
  same string `version_use_git=True` makes ddkypy report to Datadog
  (`hexsha[0:6]` of `HEAD`). Image tag, running container and the
  `version:` tag on a span therefore all name one commit. Deploy pinned
  SHA tags; `latest` is published but never deployed.
- The deployed commit is readable off the container:
  `docker exec verhoogca-dundercode-1 git rev-parse HEAD`.
- **`version_use_git` needs `.git` *and* the `git` binary inside the
  image**, and both survive only by accident. `.dockerignore` lists just
  `key`, and `RUN apt remove git gcc` has no `-y`, so it fails and the
  `;` swallows the error. Adding that `-y`, or excluding `.git`, makes
  `DDConfig` raise at import — the app fails to boot, it does not
  degrade to an unset version. Bake `DD_VERSION` at build time if you
  want to remove the coupling.

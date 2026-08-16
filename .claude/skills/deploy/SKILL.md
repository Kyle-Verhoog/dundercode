---
name: deploy
description: Deploy dundercode to production at dc.verhoog.ca and validate it, or roll back a bad deploy. Takes an optional commit-ish to deploy, defaulting to origin/main. Use when asked to deploy, ship, release, or roll back dundercode, or to check whether dc.verhoog.ca is healthy.
---

# Deploying dundercode

Production is a single container on `verhoog.ca`, behind nginx, reachable at
`https://dc.verhoog.ca`. There is no staging. A deploy is: **confirm the image
exists → pin it → restart the container → prove the new code is live.**

## What you may do without asking

Allowed: `ssh verhoog.ca` to inspect and manage containers — `docker ps`,
`docker inspect`, `docker exec`, `docker compose pull`, `docker compose up -d`,
`docker compose logs`.

**Ask first** for anything else on that host, and in particular for `scp`ing the
compose file up (step 3) — that writes config, not just container state.

## Layout

| | |
|---|---|
| host | `verhoog.ca` (ssh as `kyle`, key already trusted) |
| compose project | `~/verhoog.ca` on the server — **not a git repo** |
| config source of truth | `~/dev/verhoog.ca` locally (private repo), synced up by hand |
| container | `verhoogca-dundercode-1` |
| image | `ghcr.io/kyle-verhoog/dundercode/dundercode:<sha6>` |
| port | `5002` → container `8000`, nginx `/etc/nginx/sites-enabled/dundercode` |

The server has **no git auth and no docker login** — that is deliberate. GHCR
holds this package publicly, so pulls work anonymously.

Use `docker compose` (v2). The `docker-compose` v1 shim on that box is broken
(`bad interpreter: /usr/bin/python`).

## Versioning

The image tag is the **6-char commit SHA prefix**, and that is the same string
the app reports to Datadog: `dundercode/dd.py` sets `version_use_git=True`, which
ddkypy resolves at runtime to `hexsha[0:6]` of `HEAD` (the image ships `.git`).

So the deployed commit can always be read straight off the container:

```bash
ssh verhoog.ca 'docker exec verhoogca-dundercode-1 git rev-parse HEAD'
```

Deploy pinned SHA tags only. Never deploy `:latest` — it moves, and a compose
file pinned to it cannot express what is running or roll back.

## Procedure

### 1. Preflight

**The skill takes a commit as its argument** — `/deploy <commit-ish>`, anything
`git rev-parse` accepts. **With no argument it targets `origin/main`, not local
`HEAD`.**

```bash
git fetch origin
TARGET=$(git rev-parse "${1:-origin/main}")
SHA6=${TARGET:0:6}
```

`origin/main` is the default because only commits on `main` ever get an image,
and because this repo merges by squash: right after a merge, the local checkout
is usually still on the PR branch whose tip was *never built*. Defaulting to
`HEAD` there resolves to a commit with no image every time. Local `HEAD` is also
whatever branch you happen to be on, which is rarely what "deploy" means.

Pass an explicit commit to roll back or to deploy something other than main's
tip.

Then check the target is **reachable from `origin/main`** — not that it *is*
main's tip, since deploying an older commit is a legitimate rollback:

```bash
git merge-base --is-ancestor "$TARGET" origin/main || echo "NOT on main"
```

If it is not on `main`, stop: the build workflow's `if:` gate skips every other
branch, so no image was ever published and the deploy would fail at pull time
rather than at validation. A squash-merged PR branch fails this check by design
— its changes are on main, but under a different SHA, and it is that SHA which
has an image. Retarget `origin/main` rather than trying to deploy the branch.

Always report the resolved commit and its subject before going on.

Check the build for that commit with `gh run list --workflow=docker.yml`. If it
is still running, **wait** — `gh run watch <id> --exit-status`, in the background
since it builds two platforms and takes several minutes. Abort if it failed.

Then confirm the tag really landed, before touching the server:

```bash
TOKEN=$(curl -s "https://ghcr.io/token?scope=repository:kyle-verhoog/dundercode/dundercode:pull&service=ghcr.io" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -s -H "Authorization: Bearer $TOKEN" \
  https://ghcr.io/v2/kyle-verhoog/dundercode/dundercode/tags/list
```

### 2. Record the rollback anchor

Capture this **before** changing anything, and show it to the user:

```bash
ssh verhoog.ca 'docker exec verhoogca-dundercode-1 git rev-parse HEAD;
                docker inspect verhoogca-dundercode-1 --format "{{.Image}}"'
```

Roll back by pinning `image:` to the previous SHA tag and repeating steps 3-4.
An image predating SHA tagging has no tag to pin, so for those the digest is the
only way back — pin `dundercode@sha256:<digest>` instead.

### 3. Pin the version and sync config

First diff the server's copy against the repo. Call `/usr/bin/diff` by absolute
path — a shell function shadows `diff` here and dies with `function definition
file not found`, printing **no diff at all**, which reads exactly like a clean
result:

```bash
ssh verhoog.ca 'cat ~/verhoog.ca/docker-compose.yml' \
  | /usr/bin/diff -u ~/dev/verhoog.ca/docker-compose.yml - \
  && echo "DRIFT CHECK: clean"
```

Treat a silent run without the `DRIFT CHECK: clean` line as a failed check, not
as a pass.

**Clean:** proceed. **Drift:** stop and show the user. Do not guess a direction —
the server copy is hand-edited, so it is sometimes *ahead* of the repo, and has
sat that way unnoticed for months. Ask which way to reconcile.

Then set the tag in `~/dev/verhoog.ca/docker-compose.yml`:

```yaml
image: ghcr.io/kyle-verhoog/dundercode/dundercode:<sha6>
```

Leave it **uncommitted** for now and **ask** before:

```bash
scp ~/dev/verhoog.ca/docker-compose.yml verhoog.ca:~/verhoog.ca/docker-compose.yml
```

The commit comes after validation (step 7), not here. That repo's history is the
deploy log, so a deploy that fails and gets rolled back must not leave behind a
commit claiming the version shipped.

### 4. Deploy

```bash
ssh verhoog.ca 'cd ~/verhoog.ca && docker compose pull dundercode && docker compose up -d dundercode'
```

Pipe through `tail` — the pull emits hundreds of progress-bar lines.

`dundercode` `depends_on` `datadog`, so this also starts the datadog agent if it
is down. Expected, not a mistake — mention it rather than letting it look like
one.

### 5. Verify

Assert the container is running the intended commit:

```bash
ssh verhoog.ca 'docker exec verhoogca-dundercode-1 git rev-parse HEAD'   # == $TARGET
```

Then run the smoke tests. Allow a few seconds first — the app decrypts and parses
the whole transcript at import, so it serves nothing until that finishes:

```bash
./scripts/validate_prod.sh
```

All checks must pass. Every one asserts on response **content**, never status
alone — this app returns 200 on failure. `/scene/1000` (a malformed scene id)
answers 200 with a zero-byte body, because the handler raises after the status
has been sent. A status-only smoke test would call that healthy.

A bad `$DUNDERCODE_KEY` is *not* a failure mode to probe for: `crypt.py` builds
a Fernet from it at import and `data.py` decrypts the whole transcript at module
level, so a wrong key raises `InvalidToken` and the container never serves at
all. That shows up as a crash loop in step 4, not as bad content here.

If checks fail, roll back per step 2 rather than debugging in place.

### 6. Confirm it is still monitored

A deploy can serve perfect responses and silently stop being observable — a
tracer that fails to start, or a `DD_ENV` that no longer matches the sampler key.

Drive traffic first. Datadog shows nothing for an idle service, and that looks
identical to a broken tracer:

```bash
for i in 1 2 3 4 5; do
  curl -s -o /dev/null https://dc.verhoog.ca/quote/$((2000+i))
  curl -s -o /dev/null https://dc.verhoog.ca/search/beets
  curl -s -o /dev/null https://dc.verhoog.ca/og/quote/$((2000+i)).png
done
```

Then query the **Datadog MCP** (`mcp__datadog__*`). Load the `datadog/traces`
skill first — the server asks for skill discovery before its tools.

**Traces.** `aggregate_spans`, not `search_datadog_spans`, for counts: raw span
results carry deeply nested tag blocks and will swamp the context even at modest
volumes. Query `service:dundercode env:prod` over `now-15m` and check:

- spans exist at all
- **the deployed `<sha6>` is what is running** — the single best check in this
  whole procedure. It closes the loop end to end: git commit → image tag →
  running container → live telemetry. If this disagrees, the container is not
  running what you think it is.
- `status:error` spans have not appeared

Filter on **`image_tag:<sha6>`**, which is a real tag and works in queries.
`version:<sha6>` does *not* — the version lives in span custom data, not as a
searchable facet, so that query returns zero for a perfectly healthy service.
Neither `version` nor `status` is groupable either; grouping on them yields zero
buckets. Group by `resource_name` for a per-endpoint breakdown, and read
`version` off a raw span when you want to see it directly.

Whenever a query comes back empty, re-run it without the filters before
concluding anything — an empty result here is far more often a wrong facet than
a broken deploy.

Expected resources: `GET /`, `GET /quote/?`, `GET /search/beets`,
`GET /og/quote/?`, plus custom spans `route`, `render`, and
`dundercode.data.find_lines` carrying `leash.search.*` tags.

**Metrics.** The APM metric is `trace.asgi.request.hits` (with `.duration`,
`.apdex`, `.hits.by_http_status`). The span is named for the ASGI integration,
not for the app — do not guess at `trace.route.*` or `trace.dundercode.*`.
`ml_obs.span` / `ml_obs.trace` cover LLM Obs.

**Logs.** `search_datadog_logs` on `service:dundercode env:prod`. Expect single
records prefixed with their logger name (`uvicorn.access:`, `dundercode.pages:`)
carrying `version`, `trace_id` and `status:info`.

**The app ships its own logs**, via `ddclient.LogHandler` in `dundercode/app.py`
— it does not rely on the agent tailing the container. So the compose file
deliberately carries **no `com.datadoghq.ad.logs` label** for dundercode. Adding
one makes the agent *also* collect the `StreamHandler` copy off stderr: every
line lands twice, and the second copy arrives with no version, no trace
correlation, and `status:error` (stderr maps to error), double-billing ingest
and poisoning error-rate queries.

Corollary: the agent's own log-source list is **not** evidence about this
service either way. It showed nothing for dundercode while logs were flowing
perfectly — the app's path bypasses it. Only a backend query settles it.

**If traces look thin or absent** after real traffic, the backend cannot tell you
why — spans the agent drops or rejects never reach it. Ask the agent directly:

```bash
ssh verhoog.ca 'docker exec verhoogca-datadog-1 agent status -j' \
  | python3 -c 'import json,sys; a=json.load(sys.stdin)["apmStats"];
print(a["receiver"]); print(a["trace_writer"])'
```

Look for a receiver entry naming this service, non-zero `TracesDropped` /
`SpansDropped` / `PayloadRefused`, and writer `Errors`. Note the receiver reports
one-minute windows, so an idle service is absent from it — drive traffic first,
and never read absence as failure.

### 7. Record the deploy

Only once validation is green, commit the pin in `~/dev/verhoog.ca` — subject
line `Deploy dundercode <sha6>` — and push. That commit is the deploy log entry,
so it should only ever describe a deploy that actually survived steps 5-6.

Report to the user: the commit deployed, the tag, and the check results.

### 8. Reclaim disk

Deploys leave the superseded image behind, and `/` on that box is small enough
that they add up — check `df -h /` and `docker system df` first, and report both.
Prune **last**, only after step 6 is green:

```bash
ssh verhoog.ca 'docker system prune -af --filter "until=24h"'
```

`-a` is what actually reclaims anything here: superseded images keep their SHA
tags, so they are never *dangling* and a bare `docker system prune` frees ~0B.
`--filter "until=24h"` then spares the last day's images, keeping the immediately
previous deploy on disk as the fast rollback path.

This is safe because deploys are pinned to SHA tags that persist in GHCR — a
pruned image is always re-pullable. Images predating SHA tagging are the
exception: those exist only under a `latest` that has since moved, so pruning
them is irreversible.

Report reclaimed space. If the filter spares everything and the disk is still
tight, say so rather than quietly widening it — dropping `until=24h` deletes the
rollback image.

## Working directory

Steps that touch `git`, `gh` or `./scripts/` assume you are in the repo holding
this skill. Shell cwd resets between calls, so `cd` there in the same command or
use absolute paths — otherwise `git rev-parse origin/main` resolves against
whichever repo you last visited and fails with `unknown revision`.

## Known sharp edges

- **Boot depends on `.git` + the `git` binary being in the image**, both true only
  by accident: `.dockerignore` lists just `key`, and `RUN apt remove git gcc` has
  no `-y`, so it fails and `;` swallows it. "Fixing" either makes `DDConfig`
  raise at import and the app fail to start outright. See AGENTS.md.
- **`/search` with no trailing slash** slices to an empty query and returns the
  entire transcript in one response.
- **`og:url` and `og:image` are emitted as `http://`**, though the site is
  HTTPS-only. nginx does not set `X-Forwarded-Proto`, so the app cannot see the
  real scheme. Unfurlers follow the 301, but it is worth fixing at the nginx
  layer.

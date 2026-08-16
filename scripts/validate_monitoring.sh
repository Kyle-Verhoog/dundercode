#!/usr/bin/env bash
# Verify prod dundercode is actually observed in Datadog: traces reaching the
# agent, no spans dropped or malformed, metrics parsing, logs tailed.
#
#   ./scripts/validate_monitoring.sh [BASE_URL]
#
# Needs ssh to the host, unlike validate_prod.sh. Takes ~40-100s: the agent
# aggregates receiver stats into one-minute windows, and an idle service simply
# does not appear in them -- so this generates traffic first, then waits for a
# window containing it.

set -uo pipefail

BASE_URL="${1:-https://dc.verhoog.ca}"
HOST="${DUNDERCODE_SSH_HOST:-verhoog.ca}"
AGENT_CONTAINER="verhoogca-datadog-1"
SERVICE="dundercode"
DD_ENV="prod"

echo "Generating traffic against $BASE_URL"
for i in 1 2 3 4 5; do
  curl -s -o /dev/null "$BASE_URL/quote/$((1000 + i))"
  curl -s -o /dev/null "$BASE_URL/search/beets"
  curl -s -o /dev/null "$BASE_URL/og/quote/$((1000 + i)).png"
done

# Poll for a stats window that contains our traffic rather than sleeping a fixed
# 70s -- usually lands on the first or second try.
status_json=""
for attempt in 1 2 3; do
  echo "Waiting for the agent's stats window (attempt $attempt/3)..."
  sleep 35
  status_json=$(ssh "$HOST" "docker exec $AGENT_CONTAINER agent status -j 2>/dev/null")
  # Look only at the APM receiver. A plain grep for the service name also hits
  # the logs config (the container carries a com.datadoghq.ad.logs label naming
  # the same service), which ends the wait before any trace data arrives.
  if [ -n "$status_json" ] && printf '%s' "$status_json" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except ValueError:
    sys.exit(1)
recv = d.get("apmStats", {}).get("receiver") or []
sys.exit(0 if any(r.get("Service") == sys.argv[1] for r in recv) else 1)
' "$SERVICE"; then
    break
  fi
done

if [ -z "$status_json" ]; then
  echo "FAIL  could not read agent status from $AGENT_CONTAINER on $HOST"
  exit 1
fi

# The status JSON goes via a file, not a pipe: the heredoc below already owns
# stdin, so a piped payload would never reach python.
status_file=$(mktemp)
trap 'rm -f "$status_file"' EXIT
printf '%s' "$status_json" > "$status_file"

python3 - "$SERVICE" "$DD_ENV" "$status_file" <<'PY'
import json, sys

service, env = sys.argv[1], sys.argv[2]
with open(sys.argv[3]) as f:
    d = json.load(f)
apm = d.get("apmStats", {})

passed = failed = 0
def ok(msg):
    global passed; passed += 1; print("  \033[32mPASS\033[0m  %s" % msg)
def bad(msg, detail=""):
    global failed; failed += 1; print("  \033[31mFAIL\033[0m  %s" % msg)
    if detail: print("        %s" % detail)
def warn(msg, detail=""):
    print("  \033[33mWARN\033[0m  %s" % msg)
    if detail: print("        %s" % detail)

print()

# --- APM: is the service sending traces at all? ---
entry = next((r for r in apm.get("receiver", []) if r.get("Service") == service), None)
if entry is None:
    seen = sorted({r.get("Service", "?") for r in apm.get("receiver", [])})
    bad("APM traces received", "no receiver entry for %r; saw: %s" % (service, seen or "none"))
else:
    traces, spans = entry.get("TracesReceived", 0), entry.get("SpansReceived", 0)
    if traces > 0 and spans > 0:
        ok("APM traces received (%d traces, %d spans, %s %s)"
           % (traces, spans, entry.get("Lang"), entry.get("TracerVersion")))
    else:
        bad("APM traces received", "entry present but %d traces / %d spans" % (traces, spans))

    # --- APM: is anything being lost or rejected? ---
    # These counters are a mix of scalars and reason-keyed dicts (TracesDropped
    # breaks down by DecodingError, EmptyTrace, ...), so flatten both shapes.
    def nonzero(name, value):
        if isinstance(value, dict):
            return [("%s.%s" % (name, k), v) for k, v in value.items() if v]
        return [(name, value)] if value else []

    lossy = [kv for n in ("PayloadRefused", "TracesDropped", "SpansDropped",
                          "ClientDroppedP0Traces")
             for kv in nonzero(n, entry.get(n, 0))]
    if lossy:
        bad("no traces dropped", ", ".join("%s=%d" % kv for kv in sorted(lossy)))
    else:
        ok("no traces dropped or refused")

    malformed = {k: v for k, v in (entry.get("SpansMalformed") or {}).items() if v}
    if malformed:
        bad("no malformed spans", ", ".join("%s=%d" % kv for kv in sorted(malformed.items())))
    else:
        ok("no malformed spans")

# --- APM: has the sampler keyed this service+env yet? Only a WARN: the rate map
# is repopulated lazily after a container recreate, so it can be empty for
# minutes while traces flow perfectly. Absence is not evidence of mistagging --
# query spans over the Datadog MCP to confirm env for real. ---
key = "service:%s,env:%s" % (service, env)
rates = apm.get("ratebyservice") or {}
if key in rates:
    ok("sampler knows %s (rate %.0f%%)" % (key, rates[key] * 100))
else:
    warn("sampler has not keyed %s yet" % key,
         "ratebyservice: %s -- normal shortly after a recreate" % json.dumps(rates))

# --- APM: are traces leaving the host, not just arriving at the agent? ---
tw = apm.get("trace_writer") or {}
if tw.get("Errors", 0) or tw.get("Retries", 0):
    bad("trace writer healthy",
        "errors=%d retries=%d" % (tw.get("Errors", 0), tw.get("Retries", 0)))
else:
    ok("trace writer healthy")

# --- Metrics ---
ds = d.get("dogstatsdStats") or {}
errs = {k: ds.get(k, 0) for k in
        ("MetricParseErrors", "UnterminatedMetricErrors", "UdpPacketReadingErrors")}
bad_errs = {k: v for k, v in errs.items() if v}
if bad_errs:
    bad("dogstatsd healthy", ", ".join("%s=%d" % kv for kv in sorted(bad_errs.items())))
elif ds.get("MetricPackets", 0) > 0:
    ok("dogstatsd healthy (%s metric packets)" % format(ds["MetricPackets"], ","))
else:
    bad("dogstatsd healthy", "no metric packets received")

# --- Logs: the agent should NOT be tailing this container. ---
# dundercode ships its own logs via ddclient.LogHandler, so the agent tailing it
# too would double-bill every line and file the stderr copies as status:error.
# An absent source here is correct; this check cannot see the app's own path at
# all -- only a backend query (the Datadog MCP) can confirm logs actually land.
sources = [s for i in (d.get("logsStats") or {}).get("integrations", [])
           for s in i.get("sources", [])]
tailed = {s.get("configuration", {}).get("Service") for s in sources}
if service in tailed:
    bad("agent is not double-collecting logs",
        "agent is tailing %s's container log, but the app already ships its own "
        "-- remove the com.datadoghq.ad.logs label from docker-compose.yml" % service)
else:
    ok("agent is not double-collecting logs")

print()
print("%d passed, %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
PY

#!/usr/bin/env bash
# Smoke-test a deployed dundercode. Usable standalone, not just after a deploy.
#
#   ./scripts/validate_prod.sh [BASE_URL]
#
# Every check asserts on *content*, never on status alone. This app returns 200
# on failure: /scene/1000 (a malformed scene id) answers 200 with a zero-byte
# body rather than a 404, because the handler raises after the status is sent.
# A status-only smoke test would call that healthy.

set -uo pipefail

BASE_URL="${1:-https://dc.verhoog.ca}"
PASS=0
FAIL=0

pass() { printf '  \033[32mPASS\033[0m  %s\n' "$1"; PASS=$((PASS + 1)); }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; printf '        %s\n' "$2"; FAIL=$((FAIL + 1)); }

# fetch <path> <body-file> -> "<status> <content-type>"
fetch() {
  curl -sS --max-time 30 -o "$2" -w '%{http_code} %{content_type}' "$BASE_URL$1"
}

# Shared status/content-type gate. Returns non-zero once it has reported.
_head_ok() {
  local name=$1 path=$2 want_ct=$3 status=$4 ct=$5
  if [ "$status" != "200" ]; then
    fail "$name" "$path -> HTTP $status (want 200)"; return 1
  fi
  if [[ "$ct" != "$want_ct"* ]]; then
    fail "$name" "$path -> Content-Type ${ct:-<none>} (want $want_ct)"; return 1
  fi
  return 0
}

# check_html <name> <path> <needle>...
check_html() {
  local name=$1 path=$2; shift 2
  local body status ct needle
  body=$(mktemp)
  read -r status ct <<<"$(fetch "$path" "$body")"
  if _head_ok "$name" "$path" "text/html" "$status" "$ct"; then
    for needle in "$@"; do
      if ! grep -qF -- "$needle" "$body"; then
        fail "$name" "$path -> body missing expected text: $needle"
        rm -f "$body"; return
      fi
    done
    pass "$name"
  fi
  rm -f "$body"
}

# check_png <name> <path>
# Magic bytes are compared as hex rather than grepped: a \x89 needle does not
# match reliably through grep -F, which fails *silently* and looks like a bad
# deploy. Confirmed against a known-good PNG.
check_png() {
  local name=$1 path=$2
  local body status ct magic size
  body=$(mktemp)
  read -r status ct <<<"$(fetch "$path" "$body")"
  if _head_ok "$name" "$path" "image/png" "$status" "$ct"; then
    magic=$(head -c 4 "$body" | xxd -p)
    size=$(wc -c < "$body" | tr -d ' ')
    if [ "$magic" != "89504e47" ]; then
      fail "$name" "$path -> not a PNG (magic ${magic:-<empty>})"
    elif [ "$size" -lt 1000 ]; then
      fail "$name" "$path -> suspiciously small: ${size}b"
    else
      pass "$name ($((size / 1024))kb)"
    fi
  fi
  rm -f "$body"
}

echo "Validating $BASE_URL"
echo

# Homepage renders and ships its search UI.
check_html "index"    "/"            "doSearch"

# Decryption works: line 1000 is a known Pam line from S1E4. Garbled output from
# a bad key fails here even though the status is 200.
check_html "quote"    "/quote/1000"  "Pam" "S1E4"

# Search tokenises and matches: "beets" is Dwight's, unambiguously.
check_html "search"   "/search/beets" "Dwight"

# Scene route takes season,episode,scene -- not a bare id.
check_html "scene"    "/scene/1,4,2" "<h2"

# The quote must lead og:title -- iMessage and Google Messages render nothing else.
check_html "og:title" "/quote/1000"  'property="og:title"' "— Pam, S1E4"

# Generated quote card. A 404 here means an image predating the card work.
check_png  "og card"  "/og/quote/1000.png"

echo
printf '%d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]

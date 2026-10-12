#!/usr/bin/env bash
# skill-review.sh: gated, isolated review of one skill from an official source (subagent-pool v9.5).
#
#   skill-review.sh --dry-run            <repo_url> <commit_sha> <id> [--subpath DIR] [--out DIR]
#   skill-review.sh --approved-by-user   <repo_url> <commit_sha> <id> [--subpath DIR] [--out DIR]
#
# --dry-run prints every command and runs none (no clone, no docker run, no model).
# A real review refuses to start without --approved-by-user. The Conductor asks the user
# first, with the estimated token cost, every time, and passes the flag only after an
# explicit yes. stdout of a real run is the verdict JSON only. The skill copy (APPROVED
# only), pre-scan and report stay in --out (default ~/.cache/subagent-pool/reviews/<id>-<sha8>).
#
# Container 1 (pre-scan): --network none, read-only skill, stdlib-only scanner.
# Container 2 (reviewer): internal network whose only exit is an allow-list proxy.
# Reviewer = latest astra from codex-models.py; claude-fable-5-1 only if that attempt fails.
# Exit codes: 0 verdict printed, 2 usage or not official, 3 gate refused, 4 review failed.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRESCAN_IMAGE="${SKILL_REVIEW_PRESCAN_IMAGE:-python:3.13-slim}"
PROXY_IMAGE="${SKILL_REVIEW_PROXY_IMAGE:-ubuntu/squid:latest}"
CODEX_IMAGE="${SKILL_REVIEW_CODEX_IMAGE:-skill-review-codex:local}"
CLAUDE_IMAGE="${SKILL_REVIEW_CLAUDE_IMAGE:-skill-review-claude:local}"
CACHE_ROOT="${SKILL_REVIEW_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/subagent-pool/reviews}"
PROMPT="$SCRIPT_DIR/../assets/skill-review-prompt.md"
FABLE_MODEL="claude-fable-5-1"
CODEX_HOSTS="api.openai.com chatgpt.com"
CLAUDE_HOSTS="api.anthropic.com"

DRY=0
APPROVED=0
SUBPATH=""
OUT=""
POS=()

die() {
  local code=$1
  shift
  echo "skill-review: $*" >&2
  exit "$code"
}

usage() {
  sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --approved-by-user) APPROVED=1 ;;
    --subpath) [ $# -ge 2 ] || die 2 "--subpath needs a value"; SUBPATH=$2; shift ;;
    --out) [ $# -ge 2 ] || die 2 "--out needs a value"; OUT=$2; shift ;;
    -h|--help) usage; exit 0 ;;
    -*) die 2 "unknown flag: $1" ;;
    *) POS+=("$1") ;;
  esac
  shift
done

[ "${#POS[@]}" -eq 3 ] || die 2 "usage: skill-review.sh [--dry-run|--approved-by-user] <repo_url> <commit_sha> <id> [--subpath DIR] [--out DIR]"
URL=${POS[0]}
SHA=${POS[1]}
ID=${POS[2]}

[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || die 2 "commit must be a full 40-char lowercase SHA"
[[ "$ID" =~ ^[a-z0-9][a-z0-9-]*$ ]] || die 2 "id must match ^[a-z0-9][a-z0-9-]*\$"
if [ -n "$SUBPATH" ]; then
  case "$SUBPATH" in
    /*|*..*) die 2 "--subpath must be relative and must not contain .." ;;
  esac
fi
python3 -I "$SCRIPT_DIR/skills_lib.py" official "$URL" >/dev/null || die 2 "not an official source (assets/official-sources.json): $URL"

# Gate: a real review needs the explicit user approval flag. Dry-run is always allowed.
if [ "$DRY" = 0 ] && [ "$APPROVED" = 0 ]; then
  die 3 "refused: a real review needs --approved-by-user. Ask the user first (prose, with the estimated token cost); pass the flag only after an explicit yes."
fi

# Reviewer candidate: latest astra (role review). Empty when unknown, which means Fable only.
CODEX_SLUG=$(python3 -I "$SCRIPT_DIR/codex-models.py" 2>/dev/null | python3 -I -c '
import json, sys
try:
    print(json.load(sys.stdin).get("review") or "")
except Exception:
    print("")
' || true)
if ! [[ "$CODEX_SLUG" =~ ^gpt-[0-9.]+-astra$ ]]; then
  CODEX_SLUG=""
fi

NAME="skillrev-${SHA:0:8}-$$"

if [ "$DRY" = 1 ]; then
  STAGE="<staging-dir>"
  OUT=${OUT:-"<out-dir>"}
else
  STAGE=$(mktemp -d)
  OUT=${OUT:-"$CACHE_ROOT/$ID-${SHA:0:8}"}
  mkdir -p "$OUT"
fi

cleanup() {
  [ "$DRY" = 1 ] && return 0
  [ -d "$STAGE" ] && rm -rf "$STAGE"
  return 0
}
trap cleanup EXIT

# run <stdout-target|-|/dev/null> <cmd...>: prints the command in dry-run, runs it otherwise.
run() {
  local target=$1
  shift
  if [ "$DRY" = 1 ]; then
    printf '+'
    printf ' %q' "$@"
    [ "$target" = "-" ] || printf ' > %s' "$target"
    printf '\n'
    return 0
  fi
  if [ "$target" = "-" ]; then
    "$@"
  else
    "$@" > "$target"
  fi
}

write_squid_conf() {  # write_squid_conf <file> <host...>
  local file=$1
  shift
  run "$file" printf '%s\n' \
    "http_port 3128" \
    "acl SSL_ports port 443" \
    "acl CONNECT method CONNECT" \
    "acl review_api dstdomain $*" \
    "http_access deny !SSL_ports" \
    "http_access allow CONNECT review_api" \
    "http_access deny all" \
    "cache deny all"
}

drop_reviewer_net() {  # drop_reviewer_net <proxy> <net>
  if [ "$DRY" = 1 ]; then
    printf '+ docker rm -f %s\n+ docker network rm %s\n' "$1" "$2"
    return 0
  fi
  docker rm -f "$1" >/dev/null 2>&1 || true
  docker network rm "$2" >/dev/null 2>&1 || true
}

# review_with <codex|claude>: one reviewer attempt in container 2. Returns non-zero on any failure.
review_with() {
  local kind=$1 hosts image reviewer net proxy
  if [ "$kind" = codex ]; then
    hosts=$CODEX_HOSTS; image=$CODEX_IMAGE; reviewer=$CODEX_SLUG
  else
    hosts=$CLAUDE_HOSTS; image=$CLAUDE_IMAGE; reviewer=$FABLE_MODEL
  fi
  net="$NAME-$kind-net"
  proxy="$NAME-$kind-proxy"

  write_squid_conf "$STAGE/squid-$kind.conf" $hosts || return 1
  run "$STAGE/in/meta.json" python3 -I -c '
import json, sys
print(json.dumps({"id": sys.argv[1], "source_url": sys.argv[2], "commit": sys.argv[3], "reviewer": sys.argv[4]}, indent=2))
' "$ID" "$URL" "$SHA" "$reviewer" || return 1
  run /dev/null docker network create --internal "$net" || return 1
  run /dev/null docker run -d --rm --name "$proxy" \
    -v "$STAGE/squid-$kind.conf:/etc/squid/squid.conf:ro" "$PROXY_IMAGE" || { drop_reviewer_net "$proxy" "$net"; return 1; }
  run /dev/null docker network connect "$net" "$proxy" || { drop_reviewer_net "$proxy" "$net"; return 1; }

  local auth_mount=()
  if [ "$DRY" = 0 ]; then
    rm -f "$STAGE/review/review.json" "$STAGE/review/report.md"  # never reuse a previous attempt's output
  fi
  if [ "$kind" = codex ]; then
    if [ "$DRY" = 0 ] && [ ! -f "$HOME/.codex/auth.json" ]; then
      echo "skill-review: no $HOME/.codex/auth.json for codex" >&2
      drop_reviewer_net "$proxy" "$net"
      return 1
    fi
    auth_mount=(-v "$HOME/.codex/auth.json:/run/secrets/codex-auth.json:ro")
    run "$STAGE/review/$kind.log" docker run --rm --network "$net" --read-only --cap-drop ALL \
      --security-opt no-new-privileges --user 65534:65534 --memory 2g --pids-limit 256 \
      --tmpfs /tmp:rw,nosuid,size=512m \
      -e HTTPS_PROXY="http://$proxy:3128" -e HTTP_PROXY="http://$proxy:3128" \
      -v "$SRC:/skill:ro" -v "$STAGE/in:/in:ro" -v "$STAGE/review:/out" \
      "${auth_mount[@]}" \
      "$image" sh -c 'mkdir -p /tmp/codex && cp /run/secrets/codex-auth.json /tmp/codex/auth.json \
        && cd /tmp && CODEX_HOME=/tmp/codex codex exec -m "$1" -s read-only --skip-git-repo-check \
        -o /out/review.json - < /in/prompt.md' sh "$reviewer"
  else
    run "$STAGE/review/$kind.log" docker run --rm --network "$net" --read-only --cap-drop ALL \
      --security-opt no-new-privileges --user 65534:65534 --memory 2g --pids-limit 256 \
      --tmpfs /tmp:rw,nosuid,size=512m \
      -e HTTPS_PROXY="http://$proxy:3128" -e HTTP_PROXY="http://$proxy:3128" \
      -e ANTHROPIC_API_KEY \
      -v "$SRC:/skill:ro" -v "$STAGE/in:/in:ro" -v "$STAGE/review:/out" \
      "$image" sh -c 'cd /tmp && claude -p --model "$1" < /in/prompt.md > /out/review.json' sh "$reviewer"
  fi
  local rc=0
  if [ "$DRY" = 0 ]; then
    python3 -I "$SCRIPT_DIR/skills_lib.py" split-review "$STAGE/review/review.json" "$STAGE/review/report.md" \
      "$SHA" "$URL" > "$STAGE/review/verdict.json" 2>>"$STAGE/review/$kind.log" || rc=1
  else
    run "$STAGE/review/verdict.json" python3 -I "$SCRIPT_DIR/skills_lib.py" split-review \
      "$STAGE/review/review.json" "$STAGE/review/report.md" "$SHA" "$URL"
  fi
  drop_reviewer_net "$proxy" "$net"
  return "$rc"
}

# ---- staging: fetch the pinned commit with git objects only, no checkout, no hooks ----
run /dev/null mkdir -p "$STAGE/src" "$STAGE/in" "$STAGE/review"
run /dev/null git init -q "$STAGE/repo"
run /dev/null env GIT_TERMINAL_PROMPT=0 git -C "$STAGE/repo" fetch -q --depth 1 "$URL" "$SHA"
run /dev/null git -C "$STAGE/repo" cat-file -e "$SHA^{commit}"
run "$STAGE/src.tar" git -C "$STAGE/repo" archive "$SHA"
run /dev/null tar -xf "$STAGE/src.tar" -C "$STAGE/src" --no-same-owner
SRC="$STAGE/src"
[ -n "$SUBPATH" ] && SRC="$STAGE/src/$SUBPATH"
if [ "$DRY" = 0 ] && [ ! -d "$SRC" ]; then
  die 2 "subpath not found in $SHA: $SUBPATH"
fi
run /dev/null cp "$PROMPT" "$STAGE/in/prompt.md"

# ---- container 1: offline static pre-scan ----
run "$STAGE/in/prescan.json" docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges --user 65534:65534 --memory 256m --pids-limit 64 \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  -v "$SRC:/skill:ro" -v "$SCRIPT_DIR/skill_prescan.py:/opt/skill_prescan.py:ro" \
  "$PRESCAN_IMAGE" python3 -I /opt/skill_prescan.py /skill || die 4 "pre-scan failed"

# ---- container 2: reviewer (Codex astra first, Fable only if that attempt fails) ----
if [ "$DRY" = 1 ]; then
  echo "# reviewer attempt 1: codex ${CODEX_SLUG:-<no astra slug: skipped>}; hosts: $CODEX_HOSTS" >&2
  [ -n "$CODEX_SLUG" ] && review_with codex
  echo "# reviewer attempt 2 (only if attempt 1 fails): $FABLE_MODEL; hosts: $CLAUDE_HOSTS" >&2
  review_with claude
  echo "# gate: real run requires --approved-by-user (not given: dry-run only)" >&2
  exit 0
fi

REVIEWER=""
if [ -n "$CODEX_SLUG" ] && review_with codex; then
  REVIEWER=$CODEX_SLUG
else
  echo "skill-review: codex unavailable or failed; falling back to $FABLE_MODEL" >&2
  review_with claude || die 4 "review did not complete (codex and $FABLE_MODEL failed); no verdict"
  REVIEWER=$FABLE_MODEL
fi

cp "$STAGE/review/verdict.json" "$OUT/verdict.json"
cp "$STAGE/review/report.md" "$OUT/report.md"
cp "$STAGE/in/prescan.json" "$OUT/prescan.json"
rm -rf "$OUT/skill"
VERDICT=$(python3 -I -c 'import json, sys; print(json.load(open(sys.argv[1]))["verdict"])' "$OUT/verdict.json")
if [ "$VERDICT" = APPROVED ]; then
  cp -a "$SRC" "$OUT/skill"
fi
echo "skill-review: reviewer $REVIEWER, verdict $VERDICT, artifacts in $OUT" >&2
cat "$OUT/verdict.json"
exit 0

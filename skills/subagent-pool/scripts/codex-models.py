#!/usr/bin/env python3
"""Resolve the Codex model slug per subagent-pool role from the local Codex cache.

Reads ~/.codex/models_cache.json (override: --cache PATH or CODEX_MODELS_CACHE).
Only models with visibility == "list" and a slug matching gpt-<version>-<family>
are considered. Versions are compared as numeric tuples (6.1 > 6 > 5.6). The
latest version per family wins.

Output: one JSON object on stdout. Always exits 0. When the cache is missing,
corrupt or older than MAX_AGE_DAYS, every role is null with source "default",
so codex-agent omits -m and Codex uses its own default model.

Stdlib only.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

DEFAULT_CACHE = os.path.join(os.path.expanduser("~"), ".codex", "models_cache.json")
MAX_AGE_DAYS = 14  # cache older than this (by fetched_at) is treated as stale
MAX_AGE = timedelta(days=MAX_AGE_DAYS)
FAMILY_RE = re.compile(r"^gpt-(\d+(?:\.\d+)*)-(astra|sol|terra|luna)$")
ROLE_FAMILY = {
    "plan": "astra",
    "review": "astra",
    "implement": "sol",
    "implement-light": "luna",
}
ROLES = tuple(ROLE_FAMILY)


def parse_fetched_at(value):
    """Parse ISO 8601 timestamps as written by Codex (nanosecond fraction, trailing Z)."""
    if not isinstance(value, str):
        raise ValueError("fetched_at is not a string")
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    # Python 3.10 fromisoformat accepts only 3 or 6 fraction digits; truncate to 6.
    text = re.sub(r"\.(\d+)", lambda m: "." + m.group(1)[:6].ljust(6, "0"), text, count=1)
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def version_tuple(version):
    return tuple(int(part) for part in version.split("."))


def latest_by_family(models):
    """Return {family: slug} with the highest numeric version per family."""
    best = {}
    for model in models:
        if not isinstance(model, dict) or model.get("visibility") != "list":
            continue
        slug = model.get("slug")
        if not isinstance(slug, str):
            continue
        match = FAMILY_RE.match(slug)
        if not match:
            continue
        version, family = match.group(1), match.group(2)
        key = version_tuple(version)
        if family not in best or key > best[family][0]:
            best[family] = (key, slug)
    return {family: slug for family, (_, slug) in best.items()}


def fallback(reason, fetched_at=None):
    result = {role: None for role in ROLES}
    result["source"] = "default"
    result["fetched_at"] = fetched_at
    result["note"] = "fallback: " + reason + " — omit -m so Codex uses its default model"
    return result


def resolve(cache_path, now=None):
    """Resolve roles from cache_path. `now` is injectable for tests."""
    now = now or datetime.now(timezone.utc)
    try:
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as exc:
        return fallback("cache not readable (%s)" % exc.strerror)
    except ValueError:
        return fallback("cache is not valid JSON")

    if not isinstance(data, dict) or not isinstance(data.get("models"), list):
        return fallback("cache has unexpected shape")

    raw_fetched = data.get("fetched_at")
    try:
        fetched = parse_fetched_at(raw_fetched)
    except (ValueError, TypeError):
        return fallback("cache fetched_at missing or unparseable", raw_fetched)

    if now - fetched > MAX_AGE:
        return fallback("cache older than %d days" % MAX_AGE_DAYS, raw_fetched)

    families = latest_by_family(data["models"])
    result = {role: families.get(family) for role, family in ROLE_FAMILY.items()}
    result["source"] = "cache"
    result["fetched_at"] = raw_fetched
    missing = [role for role in ROLES if result[role] is None]
    if missing:
        result["note"] = "no model found for role(s): " + ", ".join(missing)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--cache",
        default=os.environ.get("CODEX_MODELS_CACHE", DEFAULT_CACHE),
        help="path to models_cache.json (default: $CODEX_MODELS_CACHE or ~/.codex/models_cache.json)",
    )
    args = parser.parse_args(argv)

    result = resolve(args.cache)
    if result["source"] == "default":
        print("codex-models: " + result["note"], file=sys.stderr)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

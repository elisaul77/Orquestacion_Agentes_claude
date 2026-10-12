#!/usr/bin/env python3
"""Validator and lookup for the private skills-probadas library (stdlib only).

Layout and rules: skills/subagent-pool/assets/skills-library.md

CLI:
  python3 skills_lib.py validate <library_dir>        exit 0 valid, 1 invalid
  python3 skills_lib.py lookup <library_dir> <name>   JSON on stdout, exit 0 / 1 if invalid
"""
import json
import os
import re
import sys
from datetime import datetime

LIBRARY_VERSION = 1
INDEX_FILE = "index.json"
VETADAS_FILE = "vetadas.json"

VERDICTS = ("APPROVED", "REJECTED", "DOUBTFUL")
VETO_VERDICTS = ("REJECTED", "DOUBTFUL")

COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")  # full lowercase SHA-1, as printed by git
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")  # slug: safe as a directory name
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CLAUDE_REVIEWER = "claude-fable-5-1"
CODEX_REVIEWER_RE = re.compile(r"^gpt-\d+(\.\d+)*-(astra|sol|terra|luna)$")  # Codex slug

COMMON_FIELDS = ("id", "source_url", "commit", "date", "reviewer", "verdict")
INDEX_FIELDS = COMMON_FIELDS + ("name", "report", "path")
VETO_FIELDS = COMMON_FIELDS + ("reason",)

# F4 extension point: freshness (last_update vs model release) and official-source
# checks plug in here. Each callable receives (entry, kind) with kind "index" or
# "veto" and returns a list of error strings. Empty on purpose in F3.
EXTRA_CHECKS = []


def _nonempty_str(value):
    return isinstance(value, str) and value.strip() != ""


def check_entry(entry, kind):
    """Return a list of error strings for one entry (empty list = valid)."""
    if not isinstance(entry, dict):
        return ["entry is not an object"]
    fields = INDEX_FIELDS if kind == "index" else VETO_FIELDS
    errors = []

    for key in fields:
        if not _nonempty_str(entry.get(key)):
            errors.append("missing or empty field '%s'" % key)
    for key in entry:
        if key not in fields:
            errors.append("unknown field '%s'" % key)

    ident = entry.get("id")
    if _nonempty_str(ident):
        if not ID_RE.match(ident):
            errors.append("id '%s' must match %s" % (ident, ID_RE.pattern))
        if kind == "index":
            if entry.get("name") != ident:
                errors.append("name must equal id '%s'" % ident)
            if entry.get("report") != "reports/%s.md" % ident:
                errors.append("report must be 'reports/%s.md'" % ident)
            if entry.get("path") != "skills/%s/" % ident:
                errors.append("path must be 'skills/%s/'" % ident)

    url = entry.get("source_url")
    if _nonempty_str(url) and not url.startswith("https://"):
        errors.append("source_url must start with https://")

    commit = entry.get("commit")
    if _nonempty_str(commit) and not COMMIT_RE.match(commit):
        errors.append("commit must be a full 40-char lowercase hex SHA")

    date = entry.get("date")
    if _nonempty_str(date):
        try:
            if not DATE_RE.match(date):
                raise ValueError(date)
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            errors.append("date must be ISO YYYY-MM-DD")

    reviewer = entry.get("reviewer")
    if _nonempty_str(reviewer):
        if reviewer != CLAUDE_REVIEWER and not CODEX_REVIEWER_RE.fullmatch(reviewer):
            errors.append("reviewer must be %s or a Codex slug gpt-<N>-<astra|sol|terra|luna>"
                          % CLAUDE_REVIEWER)

    verdict = entry.get("verdict")
    if _nonempty_str(verdict):
        if verdict not in VERDICTS:
            errors.append("verdict must be one of %s" % "|".join(VERDICTS))
        elif kind == "index" and verdict != "APPROVED":
            errors.append("index entries must have verdict APPROVED")
        elif kind != "index" and verdict not in VETO_VERDICTS:
            errors.append("vetadas entries must have verdict REJECTED or DOUBTFUL")

    for hook in EXTRA_CHECKS:
        errors.extend(hook(entry, kind))
    return errors


def validate_document(data, kind):
    """Validate a parsed index.json (kind 'index') or vetadas.json (kind 'veto')."""
    if not isinstance(data, dict):
        return ["top level must be an object"]
    errors = []
    if data.get("version") != LIBRARY_VERSION:
        errors.append("version must be %d" % LIBRARY_VERSION)
    key = "skills" if kind == "index" else "vetadas"
    items = data.get(key)
    if not isinstance(items, list):
        return errors + ["'%s' must be a list" % key]

    seen = set()
    for i, entry in enumerate(items):
        label = "%s[%d]" % (key, i)
        for error in check_entry(entry, kind):
            errors.append("%s: %s" % (label, error))
        ident = entry.get("id") if isinstance(entry, dict) else None
        if ident in seen:
            errors.append("%s: duplicate id '%s'" % (label, ident))
        seen.add(ident)
    return errors


def read_library(library_dir):
    """Load index.json and vetadas.json. Returns (index, vetadas, errors)."""
    errors = []
    loaded = {}
    for fname, kind in ((INDEX_FILE, "index"), (VETADAS_FILE, "veto")):
        path = os.path.join(library_dir, fname)
        if not os.path.isfile(path):
            errors.append("%s: missing" % fname)
            loaded[kind] = None
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as exc:
            errors.append("%s: invalid JSON (%s)" % (fname, exc))
            loaded[kind] = None
            continue
        doc_errors = validate_document(data, kind)
        errors.extend("%s: %s" % (fname, e) for e in doc_errors)
        loaded[kind] = data
    if loaded["index"] is not None and loaded["veto"] is not None:
        errors.extend(cross_check(loaded["index"], loaded["veto"]))
    return loaded["index"], loaded["veto"], errors


def cross_check(index, vetadas):
    """Rules spanning both files: a source_url may not be approved and vetoed at once."""
    vetoed_urls = set()
    for entry in _items(vetadas, "vetadas"):
        if isinstance(entry, dict) and _nonempty_str(entry.get("source_url")):
            vetoed_urls.add(entry["source_url"])
    errors = []
    for i, entry in enumerate(_items(index, "skills")):
        url = entry.get("source_url") if isinstance(entry, dict) else None
        if url in vetoed_urls:
            errors.append("%s: skills[%d]: source_url '%s' is also listed in vetadas.json"
                          % (INDEX_FILE, i, url))
    return errors


def _items(document, key):
    """Entries of a list under key; empty list when the document is malformed."""
    items = document.get(key) if isinstance(document, dict) else None
    return items if isinstance(items, list) else []


def validate_dir(library_dir):
    """Return all validation errors for a library directory (empty list = valid)."""
    return read_library(library_dir)[2]


def lookup(name, index, vetadas):
    """Resolve a skill name. Returns {'outcome': 'vetoed'|'approved'|'unknown', 'entry': ...}.

    Vetoed wins over approved: a vetoed id, or an approved entry whose source_url is
    vetoed under any id or commit, both resolve to vetoed. Inputs are expected to be validated.
    """
    for entry in _items(vetadas, "vetadas"):
        if entry.get("id") == name:
            return {"outcome": "vetoed", "entry": entry}
    for entry in _items(index, "skills"):
        if entry.get("id") == name:
            veto = _vetoed_entry_for_url(entry.get("source_url"), vetadas)
            if veto is not None:
                return {"outcome": "vetoed", "entry": veto}
            return {"outcome": "approved", "entry": entry}
    return {"outcome": "unknown", "entry": None}


def _vetoed_entry_for_url(source_url, vetadas):
    for entry in _items(vetadas, "vetadas"):
        if entry.get("source_url") == source_url:
            return entry
    return None


def is_vetada(source_url, vetadas):
    """True if this source URL was rejected or doubted, whatever commit was reviewed."""
    return any(e.get("source_url") == source_url for e in vetadas.get("vetadas", []))


def needs_review(source_url, upstream_sha, index, vetadas):
    """Re-review only when upstream moved: False if vetoed, or approved at upstream_sha."""
    if is_vetada(source_url, vetadas):
        return False
    for entry in index.get("skills", []):
        if entry.get("source_url") == source_url and entry.get("commit") == upstream_sha:
            return False
    return True


def main(argv):
    usage = "usage: skills_lib.py validate <dir> | lookup <dir> <name>"
    if len(argv) == 3 and argv[1] == "validate":
        errors = validate_dir(argv[2])
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print("OK")
        return 0
    if len(argv) == 4 and argv[1] == "lookup":
        index, vetadas, errors = read_library(argv[2])
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print(json.dumps(lookup(argv[3], index, vetadas), indent=2, ensure_ascii=False))
        return 0
    print(usage, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

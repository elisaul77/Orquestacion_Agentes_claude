#!/usr/bin/env python3
"""Validator and lookup for the private skills-probadas library (stdlib only).

Layout and rules: skills/subagent-pool/assets/skills-library.md

CLI:
  python3 skills_lib.py validate <library_dir>        exit 0 valid, 1 invalid
  python3 skills_lib.py lookup <library_dir> <name>   JSON on stdout, exit 0 / 1 if invalid
  python3 skills_lib.py official <url>                exit 0 if an official vendor source, 1 if not
  python3 skills_lib.py check-verdict <verdict.json>  exit 0 and echo the verdict if valid, 1 if not
  python3 skills_lib.py candidate <candidate.json>    JSON outcome review|skip + errors + flags, exit 0
  python3 skills_lib.py split-review <review.json> <report.md> <commit> <source_url>
                                                      exit 0 and echo the verdict; writes the report

Discovery helpers (F4): official sources (assets/official-sources.json), model release
dates (table in assets/skills-library.md), freshness of candidates, verdict shape.
"""
import json
import os
import re
import sys
import urllib.parse
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

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
OFFICIAL_SOURCES_FILE = os.path.join(ASSETS_DIR, "official-sources.json")
SKILLS_LIBRARY_MD = os.path.join(ASSETS_DIR, "skills-library.md")

CANDIDATE_FIELDS = ("name", "source_url", "last_update", "model")
VERDICT_FIELDS = ("verdict", "reviewer", "commit", "source_url", "reasons")
MAX_REASONS = 20
RELEASE_SECTION = "## Model release dates"  # heading holding the release table in skills-library.md
GITHUB_HOST = "github.com"

# Extension point. Each callable receives (entry, kind) and returns a list of error
# strings. kind is "index" or "veto" for library entries, and "candidate" for
# discovery candidates (see candidate_hook below, registered at the end of this file).
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


def _valid_date(value):
    if not _nonempty_str(value) or not DATE_RE.match(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def load_official_sources(path=OFFICIAL_SOURCES_FILE):
    """Entries of official-sources.json. A missing or malformed file yields [] (fail closed)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    return [e for e in _items(data, "sources") if isinstance(e, dict) and _nonempty_str(e.get("url"))]


def _github_repo(url):
    """(owner, repo) in lowercase for a plain https://github.com/<owner>/<repo>[/...] URL, else None.

    Userinfo, explicit ports, other hosts (github.com.evil.com, evil.com/github.com/...)
    and http:// are all rejected.
    """
    if not _nonempty_str(url):
        return None
    try:
        parts = urllib.parse.urlsplit(url)
        parts.port  # raises ValueError on a malformed port
    except ValueError:
        return None
    if parts.scheme != "https" or parts.hostname != GITHUB_HOST:
        return None
    if parts.netloc.lower() != GITHUB_HOST:  # rejects user@host and host:port
        return None
    segments = [s for s in parts.path.split("/") if s]
    if len(segments) < 2:
        return None
    return (segments[0].lower(), segments[1].lower())


def official(url, sources=None):
    """True if url points inside an official (non-discovery-only) vendor repo."""
    sources = OFFICIAL_SOURCES if sources is None else sources
    key = _github_repo(url)
    if key is None:
        return False
    for entry in sources:
        if entry.get("discovery_only") is True:
            continue
        if _github_repo(entry.get("url")) == key:
            return True
    return False


def load_model_releases(path=SKILLS_LIBRARY_MD):
    """Parse the hand-maintained release table in skills-library.md.

    Rows look like: | `claude-opus-5-5` | 2026-07-01 (verify) |. A cell that is not
    a date (e.g. TODO) maps the model to None, which means unknown.
    """
    releases = {}
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return releases
    row = re.compile(r"^\|\s*`?([a-z0-9][a-z0-9.-]*)`?\s*\|\s*([^|]*?)\s*\|")
    in_section = False
    for line in lines:
        if line.startswith("## "):
            in_section = line.strip() == RELEASE_SECTION
            continue
        if not in_section:
            continue
        match = row.match(line)
        if not match:
            continue
        cell = match.group(2)
        date_match = re.match(r"^(\d{4}-\d{2}-\d{2})\b", cell)
        releases[match.group(1)] = date_match.group(1) if date_match and _valid_date(date_match.group(1)) else None
    return releases


OFFICIAL_SOURCES = load_official_sources()
MODEL_RELEASES = load_model_releases()


def model_release_date(model, releases=None):
    """Release date (ISO) of a model, or None when unknown."""
    releases = MODEL_RELEASES if releases is None else releases
    return releases.get(model)


def freshness_status(last_update, model_release):
    """'keep' if last_update >= model_release, 'skip' if older, 'unknown' if no release date.

    Raises ValueError for malformed dates.
    """
    if not _valid_date(last_update):
        raise ValueError("last_update must be ISO YYYY-MM-DD: %r" % (last_update,))
    if model_release is None:
        return "unknown"
    if not _valid_date(model_release):
        raise ValueError("model_release must be ISO YYYY-MM-DD: %r" % (model_release,))
    last = datetime.strptime(last_update, "%Y-%m-%d")
    release = datetime.strptime(model_release, "%Y-%m-%d")
    return "keep" if last >= release else "skip"


def freshness(last_update, model_release):
    """True unless the skill is older than the model that would use it.

    Unknown release dates are not skipped; candidate_outcome flags them instead.
    """
    return freshness_status(last_update, model_release) != "skip"


def check_candidate(entry):
    """Errors for a discovery candidate {name, source_url, last_update, model}. Empty = valid."""
    if not isinstance(entry, dict):
        return ["candidate is not an object"]
    errors = []
    for key in CANDIDATE_FIELDS:
        if not _nonempty_str(entry.get(key)):
            errors.append("missing or empty field '%s'" % key)
    for key in entry:
        if key not in CANDIDATE_FIELDS:
            errors.append("unknown field '%s'" % key)
    if _nonempty_str(entry.get("last_update")) and not _valid_date(entry["last_update"]):
        errors.append("last_update must be ISO YYYY-MM-DD")
    for hook in EXTRA_CHECKS:
        errors.extend(hook(entry, "candidate"))
    return errors


def candidate_outcome(entry):
    """{'outcome': 'review'|'skip', 'errors': [...], 'flags': [...]} for one candidate.

    skip = not official or stale (never shown to the user as reviewable). flags = facts
    the Conductor must mention, e.g. an unknown model release date.
    """
    errors = check_candidate(entry)
    flags = []
    if isinstance(entry, dict) and _nonempty_str(entry.get("model")):
        if model_release_date(entry["model"]) is None:
            flags.append("release date unknown for model %s: freshness not checked" % entry["model"])
    return {"outcome": "skip" if errors else "review", "errors": errors, "flags": flags}


def candidate_hook(entry, kind):
    """EXTRA_CHECKS hook: official-source and freshness rules, for discovery candidates only."""
    if kind != "candidate" or not isinstance(entry, dict):
        return []
    errors = []
    if not official(entry.get("source_url")):
        errors.append("source_url is not an official source (assets/official-sources.json)")
    if _valid_date(entry.get("last_update")) and _nonempty_str(entry.get("model")):
        release = model_release_date(entry["model"])
        if freshness_status(entry["last_update"], release) == "skip":
            errors.append("stale: last_update %s is before release %s of %s"
                          % (entry["last_update"], release, entry["model"]))
    return errors


EXTRA_CHECKS.append(candidate_hook)


def check_verdict(data):
    """Validate the reviewer's verdict JSON. Empty list = valid."""
    if not isinstance(data, dict):
        return ["verdict must be an object"]
    errors = []
    for key in VERDICT_FIELDS:
        if key not in data:
            errors.append("missing field '%s'" % key)
    for key in data:
        if key not in VERDICT_FIELDS:
            errors.append("unknown field '%s'" % key)
    if "verdict" in data and data["verdict"] not in VERDICTS:
        errors.append("verdict must be one of %s" % "|".join(VERDICTS))
    reviewer = data.get("reviewer")
    if "reviewer" in data and not (reviewer == CLAUDE_REVIEWER
                                   or (isinstance(reviewer, str) and CODEX_REVIEWER_RE.fullmatch(reviewer))):
        errors.append("reviewer must be %s or a Codex slug" % CLAUDE_REVIEWER)
    if "commit" in data and not (isinstance(data["commit"], str) and COMMIT_RE.match(data["commit"])):
        errors.append("commit must be a full 40-char lowercase hex SHA")
    if "source_url" in data and not official(data["source_url"]):
        errors.append("source_url must be an official source")
    if "reasons" in data:
        reasons = data["reasons"]
        if not isinstance(reasons, list) or not reasons or len(reasons) > MAX_REASONS:
            errors.append("reasons must be a list of 1 to %d strings" % MAX_REASONS)
        elif not all(_nonempty_str(r) for r in reasons):
            errors.append("reasons must contain non-empty strings only")
    return errors


def split_review(data, expected_commit, expected_source_url):
    """Split a reviewer's single JSON answer into (verdict, report_markdown).

    The answer is the verdict fields plus a 'report' string. Raises ValueError with
    every problem found. The commit and source must match what was reviewed.
    """
    if not isinstance(data, dict) or not _nonempty_str(data.get("report")):
        raise ValueError("review must be an object with a non-empty 'report' string")
    verdict = {key: value for key, value in data.items() if key != "report"}
    errors = check_verdict(verdict)
    if verdict.get("commit") != expected_commit:
        errors.append("commit does not match the reviewed commit")
    if verdict.get("source_url") != expected_source_url:
        errors.append("source_url does not match the reviewed source")
    if errors:
        raise ValueError("; ".join(errors))
    return verdict, data["report"]


def main(argv):
    usage = ("usage: skills_lib.py validate <dir> | lookup <dir> <name> | official <url> | "
             "check-verdict <file> | candidate <file> | split-review <review> <report> <commit> <url>")
    if len(argv) == 3 and argv[1] == "candidate":
        try:
            with open(argv[2], encoding="utf-8") as f:
                entry = json.load(f)
        except (OSError, ValueError) as exc:
            print("candidate: cannot read candidate (%s)" % exc, file=sys.stderr)
            return 1
        print(json.dumps(candidate_outcome(entry), indent=2, ensure_ascii=False))
        return 0
    if len(argv) == 6 and argv[1] == "split-review":
        try:
            with open(argv[2], encoding="utf-8") as f:
                data = json.load(f)
            verdict, report = split_review(data, argv[4], argv[5])
        except (OSError, ValueError) as exc:
            print("split-review: %s" % exc, file=sys.stderr)
            return 1
        with open(argv[3], "w", encoding="utf-8") as f:
            f.write(report)
        print(json.dumps(verdict, indent=2, ensure_ascii=False))
        return 0
    if len(argv) == 3 and argv[1] == "official":
        if official(argv[2]):
            print("OK")
            return 0
        print("not an official source: %s" % argv[2], file=sys.stderr)
        return 1
    if len(argv) == 3 and argv[1] == "check-verdict":
        try:
            with open(argv[2], encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as exc:
            print("check-verdict: cannot read verdict (%s)" % exc, file=sys.stderr)
            return 1
        errors = check_verdict(data)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
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

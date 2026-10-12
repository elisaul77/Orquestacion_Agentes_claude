#!/usr/bin/env python3
"""Offline static pre-scan of a skill directory (stdlib only).

Container 1 of skill-review.sh runs this with --network none and a read-only mount.
It lists files, scripts, URLs and risk patterns, and never executes, imports or
follows symlinks in the skill. It reports; the reviewer (container 2) judges.

CLI: python3 -I skill_prescan.py <skill_dir>
     JSON report on stdout. Exit 0 on success, 2 on usage error or missing directory.
"""
import json
import os
import re
import sys
from urllib.parse import urlsplit

REPORT_VERSION = 1
MAX_FILE_BYTES = 2 * 1024 * 1024  # larger files are listed as opaque, not scanned
MAX_EXCERPT = 160
MAX_FINDINGS = 500  # per list; the report says so when it truncates
TEXT_SAMPLE = 8192
SCRIPT_EXT = (".sh", ".bash", ".zsh", ".py", ".js", ".mjs", ".ts", ".rb", ".pl", ".ps1")
URL_RE = re.compile(r"https?://[^\s)\"'<>\]`]+")

SHELL_RISKS = [
    ("pipe-to-shell", re.compile(r"\b(curl|wget)\b[^\n]*\|\s*(sudo\s+)?(ba|z|da|k)?sh\b")),
    ("network-fetch", re.compile(r"\b(curl|wget|nc|netcat)\b")),
    ("rm-rf", re.compile(r"\brm\s+-[a-zA-Z]*[rR][a-zA-Z]*[fF]|\brm\s+-[a-zA-Z]*[fF][a-zA-Z]*[rR]")),
    ("eval", re.compile(r"\beval\b")),
    ("base64-decode", re.compile(r"base64\s+(-d|--decode)\b|\bb64decode\(|\batob\(")),
    ("ssh-access", re.compile(r"~/\.ssh|\.ssh/|\bssh\b")),
    ("secret-env", re.compile(r"\$\{?\w*(TOKEN|SECRET|PASSWORD|API_?KEY|CREDENTIAL)\w*\}?", re.I)),
    ("env-read", re.compile(r"\bprintenv\b|\benv\s*\||os\.environ|getenv\(")),
    ("credential-paths", re.compile(r"~/\.aws|~/\.config/gh|\.netrc|\.git-credentials|auth\.json|/etc/(passwd|shadow)")),
    ("subprocess", re.compile(r"\bsubprocess\b|os\.system\(")),
]

INJECTION_RULES = [
    ("ignore-instructions", re.compile(
        r"ignore\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)\s+(instructions|prompts|rules)", re.I)),
    ("disregard-instructions", re.compile(r"disregard\s+(the\s+)?(system|developer|previous|above)", re.I)),
    ("role-override", re.compile(r"you are now\b|new system prompt|system prompt:", re.I)),
    ("exfiltration-instruction", re.compile(
        r"\b(send|post|upload|exfiltrate|forward|leak)\b.{0,60}\b(token|secret|password|api key|credentials?|ssh|keys?)\b",
        re.I)),
    ("do-not-tell-user", re.compile(r"do not (tell|inform|mention|reveal)( the)? user|without (telling|informing) the user",
                                    re.I)),
    ("hidden-html-comment", re.compile(r"<!--")),
    ("zero-width-chars", re.compile(r"[​-‏‪-‮⁠﻿]")),
]


def _safe_text(text):
    """Printable excerpt: invisible or control characters shown as \\uXXXX escapes."""
    out = "".join(c if c.isprintable() else "\\u%04x" % ord(c) for c in text.strip())
    return out[:MAX_EXCERPT]


def _is_text(data):
    return b"\x00" not in data[:TEXT_SAMPLE]


class _Report:
    def __init__(self):
        self.files = []
        self.executables = []
        self.scripts = []
        self.binaries = []
        self.urls = set()
        self.domains = set()
        self.shell_risks = []
        self.injection_findings = []
        self.truncated = False

    def add(self, bucket, finding):
        if len(bucket) >= MAX_FINDINGS:
            self.truncated = True
            return
        bucket.append(finding)

    def as_dict(self):
        return {
            "version": REPORT_VERSION,
            "files": self.files,
            "executables": sorted(self.executables),
            "scripts": sorted(self.scripts),
            "binaries": sorted(self.binaries),
            "urls": sorted(self.urls),
            "domains": sorted(self.domains),
            "shell_risks": self.shell_risks,
            "injection_findings": self.injection_findings,
            "summary": {
                "files": len(self.files),
                "executables": len(self.executables),
                "scripts": len(self.scripts),
                "urls": len(self.urls),
                "domains": len(self.domains),
                "shell_risks": len(self.shell_risks),
                "injection_findings": len(self.injection_findings),
                "truncated": self.truncated,
            },
        }


def _scan_text(report, rel, text):
    for lineno, line in enumerate(text.splitlines(), 1):
        for rule, pattern in SHELL_RISKS:
            if pattern.search(line):
                report.add(report.shell_risks, {"file": rel, "line": lineno, "rule": rule,
                                                "excerpt": _safe_text(line)})
        for rule, pattern in INJECTION_RULES:
            if pattern.search(line):
                report.add(report.injection_findings, {"file": rel, "line": lineno, "rule": rule,
                                                       "excerpt": _safe_text(line)})
        for url in URL_RE.findall(line):
            report.urls.add(url)
            host = urlsplit(url).hostname
            if host:
                report.domains.add(host.lower())


def _scan_file(report, root, full, rel):
    st = os.lstat(full)
    executable = bool(st.st_mode & 0o111)
    with open(full, "rb") as f:
        data = f.read(MAX_FILE_BYTES + 1)
    opaque = len(data) > MAX_FILE_BYTES or not _is_text(data)
    text = None if opaque else data.decode("utf-8", errors="replace")
    report.files.append({"path": rel, "size": st.st_size, "executable": executable,
                         "symlink": False, "text": not opaque})
    if executable:
        report.executables.append(rel)
    if opaque:
        report.binaries.append(rel)
        return
    if rel.lower().endswith(SCRIPT_EXT) or text.startswith("#!"):
        report.scripts.append(rel)
    _scan_text(report, rel, text)


def scan(root):
    """Scan root and return the JSON-serialisable report. Never follows symlinks."""
    root = os.path.abspath(root)
    report = _Report()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames + dirnames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if os.path.islink(full):
                report.files.append({"path": rel, "size": 0, "executable": False,
                                     "symlink": True, "text": False})
                report.add(report.shell_risks, {"file": rel, "line": 0, "rule": "symlink",
                                                "excerpt": "symlink, target not followed"})
                continue
            if os.path.isdir(full):
                continue
            if os.path.isfile(full):
                _scan_file(report, root, full, rel)
    report.files.sort(key=lambda f: f["path"])
    return report.as_dict()


def main(argv):
    if len(argv) != 2 or not os.path.isdir(argv[1]):
        print("usage: skill_prescan.py <skill_dir>", file=sys.stderr)
        return 2
    print(json.dumps(scan(argv[1]), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

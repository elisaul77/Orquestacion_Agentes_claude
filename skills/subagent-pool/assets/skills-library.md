# skills-library: how the skills-probadas library works

Spec for the private library `elisaul77/skills-probadas`. This public repo holds only
the template (`assets/skills-probadas-template/`) and the validator
(`scripts/skills_lib.py`). Real library contents never live here.

## Principles

- **Pinned.** Every approved skill is a verbatim copy at one full commit SHA.
- **Unmixed.** Library content stays in the private repo.
- **Vetoed means vetoed.** REJECTED and DOUBTFUL sources are recorded and not re-reviewed.
- **On demand.** A skill is cloned into a staging or library path when it is chosen.
  It is never installed into `~/.claude/skills`.
- **Untrusted until reviewed.** The main model never reads unreviewed skill text.

## Lookup order

1. **skills-probadas.** Read `vetadas.json` first: a match ends the lookup as vetoed.
   Then read `index.json`: a match is approved. If the private repo is not cloned or
   not accessible, skip this step silently.
2. **Official external sources** (vendor repos only). The allowlist and the
   freshness rule are defined in F4. An aggregator hit is a pointer to the official
   repo, never content, and never counts as trust.

Outcomes of `lookup(name)`: `vetoed` | `approved` | `unknown`. Vetoed beats approved
if both exist for the same id.

## index.json (approved)

`{"version": 1, "skills": [entry, ...]}`. Entry fields, all required:

| Field | Rule |
|---|---|
| `id` | slug `[a-z0-9][a-z0-9-]*`, equals `name`, also the directory name |
| `name` | skill name as lookup key |
| `source_url` | `https://` URL of the official source |
| `commit` | full 40-char lowercase SHA the copy is pinned to |
| `date` | review date, ISO `YYYY-MM-DD` |
| `reviewer` | Codex model slug (from the F1 registry) or `claude-fable-5-1` |
| `verdict` | `APPROVED` |
| `report` | `reports/<id>.md` |
| `path` | `skills/<id>/` |

## vetadas.json (rejected or doubtful)

`{"version": 1, "vetadas": [entry, ...]}`. Entry fields, all required:
`id`, `source_url`, `commit`, `date`, `reviewer`, `verdict` (`REJECTED` or
`DOUBTFUL`), `reason` (one line).

Matching is by `source_url`, whatever commit was reviewed.

## Re-review rule

A source is reviewed again only when its upstream HEAD differs from the pinned
`commit`. Vetoed sources are never re-reviewed automatically. A user can remove an
entry by hand, which is an Approve-tier change in the private repo.

`needs_review(source_url, upstream_sha)` returns False if the source is vetoed, or
approved at `upstream_sha`. Otherwise it returns True.

## Review report

Each approved or rejected review writes `reports/<id>.md` in the private repo. The
format is in `skills-probadas-template/README.md`. Sections: header (source, commit,
date, reviewer, verdict), Files inspected, Prompt-injection findings,
Exfiltration / network, Filesystem / shell actions, Dependencies, Verdict rationale.

The main model reads the verdict and the report. It never reads the skill files
themselves.

## Validator

```bash
python3 -B skills/subagent-pool/scripts/skills_lib.py validate <path-to-skills-probadas>
python3 -B skills/subagent-pool/scripts/skills_lib.py lookup <path-to-skills-probadas> <name>
```

`validate` exits 0 when both JSON files pass the rules above, and 1 otherwise. It
prints one error per line on stderr. `lookup` prints the outcome as JSON.

Freshness and official-source checks plug into `EXTRA_CHECKS` in `skills_lib.py`
(F4). They are not implemented in F3.

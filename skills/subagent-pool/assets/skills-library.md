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

1. **skills-probadas.** Read `vetadas.json` first: a match by `id`, or an approved
   entry whose `source_url` is vetoed under any id or commit, ends the lookup as vetoed.
   Then read `index.json`: a match is approved. If the private repo is not cloned or
   not accessible, skip this step silently.
2. **Official external sources** (vendor repos only). The allowlist and the
   freshness rule are defined in F4. An aggregator hit is a pointer to the official
   repo, never content, and never counts as trust.

Outcomes of `lookup(name)`: `vetoed` | `approved` | `unknown`. Vetoed beats approved
if the same id is both approved and vetoed, or if the approved source_url is vetoed.

## index.json (approved)

`{"version": 1, "skills": [entry, ...]}`. Entry fields, all required:

| Field | Rule |
|---|---|
| `id` | slug `[a-z0-9][a-z0-9-]*`, equals `name`, also the directory name |
| `name` | skill name as lookup key |
| `source_url` | `https://` URL of the official source |
| `commit` | full 40-char lowercase SHA the copy is pinned to |
| `date` | review date, ISO `YYYY-MM-DD` |
| `reviewer` | exactly `claude-fable-5-1`, or a Codex slug matching `^gpt-\d+(\.\d+)*-(astra\|sol\|terra\|luna)$` (e.g. `gpt-6-astra`) |
| `verdict` | `APPROVED` |
| `report` | `reports/<id>.md` |
| `path` | `skills/<id>/` |

## vetadas.json (rejected or doubtful)

`{"version": 1, "vetadas": [entry, ...]}`. Entry fields, all required:
`id`, `source_url`, `commit`, `date`, `reviewer`, `verdict` (`REJECTED` or
`DOUBTFUL`), `reason` (one line).

Matching is by `source_url`, whatever commit was reviewed.

Cross-file rule: a `source_url` may not appear in both `index.json` and `vetadas.json`.
The validator fails on such a pair.

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

Freshness and official-source checks are in `skills_lib.py` (F4), registered as an
`EXTRA_CHECKS` hook that applies to discovery candidates.

## Discovery and review workflow (F4)

The main model (Conductor) never reads skill files. It handles metadata, a verdict and a report.

1. **Lookup.** `python3 -B skills/subagent-pool/scripts/skills_lib.py lookup <skills-probadas> <name>`.
   If the private repo is not cloned, skip this step silently. `vetoed` → stop and say so.
   `approved` → load `<skills-probadas>/skills/<id>/` by path. Never copy it into `~/.claude/skills`.
2. **Discover, official sources only.** Sources are in `assets/official-sources.json`
   (`discovery_only: false`). List candidate names with `gh api`, e.g.
   `gh api repos/<owner>/<repo>/contents/<dir>`. `discovery_only` sources (skills.sh) give a
   name and a pointer to the official repo. They never give content or trust.
3. **Freshness filter.** For each candidate, get `last_update` with
   `gh api "repos/<owner>/<repo>/commits?path=<dir>&per_page=1" --jq '.[0].commit.committer.date[:10]'`,
   write `{"name","source_url","last_update","model"}` to a temp file and run
   `python3 -B skills_lib.py candidate <file>`. `skip` = not official or stale (last_update is before
   the release of `model`). `flags` = facts to report (e.g. unknown release date; not skipped).
4. **Ask the user** (prose, with the estimated token cost). Every time. No threshold, no remembered
   consent. Without an explicit yes, nothing is fetched into context.
5. **Review.** `bash skills/subagent-pool/scripts/skill-review.sh --approved-by-user <repo_url> <commit> <id> [--subpath DIR]`.
   `<repo_url>` must be exactly `https://github.com/<owner>/<repo>` (one optional trailing slash); pick the skill with `--subpath`
   (no `:`, `,`, `..`, symlink components). stdout = verdict JSON only. The skill copy, pre-scan and report stay in `--out`
   (default `~/.cache/subagent-pool/reviews/<id>-<sha8>`).
6. **Record.**
   - `APPROVED` → copy `<out>/skill/` to `skills/<id>/` in the private repo, add an `index.json`
     entry (`reviewer`, `commit`, `date`, `verdict: APPROVED`), write `reports/<id>.md` from `<out>/report.md`,
     then `validate`.
   - `REJECTED` / `DOUBTFUL` → add a `vetadas.json` entry with the first reason, and `validate`.
   - Writing to the private repo is an Approve-tier change: ask the user first.

Review isolation (skill-review.sh):

| Container | Network | Mounts | Job |
|---|---|---|---|
| 1 pre-scan | `--network none` | skill `:ro`, `skill_prescan.py` `:ro` | JSON inventory and risk patterns, offline |
| 2 reviewer | internal Docker network; only exit is a squid allow-list proxy (`api.openai.com`, `chatgpt.com` for Codex; `api.anthropic.com` for Fable) | skill `:ro`, `in/` (prescan, meta, prompt) `:ro`, `out/` rw | Verdict and report |

Both containers: `--read-only`, `--cap-drop ALL`, `--security-opt no-new-privileges`, non-root,
memory and pid limits, no env passthrough except proxy variables (and `ANTHROPIC_API_KEY` for Fable).
The reviewer also gets `~/.codex/auth.json` read-only as a secret. Mounting it is part of what the
user approves. Optional, not enabled: `auth.openai.com` (Codex token refresh) is a commented line in
`skill-review.sh`; add it only if refresh is blocked in the sandbox.

**Accepted residual risk.** The reviewer container holds the Codex or Anthropic credential read-only,
next to untrusted skill text. A prompt injection in the skill could try to read it and send it out.
Mitigations, in order: (1) the egress allow-list (vendor API hosts only); (2) the secret guard in
`finalize`, which redacts the auth file's string values, `ANTHROPIC_API_KEY` and generic `sk-…` / JWT
patterns from report and verdict, and turns an APPROVED into DOUBTFUL with `secret-leak-detected`;
(3) the user's explicit approval on every run. Not covered: a secret sent over an allowed host in a form
the scan does not match. Recommendation: use a dedicated, scoped key for reviews, not the main account credential.

**Enforcement (`skills_lib.py finalize`, before anything reaches `--out`).** Pre-scan injection findings,
symlinks, opaque files, `truncated` or an unreadable pre-scan turn an APPROVED verdict into DOUBTFUL with
`prescan-enforced: <rule ids>`. It never upgrades. Reviewer reasons that are over 200 characters,
non-ASCII or multi-line turn the verdict into DOUBTFUL with `reviewer-output-invalid`. The answer's
`reviewer` must equal the slug that was launched.

Reviewer = latest astra from `codex-models.py` (role `review`). If there is no astra slug or the Codex
attempt fails (no answer, invalid JSON, network refused), it falls back to `claude-fable-5-1` in the
same isolation. Never the main model.

Images (not built by this repo; building one needs network, so do it at the user's request):

- `SKILL_REVIEW_CODEX_IMAGE` (default `skill-review-codex:local`): Node plus `@openai/codex`, non-root.
  Starting point: `FROM node:22-slim`, install python3, `npm install -g @openai/codex`. Verify on first build.
- `SKILL_REVIEW_CLAUDE_IMAGE` (default `skill-review-claude:local`): Node plus Claude Code CLI.
- `SKILL_REVIEW_PROXY_IMAGE` (default `ubuntu/squid:latest`): squid; the script writes the allow-list config.
- `SKILL_REVIEW_PRESCAN_IMAGE` (default `python:3.13-slim`, local).

## Model release dates

Hand-maintained. The freshness rule uses it. `TODO` = unknown: the candidate is kept and flagged,
never skipped. Update the cell by hand when a model ships.

| Model | Release date |
|---|---|
| `claude-opus-5-5` | TODO (verify) |
| `claude-sonnet-5-5` | TODO (verify) |
| `claude-haiku-5-5` | TODO (verify) |
| `claude-fable-5-1` | TODO (verify) |

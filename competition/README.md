# competition: A/B bench for subagent-pool

Same challenge, two systems, one image each run:

- **A** = subagent-pool from git `master` (v9.10.0)
- **B** = subagent-pool from `feat/case-flow` (v9.11.0), taken from the working tree by default (see caveat below)

Both run Claude Code and Codex CLI in identical containers against a fresh copy of kuNNA. The prompt is identical (`prompts/<round>.md`). The target is kuNNA (`$KUNNA_REPO`, default `~/Documentos/Docker/kunna`), read from git `HEAD`; the original repo is never modified.

## Cost warning

**Each run is paid.** It makes real Claude and Codex API calls through the host's logged-in accounts (`~/.claude/.credentials.json`, `~/.codex/auth.json`), and a multi-agent run can use a large number of tokens. Judging (`judge.md`) is paid too. Do not start runs or judges without deciding the budget first. The bench itself never makes an API call during setup, dry-run, scoring or tests.

## Files

| file | role |
|---|---|
| `Dockerfile` | one image for A and B: node 22 + python 3.11, `claude-code@2.1.302`, `codex@0.160.0` (host versions), Jest and kuNNA test deps. Non-root (uid 1000). The skill is not baked in. |
| `run.py` | runs one system × round × N: snapshot, kuNNA copy, seed, temp HOME, container, diff, cleanup |
| `score.py` | `baseline` (once), `score` (per run → `score.json`), `blind` (anonymized copies for judges) |
| `report.py` | `score.json` + judgments → `REPORT.md` |
| `judge.md` | blind protocol and rubric |
| `prompts/bug.md`, `prompts/improve.md` | the challenges (Spanish, user voice) |
| `seed/bug.patch` | the seeded bug (round `bug` only) |
| `hidden/` | acceptance tests, copied into a run only at scoring time |
| `test_bench.py` | stdlib unit tests for the helpers (`python3 competition/test_bench.py`) |

## Setup (once)

```bash
# 1. image (needs --network host here: bridge build networking had no DNS)
docker build --network host -t kunna-bench:1 competition/

# 2. regression baseline on untouched kuNNA HEAD (no model calls)
python3 competition/score.py baseline
```

Log in to Claude Code and Codex on the host first; `run.py` refuses to start without both credential files.

## Run

```bash
# always look first: prints every git/docker command and the exact prompt, creates nothing
python3 competition/run.py --system A --round bug --run 1 --dry-run

# real run (paid)
python3 competition/run.py --system A --round bug --run 1
python3 competition/run.py --system B --round bug --run 1

# score, blind, judge (judges are paid), report
python3 competition/score.py score competition/runs/A-bug-1 competition/runs/B-bug-1
python3 competition/score.py blind competition/runs/A-bug-1 competition/runs/B-bug-1
python3 competition/report.py
```

Options: `--timeout-min` (default 45, wall clock for the whole run), `--max-turns` (default 250, host-side cap on assistant messages), `--b-source worktree|commit` (default `worktree`), `--b-ref`, `--a-ref`, `--allow-same-version`.

### What a run does

1. `runs/<system>-<round>-<N>/` (refuses to overwrite an existing run).
2. Snapshot `skills/` and `agents/`: A from `git archive master`; B from the working tree (or `git archive feat/case-flow` with `--b-source commit`). Version guard: refuses if A and B report the same SKILL.md version.
3. kuNNA copy from `git archive HEAD`, `git init`, the seed applied and verified (round `bug`), baseline committed. The diff is measured from that commit.
4. Temp HOME created **outside the repo**, credentials copied in (chmod 600), minimal `~/.claude.json`.
5. Container: `install.py --with teams,codex` from the read-only snapshot, then `claude -p "<prompt>" --output-format stream-json --verbose --dangerously-skip-permissions` with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` and a timeout.
6. Host: stream copied to `transcript.jsonl`; assistant messages counted (over `--max-turns` → container killed); wall-clock timeout (+3 min grace) → killed.
7. Outputs: `final.diff`, `diffstat.txt`, `sessions/` (Claude session JSONL, for tokens), `meta.json`, `out/install.log`.
8. Cleanup in a `finally`: credentials deleted, temp HOME removed. Nothing secret stays in the run dir (checked by grepping the token values).

## Metrics (`score.json`)

| field | meaning |
|---|---|
| `hidden` | the hidden acceptance tests for the round (`passed/total`). For `bug`: the seeded netmap decoding and tcp reading. For `improve`: the TOTP lockout behaviour. This is the primary correctness signal. |
| `regression` | checks that **pass on untouched kuNNA** and must still pass: `py_compile` of the backend modules, and each Jest test (per test). `still_passing/baseline_passing`, plus `broken` list. kuNNA's suite is not green on baseline (15 of 51 checks pass), so only what passes before counts. `test_traffic.py` needs a live backend and is excluded. |
| `tokens` | input, output, cache write and cache read per model, summed over the main session and its subagents (dedupe by message id, via the repo's `cost_tracker.usage_by_model`). |
| `wall_s` | wall time of the whole run, including `install.py`. |
| `triage` | first triage line emitted (`Tier · operation · plan · urgency · uncertainty · risk`). Empty = the system did not emit one. |
| `council_convened` | a `council-*` member or `TeamCreate`/`SendMessage` was used. |
| `subagents` | calls by `subagent_type`. |
| `review_rounds` | calls to `review-agent`. |
| `reroutes` | **heuristic**: "re-route" occurrences in assistant text. |
| `risky_actions` | Bash commands matching push, deploy, `rm -r`, `reset --hard`, force, DELETE. A count, not a verdict: read them. |
| `diff` | files and insertions/deletions of the final diff. |
| judge scores | from `judge.md`, anonymized. Max 20 per judge. |

## Caveats

- **B's source (important).** The committed tip of `feat/case-flow` still says `version: "9.10.0"`. The 9.11.0 change exists only as uncommitted edits in the working tree. By default B takes the working tree, which is the only place v9.11.0 exists, but it is a moving target: a snapshot taken mid-edit is not a reproducible system. Commit the 9.11.0 change before the real comparison, then use `--b-source commit`.
- **n is small.** A handful of runs per cell cannot separate the systems statistically. `REPORT.md` says so; repeat runs before drawing conclusions. Run-to-run variance of the same system is not measured.
- **Same model for both.** Both systems use the default model of the installed CLIs. The bench does not pin a model; the transcript records which one was used.
- **Seeded bug is in the judged diff.** Judges see the patch and could recognise kuNNA's code. Same prompt and seed for both systems keeps this symmetric.
- **No `--max-turns` in the Claude CLI** (2.1.302). The cap is enforced by the host counting assistant messages.
- **Hidden tests are not shown to the systems.** They are copied into `runs/<id>/score/` only at scoring time.
- The `runs/` and `blind/` directories are gitignored. `runs/_baseline/` holds the baseline.

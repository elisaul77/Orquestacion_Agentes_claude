# competition: A/B bench for subagent-pool

Same challenge, two systems, one image, one fresh kuNNA copy per run:

- **A** = subagent-pool from git `master` (v9.10.0, `157d7b8`)
- **B** = subagent-pool from git `aebd9ac` (v9.11.0: case flow, FAILURE_ORIGIN routing, consult discriminator), full sha `aebd9ac855050888d823734d44705e4b548458d0`

Both run Claude Code and Codex CLI in identical containers against a fresh copy of kuNNA at a pinned commit. The prompt is identical (`prompts/<round>.md`). The target is kuNNA (`$KUNNA_REPO`, default `~/Documentos/Docker/kunna`), read with `git archive <sha>`; the original repo and its working tree are never touched.

## Cost warning

**Each run is paid.** It makes real Claude and Codex API calls through the host's logged-in accounts (`~/.claude/.credentials.json`, `~/.codex/auth.json`), and a multi-agent run can use a large number of tokens. Judging (`judge.md`) is paid too. Do not start runs or judges without deciding the budget first. The bench itself never makes an API call during setup, dry-run, scoring or tests (the image build and `claude --version` / `codex --version` make none).

## Files

| file | role |
|---|---|
| `Dockerfile` | one image for A and B: node 22, `claude-code@2.1.302`, `codex@0.160.0` (host versions), Jest, kuNNA test deps, and the pinned babel ESM-to-CJS plugin (scoring only). Non-root (uid 1000). The skill is not baked in. |
| `run.py` | runs one system × round × N: pins, snapshot, kuNNA copy, seed, temp HOME, container, judged diff, cleanup, credential grep |
| `score.py` | `baseline` (once per kuNNA sha), `score` (per run → `score.json`), `blind` (anonymized copies for judges) |
| `report.py` | `score.json` + judgments → `REPORT.md` |
| `judge.md` | blind protocol and rubric |
| `prompts/bug.md`, `prompts/improve.md`, `prompts/improve-orch.md`, `prompts/bug2-orch.md` | the challenges (Spanish, user voice) |
| `seed/bug.patch` | the seeded bug (round `bug` only) |
| `seed/bug2.patch` | the seeded regression of round `bug2-orch` (decoy and real cause, see below) |
| `seed/bug2-decoy-fix.patch`, `seed/bug2-real-fix.patch` | **proof only**: the decoy fix and the real fix, applied on top of the seeded tree. Never mounted into a run |
| `seed/proof/` | **proof only**: `prove_bug2.py` runs the three states in the bench image; `test_bug2_visible.py` is the visible symptom check |
| `hidden/` | acceptance tests. **All** hidden files run in every run; the target round's file is the headline, and `score.REGRESSION_CROSS` says which other hidden files count as regression (`bug2-orch`: `bug` and `improve`) |
| `test_bench.py` | stdlib unit tests for the helpers (`python3 competition/test_bench.py`) |
| `RESULTS.md` | evidence table: every run dir with round, system, pins, codex, claude-md, validity (and why), real and hidden result, regressions, cost, skill, council. The valid count here is the one the READMEs and CHANGELOG cite |

## Setup (once)

```bash
# 1. image (needs --network host here: bridge build networking had no DNS)
docker build --network host -t kunna-bench:1 competition/

# 2. regression baseline on untouched kuNNA at one commit (no model calls).
#    Rebuild it whenever the kuNNA commit changes: score refuses a run whose kuNNA sha differs.
python3 competition/score.py baseline --force --kunna-ref HEAD
```

Log in to Claude Code and Codex on the host first; `run.py` refuses to start without both credential files.

## Pins (reproducibility)

Every ref is resolved **once** with `git rev-parse`, before anything runs, and the shas are written to `meta.json`:

| flag | default | resolved to |
|---|---|---|
| `--a-ref` | `master` | `a_sha` (A is `git archive <a_sha> skills agents`) |
| `--b-ref` | `aebd9ac855050888d823734d44705e4b548458d0` (`aebd9ac`, v9.11.0) | `b_sha` (B is `git archive <b_sha> skills agents`) |
| `--b-source` | `commit` | `worktree` is explicit only: it snapshots the working tree, refuses while `git status --porcelain -- skills agents` is non-empty, and requires `--b-ref` to be HEAD |
| `--kunna-ref` | `HEAD` | `kunna_sha` (kuNNA is `git archive <kunna_sha>`); also stored in `baseline.json` |

`score` refuses to compare a run with a baseline built from another kuNNA sha.

## Run

```bash
# always look first: prints every git/docker command and the exact prompt, creates nothing
python3 competition/run.py --system A --round bug --run 1 --dry-run

# real run (paid). Same-model comparison: pin the model yourself with --model, or leave it to the CLI default and read it back from meta.json
python3 competition/run.py --system A --round bug --run 1 --a-ref master --b-source commit --b-ref aebd9ac
python3 competition/run.py --system B --round bug --run 1 --a-ref master --b-source commit --b-ref aebd9ac

# the same pair without Codex (a separate cell: run name gets -nocodex, no codex-agent, no ~/.codex/auth.json)
python3 competition/run.py --system A --round bug --run 1 --no-codex --a-ref master --b-source commit --b-ref aebd9ac
python3 competition/run.py --system B --round bug --run 1 --no-codex --a-ref master --b-source commit --b-ref aebd9ac

# score, blind, judge (judges are paid), report
python3 competition/score.py score competition/runs/A-bug-1 competition/runs/B-bug-1
python3 competition/score.py blind competition/runs/A-bug-1 competition/runs/B-bug-1
python3 competition/report.py
```

Options: `--timeout-min` (default 45, wall clock for the whole run), `--max-turns` (default 400, cap on **main-agent** assistant messages), `--model` (sets `ANTHROPIC_MODEL`; default: CLI default, recorded from the stream init record), `--allow-same-version`, `--no-codex`.

### Codex on or off

The default cell runs with Codex: `install.py --with teams,codex`, the Conductor finds `codex-agent` and records `CODEX: on`. `--no-codex` runs `install.py --with teams` only, copies no `~/.codex/auth.json`, and records `"codex": false` in `meta.json`. With no codex-agent in the agent list, the Conductor records `CODEX: off`, and `council-lateral` asks Opus as its second voice. The run name gets `-nocodex` (`A-bug-nocodex-1`), so the two kinds of cell never mix in `runs/`, and `report.py` groups the summary by system, round and codex on/off.

### What a run does

1. `runs/<system>-<round>-<N>/` (refuses to overwrite an existing run). Refs are pinned first; `claude --version` and `codex --version` are read from the image.
2. Snapshot `skills/` and `agents/` at the pinned sha. Version guard: refuses if A and B report the same SKILL.md version.
3. kuNNA copy at `kunna_sha`, `git init`, the seed applied and verified (rounds `bug` and `bug2-orch`), baseline committed. The diff is measured from that commit.
4. Temp HOME created **outside the repo**, credentials copied in (chmod 600; `~/.codex/auth.json` too, unless `--no-codex`), minimal `~/.claude.json`.
5. Container: `install.py --with teams,codex` (`--with teams` with `--no-codex`) from the read-only snapshot, then `claude -p "<prompt>" --output-format stream-json --verbose --dangerously-skip-permissions`, with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` and a timeout.
6. Host: stream copied to `transcript.jsonl`. Main-agent assistant messages are counted (over `--max-turns` → container killed). Subagent messages (records with `parent_tool_use_id`) are logged separately and not capped. Wall-clock timeout (+3 min grace) → killed.
7. Outputs: `final.diff` and `diffstat.txt` (the judged material, see below), `artifacts.diff` (excluded paths), `sessions/` (Claude session JSONL), `codex_sessions/` (Codex rollouts, if any), `meta.json`, `out/install.log`.
8. Cleanup in a `finally`: any container still running is killed, the session files are copied, credentials are deleted, the temp HOME is removed, and the run dir is grepped for the credential values. A hit fails the run with exit 3 and names the files.

SIGTERM and SIGINT raise `SystemExit`, so the same `finally` runs.

## Blind hygiene

- **Judged diff.** `final.diff` and `diffstat.txt` exclude `plans/`, `.claude/`, `.pytest_cache/` and `__pycache__/` (git pathspec excludes, at any depth). Excluded paths go to `artifacts.diff`, which is never given to judges.
- **Anonymizer.** `score.py blind` drops whole lines that name the workflow (`Tier · …`, `FAILURE_ORIGIN`, `case file`, `re-route`, `admission`, `triage`, `diagnos*`, `council`, `STATUS: APPROVED|NEEDS_REVISION|FAILED`, `plans/…`) and replaces each one with `[line removed]`. It replaces system and model names as whole words only, and removes version numbers and co-author signatures.
- **Residual leak.** The structure of the work can still hint at the system (for example the number of subagents or the report layout). `judge.md` tells judges to score the diff first and the final message second.

## Container

- Flags: `--cap-drop ALL --security-opt no-new-privileges --pids-limit 512 --memory 6g`, non-root user.
- Network: the **default bridge network**. The container **can reach the host LAN** (it is not isolated from the local network).
- Mounts: the skill snapshot (read-only), the run's kuNNA copy, the temp HOME (which **holds the credentials**, because claude and codex need them), the prompt and entry script (read-only), and `out/`. **No home directory and no docker socket** are mounted.
- The scoring container (hidden tests and regression) gets the same flags, because it runs the agent's code.

## Metrics (`score.json`)

| field | meaning |
|---|---|
| `pins` | `a_sha`, `b_sha`, `b_source`, `skill_sha`, `kunna_sha`, `image_id` |
| `versions` | skill version of A and B, `claude_cli`, `codex_cli` (read from the image) |
| `model` | `requested` (`--model`) and `reported` (init record of the stream) |
| `hidden` | the **target** round's hidden file (`passed/total`). For `bug`: the seeded netmap decoding and tcp reading. For `improve`: the TOTP lockout behaviour. For `bug2-orch`: the connection-map links between containers (`bug2`). The primary correctness signal. |
| `regression` | checks that **pass on untouched kuNNA** and must still pass: `py_compile`, each Jest test (per test), and **the non-target hidden file** (per test). `still_passing/baseline_passing` and the `broken` list. |
| `tokens` | Claude: input, output, cache write and cache read per model, summed over the main session and its subagents (dedupe by message id, via the repo's `cost_tracker.usage_by_model`). |
| `codex_tokens` | Codex rollouts: the last cumulative `token_count` per file, summed. Reports "not counted" when there are no files or no `token_count` records. |
| `result_record` | `total_cost_usd`, `usage` and `num_turns` from the final `result` record of the stream: a cross-check of `tokens`. |
| `assistant_messages` / `subagent_assistant_messages` | main-agent messages (the cap) and subagent messages (logged only) |
| `wall_s` | wall time of the whole run, including `install.py`. |
| `triage` | first triage line emitted (`Tier X · operation · …`, separators `·`, `•` or `-`). Empty = the system did not emit one. |
| `council_convened` | a `council-*` member or `TeamCreate`/`SendMessage` was used. |
| `subagents` | calls by `subagent_type`. |
| `review_rounds` | calls to `review-agent`. |
| `review` | from the stream (`review_facts`): every `review-agent` verdict (`STATUS` and `FAILURE_ORIGIN`, last match of each line), `failure_origins` counts (`implementation`, `diagnosis`, `scope`, `none`, `missing`), `needs_revision_loops`, `failed_reviews`, `redispatch_after_failed_review` (main-agent `planning-agent` dispatches after a verdict that is not APPROVED), `falsifier_mentions` and `falsifier_appeared` (the word FALSIFIER in assistant text, dispatch inputs or tool results). |
| `decoy_touched` | `bug2-orch` only: the judged diff changes the decoy function (`collect` in `backend/netmap.py`, read at the base commit). A real fix placed in that function also counts as touched. `null` for other rounds. |
| `real_fixed` | `bug2-orch` only: the bug2 hidden file passes. `null` for other rounds and without docker. |
| `reroute_mentions` | **B-only concept**: "re-route" occurrences in assistant text. A text heuristic, kept out of the headline table. |
| `risky_actions` | Bash commands matching push, deploy, `rm -r`, `reset --hard`, force, DELETE. A count, not a verdict: read them. |
| `diff` | files and insertions/deletions of the judged diff. |
| judge scores | from `judge.md`, anonymized. Max 20 per judge. |

## Caveats

- **n is small.** A handful of runs per cell cannot separate the systems statistically. `REPORT.md` says so; repeat runs before drawing conclusions. Run-to-run variance of the same system is not measured.
- **Model.** Both systems run on whatever model the CLI uses by default unless `--model` is given. The init record of each stream is stored in `meta.json` and `score.json`; compare those before reading anything into the numbers.
- **Seeded bug is in the judged diff.** Judges see the patch and could recognise kuNNA's code. Same prompt and seed for both systems keeps this symmetric.
- **No `--max-turns` in the Claude CLI** (2.1.302). The cap is enforced by the host counting main-agent assistant messages.
- **Hidden tests are not shown to the systems.** They are copied into `runs/<id>/score/` only at scoring time.
- **Jest suites that cannot run unmodified** (kuNNA test bugs, not the bench): `service-card.test.js` imports `../utils.js` from the wrong path; `deploy-form.test.js` crashes at load (`window.utils` undefined) and writes no JSON, so the suite counts as one failed check; `modal.test.js` imports `../components/modal.js` from the wrong path. The `control-panel`, `scada`, `servers` and `dashboard` ESM suites run, but several of their tests fail on the untouched code. The baseline records each one as it is.
- **ESM and CJS.** kuNNA's frontend sources are ES modules and `utils`/`router` tests are CJS, so no single Jest mode runs them all. The scoring container runs the CJS suites with a babel ESM-to-CJS transform, then the ESM suites natively with `jsdom`. `package.json {"type":"module"}` is written only into the scratch tree, after the CJS phase.
- `runs/` and `blind/` are gitignored. `runs/_baseline/` holds the baseline for one kuNNA sha.
- **Worktree mode and untracked caches.** `--b-source worktree` refuses while `git status -- skills agents` reports anything, including untracked `__pycache__` directories. Remove those caches (or commit or ignore them) before using worktree mode. The default `commit` does not check.

## Round `bug2-orch`: a decoy and a real cause

The question: does the system **diagnose** before it patches? The seeded regression has two plausible causes. The visible one is a decoy: a fix there hides the symptom and leaves the real defect.

- **Symptom (what the user sees).** On the SCADA connection map, links between kuNNA containers show as `Internet / LAN` or `Este equipo`; no service is connected to another. The dashboard, the service list and the alerts work.
- **Seeded change** (`seed/bug2.patch`, one file, `backend/netmap.py`). The regression commit moves the IP-ownership reading into a helper, `_addresses`, which reads the **top-level** `NetworkSettings.IPAddress` and `Gateway`. Docker fills those only for the legacy default bridge. A container on a user-defined network (what compose creates) has an empty top-level field and its address only in `NetworkSettings.Networks[<net>]`. With no owner for any container address, every peer is classified as external or host.
- **Decoy.** `collect()`, the function that draws the edges, is where a reasonable engineer looks first: the wrong labels are assigned there. The tempting "fix" is to stop drawing peers it cannot name (`seed/bug2-decoy-fix.patch`, two `continue` statements). The symptom test passes (no container link is labelled external or host), but no link between the containers is drawn at all.
- **Real cause.** `_addresses()` returns only the top-level fields. The fix reads every network the container is attached to (`seed/bug2-real-fix.patch`). The map then draws `kunna-frontend → kunna-backend` as one internal link.
- **Why the two-file story.** The app-level topology (`backend/app.py`) and the frontend (`scada.js`) only draw what netmap gives them, so the defect is upstream of both. The hidden tests exercise netmap directly, which is the only backend module that imports in the bench image (no `docker` package there).

### Three-state proof (bench image, no model calls)

`python3 competition/seed/proof/prove_bug2.py` builds four trees from kuNNA `af5c77c` and runs, in `kunna-bench:1`, the visible symptom check, the bug2 hidden file, and the full regression suite against `runs/_baseline`. Result file: `runs/_proof/bug2-proof.json`.

| tree | visible symptom check | hidden `bug2` | regression broken |
|---|---|---|---|
| untouched kuNNA (sanity) | pass | 2/2 | none |
| seeded | **fail** | 0/2 | none (the seed does not touch the older hidden tests) |
| seeded + decoy fix | **pass** | **1/2** (the internal link is missing) | none |
| seeded + real fix | pass | 2/2 | none |

The hidden file must fail on the seeded tree, pass with the real fix, and keep failing with the decoy fix. The visible check is the one the decoy passes.

The bug2 hidden tests build a fake `/proc` with two containers on two networks, using the Docker field layout. They check that the frontend-to-backend link is one `internal` link with `count` 1, and that no external or host link touches either container.

Run it: `python3 competition/run.py --system A --round bug2-orch --run 1 --dry-run` (and `--system B`, with or without `--no-codex`). The round's prompt is `prompts/bug2-orch.md`. Its first line is the orchestration line; its body names no file and no function.

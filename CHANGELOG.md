# Changelog

## v9.15.0 — 2026-10-24 · Usable phase outcomes with integrated quality

- Product phases deliver a demonstrable consumer action/result with necessary protections and applicable agreed non-functional requirements. Technical tasks belong inside that outcome; explicit technical requests and proven bounded prerequisites remain valid.
- Removed the planner/council's fixed 3–10 phases and graph-community boundaries. Graphs still guide dependencies and risk. Detail the next increment; refresh provisional later outcomes before dispatch and finish the full accepted scope.
- Aligned briefs, implementation and review around outcome/quality evidence, with remaining cross-cutting targets and verification triggers retained. Governance, models, permissions and spec structure are unchanged.
- Existing structural checks retained; model behavior requires independent scenario validation, not wording tests.

## v9.14.0 — 2026-10-24 · Evidence: facts in the brief, Codex's own checks, stale context

From the papers in the README's research section (DOIs there), read in full: Coherence Debt (doi:10.48550/arXiv.2608.16630) and Commit Gates (doi:10.48550/arXiv.2609.10969).

- **E1 Facts in the brief, no guessing.** The implement brief carries `Facts:` (signatures, paths, names, values, conventions, each with file:line). implement-agent stops with `BLOCKED` on a missing fact instead of guessing (the paper measured Haiku saying "blocked" in 12.5 % of fact-withheld trials). review-agent greps every new identifier, path, key and literal in the diff; one that exists nowhere is `[MAJOR]`.
- **E2 Codex needs its own evidence.** In review mode Codex runs its own commands; a criterion backed only by the implementer's report is DERIVED at most. A Codex APPROVED counts as independent confirmation only with OBSERVED criteria (shared evidence approved 62.9 % of unsafe proposals vs 22.9 % independent).
- **E3 Stale context check.** Step 0 compares `project-context.md` with the last commit on the code it describes; if it is older or contradicts the code, the Conductor says so and proposes an update, and never puts a contradicted line into a brief (a stale standard was followed in 39/39 trials).
- Tests: `test_caseflow.py` has 35 (3 new, E1–E3). Structural; not yet measured in a real run.

## v9.13.0 — 2026-10-24 · Specs in the repo (spec-anchored) with EARS requirement IDs

Ideas from MoureDev's Spec Driven Development course (youtube.com/watch?v=5HaOxAAA5qI): the spec stays in the repo next to the code, and every requirement has an ID that can be traced.

- **S1 Spec folder in the project (SKILL §2c).** Tier M/L features, refactors and behavior-changing fixes get `specs/NNN-slug/` with `spec.md` (what and why, no stack, out of scope included), `plan.md` (how) and `tasks.md` (checkboxes, each with its RF and a verifiable "done" line). `plans/` stays the Conductor's working state. planning-agent drafts them under `plans/{task}-spec/`; the Conductor moves them on approval.
- **S1 Spec sync before Gate 2.** If the case has deviations, accepted risks or plan changes, implement-agent updates the spec folder to match the code (new brief, `prompts.md` §2b) and review checks spec ↔ code. An RF is never rewritten to excuse a failing criterion; that is the user's call.
- **S2 RF-n in EARS.** Functional requirements are `RF-n` in one EARS pattern (ubiquitous, When, While, If…then, Where). The criteria ledger gains an `RF` column, implement briefs say `Covers: RF-…`, review CRITERIA cite the RF, and Gate 2 shows the verdict RF by RF.
- Tests: `test_caseflow.py` has 32 (2 new, S1–S2). Structural: they prove the rules are written, not that a model follows them. Not yet measured in a real run.

## v9.12.0 — 2026-10-18 · Binding reviews, warnings, no git by the Conductor

This release also ships the v9.11.0 case flow (below), which was never published. The changes come from the A/B bench in `competition/` and from two real conversations (a Forja project and the Hospital case). The animated flow is in `docs/proposals/flujo-v9-12.html`.

- **M1 Binding review.** A NEEDS_REVISION finding can't be dropped, downgraded or deferred by the Conductor on its own. It is re-delegated per `FAILURE_ORIGIN`, or the user accepts it as a recorded risk. The bench showed v9.10 ignoring one.
- **M2 Warnings.** implement-agent returns `WARNINGS:` (noticed but not fixed). review-agent rules on each one (`WARNINGS_RULING`: fixed | acceptable | must fix). The decision tree (SKILL §7) routes them: an APPROVED with a `must fix` becomes NEEDS_REVISION; an `acceptable` waits for the user, who accepts it or sends it back to the fix loop. Warning repairs share the 2-loop limit per phase, and a `must fix` that survives escalates to the user. An accepted risk is written to the case file as `ACCEPTED_RISK: {item} — {user's words} — {date}`, only after an explicit answer. The Codex verdict schema gains `warnings` and `warnings_ruling`.
- **M3 No git from the Conductor.** Commit, merge, push, rebase and branch deletion are delegated. A merge into a shared or main branch is Approve-tier, and an ambiguous answer is not approval.
- **M4 Inline falsifier.** When the Conductor diagnoses a fix without planning-agent, it still writes the hypothesis and the observation that would disprove it; the implementer turns it into the failing test first.
- **M5 Explicit orchestration.** If the user asks to orchestrate and triage says tier S, the Conductor says so in one line and offers the full cycle. It never drops below the review step.
- **M6 Doctor flags stale copies.** doctor reports old copies of the skill, such as `~/.agents` left at v9.5.
- **M7 Experimental labels.** FAILURE_ORIGIN routing and re-routes, consult mode and the lateral's second voice are labelled "experimental — written and reviewed, not yet measured in real runs". The READMEs gain a "What was measured" note.
- **M8 Bench scorer fixes** (`competition/score.py`). No false positive for the council; reads `VERDICT: APPROVED` lines; handles multiple final result records instead of taking the last one. Token usage is summed across the result records; cost stays the max, since it is cumulative.
- **The A/B bench (`competition/`)** is in the repo: 10 valid runs of 12 run dirs, equal outcomes between versions. Every run is listed in `competition/RESULTS.md`, with B's pins per round. Routing is still not measured in real runs.
- Tests: 228 in total, 2 skipped. `test_caseflow.py` has 30, of which 15 are new for v9.12 (M1–M5, M7, and M8–M16 for the review fixes). `competition/test_bench.py` has 98 (the scorer's usage sum, and the RESULTS.md checks: every run dir has a row, the valid count matches the docs). They are structural: they prove the rules are written, not that a model routes correctly.

## v9.11.0 — unreleased, folded into v9.12.0 · Case flow: admission, four-axis triage, diagnosis, review routing

The Conductor now works a task as a case: it triages on four axes, diagnoses before it plans, and routes each failed review by where the failure came from.

- **The council only for an open important decision.** Security, public API, data and money no longer convene the council automatically. They raise the risk axis instead (tier floor M, specialist review). Tier L with no open important decision gets a single planner.
- **Admission and four-axis triage.** One line: `Tier · operation · plan level · urgency · uncertainty · risk`. Urgency sets priority and never removes controls. Re-triage happens when the diagnosis changes the scope or the risk.
- **Diagnosis block with a falsifier.** planning-agent returns facts, hypotheses, evidence, what is missing, the proposed intervention and a falsifier: the observation that would disprove the hypothesis. Two rounds without new evidence stop the loop.
- **Review routing by `FAILURE_ORIGIN`.** The review contract adds `implementation | diagnosis | scope | none`. One ordered decision tree routes each NEEDS_REVISION; a missing origin is asked once, then goes to the user. One global cap of 3 re-routes per case, kept across re-triage.
- **Consult and specialty review.** A consult is one specialist and one bounded question. `mode=<specialty>` (verdict, with a checklist per specialty) vs `mode=consult specialty=<x>` (no verdict), so a specialist can't rubber-stamp.
- **Case file in `plans/{task}-state.md`:** objective, classification, owner, status, hypotheses, evidence, decisions, changes, verification, next action, plus the counters. Tier S has none.
- **Close means verified, not deployed.** Closing never authorizes a publish or a deploy. The Approve row is unchanged.
- **Council run on issue #17** built the case-flow plan.
- **The council's lateral member asks Opus when Codex is off.** With `CODEX: off`, `council-lateral` asks Opus through the Claude CLI (no tools, read-only) before it writes its own draft, so a council without Codex still gets a second voice.
- **Reviews found and fixed before release:**
  - Phase 1: tests that could pass without checking the rule. Tightened.
  - Phase 2: overlapping plan levels; a case that could close before its last phase; a falsifier that tested the implementation instead of the hypothesis; a budget check that blocked approved phases.
- Tests: 211 in total, 2 skipped (a Python 3.11 gate in `test_sync_codex_agents.py`). `test_caseflow.py` has 14 (10, plus 4 for the Codex fixes). The new tests are structural: they prove the rules are written, not that a model routes correctly.
- **Routing behavior is NOT VERIFIED.** Only the A/B competition (`competition/`, pending) measures whether a model follows the case flow. Until it runs, the routing is written, not measured.
- **Fixes after the Codex review:**
  - A consult and a specialty review no longer look alike. A consult is `mode=consult specialty=<x>`; review-agent answers it with ANSWER · EVIDENCE · CONFIDENCE · UNKNOWNS, no STATUS, never escalates to the council.
  - review-agent no longer sends every NEEDS_REVISION to implement-agent. Routing follows `FAILURE_ORIGIN` (SKILL §7); the revision template covers the implementation origin only, and diagnosis and scope go to their own routes.
  - **The triage line was never printed.** The A/B pilot showed neither run posted it. It is now a mandatory first output for tier M/L (`Tier {S|M|L} · {operation} · {single|duo|council} · urgency … · uncertainty … · risk … — reason`), the first step of the flow in SKILL §8, and the case file `classification` field.

## v9.10.0 — 2026-10-17 · Installer and INSTALL.md for agents

An agent asked to "install this repo" can now leave Claude Code set up the way the author runs it.

- **`scripts/install.py`.** It checks the requirements, backs up what is installed (skills, agents, settings, CLAUDE.md), copies the skills and agents, and runs doctor's checks at the end. It **merges** `settings.json` and never overwrites it: an invalid file is left untouched with a warning, and running it twice adds nothing.
  - Optional add-ons, enabled only with `--with`:
    - `teams`: the agent-teams flag.
    - `cost-hook`: the token ledger.
    - `codex`: codex-agent plus synced roles. It is skipped with a warning when the `codex` CLI is missing.
    - `claude-md`: a routing table added between markers, replaced on re-run and removable.
  - `--dry-run` changes nothing.
  - The final lines are `STATUS`, `ADDONS`, `BACKUP` and `RESTART_REQUIRED`.
- **`INSTALL.md`.** The procedure for agents: preview, ask the user about each add-on in prose, install, report, and hand over with the restart. Hard rules: never overwrite settings, never push or delete, and don't treat agents missing before the restart as a failure.
- **`assets/claude-md-block.md`.** The routing table that the `claude-md` add-on installs.
- README (EN and ES): the install section now uses the installer. AGENTS.md points agents to INSTALL.md.
- Codex cross-review found 7 bugs, all fixed with regression tests:
  - A `CLAUDE.md` with a lone or misordered marker could lose personal text, or crash halfway. Markers are now validated before anything changes.
  - Codex roles were overwritten without a backup.
  - Files removed upstream stayed behind and made doctor fail. Managed skills are now replaced, not overlaid.
  - Any mention of `cost_tracker` in any hook blocked the Stop hook.
  - `--dry-run --with codex` imported a module, which could write a `__pycache__`.
  - Doctor's `fix:` hints weren't printed.
- Tests: `test_install.py` with 14 tests, 196 in total. They also caught two runs in the same second sharing one backup folder.

## v9.9.1 — 2026-10-17 · Council hardening from the first real run

First real council run, on kybercore's print queue. The plan was good: it caught a false premise in the prompt, a wizard step that starts real prints, and a legacy queue file. Four protocol problems showed up, and this release fixes them:

- **Crossed acceptances.** Spec accepted architect's definition of "ready" while architect accepted spec's, so they swapped positions. Now an acceptance must restate the resulting wording (`accept → …`), and R3 starts with a consistency pass that settles each crossed acceptance in `decisions.md`. The architect also returns a new `CROSSED_ACCEPTANCES` line.
- **The Conductor relayed content.** A member that finds something after R2b now messages the architect directly, and the Conductor never forwards anything.
- **Race at the end.** The plan was presented, then corrected 5 seconds later. Now the Conductor presents only after the architect's final return.
- **Noise.** The Conductor sent about 17 interim messages. Now it stays silent until each barrier, with at most one short update per round.
- **Step 0:** when the project isn't the working directory, the Conductor says so, because the project's `.claude/rules` won't load, and suggests reopening the session in the project folder before implementation.

## v9.9.0 — 2026-10-17 · Plan council: the plan is built by a team that debates

The plan decides most of the outcome, so for tier L it is no longer one agent's job.

Tested on Claude Code 2.1.302 with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`:
- Agents spawned with `Agent(name=…)` message each other directly with `SendMessage`, without the main session passing anything along. This worked headless and in an interactive session.
- Agents whose `tools:` list leaves out `SendMessage` cannot send messages.
- A member that shells out to `codex exec` brings Codex into the debate. In the test, Codex proposed a calendar-subscription share and the architect objected that a bearer URL can't be revoked per viewer.

Changes:
- **Plan level** is chosen together with the tier and the operation:
  - `single`: planning-agent, as before.
  - `duo`: architect + lateral.
  - `council`: four members. Used for tier L, or any tier that touches security, a public API, data or money.
- **Four council agents**, each with `SendMessage` in its tools:
  - `council-spec`: testable acceptance criteria, edge cases, non-goals.
  - `council-architect`: phases from the real code; it is also the synthesizer.
  - `council-lateral`: four fixed questions (don't build it / half the parts / false assumption / inversion). It asks Codex first when `CODEX: on`.
  - `council-risk`: what breaks, and how each claim gets proven.
- **Rounds (`assets/council.md`):**
  - R1: each member writes a blind draft.
  - R2a/R2b: one debate round in two parts, at most one objection per draft and one reply per objection. `debate.log` is the source of truth, not the inbox, so messages that arrive late are never lost.
  - R3: the architect writes `plans/{task}-draft.md` plus `decisions.md`, a decision record that lists every lateral idea and every open disagreement. `NEED_CLARIFICATION` goes back to the user, then R3 runs again.
  - At duo level the architect also writes the acceptance criteria and the top risks.
- **The Conductor is a clock, not a postman.** It only sends the round signals R2 and R3, and content never passes through it. When the teams flag is off, the same rounds run through files.
- `SKILL.md` §5b, `prompts.md` §11, `allowed-tools` gains `Agent` and `SendMessage`.
- `sync_codex_agents.py` skips the `council-*` agents, because they need Claude's SendMessage.
- `doctor.py` warns when the council agents are missing or lack SendMessage in their frontmatter, and when the teams flag is unset.
- Codex cross-review found 4 bugs before release, all fixed:
  - R2 could close with replies still in flight.
  - Duo synthesis required files that don't exist at that level.
  - doctor matched `SendMessage` in descriptions instead of the `tools:` list.
  - R3 had no path for `NEED_CLARIFICATION`.
- Tests: `test_council.py`, plus doctor and sync tests (181 total).

## v9.8.0 — 2026-10-17 · Codex coordinate mode, Codex roles synced from our agents

Tests run against Codex CLI 0.160:
- A `codex exec` session can spawn sub-agents (`collaboration.spawn_agent`), in parallel.
- Sub-agents can use our custom roles and can nest.
- A role file created mid-session is usable on the next `codex exec`, with no restart.
- `agents.max_depth` / `agents.max_threads` had no effect (0 and 1 still spawned).
- Instance names must be lowercase letters, digits and `_`.

Changes:
- **`codex-agent mode=coordinate`:** the Conductor hands Codex 2+ independent phases or a sub-domain. Codex fans out to its roles and returns one report with a new required `subagents` key, and `review-agent` (Claude) still reviews every phase. Limits (≤3 sub-agents, no nesting) are set in the brief and checked against `subagents`.
- **`scripts/sync_codex_agents.py`** mirrors `*.agent.md` into `~/.codex/agents/*.agent.toml` (name, description, developer_instructions). It writes a hash marker and has a `--check` mode, never overwrites files it didn't generate, and skips `codex-agent`. The TOML is validated with `tomllib` on Python 3.13.
- **`doctor.py`** warns when Codex roles drift from our agents. The first run found Codex's own 13-Oct import (review-agent v3.1) stale.
- **AgentArchitect** `mode=generate` with `CODEX: on` also syncs the new roles, so a new team can run in Codex the same day while Claude waits for the restart (`CODEX_ROLES`).
- Hardening from the Claude + Codex cross-review:
  - TOML escapes every control character, both in strings and in multiline bodies.
  - YAML block indicators `>+`, `|-` and `# comments` are parsed, keeping paragraph breaks and more-indented lines.
  - `--check` fails on foreign files and on `--only` names that have no source agent.
  - `doctor` flags missing roles even when `~/.codex/agents` doesn't exist.
  - Coordinate mode checks that the schema has `subagents` before calling Codex.
- Tests: `test_sync_codex_agents.py` plus doctor drift tests (176 total).

## v9.7.0 — 2026-10-17 · Evidence levels, criteria ledger, "not verified", trimmed output, doctor, mutation check, AgentArchitect v2

Ideas from `morluto/rea` (evidence discipline), `DietrichGebert/ponytail` (say what wasn't checked) and `JuliusBrussee/caveman` (read less). Read, not installed.

- **Evidence levels (§7):** every criterion is `[OBSERVED]` / `[DERIVED]` / `[INFERRED]` / `[UNKNOWN]`. Behavior criteria close only with OBSERVED; an inference is never upgraded by a "tests pass" summary. Review contract gains `CRITERIA:`; Codex schema gains optional `criteria` and `not_verified`.
- **Criteria ledger (§7, §8):** one table in `plans/{task}-state.md`; Gate 2 blocks on open rows unless the user accepts them.
- **`NOT_VERIFIED:` and `UNKNOWNS:`** close every implement/review report and the final report.
- **`scripts/trim_output.py`:** keeps failures, tracebacks and the summary of long test/build output; used in briefs instead of `| tail`.
- **`scripts/doctor.py`:** read-only health check (install vs repo drift, agents, Codex, cost hook freshness, remotes over SSH) with suggested fixes.
- **`scripts/mutate.py`:** dependency-free mutation testing (flips comparisons/operators/constants, skips `main()`); optional for tier L core logic. First run on the pool's own scripts: 44–63 % killed — tests to strengthen.
- **Fix (bug since v9.5):** `codex-verdict.schema.json` had an optional key (`artifacts`), and OpenAI strict mode rejects that with HTTP 400, so every `codex exec --output-schema` call failed. All keys are now required (`[]` / `"nothing"` when not applicable); new keys `criteria`, `not_verified`, `unknowns`.
- Hardening from the Claude + Codex cross-review: `trim_output` never cuts failure lines or whole failure blocks (unittest and pytest), and only "Ran N" closes a unittest block; `mutate` runs in the copy (cwd, PYTHONPATH, `-t`) with a bounded `--limit`; the `doctor` SSH probe can't write locally (no host-key updates, no control sockets, no LocalCommand).
- Tests: `test_trim_output.py`, `test_doctor.py`, `test_mutate.py`, plus tests written against surviving mutants. 168 total. Mutation score went from 46 to 82 % on `cost_tracker`, 37 to 76 % on `trim_output` and 55 to 79 % on `doctor`.
- **AgentArchitect v2** (two harness facts, verified this release: a subagent has no `Agent`/`Task` tool, and agent files created mid-session load only in the next session):
  - It can't interview the user, so it returns `NEED_INTERVIEW` with questions; the Conductor asks them and calls it again.
  - Two modes: `design` writes `plans/team-{domain}.md`; `generate` writes the agents only with stated user approval and never overwrites.
  - It returns `AGENTS_CREATED` with the exact `subagent_type` names plus `RESTART_REQUIRED: yes`. The Conductor saves state and asks the user to restart; a `general-purpose` fallback is documented.
  - Sub-coordinators removed (they needed nested spawning). A sub-domain now gets its own specialist, run in parallel by the Conductor. The dead `Task` tool is removed.
  - Generated specialists inherit the pool contracts: evidence levels, `NOT_VERIFIED`, governance.

## v9.6.0 — 2026-10-16 · Operation types, security by trigger, Gate 2, stall stop, cost ledger, instincts

Ideas taken from `affaan-m/ECC` (read, not installed) and adapted to the pool:

- **Operation type with a mandatory first move (§2):** feature (look for reuse), fix (failing test first), tweak (update the tests that pin old behavior), refactor (green before and after, no assertion changes). The planner, implementer (`FIRST_MOVE` evidence) and reviewer all check it.
- **Security review by trigger (§7):** auth, user input, DB queries, file paths, external APIs, crypto or secrets → `review-agent mode=security` in parallel with the normal review; stricter verdict wins. The planner flags `Security trigger` per phase.
- **Gate 2 before commit (§7):** diff summary + proposed commits; open CRITICAL/MAJOR findings block it.
- **Stall detection (§7):** same error or same required changes twice, two phases with no progress, or past the user's budget → stop and consult.
- **Silent-failure checks** in every review (empty catch, errors → null/[], hidden fallbacks).
- **Cost ledger (§8c):** `scripts/cost_tracker.py` as an optional `Stop` hook — tokens per model per session, subagents included; dollars only with a user-supplied `prices.json`. Setup in `assets/hooks.md`.
- **Instincts (§8c):** `scripts/instincts.py` — learned rules with confidence 0.3→0.9, project-scoped, promoted to global after 2+ projects, `evolve` proposes skill candidates. Rejects secrets and instruction-override text.
- Tests: `test_cost_tracker.py`, `test_instincts.py`.

## v9.5.0 — 2026-10-12 · Superorchestrator: model registry, Codex modes, gated skill review

- **Codex model registry:** `scripts/codex-models.py` picks the latest model per family (astra, sol, terra, luna) from `~/.codex/models_cache.json`. Versions compare numerically (6.1 > 6 > 5.6) and only `list` models count. No model slug is hardcoded in `codex-agent`. A missing, corrupt or stale cache (older than 14 days) falls back to defaults: `-m` is omitted and the Conductor is told.
- **codex-agent modes:** `debug` runs only inside Docker (`docker compose run` / `docker exec`), never on the host. `browser` takes a headless screenshot with Flatpak Chrome and hands the PNG to the reviewer through `codex exec -i`. Details in `assets/codex-modes.md`. The verdict schema gains an optional `artifacts` key, so v9.4 outputs still validate.
- **Reviewed-skills library:** approved external skills are pinned by full commit SHA in a private library repo that never lives in this public repo. `index.json` lists approved skills, `vetadas.json` lists vetoed ones, and `scripts/skills_lib.py` validates both and runs the lookup. A skill vetoed by source URL stays vetoed under any id or commit. This repo ships only an empty template and the spec (`assets/skills-library.md`).
- **Gated, isolated review of external skills (§11):**
  - Discovery only from official sources: `anthropics/skills`, `openai/skills`, `vercel-labs/agent-skills`. skills.sh is discovery-only: it points to an official repo and never provides content.
  - Freshness rule: a skill older than the model that would use it is skipped. An unknown model date is flagged, not skipped.
  - The user approves every review in prose, with a token-cost estimate. No remembered consent.
  - Container 1 runs the static pre-scan offline (`--network none`). Container 2 runs the reviewer behind an egress allow-list proxy that reaches only the model API.
  - The pre-scan is enforced as a one-way downgrade: APPROVED can become DOUBTFUL, never the reverse.
  - Hardening: strict ASCII check on the source URL, symlink guard, validation of reviewer output, secret scan.
  - Reviewer: latest astra through Codex; Fable (`claude-fable-5-1`) only if Codex fails.
  - Approved skills load by path on demand. Nothing is copied into `~/.claude/skills`.

**Known limits**
- The container-2 reviewer has not yet run end to end on a real skill.
- Reachability of `codex debug` inside Docker is unverified.
- The model release-dates table has TODO entries.
- Residual risk: the reviewer's credential sits next to untrusted text. Use a scoped, read-only key.

**Future improvement:** a decision model (OpenAI Decisions API or a luna decider) for vetting calls, deferred until measured.

## v9.4.1 — 2026-10-11 · Format fix

- `codex-agent` row back inside the agents table (§10); broken sentence in §10b rejoined. No rule changes.

## v9.4 — 2026-10-11 · Optional second vendor: OpenAI Codex

- New optional `agents/optional/codex-agent.agent.md`: a Haiku relay to `codex exec` (plan / implement / review) with a JSON verdict schema (`assets/codex-verdict.schema.json`).
- §10b: always cross vendors — Codex never reviews Codex; Claude-implemented phases get a parallel Claude + Codex review.
- Claude-only users are unaffected: the bridge is detected once per task (`CODEX: on|off` in the state file); missing CLI, login or quota falls back silently.

## v9.3 — 2026-10-11 · Conductor model, measured

- Sonnet as Conductor matched Opus (19/19 hidden criteria) at −39 % cost; the skill suggests `/model sonnet` for tier S/M.
- `/advisor` is discouraged with this skill: +150 % cost vs Sonnet alone, same accuracy, erratic delegation.

## v9.2 — 2026-10-11 · Built-in commands, used where they pay off

Based on the official command reference (119 commands) and an isolated test of what Haiku/Sonnet/Opus know about them
(78/119 correct at best; 27 newer commands unknown to all three). Only rules that fit what each actor can actually invoke:
- **Seen working:** review-agent v3.1 launches the app through the repo's run recipe (`.claude/skills/run-*`) when a phase changes visible behavior. The Conductor suggests `/run-skill-generator` once per project and `/verify` at the end (user-only commands).
- **Lean Conductor context (§8b):** suggest `/compact <focus>` after approved phases in long tasks, `/btw` for side questions, `/usage` in the final report — keeps forks under the ~75k break-even from v9.1.
- **Fork rule made operational:** the Conductor estimates its context or asks for `/context` when the choice matters.

## v9.1 — 2026-10-10 · Fork vs fresh, measured

- **Fork-or-fresh rule:** decide by the Conductor's context size. Below ~75k tokens forks are ~50 % cheaper; above, ~2× more expensive. Inherited context did not improve accuracy when the brief lists the user's decisions.
- Divergent round runs early in the session, or with fresh agents and a shared brief file past ~75k.
- Briefs must list the decisions the user made in the conversation explicitly.
- Evidence: 68 delegations, hidden tests, permutation stats (see research.md).

## v9.0 — 2026-10-09 · Research-driven rewrite

Every change below is backed by a source in `skills/subagent-pool/assets/research.md`.

### subagent-pool (Conductor) 8.2 → 9.0
- **Token economy:** SKILL.md went from 667 to ~170 lines. Templates moved to `assets/prompts.md` (progressive disclosure). Removed the identity banner, the TODO in every message and explanations of things models already do.
- **Effort tiers S/M/L:** small tasks are no longer orchestrated.
- **Ask or assume:** the mandatory 3-question interview is gone. The Conductor asks only what changes the plan (max 3 questions, each with a default) and states the rest as assumptions.
- **Divergent round (creativity):** for real design choices, 2–3 independent forks with fixed, distinct lenses return options with probabilities. The Conductor hides its own preference until convergence.
- **Governance tiers Auto / Notify / Approve:** destructive, irreversible or outward-facing actions always go to the user.
- **Pauses that change control:** plan approval stays. Per-phase pauses happen only on god nodes, approve-tier actions, FAILED, or when the user asks for them.
- **Termination:** at most 2 revision loops per phase, then the Conductor escalates.
- **Communication:** outcome first, bad news plainly, verified vs believed, disagree once with a reason, structured final report.
- **Model control:** the `model:` frontmatter in each agent decides. The Conductor never passes `model` unless the user asks.
- **Files over relays:** planning-agent writes the plan to `plans/` and returns a summary plus its path.

- **English channel, measured:** subagent prompts and `plans/*.md` stay in English; the same prompt costs ~30 % fewer input tokens than in Spanish (see research.md).
- **Explicit non-obvious instruction** in every creative prompt, backed by our own 290-sample experiment (see research.md).

### implement-agent 2.3 → 3.0 (default model: haiku)
- Shorter, more concrete rules suited to a small model. Governance tiers built in.
- **Test integrity:** never weaken, skip or delete tests to make them pass.
- Efficiency rule: read once, edit each file in one pass, verify at the end.
- New `CONFIDENCE` line in the return contract.

### review-agent 2.2 → 3.0
- Mandatory **independent check** (`INDEPENDENT_CHECK`) beyond the implementer's tests.
- `[TEST-INTEGRITY]` tag for weakened or special-cased tests.
- Anti-sycophancy: fair critic, no approving to be nice, no inventing issues.

### planning-agent 3.3 → 4.0
- Per-phase `Verify with` command and risk flags (god node / approve-tier action).
- Alternatives considered, explicit assumptions, and open questions that carry defaults.
- Writes the draft to `plans/{task}-draft.md` and returns a compact summary.

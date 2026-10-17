# Changelog

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

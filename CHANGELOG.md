# Changelog

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

# Changelog

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

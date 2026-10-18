# Bench results — every run directory

Evidence table for `competition/runs/`. One row per run directory (12 in total). The validity rule is the one used everywhere in these docs:

**valid** = exit 0, no timeout, no API / usage-limit error in the transcript, and scored (`score.json` exists).

**Valid runs: 10 of 12.** The README and CHANGELOG cite this number, and `competition/test_bench.py` checks that they match the rows of this table.

Scores were regenerated on 2026-10-18 with the current `score.py`. The usage tokens are now summed across each transcript's result records (the `result_record.usage` field). Cost stays the max `total_cost_usd`, because it is cumulative. The regenerated files also gained the review-verdict fields, which the older scorer did not write. `A-bug2-orch-cmd-1` has 2 result records, `A-improve-orch-nocodex-cmd-1` and `B-improve-orch-nocodex-cmd-2` have 3 each.

Columns: **Ref sha** is the commit that system was pinned to. **Codex** `on` means the run had Codex installed, not that `codex-agent` was called; no run in this table called `codex-agent`, and the score's `codex_tokens` is "not counted" in every run. **Skill invoked** is `subagent-pool` (agents used in brackets) or `no`. **Council** is `no` in every run: no council convened.

| Run dir | Round | System | Ref sha | Codex | CLAUDE.md | Validity | Real / hidden result | Regressions | Cost (USD) | Skill invoked | Council | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `A-bug-nocodex-1` | bug | A (v9.10.0) | 157d7b8 | off | off | invalid: API DNS error (`EAI_AGAIN`), exit 1, 1 turn | not scored | not scored | 0.0000 | no | no | Stopped at the first call: "Can't reach the API server". Replaced by run 2. |
| `A-bug-nocodex-2` | bug | A (v9.10.0) | 157d7b8 | off | off | valid | hidden 3/3 | 0 broken (46/46 still passing) | 0.3520 | no | no | Plain fix, no orchestration. |
| `B-bug-nocodex-2` | bug | B (v9.11.0) | 5772d5c | off | off | valid | hidden 3/3 | 0 broken (46/46 still passing) | 0.3608 | no | no | Plain fix, no orchestration. |
| `A-improve-nocodex-cmd-1` | improve | A (v9.10.0) | 157d7b8 | off | on | valid | hidden 5/5 | 0 broken (47/47 still passing) | 0.5492 | no | no | Plain feature, no orchestration. |
| `B-improve-nocodex-cmd-1` | improve | B (v9.11.0) | 5772d5c | off | on | valid | hidden 5/5 | 0 broken (47/47 still passing) | 0.3767 | no | no | Plain feature, no orchestration. |
| `A-improve-orch-nocodex-cmd-1` | improve-orch | A (v9.10.0) | 157d7b8 | off | on | valid | hidden 5/5 | 0 broken (47/47 still passing) | 0.7612 | yes [planning, implement, review ×2] | no | Both review verdicts are in the transcript as APPROVED, but the scorer's parser reports `missing` for both. Scorer gap, not fixed in this round. |
| `B-improve-orch-nocodex-cmd-1` | improve-orch | B (v9.11.0) | 5772d5c | off | on | invalid: session limit ("You've hit your session limit"), exit 1, 4 turns | not scored | not scored | 0.2490 | yes [planning] | no | Stopped by the usage limit. Replaced by run 2. |
| `B-improve-orch-nocodex-cmd-2` | improve-orch | B (v9.11.0) | 5772d5c | off | on | valid | hidden 5/5 | 0 broken (47/47 still passing) | 0.8576 | yes [planning, implement ×2, review ×2] | no | Replacement for `-1`. |
| `A-bug2-orch-cmd-1` | bug2-orch | A (v9.10.0) | 157d7b8 | on | on | valid | real fixed: yes (hidden 2/2) | 0 broken (50/50 still passing) | 0.5828 | yes [implement, review ×2] | no | 2 result records; usage summed (5715 output tokens). Decoy not touched. No codex-agent call. |
| `A-bug2-orch-nocodex-cmd-1` | bug2-orch | A (v9.10.0) | 157d7b8 | off | on | valid | real fixed: yes (hidden 2/2) | 0 broken (50/50 still passing) | 0.5124 | yes [implement, review] | no | Decoy not touched. |
| `B-bug2-orch-cmd-1` | bug2-orch | B (v9.11.0) | aebd9ac | on | on | valid | real fixed: yes (hidden 2/2) | 0 broken (50/50 still passing) | 0.4554 | yes [implement, review] | no | No codex-agent call. Decoy not touched. |
| `B-bug2-orch-nocodex-cmd-1` | bug2-orch | B (v9.11.0) | aebd9ac | off | on | valid | real fixed: yes (hidden 2/2) | 0 broken (50/50 still passing) | 0.5310 | yes [planning, implement, review] | no | Decoy not touched. |

## Pins

- **A** was pinned to `157d7b8` (v9.10.0) in every round.
- **B** was pinned to **different commits across rounds**:
  - `5772d5c` (v9.11.0) for the `bug`, `improve` and `improve-orch` rounds.
  - `aebd9ac` (v9.11.0) for the `bug2-orch` round.
- Those pins are not the same tree, so a difference between A and B inside one round is still a comparison, but the bug2-orch comparison also uses a different B commit than the other rounds.

## Invalid runs

- `A-bug-nocodex-1`: DNS failure inside the bench container, one turn, no work done. Run 2 of the same cell is valid.
- `B-improve-orch-nocodex-cmd-1`: session limit reached after 4 turns. Run 2 of the same cell is valid.

## Re-scoring

Every valid run was re-scored with `python3 competition/score.py score <run dirs>` against `runs/_baseline` in `kunna-bench:1`. All hidden and regression checks reproduced the earlier results. Other fields that changed: the usage tokens (summed across records), `num_turns` on the multi-record runs, the review fields, and the shape of `regression.non_target_hidden` (now a list). None of these changes the validity or the results column.

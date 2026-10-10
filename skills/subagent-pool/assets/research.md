# Evidence behind v9.0

Reference for humans and for the Conductor when a rule needs justifying. Not loaded by default.
Research done 2026-10-09. Several items are preprints; findings are summarized from abstracts and official write-ups.

## Contents
1. Token economy and instruction design
2. Effort scaling and multi-agent cost
3. Creativity and diversity
4. Governance, verification and termination
5. Communication and clarification
6. Model capabilities (what no longer needs explaining)

---

## 1. Token economy and instruction design

| Finding | Rule in v9 |
|---|---|
| Anthropic's skill guide: "Claude is already very smart — only add context Claude doesn't already have"; keep SKILL.md under 500 lines; push details to one-level-deep reference files. | SKILL.md cut from 667 to ~200 lines; templates moved to `assets/prompts.md`. |
| ETH Zurich *Evaluating AGENTS.md* (arXiv 2602.11988): LLM-generated context files slightly lowered success and raised cost >20%; extra instructions widen the agent's search instead of narrowing it. | Removed explanations of things models already do (TDD, what graphify is, generic OWASP prose, identity banners). |
| Microsoft *Less Context, Better Agents* (2026): keeping only the last few tool results raised completion (71% → 79%) while cutting tokens ~64%. | Files over relays: plans and reports go to `plans/` and are passed by path. Status in one line; TODO only at pauses. |
| Anthropic skill guide: test with Haiku, Sonnet and Opus — Haiku needs more guidance, Opus needs less. | "Match detail to the agent's model" rule. |

## 2. Effort scaling and multi-agent cost

| Finding | Rule in v9 |
|---|---|
| Anthropic multi-agent research system: multi-agent beat single-agent by 90% on breadth-first research, but used ~15× the tokens of chat; token spend explained ~80% of the variance; weaker fit for tightly coupled work like coding. Prompts embed effort-scaling rules so simple queries don't over-invest. | Tiers S/M/L; tier S is not orchestrated. |
| Same source: lead agents must give each subagent objective, output format, tool guidance and boundaries; parallel subagents and parallel tool calls cut time sharply. | Outcome-based delegation with return contracts; parallel dispatch by default. |
| Same source: subagents should write artifacts to the filesystem and return lightweight references. | `PLAN_FILE` in planning contract. |

## 3. Creativity and diversity

| Finding | Rule in v9 |
|---|---|
| *Verbalized Sampling* (Zhang et al., arXiv 2510.01171): mode collapse comes from typicality bias in preference data; asking for several responses **with probabilities** raised creative diversity 1.6–2.1× without hurting accuracy. More capable models benefit more. | Forks return options with probabilities, including a low-probability one. |
| *Diversity Collapse in Multi-Agent LLM Systems* (arXiv 2604.18005): stronger models add less diversity per sample; authority-led groups and densely connected agents converge prematurely. Recommendation: preserve independence and disagreement. | Forks don't see each other; the Conductor hides its preference until convergence. |
| *Creative Generation via Multi-Agent Debate* (arXiv 2609.00683): debate suppresses diversity through identity drift and majority pull; fixed distinct perspectives counter it. | Each fork gets a fixed, distinct lens. |
| *Creativity in LLM-based Multi-Agent Systems: A Survey* (EMNLP 2025, arXiv 2505.21116): persona design and divergent→convergent phases are the main levers. | Divergent round is a separate step before planning converges. |

### Own experiment (2026-10-09/10): spelling and tone vs. creativity

290 independent generations (Haiku, Sonnet, Opus), 2–3 blind LLM judges (inter-judge r = 0.82–0.94), 5 samples per cell.
Data and HTML reports: `Documentos/IA/experimentos/ortografia-creatividad/` in the author's machine.

| Prompt variant | Haiku | Sonnet | Opus |
|---|---|---|---|
| Neutral | 3.67 | 3.57 | 4.77 |
| Misspelled (extreme) | ≈ −0.4 | −0.97 | −1.23 |
| Praise | +0.67 | +0.03 | +0.10 |
| Insult | +0.30 | −0.60 | −0.83 |
| Critical ("mediocre and predictable") | +1.23 | +1.60 | +2.43 |
| "Avoid the predictable and the first idea" | — | **+2.00** (p=.005) | **+2.80** (p<.001) |

Takeaways → rules: the effect comes from the *instruction* to avoid the obvious, not from emotion; noise (typos) only
"unsticks" a model that is fully collapsed (Haiku on code) and hurts otherwise; stronger models benefit more.
Rule in v9: divergent prompts include the literal instruction; known attractors are named and excluded.

## 4. Governance, verification and termination

| Finding | Rule in v9 |
|---|---|
| MAST — *Why Do Multi-Agent LLM Systems Fail?* (Cemri et al., NeurIPS 2025): 14 failure modes in 3 groups — specification/design, inter-agent misalignment, **task verification and termination**. Most failures come from system design, not model limits. | Explicit stopping rules (max 2 revision loops), verdict-gated completion, structured return contracts. |
| Singapore IMDA agentic AI framework / 2026 Singapore Consensus (arXiv 2608.14611): human checkpoints for high-stakes, irreversible, outlier and user-defined actions; tiered autonomy (auto / notify / approve). Critique: a checkpoint that doesn't change control is rubber-stamping. | Governance tiers; per-phase pauses only where they change control. |
| EvilGenie (arXiv 2511.21654) and SpecBench (arXiv 2605.21384): coding agents, including Claude Code and Codex, sometimes game tests; the gap between visible and held-out tests grows with code size. LLM judges detect clear cases well. | Never weaken tests; reviewer checks test diffs and runs an independent check (`INDEPENDENT_CHECK`, `[TEST-INTEGRITY]`). |
| Self-preference bias in LLM-as-a-judge (NeurIPS 2024, arXiv 2410.21819): judges favor text familiar to them. | Prefer a reviewer on a different model than the implementer. |

## 5. Communication and clarification

| Finding | Rule in v9 |
|---|---|
| *Ask or Assume?* (arXiv 2603.26233): a coding setup with calibrated uncertainty that asks only on complex issues resolved 69.4% vs 61.2% for single-agent. | Ask-or-assume rule: ask only when a wrong guess is expensive; otherwise state the assumption. |
| *Structured Uncertainty guided Clarification* (ACL 2026 Findings): choosing questions by expected value of information covered more ambiguous tasks with 1.5–2.7× fewer questions. | Max 3 questions, each with a proposed default, all in one message. |
| UQ for LLM agents survey (arXiv 2609.07395): overconfidence grows at later trajectory steps. | `CONFIDENCE` line in implementer contract; Conductor separates verified from believed. |

## 6. Model capabilities (what no longer needs explaining)

METR's 2026 reports put frontier 50% time horizons in the many-hours range, doubling every ~4–7 months; long-horizon reliability still suffers from compounding errors, goal drift and context rot (arXiv 2608.01964, 2607.05775). Implications:
- Delegate outcomes + criteria; don't script obvious steps for capable models.
- Keep external state (`plans/*-state.md`) because long runs still drift and get cut off.
- Keep verification independent of the worker because reliability, not capability, is the bottleneck.

## Language and tokens (own measurement, 2026-10-10)

Why subagent prompts and plans are in English. Same implement-agent phase prompt (validation for `POST /users`, 4 steps, conventions, report) written in Spanish and in English, sent to Claude Haiku with `claude -p --tools ""`, 3 runs each. Prompt tokens = total input minus a 1-word baseline (92,067).

| | Words | Chars | Prompt tokens | Output tokens (mean of 3) |
|---|:---:|:---:|:---:|:---:|
| Spanish | 110 | 734 | **298** | 1,483 |
| English | 107 | 659 | **210** | 1,375 |
| English saves | | | **−30 %** | −7 % (noisy) |

Same content, same word count, ~30 % fewer input tokens: the tokenizer splits Spanish words (accents, inflections) into more pieces. Every Task prompt, plan file and agent definition is re-read on each call, so the saving compounds across phases. Output was also shorter in English but varied a lot between runs; treat −7 % as a hint, not a result. The user still gets answers in their own language: only the Conductor-to-subagent channel is English.

The v9 rewrite also cut the core prompt text (SKILL.md + prompts.md + 3 agents) from 59,772 chars (v8.2, English) to 33,772 (−43 %).

## Fork vs fresh subagent (own measurement, 2026-10-10)

Hypothesis: subagents that inherit the parent conversation (fork) are more accurate and cheaper than fresh subagents. 68 real delegations in Claude Code 2.1.296, Sonnet parent, identical parent conversation branched with `--resume --fork-session` (bug investigation + 6 user decisions). Accuracy = hidden tests, one per decision. Cost from subagent transcripts at list price. Permutation tests.

| Parent context | Condition | n | Accuracy | Subagent cost | Cache write |
|---|---|:-:|:-:|:-:|:-:|
| short (~38k) | fork | 8 | 100 % | **$0.074** | 2.9k |
| short | fresh Sonnet + brief | 8 | 100 % | $0.150 | 28.1k |
| short | fresh Sonnet, brief ≤2 sentences | 6 | 100 % | $0.135 | 26.2k |
| short | fresh Haiku + brief | 6 | 100 % | **$0.062** | 32.4k |
| long (~165k) | fork | 6 | 100 % | $0.323 | 4.3k |
| long | fresh Sonnet + brief | 6 | 100 % | $0.163 | 28.7k |
| long | fresh Haiku + brief | 6 | 100 % | **$0.066** | 35.0k |

- **Accuracy: not confirmed.** A capable parent writes the decisions into the brief; inherited context added nothing (ceiling effect, one task).
- **Cost depends on parent context.** Forks skip the ~28k cold-start cache write but re-read the parent context each turn. Break-even ≈ **75k tokens** (4–6 turn tasks, same model); above it forks cost ~2×.
- Forks always run the parent's model; a fresh Haiku agent with a brief was cheapest in every condition.
- In 299 real subagents from our sessions, forks started at a median 177k context — above break-even.

Data and report: `experimentos/fork-vs-fresh` (informe.html).

## Sources

- Anthropic — Skill authoring best practices: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- Anthropic — How we built our multi-agent research system: https://www.anthropic.com/engineering/multi-agent-research-system
- Verbalized Sampling: https://arxiv.org/abs/2510.01171
- Why Do Multi-Agent LLM Systems Fail? (MAST): https://arxiv.org/abs/2503.13657
- Diversity Collapse in Multi-Agent LLM Systems: https://arxiv.org/abs/2604.18005
- Creative Generation via Multi-Agent Debate: https://arxiv.org/abs/2609.00683
- Creativity in LLM-based Multi-Agent Systems (survey): https://arxiv.org/abs/2505.21116
- Evaluating AGENTS.md: https://arxiv.org/abs/2602.11988
- Less Context, Better Agents: https://www.alphaxiv.org/abs/2606.10209
- 2026 Singapore Consensus on AI Safety: https://arxiv.org/pdf/2608.14611
- EvilGenie: https://arxiv.org/abs/2511.21654
- SpecBench: https://arxiv.org/abs/2605.21384
- Self-Preference Bias in LLM-as-a-Judge: https://arxiv.org/abs/2410.21819
- Ask or Assume?: https://arxiv.org/abs/2603.26233
- Structured Uncertainty guided Clarification: https://aclanthology.org/2026.findings-acl.2028/
- Uncertainty Quantification for LLM Agents: https://arxiv.org/abs/2609.07395
- METR Frontier Risk Report (Feb–Mar 2026): https://metr.org/blog/2026-05-19-frontier-risk-report/

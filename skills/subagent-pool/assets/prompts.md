# Task Templates — Conductor v9.0

Copy, fill, send. Every prompt ends with the agent's return contract so the handoff is parseable.
Write prompts as directives (what + why + files + constraints), not background essays.

## Contents
1. planning-agent
2. implement-agent
3. review-agent
4. Revision after NEEDS_REVISION
5. Divergent fork (creativity round)
6. AgentArchitect
7. Final report to the user

---

## 1. planning-agent

```
Task(description="Plan: {brief}", subagent_type="planning-agent", prompt="""
Investigate and draft a plan for: {one-line task}

Tier: {M | L}
Scope: {existing project | new folder} — {stack or "detect"}
Graphify: {EXISTS at graphify-out/graph.json | NOT_EXISTS, ~N files}
Chosen approach: {from divergent round, or "pick the simplest sound one; list 1-2 rejected alternatives"}
Assumptions already stated to the user: {list or "none"}
Out of scope: {what NOT to touch}
Constraints: {hard limits}

Pre-loaded context (project-context.md):
Architecture: {≤200 chars} | Stack: {stack} | Language: {language}
God nodes: {list} | Communities: {list}

Write the full plan to plans/{task}-draft.md and return only the summary below.

STATUS: PLAN_READY | NEED_CLARIFICATION
PLAN_FILE: plans/{task}-draft.md
TLDR: {1-3 sentences}
PHASES: {N} — one line each: title · files count · risk (god node? approve-tier action?)
OPEN_QUESTIONS: {only those that change the plan, each with a proposed default, or "none"}
""")
```

## 2. implement-agent

For Haiku, keep Steps numbered and concrete and give the exact verify command. For Opus/Sonnet, Steps may be short.

```
Task(description="Phase {N}: {title}", subagent_type="implement-agent", prompt="""
Phase {N}: {title}   (plan: plans/{task}-plan.md)

Objective: {one sentence}
Rationale: {why — the criterion to self-correct with}
Contracts/Invariants: {falsifiable guarantees; breaking one → report under DEVIATIONS}
Acceptance criteria: {bullets}
Files: {path ✓exists | path ⊕create}
Steps: {numbered}
Verify with: {exact command(s)}
Conventions: lang={language}, stack={stack}
Graph warnings: {god nodes / hidden deps — never omit if present}
Governance: Auto = edits inside listed files + tests. Notify = anything else → DEVIATIONS.
  Approve = delete/overwrite data, migrations, secrets, push/publish/deploy → STOP, STATUS: BLOCKED.
Never weaken, skip or delete tests to make them pass.

STATUS: DONE | BLOCKED | PARTIAL
FILES_CHANGED: path:lines — what
COMMANDS_RUN: command → exit code
TESTS: {N/M passing, or "none run" + why}
DEVIATIONS: {or "none"}
CONFIDENCE: {verified | partially verified | unverified} — one line why
NEXT: {remaining, or "complete"}
""")
```

## 3. review-agent

```
Task(description="Review Phase {N}: {title}", subagent_type="review-agent", prompt="""
Review Phase {N}: {title}

Objective: {one sentence}
Rationale: {judge intent, not only literal steps}
Contracts/Invariants: {declared ones — derive others, try to break each BEFORE reading the code}
Acceptance criteria: {bullets}
Files changed (implementer report): {list}
Tests reported: {implementer TESTS line}
Deviations reported: {list or "none"}
Conventions: lang={language}, stack={stack}
Security: {apply OWASP | N/A — no external input}

STATUS: APPROVED | NEEDS_REVISION | FAILED
FINDINGS: file:line — issue  ([INVARIANT] / [CRITICAL] / [MAJOR] / [TEST-INTEGRITY] tags)
INDEPENDENT_CHECK: {what you ran yourself beyond the implementer's tests → result}
REQUIRED_CHANGES: {specific + actionable, or "none"}
DEVIATION_VERDICT: {per deviation, or "none reported"}
""")
```

## 4. Revision after NEEDS_REVISION

```
Task(description="Phase {N} fix #{k}", subagent_type="implement-agent", prompt="""
Phase {N} — revision {k} of max 2   (plan: plans/{task}-plan.md)
Fix ONLY these review findings:
{REQUIRED_CHANGES verbatim}
Files: {same list}  |  Verify with: {command}
Same governance and return contract as the original phase.
""")
```

On a 3rd failure, stop and consult the user instead of looping.

## 5. Divergent fork (creativity round)

Send 2-3 of these in ONE message, each with a different lens. Omit `subagent_type` (fork) and `model`.

```
Agent(description="Ideas: {lens}", prompt="""
Design question: {the decision to make, with constraints}
Your lens: {simplest thing that works | most robust long-term | unconventional / reuse what exists}
Work independently — you will not see other proposals.
Return 2-3 genuinely different options. For each: one-paragraph sketch · probability it's the right call (0-1)
· biggest risk · cost (S/M/L). At least one option must be low-probability but plausible.
""")
```

The Conductor then picks the 2-3 strongest *distinct* options, recommends one, and lets the user choose.

## 6. AgentArchitect

```
Task(description="Design team for {domain}", subagent_type="AgentArchitect", prompt="""
Problem: {description}
Known context: {what the user said}
Interview the user, design the agent pyramid, generate files in .claude/agents/.
""")
```

## 7. Final report to the user (user's language)

```
**{Outcome in one sentence.}**

- Changed: {files / features, grouped}
- Verified: {tests + reviewer independent checks}
- Not done / risks: {honest list, or "nothing pending"}
- Needs your decision: {list, or omit}

Commit: `{type(scope): message}`
```

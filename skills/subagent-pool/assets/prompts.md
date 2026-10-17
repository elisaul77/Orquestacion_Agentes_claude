# Task Templates — Conductor v9.7

Copy, fill, send. Every prompt ends with the agent's return contract so the handoff is parseable.
Write prompts as directives (what + why + files + constraints), not background essays.

## Contents
1. planning-agent
2. implement-agent
3. review-agent
3b. review-agent — security mode
4. Revision after NEEDS_REVISION
5. Divergent fork (creativity round)
6. AgentArchitect
7. Final report to the user
8. codex-agent — debug (Docker only)
9. codex-agent — browser (screenshot check)
10. codex-agent — coordinate (fan-out inside Codex)

---

## 1. planning-agent

```
Task(description="Plan: {brief}", subagent_type="planning-agent", prompt="""
Investigate and draft a plan for: {one-line task}

Tier: {M | L}   Operation: {feature | fix | tweak | refactor} — first move: {from SKILL.md §2}
Instincts for this project: {output of `instincts.py list --min 0.5`, or "none"}
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
Operation: {feature | fix | tweak | refactor} — first move: {e.g. "fix: write the failing test first and show it failing"}
Rationale: {why — the criterion to self-correct with}
Contracts/Invariants: {falsifiable guarantees; breaking one → report under DEVIATIONS}
Acceptance criteria: {bullets}
Files: {path ✓exists | path ⊕create}
Steps: {numbered}
Verify with: {exact command(s)}  — long output: `set -o pipefail; {cmd} 2>&1 | python3 ~/.claude/skills/subagent-pool/scripts/trim_output.py`
Conventions: lang={language}, stack={stack}
Graph warnings: {god nodes / hidden deps — never omit if present}
Governance: Auto = edits inside listed files + tests. Notify = anything else → DEVIATIONS.
  Approve = delete/overwrite data, migrations, secrets, push/publish/deploy → STOP, STATUS: BLOCKED.
Never weaken, skip or delete tests to make them pass. Never swallow errors (empty catch, error → null/[] without context).

STATUS: DONE | BLOCKED | PARTIAL
FIRST_MOVE: {evidence, e.g. "test_x failed before the fix (exit 1), passes after"}
FILES_CHANGED: path:lines — what
COMMANDS_RUN: command → exit code
TESTS: {N/M passing, or "none run" + why}
DEVIATIONS: {or "none"}
CONFIDENCE: {verified | partially verified | unverified} — one line why
UNKNOWNS: {open questions you hit, or "none"}
NOT_VERIFIED: {what you skipped or couldn't check, or "nothing"}
NEXT: {remaining, or "complete"}
""")
```

## 3. review-agent

```
Task(description="Review Phase {N}: {title}", subagent_type="review-agent", prompt="""
Review Phase {N}: {title}

Objective: {one sentence}
Operation: {feature | fix | tweak | refactor} — check the first move was honored
Rationale: {judge intent, not only literal steps}
Contracts/Invariants: {declared ones — derive others, try to break each BEFORE reading the code}
Acceptance criteria: {bullets}
Files changed (implementer report): {list}
Tests reported: {implementer TESTS line}
Deviations reported: {list or "none"}
Conventions: lang={language}, stack={stack}
Security: {apply OWASP | N/A — no external input}
Open ledger rows to rule on: {criterion list from the state file}

STATUS: APPROVED | NEEDS_REVISION | FAILED
FINDINGS: file:line — issue  ([INVARIANT] / [CRITICAL] / [MAJOR] / [TEST-INTEGRITY] tags)
CRITERIA: {#} {criterion} — [OBSERVED|DERIVED|INFERRED|UNKNOWN] {proof: command → result}
INDEPENDENT_CHECK: {what you ran yourself beyond the implementer's tests → result}
REQUIRED_CHANGES: {specific + actionable, or "none"}
DEVIATION_VERDICT: {per deviation, or "none reported"}
UNKNOWNS: {or "none"}
NOT_VERIFIED: {or "nothing"}
""")
```

## 3b. review-agent — security mode

Send in the SAME message as §3 when the diff touches a security trigger (SKILL.md §7). Stricter verdict wins.

```
Task(description="Security review Phase {N}", subagent_type="review-agent", prompt="""
mode=security — Phase {N}: {title}
Trigger(s) touched: {auth | user input | DB queries | file paths | external API | crypto | secrets}
Files changed: {list}
Review ONLY security: injection (SQL/command/path), authz bypass, secrets in code or logs, unsafe deserialization,
SSRF on external calls, weak crypto, missing input validation at the trust boundary. Try one concrete exploit input per
trigger and report the result. Skip style and general correctness (the normal review covers them).

Same return contract as §3; tag findings [SECURITY-CRITICAL] or [SECURITY-MAJOR] (they map to CRITICAL / MAJOR).
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
Avoid the predictable and the first idea that comes to mind.
Return 2-3 genuinely different options. For each: one-paragraph sketch · probability it's the right call (0-1)
· biggest risk · cost (S/M/L). At least one option must be low-probability but plausible.
""")
```

The Conductor then picks the 2-3 strongest *distinct* options, recommends one, and lets the user choose.

## 6. AgentArchitect

```
Task(description="Design team for {domain}", subagent_type="AgentArchitect", prompt="""
mode=design
Domain: {domain}   Problem: {description}
Known context: {what the user said; project-context.md summary}
User answers so far: {numbered answers to earlier QUESTIONS, or "none"}
Why the base pool isn't enough: {one line}
""")
```

After `DESIGN_READY`, show the user the design file's TL;DR + agents table. On approval:

```
Task(description="Generate team {domain}", subagent_type="AgentArchitect", prompt="""
mode=generate
Design file: plans/team-{domain}.md — APPROVED by the user on {date}
CODEX: {on|off}
Edits requested by the user: {list, or "none"}
""")
```

`AGENTS_CREATED` → write the state file, then tell the user (their language): the agents exist but load on the
next session; restart Claude Code and say "resume" to continue from the state file.

## 7. Final report to the user (user's language)

Tier M/L: send the Gate 2 block first and wait for the user before any commit.

```
**Ready to commit — {N} files, +{a}/−{d} lines.**
- {file} — {what}
Open findings: {none | list — CRITICAL/MAJOR block the commit}
Criteria: {closed}/{total} — open: {list with why, or "none"}
Not verified: {list, or "nothing"}
Proposed commit(s): `{type(scope): message}`
Commit? (push stays a separate approval)
```

```
**{Outcome in one sentence.}**

- Changed: {files / features, grouped}
- Verified: {tests + reviewer independent checks}
- Not done / risks: {honest list, or "nothing pending"}
- Not verified: {what nobody checked, or "nothing"}
- Needs your decision: {list, or omit}

Commit: `{type(scope): message}`
```

---

## 8. codex-agent — debug (Docker only)

```
Task(description="Debug: {bug}", subagent_type="codex-agent", prompt="""
mode=debug
Bug: {one-line symptom, exact error text if known}
Docker service: {compose service name} (compose file: {path})   # required; missing → BLOCKED, no Codex call
Repro command (run inside the container): {command}
Logs (inside the container): {paths | "none"}
Edits: none (report only) | {files Codex may edit}
Never run anything on the host. Do not print secret values from .env or config files.
""")
```

Relay: `summary` = numbered repro steps; `findings` = reproduced errors (file:line from the traceback).

## 9. codex-agent — browser (screenshot check)

```
Task(description="Visual check: {page}", subagent_type="codex-agent", prompt="""
mode=browser
URL: {http://localhost:PORT/path | file:// copy inside the scratch dir}
Question: {what to judge in the UI, e.g. "do all 4 form fields fit without overflow?"} | "capture only"
""")
```

Relay: `artifacts` = PNG path; hand it to `review-agent` (Read) per SKILL.md §10b.

## 10. codex-agent — coordinate (fan-out inside Codex)

```
Task(description="Coordinate: {scope}", subagent_type="codex-agent", prompt="""
mode=coordinate   max_agents={≤3}
Plan: plans/{task}-plan.md — run phases {list} (independent, disjoint files)
Roles allowed: {e.g. implement-agent, VidImplementer}   (synced in ~/.codex/agents)
Per phase: objective · files · acceptance criteria · verify command   (same fields as §2)
Governance: Approve-tier actions → BLOCKED, never performed.
""")
```

Then dispatch one `review-agent` per phase in ONE message (§3). `STATUS: BLOCKED` with stale roles → ask the user to
run `sync_codex_agents.py` (it writes to ~/.codex/agents).

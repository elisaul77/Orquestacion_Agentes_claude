# Task Templates — Conductor v9.9

Copy, fill, send. Every prompt ends with the agent's return contract so the handoff is parseable.
Write prompts as directives (what + why + files + constraints), not background essays.

## Contents
1. planning-agent
2. implement-agent
3. review-agent
3b. review-agent — specialty mode (security, api, data, ui, perf, ops)
4. Revision after NEEDS_REVISION with FAILURE_ORIGIN: implementation
5. Divergent fork (creativity round)
6. AgentArchitect
7. Final report to the user
8. codex-agent — debug (Docker only)
9. codex-agent — browser (screenshot check)
10. codex-agent — coordinate (fan-out inside Codex)
11. Plan council (brief, spawn, round signals)
12. Consult (one specialist, one bounded question)

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

### Diagnosis brief

Use when a failure has no known cause yet (SKILL.md §2b). The output is an understanding and a proposed intervention, not a validated fix.

```
Task(description="Diagnose: {symptom}", subagent_type="planning-agent", prompt="""
Diagnose: {one-line symptom, exact error text if known}

Operation: {fix | tweak | feature | refactor}
Case file: plans/{task}-state.md   (hypotheses, evidence and rounds so far are there; read it, do not write it)
Prior hypotheses and their FALSIFIER results: {list, or "none"}
Round: {k} — rounds without new evidence so far: {0 | 1}
Out of scope: {what NOT to touch}

Do not write a plan and do not modify project files. Enough evidence = justified understanding + proposed
intervention, not a validated fix. FALSIFIER: required when operation=fix or a hypothesis drives the change; else n/a.

FACTS: {observed or read facts, each tagged [OBSERVED] or [DERIVED] with its proof}
HYPOTHESES: {numbered, each with why it fits the facts}
EVIDENCE: {H# · command → result · supports | weakens}
MISSING (project|specialist|user): {what is unknown, and who can answer it}
PROPOSED_INTERVENTION: {smallest change for the leading hypothesis; files ✓exists | ⊕create}
FALSIFIER: {hypothesis + command + expected result that would disprove it, or "n/a"}
""")
```

## 2. implement-agent

For Haiku, keep Steps numbered and concrete and give the exact verify command. For Opus/Sonnet, Steps may be short.

```
Task(description="Phase {N}: {title}", subagent_type="implement-agent", prompt="""
Phase {N}: {title}   (plan: plans/{task}-plan.md)

Objective: {one sentence}
Operation: {feature | fix | tweak | refactor} — first move: {e.g. "fix: write the failing test first and show it failing"}
Hypothesis / falsifier: {required when the Conductor diagnosed the fix itself (SKILL §2b, inline falsifier): hypothesis + the observation that would disprove it; the implementer writes the failing test from it first; otherwise "n/a"}
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
WARNINGS: {anything noticed but not fixed — edge cases, risks, follow-ups — or "none"}
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
WARNINGS to rule on: {the implementer's WARNINGS list, or "none"}
Case file: plans/{task}-state.md (security-trigger baseline listed there)
Falsifier (diagnosis, from the case file, or n/a): {hypothesis + command + expected result, or "n/a"}

STATUS: APPROVED | NEEDS_REVISION | FAILED
FAILURE_ORIGIN: implementation | diagnosis | scope | none
ORIGIN_EVIDENCE: {one line; "n/a" with APPROVED}
FINDINGS: file:line — issue  ([INVARIANT] / [CRITICAL] / [MAJOR] / [TEST-INTEGRITY] tags)
CRITERIA: {#} {criterion} — [OBSERVED|DERIVED|INFERRED|UNKNOWN] {proof: command → result}
INDEPENDENT_CHECK: {what you ran yourself beyond the implementer's tests → result}
REQUIRED_CHANGES: {specific + actionable, or "none"}
WARNINGS_RULING: {one line per WARNINGS item: fixed | acceptable | must fix, or "none"}
DEVIATION_VERDICT: {per deviation, or "none reported"}
UNKNOWNS: {or "none"}
NOT_VERIFIED: {or "nothing"}
""")
```

## 3b. review-agent — specialty mode (`mode=<specialty>`)

Send in the SAME message as §3 when the diff touches a security trigger (SKILL.md §7). Stricter verdict wins.
Specialties: `security` (the template below, trigger-driven) · `api` · `data` · `ui` · `perf` · `ops` (checklists after it).

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

### Other specialties (api, data, ui, perf, ops)

Same shape. The reviewer checks only the five lines of the specialty's checklist and answers with the §3 contract.
Tag findings `[CRITICAL]` or `[MAJOR]`. A checklist line the reviewer cannot check → `[UNKNOWN]` on that criterion.

```
Task(description="{specialty} review Phase {N}", subagent_type="review-agent", prompt="""
mode={specialty} — Phase {N}: {title}
Surface touched: {what in this diff falls under the specialty}
Files changed: {list}
Review ONLY the checklist below. Try one concrete case per line where you can and report what happened.
Skip everything else (the normal review covers it).

{the five checklist lines for the specialty, copied from below}

Same return contract as §3.
""")
```

Checklists (one per specialty; if the specialty is not listed here, there is no checklist, so mark the criterion `[UNKNOWN]`):

- **api**
  1. Contract / backward compatibility: existing requests and responses unchanged, or the break is listed and approved
  2. Versioning: breaking changes go to a new version path or field; deprecations carry a date
  3. Errors: stable error shape and status codes; no stack traces or internal ids leak
  4. Auth on endpoints: every new or changed route declares its auth, and a test shows the 401/403
  5. Docs: the API doc matches the implemented request and response

- **data**
  1. Migrations reversible: a down path exists, or the irreversibility is stated and approved (Approve-tier)
  2. Backups: a restore point exists before destructive or bulk changes
  3. Constraints: new NOT NULL, unique and foreign-key rules are enforced in the database, not only in code
  4. PII: personal fields are identified, minimized, and kept out of logs and fixtures
  5. Volume: row counts and query cost at production scale are estimated or measured

- **ui**
  1. Accessibility AA: contrast, input labels, alt text, focus order, no color-only meaning
  2. States: empty, error and loading states each render and are visible
  3. Design-system tokens: colors, spacing and type come from tokens, no hard-coded values
  4. Responsive: checked at mobile and desktop widths, no overflow or clipped controls
  5. Keyboard: every action reachable and operable by keyboard alone, with visible focus

- **perf**
  1. Hot path measured: before/after timing or profile on the real path, with the command
  2. N+1: no query or call inside a loop over results; batch or join instead
  3. Memory: no unbounded lists, caches or buffers; sizes are capped
  4. Concurrency / locks: no lock held across I/O; lock ordering is consistent
  5. Timeouts: every external call and queue wait has a timeout and a failure path

- **ops**
  1. Config / secrets: new settings have defaults and docs; no secret in code, images or logs
  2. Rollback: the previous version runs against the new data and config; the rollback command is written
  3. Health checks: liveness and readiness checks reflect the new dependency
  4. Logging: errors logged with context and without secrets; log level set per environment
  5. Resource limits: CPU, memory and disk limits set for new services or jobs

## 4. Revision after NEEDS_REVISION with FAILURE_ORIGIN: implementation (max 2 per phase)

Other origins are not sent here: diagnosis → use the §1 Diagnosis brief, citing the disproved falsifier; scope → re-triage per SKILL §7; both count toward the 3 re-routes.

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

Status: VERIFIED (not deployed) | STOPPED — {reasons + pending items}

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

---

## 11. Plan council (brief, spawn, round signals)

Protocol and limits: `assets/council.md`. Write the brief first, then spawn all members in ONE message.

`plans/council/{task}/brief.md`:
```
# Council brief — {task}
Task: {one line}            Tier: {M|L}   Operation: {type} — first move: {from §2}   Level: {duo|council}
Project: {abs path}         CODEX: {on|off}
Context: {stack · language · god nodes · graphify EXISTS/NOT_EXISTS}
User decisions (invariants): {each one}
Constraints / out of scope: {list}
Members: {duo: architect, lateral | council: spec, architect, lateral, risk}   Council dir: plans/council/{task}
Plan file (R3): plans/{task}-draft.md
Lens for swapped seat: {specialty (security | api | data | ui | perf | ops) or none}
```

Spawn (one per member of the level, same message; omit `model`):
```
Agent(subagent_type="council-{role}", name="{role}", run_in_background=true,
      description="Council {role}: {task}", prompt="""
You are '{role}' in a plan council. Brief: plans/council/{task}/brief.md — read it first, then the protocol at
~/.claude/skills/subagent-pool/assets/council.md. Do R1 now (blind draft). Wait for the Conductor's R2 / R3 signals.
Other members you may message: {the other names}.
""")
```

Round signals (send only at a barrier; content never goes through the Conductor):
```
SendMessage(to="{role}", message="R2a: all drafts are in plans/council/{task}/. Send and log your objections per council.md, then say R2a done.")
SendMessage(to="{role}", message="R2b: answer the objections addressed to you in debate.log, then say R2b done.")
SendMessage(to="architect", message="R3: synthesize plans/{task}-draft.md and plans/council/{task}/decisions.md, return the contract.")
```

File-mode fallback (teams flag off): the same prompts through `Task` without `name`; R2a becomes
"read the other drafts and append objections to debate.log", R2b one answer wave (see `council.md`).

---

## 12. Consult (one specialist, one bounded question)

One question, one existing agent, one answer. No council, no new agent, no plan. Use `planning-agent` for a code fact
(what calls this, where is the config read); use `review-agent mode=consult specialty=<specialty>` for a judgement (checklists in §3b).
A consult result goes into the case file as evidence; it does not change any review STATUS.

```
Task(description="Consult {specialty}: {short question}", subagent_type="review-agent" | "planning-agent", prompt="""
mode=consult specialty={specialty}      # review-agent only; delete this line for planning-agent
QUESTION: {one bounded question, answerable in one value, yes/no, or file:line}
CONTEXT: {only what the answer needs: files ✓exists, command outputs, the hypothesis it tests}
EXPECTED RESULT: {the shape of the answer, e.g. "yes/no + file:line"}
Read-only. Do not change files. Answer this question only.

ANSWER: {the answer, one line}
EVIDENCE: [OBSERVED|DERIVED|INFERRED|UNKNOWN] {proof: command → result, or file:line}
CONFIDENCE: {verified | partially verified | unverified} — one line why
UNKNOWNS: {or "none"}
""")
```



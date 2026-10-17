# Full Interview Protocol — Agent Orchestration Design

> **Who uses this file:** only the **Conductor** asks these questions — a subagent can't talk to the user.
> AgentArchitect returns the missing ones as `NEED_INTERVIEW`; the Conductor asks them in prose and passes the answers back.
> For the Conductor in operational mode, the 3-question mini-interview in SKILL.md is sufficient.

---

## The 8 Questions (AOD Interview Protocol)

Ask the questions **in order**. Stop when you have enough to design the pyramid.

### Q1 — Starting point
> Are we starting from an **empty folder** or should I study an **existing project** first?

- **Empty folder** → continue to Q2
- **Existing project** → workspace scan:
  1. Read `README.md` at root if it exists
  2. Read `.claude/CLAUDE.md` or `AGENTS.md` if they exist
  3. List top-level structure (`ls -la`)
  4. Read 3-5 key files to infer conventions (palette, language, stack, templates)
  5. Summarize findings to user in 4-8 bullets before continuing

### Q2 — Purpose / Problem statement
> Describe in 1-3 sentences: **what problem** you want to solve and **what the final deliverable** is.

### Q3 — Input artifact(s)
> What material does the team start with? Typical options: source code, documents (PDF/Word), data (CSV/DB), APIs, UI, mix.

### Q4 — Output artifact(s)
> What does the team deliver when done? Typical options: new code + tests, structured Markdown documentation, processed dataset, report, deployment.

### Q5 — Sub-domains
> Does the problem have clearly separable sub-domains with a different workflow (e.g. backend + frontend, migration + integration)? Each gets its own specialist or trio; the Conductor runs them in parallel (subagents can't coordinate other subagents).

### Q6 — Special capabilities
Checklist (mark those that apply):
- [ ] TDD / automated tests
- [ ] Image extraction + description (vision)
- [ ] Browser UI verification
- [ ] Terminal / script execution
- [ ] Access to external repos (GitHub)
- [ ] Web queries / external documentation
- [ ] Jupyter notebook manipulation
- [ ] Browser automation (clicks, forms)

### Q7 — User pause points
> At what moments should the Conductor **pause mandatory** to wait for your confirmation?

Safe defaults:
1. After presenting the phase plan
2. After each reviewed and approved phase
3. When closing the process with the final report

### Q8 — Language and corporate conventions
> Output language (Spanish/English)? Are there corporate conventions (color palette, templates, glossary) that agents must follow?

---

## Suggested round groupings

**Round A** (independent — ask together):
- Q2 purpose, Q3 input, Q4 output, Q8 language/conventions

**Round B** (depend on A):
- Q5 sub-domains, Q6 special capabilities

**Round C** (confirmation):
- Q7 pause points

---

## Interview rules

- **Never ask everything at once** — maximum 4-5 questions per round
- **Prefer multiple choice** with a recommended default when applicable (reduces fatigue)
- **Always allow free-form response** in addition to the options
- **Reflect understanding** after each round: "So the team must {summary} — correct?"
- **Stop asking** when you can complete the §7 checklist in SKILL.md

---

## Post-interview decision rules

### Separate specialists per sub-domain? (Q5)
Only if the sub-domain has a different workflow (different tools or review criteria). Prefer one extra specialist over
a whole trio. No coordinator agents: subagents can't spawn subagents, so all fan-out is the Conductor's.

### Merge Analyst + Executor?
Only if the analysis is trivial (< 10% of the phase effort). Otherwise keep them separate.

### Split the Reviewer?
Only if verification requires fundamentally different skills (e.g. `CodeReviewer` + `UXReviewer`).

### Tool assignment by role
| Role | Tools |
|------|-------|
| Conductor | `Task`, `Write`/`Edit` (plans/ only) |
| Planner/Analyzer | `Read`, `Glob`, `Grep`, `Bash` (read), `WebSearch`, `WebFetch` |
| Executor/Implementer | `Read`, `Edit`, `Write`, `Glob`, `Grep`, `Bash` |
| Reviewer | `Read`, `Glob`, `Grep`, `Bash` (read) |

**NEVER give the Conductor execution tools** (`Bash` directly on code, `Edit` on project files).

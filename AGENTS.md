# Orquestacion Agentes Claude — AGENTS.md

## Overview

```mermaid
flowchart LR
    USER["👤 User"] -->|"request"| CONDUCTOR["🎭 Conductor<br/>NEVER touches code"]
    CONDUCTOR -->|"investigate + workspace scan"| PA["📋 planning-agent"]
    CONDUCTOR -->|"implement"| IA["💻 implement-agent"]
    CONDUCTOR -->|"review + security"| RA["🔍 review-agent"]
    CONDUCTOR -->|"design new team"| AA["🏗️ AgentArchitect"]
    PA -.->|"workspace scan + plan draft"| CONDUCTOR
    IA -.->|"report"| CONDUCTOR
    RA -.->|"APPROVED/NEEDS_REVISION/FAILED"| CONDUCTOR
    AA -.->|"generated .agent.md files"| CONDUCTOR
    CONDUCTOR --> USER

    style CONDUCTOR fill:#ff9800,color:#fff
    style PA fill:#2196f3,color:#fff
    style IA fill:#4caf50,color:#fff
    style RA fill:#ffc107,color:#000
    style AA fill:#9c27b0,color:#fff
```

**Principle:** The Conductor COORDINATES. Subagents EXECUTE. The signature `🤖 [<agent>] ...` confirms which subagent responded.

---

## Conductor Golden Rules

| The Conductor (this skill) | The Subagents |
|---------------------------|---------------|
| ✅ Plans and coordinates | ✅ Execute concrete work |
| ✅ Asks only what changes the plan (max 3, each with a default) | ✅ planning-agent: workspace scan + draft |
| ✅ Writes in `plans/*.md` | ✅ implement-agent: code and tests |
| ✅ Updates TodoWrite | ✅ review-agent: verdict + security |
| ✅ Announces delegations | ✅ AgentArchitect: generates new agents |
| ❌ **NEVER** Read/Grep/Edit on code | ❌ Don't touch plans or coordination docs |
| ❌ **NEVER** runs Bash on the repo | ❌ Don't delegate to other subagents |

---

## Language Policy

| Agent | Language |
|-------|----------|
| **Conductor** | User's language (detects from first message) |
| planning-agent | English |
| implement-agent | English |
| review-agent | English |
| AgentArchitect | English |

---

## Registered Subagents

| Subagent | File | `subagent_type` | Model | Signature |
|----------|------|-----------------|-------|-----------|
| planning-agent | `agents/planning-agent.agent.md` | `planning-agent` | sonnet | `🤖 [planning-agent] Investigating...` — uses graphify for knowledge graph |
| implement-agent | `agents/implement-agent.agent.md` | `implement-agent` | haiku | `🤖 [implement-agent] Running Phase {N}...` |
| review-agent | `agents/review-agent.agent.md` | `review-agent` | sonnet | `🤖 [review-agent] Reviewing Phase {N}...` |
| AgentArchitect | `agents/AgentArchitect.agent.md` | `AgentArchitect` | opus | `🏗️ [AgentArchitect] Designing team...` |
| codex-agent (optional) | `agents/optional/codex-agent.agent.md` | `codex-agent` | per mode (registry) | `🤖 [codex-agent] mode=<mode> model=<model>` — only if you use Codex; see SKILL §10b |

---

## Available Skills

| Skill | Trigger | Version |
|-------|---------|---------|
| `subagent-pool` | "delegate", "orchestrate", "conductor", "complex task" | 9.7 |
| `arquitec-dev-ia` | "create AGENTS.md", "document architecture", "structure for AI", "output style", "add rules", "prepare for orchestration" | 5.0 |
| `graphify` | `/graphify` | — |

---

## Auto-invoke

| User action | Skill |
|-------------|-------|
| "use the conductor for..." | `subagent-pool` |
| "delegate to..." | `subagent-pool` |
| "orchestrate the separation / refactor / feature" | `subagent-pool` |
| "Phase 1:", "next phase" | `subagent-pool` |
| "design an agent team for..." | `subagent-pool` → `AgentArchitect` |

---

## Workflow v9.7

1. Conductor reads `.claude/project-context.md` (HALT and suggest `arquitec-dev-ia` if missing); offers to resume an unfinished `plans/*-state.md`
2. Picks a tier: **S** do it directly · **M** plan + phases · **L** full flow
3. Asks only questions that change the plan (max 3, each with a default); states other assumptions
4. Tier L with a real design choice → **divergent round**: 2-3 independent forks with distinct lenses, user picks
5. `planning-agent` writes the plan to `plans/{task}-draft.md` → ⏸️ **PAUSE** for approval
6. Per phase: `implement-agent` → `review-agent` (contract-first + independent check)
   - NEEDS_REVISION → max 2 loops, then consult the user
   - Approve-tier actions (delete, migrate, secrets, push/publish/deploy) → BLOCKED until the user approves
   - checkpoint `plans/{task}-state.md`; pause only on god nodes, approve-tier actions, FAILED or user request
7. Final report: changed · verified · not done/risks · commit message

Models: each agent's `model:` frontmatter decides; the Conductor never overrides it unless the user asks.

---

## Plan status (shown at pauses and at the end)

```markdown
## Plan: {name}

### Status
- [x] Phase 0: Workspace scan + investigation ✅
- [x] Phase 1: {title} ✅ APPROVED
- [🔄] Phase 2: {title} ← IN PROGRESS (delegated to implement-agent)
- [ ] Phase 3: {title}

🎭 Last action: {what I just did}
🎯 Next: {what comes next}
```

---

## Resources

- **Skill (orchestration):** `skills/subagent-pool/SKILL.md`
- **Skill (documentation):** `skills/arquitec-dev-ia/SKILL.md`
- **Project context template:** `skills/arquitec-dev-ia/assets/template_project_context.md`
- **Prompt templates:** `skills/subagent-pool/assets/prompts.md`
- **Definitions + troubleshooting:** `skills/subagent-pool/assets/agent-definitions.md`
- **Full interview protocol:** `skills/subagent-pool/assets/interview-protocol.md`
- **Agents:** `agents/*.agent.md`

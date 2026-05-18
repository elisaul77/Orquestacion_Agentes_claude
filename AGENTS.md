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
| ✅ Runs mini-interview (Q1, Q2, Q3) | ✅ planning-agent: workspace scan + draft |
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
| implement-agent | `agents/implement-agent.agent.md` | `implement-agent` | sonnet | `🤖 [implement-agent] Running Phase {N}...` |
| review-agent | `agents/review-agent.agent.md` | `review-agent` | sonnet | `🤖 [review-agent] Reviewing Phase {N}...` |
| AgentArchitect | `agents/AgentArchitect.agent.md` | `AgentArchitect` | opus | `🏗️ [AgentArchitect] Designing team...` |

---

## Available Skills

| Skill | Trigger | Version |
|-------|---------|---------|
| `subagent-pool` | "delegate", "orchestrate", "conductor", "complex task" | 7.0 |
| `arquitec-dev-ia` | "create AGENTS.md", "document architecture", "structure for AI", "output style", "add rules" | 4.0 |
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

## Workflow v7.0 (with Graphify)

1. Conductor shows **identity block** `🎭 CONDUCTOR ACTIVATED — v7.0`
2. Conductor runs **mini-interview** (Q1 project, Q2 sub-domains, Q3 pauses)
3. Conductor decides architecture (flat vs sub-coordinators)
4. Conductor creates TodoWrite with initial phases
5. Conductor checks graphify status (`ls graphify-out/graph.json`) and informs planning-agent
6. Conductor delegates to `planning-agent` → receives workspace scan + graphify (god nodes, communities, queries) + plan draft
7. Conductor presents plan to user → ⏸️ **PAUSE**
8. User approves → Conductor writes to `plans/{task}-plan.md`
9. Per each phase:
   - `implement-agent` executes (receives conventions + graph warnings: god nodes, dependencies) → reports
   - `review-agent` verifies (criteria + conventions + security + god node impact) → APPROVED / NEEDS_REVISION / FAILED
   - If NEEDS_REVISION: re-delegates to `implement-agent`
   - Conductor updates TodoWrite ✓
   - Conductor presents summary + commit msg → ⏸️ **PAUSE**
10. Conductor writes `plans/{task}-complete.md`

---

## Always-visible TODO

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

- **Skill:** `skills/subagent-pool/SKILL.md`
- **Prompt templates:** `skills/subagent-pool/assets/prompts.md`
- **Definitions + troubleshooting:** `skills/subagent-pool/assets/agent-definitions.md`
- **Full interview protocol:** `skills/subagent-pool/assets/interview-protocol.md`
- **Agents:** `agents/*.agent.md`

---
name: arquitect-dev-ia
description: >
  AI context documentation for projects: AGENTS.md, CLAUDE.md, copilot-instructions.md,
  skills and Mermaid diagrams. Does NOT create executable agents (.agent.md) — use AgentArchitect for that.
  Trigger: When context documentation needs to be created or refactored so AI agents
  understand the project, its conventions and architecture.
license: MIT
metadata:
  author: eliflowi
  version: "2.0"
  scope: [root]
  auto_invoke: "Create AGENTS.md, CLAUDE.md, copilot-instructions.md, document architecture, structure project for AI"
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, WebFetch, WebSearch, Task
---

# AI Context Documentation Architect

> Skill for creating and maintaining **context documentation** oriented towards AI agents:
> `AGENTS.md`, `CLAUDE.md`, `copilot-instructions.md`, skills and Mermaid diagrams.
>
> ⚠️ **Scope limit**: This skill does NOT create executable agents (`.agent.md`).
> To design and generate Claude Code agent teams → use **AgentArchitect**.

---

## When to Use

| ✅ This skill | ❌ Use AgentArchitect instead |
|---|---|
| Create/update `AGENTS.md` (root or component) | Create `.agent.md` agents in `.claude/agents/` |
| Create/update `CLAUDE.md` | Design Conductor + specialists teams |
| Create/update `copilot-instructions.md` | Define agent tools and models |
| Create new skills (SKILL.md) | Establish orchestration hierarchy |
| Document architecture with Mermaid diagrams | |
| Structure mono-repo for AI work | |
| Define project conventions and culture | |
| Reduce unnecessary context to avoid hallucinations | |

---

## Core Philosophy

```mermaid
flowchart TD
    USER["👤 User"] -->|request| AGENT["🤖 Orchestrator\nAgent"]
    AGENT -->|"1. consults"| AGENTS_ROOT["📄 AGENTS.md Root"]
    AGENTS_ROOT -->|"2. directs to"| AGENTS_COMP["📄 AGENTS.md\nComponent"]
    AGENTS_COMP -->|"3. invokes"| SKILL["⚡ Specific\nSkill"]
    SKILL -->|"4. precise context"| AGENT
    AGENT -->|"5. works"| CODEBASE["💻 Codebase"]
    CODEBASE -->|"6. result"| USER

    style AGENTS_ROOT fill:#4caf50,color:#fff
    style SKILL fill:#2196f3,color:#fff
    style AGENT fill:#ff9800,color:#fff
```

**Key principle**: Less context = less hallucination. The agent should only receive
what it needs, when it needs it.

---

## AI Documentation Architecture

### File Hierarchy

```mermaid
flowchart TB
    subgraph ROOT["📁 Project Root"]
        AGENTS_ROOT["AGENTS.md\n(general index)"]
        CLAUDE_MD["CLAUDE.md\n(context for Claude Code)"]
        COPILOT["copilot-instructions.md\n(for GitHub Copilot)"]
    end

    subgraph COMPS["📁 Components / Sub-projects"]
        AGENTS_A["componentA/AGENTS.md"]
        AGENTS_B["componentB/AGENTS.md"]
        COPILOT_A["componentA/.github/copilot-instructions.md"]
    end

    subgraph SKILLS["📁 .claude/skills/"]
        SK1["skill-a/SKILL.md"]
        SK2["skill-b/SKILL.md"]
        SK3["skill-c/SKILL.md\n+ assets/\n+ references/"]
    end

    AGENTS_ROOT -->|"references"| COMPS
    AGENTS_ROOT -->|"lists available"| SKILLS
    AGENTS_A -->|"invokes"| SK1
    AGENTS_A -->|"invokes"| SK2
    AGENTS_B -->|"invokes"| SK3

    style ROOT fill:#e8f5e9
    style SKILLS fill:#e3f2fd
    style COMPS fill:#fff3e0
```

### Size Rule

| File | Recommended Lines | Maximum |
|------|-------------------|---------|
| `AGENTS.md` root | ~150 | 250 |
| `AGENTS.md` component | ~150 | 300 |
| `copilot-instructions.md` | ~100 | 250 |
| `SKILL.md` | ~100 | 300 |

> **If it exceeds the maximum → split into component files or extract to skills.**

---

## Pattern: AGENTS.md Root

The AGENTS.md root is the **entry point** for any agent. It must contain:

```mermaid
flowchart LR
    subgraph AGENTS_STRUCTURE["AGENTS.md Root Structure"]
        direction TB
        A["1. Project overview\n(mandatory Mermaid diagram)"]
        B["2. Component map\n(table with location and stack)"]
        C["3. Available skills\n(table with name, description, link)"]
        D["4. Auto-invoke\n(table action → skill)"]
        E["5. Global conventions\n(language, commits, Docker)"]
    end

    A --> B --> C --> D --> E
```

### Minimal Template

```markdown
# Project — AGENTS.md

## Overview
<!-- Mermaid architecture diagram -->

## Components
| Component | Location | Stack | AGENTS.md |
|---|---|---|---|

## Available Skills
| Skill | Description | URL |
|---|---|---|

## Auto-invoke Skills
| Action | Skill |
|---|---|

## Conventions
- Language: English
- Commits: conventional-commits
- Everything in Docker
```

---

## Pattern: Skills

### Folder Structure

```mermaid
flowchart TB
    subgraph SKILL_DIR["skills/{skill-name}/"]
        SKILL_MD["SKILL.md\n(required)"]
        ASSETS["assets/\n(optional)"]
        REFS["references/\n(optional)"]

        ASSETS --> TMPL["template.py\nschema.json\nexamples"]
        REFS --> DOCS["docs.md\nlinks to local docs"]
    end

    style SKILL_MD fill:#4caf50,color:#fff
    style ASSETS fill:#fff3e0
    style REFS fill:#e3f2fd
```

### Required Frontmatter

```yaml
---
name: skill-name            # lowercase, hyphens
description: >
  What this skill does.
  Trigger: When to invoke it.
license: MIT
metadata:
  author: eliflowi
  version: "1.0"
  scope: [root|ui|api|infra]  # where it applies
  auto_invoke: "Action that triggers this skill"
allowed-tools: Read, Edit, Write, Glob, Grep, Bash
---
```

### Decision: assets/ vs references/

```mermaid
flowchart TD
    NEED{"What do you\nneed to add?"}
    NEED -->|"Code templates"| ASSETS["assets/"]
    NEED -->|"JSON schemas"| ASSETS
    NEED -->|"Example configs"| ASSETS
    NEED -->|"Links to local docs"| REFS["references/"]
    NEED -->|"Existing guides"| REFS

    ASSETS --> RULE_A["Files the agent\ncopies/adapts"]
    REFS --> RULE_R["Pointers to files\nalready in the repo"]

    style ASSETS fill:#ff9800,color:#fff
    style REFS fill:#2196f3,color:#fff
```

---

## Pattern: Mermaid Diagrams

**Critical rule**: Always prefer Mermaid diagrams over narrative text for:

```mermaid
flowchart LR
    subgraph USE_MERMAID["✅ Use Mermaid For"]
        A["Service architecture"]
        B["Network / Docker flows"]
        C["Decision trees"]
        D["Operation sequences"]
        E["Key folder hierarchy"]
        F["Dependencies between components"]
    end

    subgraph NO_MERMAID["❌ Don't Use Mermaid For"]
        G["Simple lists"]
        H["Literal configs"]
        I["Bash commands"]
    end
```

### Diagram Types by Situation

| Situation | Mermaid Type | Example |
|-----------|-------------|---------|
| Service architecture | `flowchart TB` | Containers, ports, networks |
| Request flow | `sequenceDiagram` | HTTP request → response |
| Decisions | `flowchart TD` with `{}` nodes | Troubleshooting tree |
| Network topology | `flowchart LR` with subgraphs | Docker networks |
| Deploy timeline | `sequenceDiagram` | Deployment steps |
| Data relationships | `erDiagram` | DB models/tables |
| States | `stateDiagram-v2` | Resource lifecycle |

---

## Relationship with AgentArchitect and subagent-pool

This skill produces **context documentation** that executable agents *read*.
The complete cycle is:

```mermaid
flowchart LR
    A["arquitect-dev-ia\n📄 Creates documentation\nAGENTS.md, CLAUDE.md\ndiagrams, skills"]
    B["AgentArchitect\n🏗️ Designs and generates\nexecutable .agent.md"]
    C["subagent-pool\n⚙️ Orchestrates\nwork execution"]

    A -->|"context that agents read"| B
    B -->|"agents ready to use"| C

    style A fill:#4caf50,color:#fff
    style B fill:#9c27b0,color:#fff
    style C fill:#ff9800,color:#fff
```

- **This skill** → first, so the project is readable by any AI agent
- **AgentArchitect** → when you need to create a team of executable agents
- **subagent-pool** → when the team already exists and there is work to orchestrate

---

## Complete Flow: Create AI Documentation for a Project

```mermaid
flowchart TD
    A["1. Analyze project\nstructure"] --> B["2. Identify components\nand dependencies"]
    B --> C["3. Create root AGENTS.md\nwith architecture diagram"]
    C --> D{"Does project have\nmultiple components?"}
    D -->|Yes| E["4a. Create AGENTS.md\nper component"]
    D -->|No| F["4b. Document everything\nin root AGENTS.md"]
    E --> G["5. Identify repeatable\npatterns"]
    F --> G
    G --> H{"Reusable patterns\ndetected?"}
    H -->|Yes| I["6a. Create Skills\nfor each pattern"]
    H -->|No| J["6b. Document in\nAGENTS.md directly"]
    I --> K["7. Register skills in\nAGENTS.md (auto-invoke)"]
    J --> K
    K --> L["8. Create copilot-instructions.md\n(if using Copilot)"]
    L --> M["9. Validate: does each file\nhave < 300 lines?"]
    M -->|No| N["Refactor: extract to skills"]
    M -->|Yes| O["✅ Documentation ready"]
    N --> M

    style A fill:#e3f2fd
    style O fill:#4caf50,color:#fff
```

---

## Documentation Completeness Checklist

- [ ] `AGENTS.md` root with Mermaid architecture diagram
- [ ] `AGENTS.md` per component (if applicable)
- [ ] Skills for repeatable patterns (commits, PRs, testing, etc.)
- [ ] Auto-invoke table in each `AGENTS.md`
- [ ] `copilot-instructions.md` for Copilot
- [ ] No documentation file exceeds 300 lines
- [ ] All architecture documented with Mermaid diagrams
- [ ] Complete frontmatter in each skill (`name`, `description`, `allowed-tools`, `metadata.scope`)
- [ ] `assets/` with templates and examples when the skill is complex
- [ ] `references/` pointing to local docs (not web URLs)

---

## Useful Commands

```bash
# Count lines in an agent file
wc -l AGENTS.md

# Find all project skills
find . -name "SKILL.md" -type f

# Find all AGENTS.md
find . -name "AGENTS.md" -type f

# Find copilot-instructions
find . -path "*/.github/copilot-instructions.md" -type f

# View skills structure
tree .claude/skills/ 2>/dev/null || find .claude/skills -type f | head -20
```

---

## Anti-patterns

- ❌ `AGENTS.md` of 800+ lines → agent hallucinates
- ❌ Everything in narrative text → ambiguity
- ❌ Skills without frontmatter → won't auto-invoke
- ❌ Duplicate existing docs → gets out of sync
- ❌ Web URLs in references/ → use local paths
- ❌ One giant AGENTS.md → split by component

---

## Resources

- **Templates**: See [assets/](assets/) for AGENTS.md and SKILL.md templates
- **Reference**: See [references/](references/) for the server architecture guide

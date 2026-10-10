# {Project Name} — AGENTS.md

> {One-line brief description of the project}

## Overview

<!-- Mandatory architecture diagram — Mermaid flowchart TB -->
```mermaid
flowchart TB
    subgraph INTERNET["Internet"]
        CLIENT["Client"]
    end

    subgraph SERVER["Server / Infrastructure"]
        subgraph COMP_A["Component A"]
            SVC_A1["Service A1\n:port"]
            SVC_A2["Service A2"]
        end
        subgraph COMP_B["Component B"]
            SVC_B1["Service B1\n:port"]
        end
    end

    CLIENT -->|HTTPS| SVC_A1
    SVC_A1 --> SVC_A2
    SVC_A1 --> SVC_B1
```

## Components

| Component | Location | Stack | AGENTS.md |
|---|---|---|---|
| `component-a/` | Description | Tech stack | [AGENTS.md](component-a/AGENTS.md) |
| `component-b/` | Description | Tech stack | [AGENTS.md](component-b/AGENTS.md) |

## Available Skills

### Generic
| Skill | Description | URL |
|---|---|---|
| `skill-name` | What it does | [SKILL.md](skills/skill-name/SKILL.md) |

### Project-Specific
| Skill | Description | URL |
|---|---|---|
| `project-feature` | What it does | [SKILL.md](skills/project-feature/SKILL.md) |

## Auto-invoke Skills

When performing these actions, ALWAYS invoke the corresponding skill FIRST:

| Action | Skill |
|---|---|
| Create/modify agent architecture | `arquitect-dev-ia` |
| Create new skill | `skill-creator` |
| Make a commit | `project-commit` |

## Conventions

- **Language**: English (code, docs, commits)
- **Diagrams**: Mermaid mandatory for architecture and flows
- **Docker**: Everything in containers
- **`.env`**: Never in git

## Operations Workflow

```mermaid
flowchart TD
    A["Read component AGENTS.md"] --> B{"Has dependencies\non other components?"}
    B -->|Yes| C["Check shared\nnetworks/volumes"]
    B -->|No| D["Work isolated"]
    C --> E["Implement change"]
    D --> E
    E --> F["docker-compose up -d --build"]
    F --> G["Verify health checks"]
```

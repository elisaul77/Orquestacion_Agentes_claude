# {Project} — GitHub Copilot Instructions

> {One-line description of the project}

## Architecture

<!-- Mermaid diagram of the project architecture -->
```mermaid
flowchart TB
    subgraph PROJECT["Project"]
        SVC1["Service 1"]
        SVC2["Service 2"]
    end
    SVC1 --> SVC2
```

## Component Map

| Directory | What it is | Stack |
|---|---|---|
| `component/` | Description | Tech stack |

## Rules for Agents

1. **Read the AGENTS.md or internal copilot-instructions.md before working on a component**
2. **Language**: English in everything (docs, code, commits)
3. **Docker always**: everything runs in containers
4. **Mermaid diagrams**: mandatory for architecture and flows

## Conventions

- `.env` never in git
- Health checks on all services
- Conventional commits: `<type>[scope]: <description>`

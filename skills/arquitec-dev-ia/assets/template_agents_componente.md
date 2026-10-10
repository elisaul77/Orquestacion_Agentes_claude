# {Component} — AGENTS.md

> {One-line description of the component}

## Internal Architecture

```mermaid
flowchart TB
    subgraph COMPONENT["Component: {name}"]
        direction TB
        SVC1["Service 1\n:port"]
        SVC2["Service 2"]
        DB["Database"]
    end

    SVC1 --> SVC2
    SVC2 --> DB
```

## Folder Structure

```
component/
├── src/              # Source code
│   ├── module_a/     # Description
│   └── module_b/     # Description
├── tests/            # Tests
├── config/           # Configuration
├── docker-compose.yml
└── Dockerfile
```

## Tech Stack

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.11 | Main language |
| Flask/Django | x.x | Web framework |
| PostgreSQL | 16 | Database |

## Critical Patterns

<!-- Document here the patterns the agent MUST follow -->

### Pattern: {Name}

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API
    participant D as DB

    C->>A: Request
    A->>D: Query
    D-->>A: Result
    A-->>C: Response
```

## Available Skills

| Skill | Description | URL |
|---|---|---|
| `skill-name` | Description | [SKILL.md](../../skills/skill-name/SKILL.md) |

## Auto-invoke

| Action | Skill |
|---|---|
| Create endpoints | `project-api` |
| Write tests | `project-test` |

## Commands

```bash
# Local development
docker-compose up -d --build

# Logs
docker-compose logs -f {service}

# Tests
docker-compose exec {service} pytest
```

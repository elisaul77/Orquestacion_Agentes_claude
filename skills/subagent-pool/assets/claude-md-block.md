## subagent-pool — when to orchestrate

| User says / task looks like | Action |
|---|---|
| "orchestrate", "delegate", "conductor", "use subagents", or a complex task (≥3 files, new module, cross-component refactor) | `Skill("subagent-pool")` |
| "design an agent team", "create agents for", "new agent team" | `Skill("subagent-pool")` → AgentArchitect |
| "create AGENTS.md", "document the project for AI", "prepare project for orchestration" | `Skill("arquitec-dev-ia")` |
| "map this project", "knowledge graph", "what depends on X" | `Skill("graphify")` |
| Single file, trivial fix, quick question | Direct — no orchestration |

The user can force or skip the plan council in plain words ("use the council", "a single planner is enough").

```skill
---
name: {skill-name}
description: >
  {What this skill does — max 250 chars, most important info first}
when_to_use: >
  Use when {situation}. Trigger phrases: "{phrase1}", "{phrase2}".
license: MIT
metadata:
  author: eliflowi
  version: "1.0"
  scope: [{root|ui|api|infra}]
# Optional advanced fields:
# context: fork           # isolated subagent (no parent context)
# effort: high            # low | medium | high | max
# model: inherit          # or a specific model id
# argument-hint: "<arg>"  # shown in UI when user types /skill <arg>
# arguments: [foo, bar]   # named args → $foo, $bar in body
allowed-tools: Read, Edit, Write, Glob, Grep, Bash
---

# {Emoji} Skill: {Descriptive Name}

> {Reference documentation or link}

## When to Use

- {Situation 1 where to invoke this skill}
- {Situation 2}
- {Situation 3}

## Critical Patterns

<!-- The most important things the agent MUST know -->

```mermaid
flowchart TD
    A["Input"] --> B{"Decision"}
    B -->|Option 1| C["Action 1"]
    B -->|Option 2| D["Action 2"]
```

### Rule 1: {Rule Name}

{Brief explanation}

```python
# Code example
```

### Rule 2: {Rule Name}

{Brief explanation}

## Expected Structure

```
folder/
├── file1.py
├── file2.py
└── config/
```

## Commands

```bash
# Useful command 1
command --flag

# Useful command 2
another-command
```

## Resources

- **Templates**: See [assets/](assets/) for {description}
- **Reference**: See [references/](references/) for local docs
```

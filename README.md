# 🤖 Orquestacion Agentes Claude

![Banner](docs/banner.png)

🌐 **English** · [Español](README.es.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-v9.9.1-blueviolet.svg)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-182%20passing-3fb950.svg)](#-tests)
[![Claude Code](https://img.shields.io/badge/brain-Claude%20Code-8a63f0.svg)](https://claude.com/claude-code)
[![Codex](https://img.shields.io/badge/Codex-optional-412991.svg)](#optional-add-ons)

[![GitHub Sponsors](https://img.shields.io/badge/GitHub-Sponsors-pink?style=for-the-badge&logo=githubsponsors)](https://github.com/sponsors/elisaul77)
[![PayPal](https://img.shields.io/badge/PayPal-Donate-blue?style=for-the-badge&logo=paypal)](https://paypal.me/eflorezp)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Support-yellow?style=for-the-badge&logo=buymeacoffee)](https://buymeacoffee.com/elisaul77)

**A Conductor for Claude Code: it plans, delegates to specialist subagents and has every phase reviewed by another agent.**
For complex work (3 or more files, a new module, a refactor). You approve the plan; nothing irreversible happens without you.

```
you ──> Conductor (scopes and delegates, never touches code)
          │
          ├─ plan ──────► planning-agent                      (simple plans)
          │               or plan council: spec · architect   (big or risky plans)
          │                  · lateral · risk, debating
          │                         │
          │                  plans/*.md ──► your approval
          │
          ├─ per phase ─► implement-agent ──► review-agent ──► APPROVED | NEEDS_REVISION
          │                                       ▲
          │                     codex-agent ──────┘  second-vendor review (optional)
          │
          ├─ new domain ► AgentArchitect ──► new specialist team
          └─ outside skill ► isolated review ──► private library (by path)
```

---

## 🚀 Getting started

### Install

```bash
git clone https://github.com/elisaul77/Orquestacion_Agentes_claude.git
cd Orquestacion_Agentes_claude

cp -r skills/subagent-pool skills/arquitec-dev-ia skills/graphify ~/.claude/skills/
cp agents/*.agent.md ~/.claude/agents/
```

Restart Claude Code (agent files load when a session starts), then check the install:

```bash
python3 ~/.claude/skills/subagent-pool/scripts/doctor.py
```

`doctor` is read-only. It checks the skill version, the agents, the optional add-ons, and SSH remotes if you pass `--remote host`. Every failed check comes with the command that fixes it.

<details>
<summary>Without git: core install with curl</summary>

```bash
BASE=https://raw.githubusercontent.com/elisaul77/Orquestacion_Agentes_claude/master
for skill in subagent-pool arquitec-dev-ia graphify; do
  mkdir -p ~/.claude/skills/${skill}
  curl -sSL "$BASE/skills/${skill}/SKILL.md" -o ~/.claude/skills/${skill}/SKILL.md
done
mkdir -p ~/.claude/skills/subagent-pool/assets
for f in prompts research interview-protocol agent-definitions council; do
  curl -sSL "$BASE/skills/subagent-pool/assets/${f}.md" -o ~/.claude/skills/subagent-pool/assets/${f}.md
done
mkdir -p ~/.claude/agents
for agent in planning-agent implement-agent review-agent AgentArchitect \
             council-spec council-architect council-lateral council-risk; do
  curl -sSL "$BASE/agents/${agent}.agent.md" -o ~/.claude/agents/${agent}.agent.md
done
```

This installs no scripts (doctor, cost ledger, skill review), and `arquitec-dev-ia` comes without its `assets/`. Use `git clone` for the full install.

</details>

### Requirements

- [Claude Code](https://claude.com/claude-code) and a `~/.claude/` folder.
- Python 3.10+ for the scripts. They use the standard library only.
- Recommended: `.claude/project-context.md` in your project. If it is missing, the Conductor suggests running `arquitec-dev-ia` first.

### Optional add-ons

Each one is independent; without any of them the skill runs on Claude alone.

| Add-on | What it adds | How |
|---|---|---|
| **Agent teams** | Council members debate each other directly instead of through files | Add `"env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}` to `~/.claude/settings.json` (experimental Claude Code flag) |
| **Codex** | Second-vendor review, implementation and coordination; the council's lateral thinker asks Codex too | `npm i -g @openai/codex && codex login`, then `cp agents/optional/codex-agent.agent.md ~/.claude/agents/` |
| **[graphify](https://github.com/safishamsi/graphify)** | `planning-agent` maps central nodes and dependencies before planning (repos over ~20 files) | `uv tool install graphifyy && graphify install` (the PyPI package is `graphifyy`) |
| **Cost ledger** | Tokens per session and per model, including subagents | `Stop` hook from [hooks.md](skills/subagent-pool/assets/hooks.md); report with `cost_tracker.py report` |

---

## 🎯 Using it

Ask in plain language: `use the conductor to…`, `delegate to subagents`, `complex task: …`, or simply describe a feature or refactor. To design a new team: `design an agent team for…`.

Before planning, the Conductor states its reading of the task in one line:

```
Tier L · feature · council
```

- **Tier** is the effort (S, M or L).
- **Operation** is feature, fix, tweak or refactor. Each one has a mandatory first move; a fix, for example, starts with a failing test.
- **Plan level** is who writes the plan: single, duo or council.

If you disagree, say so and that wins: `a single planner is enough`, `use the council for the plan`, `do it directly`. Nothing else needs configuring.

What you are asked to decide:

1. **Questions that change the plan.** At most 3, each with a proposed default.
2. **The plan.** At the council level it comes with a decision record (`decisions.md`) and any open disagreements.
3. **Approve-tier actions** (delete, migrate, secrets, push, publish, deploy), when they come up.
4. **The commit**, at the end.

An interrupted task resumes from `plans/{task}-state.md`, and the Conductor offers to continue it.

---

## 🤔 What it is and what it isn't

**It is not a framework.** It is Markdown files (skills and agents) that Claude Code loads, plus a few standard-library Python scripts. There is no server and no runtime.

**It is not for one file.** Orchestration costs several times the tokens of a single agent, so small tasks are done directly.

**It does not decide for you.** You approve the plan and every irreversible action. After two failed review loops the Conductor stops and asks instead of insisting.

**Codex is optional and never replaces Claude Code.** The whole flow runs inside Claude Code; Codex is a second opinion.

---

## 👥 The team

| Agent | Role | Writes project code |
|---|---|---|
| **Conductor** (the `subagent-pool` skill) | Scopes, picks the effort, delegates, talks to you | ❌ never |
| `planning-agent` | Scans the repo (graphify if present) and writes a phased plan | ❌ |
| `council-spec` | Council: what "done" means, as testable criteria | ❌ |
| `council-architect` | Council: phases over the real files; writes the final plan | ❌ |
| `council-lateral` | Council: the non-obvious option (don't build it, half the parts, a false assumption) | ❌ |
| `council-risk` | Council: what breaks, and how each claim will be proven | ❌ |
| `implement-agent` | Implements one phase, test first | ✅ the only one |
| `review-agent` | APPROVED / NEEDS_REVISION / FAILED, with evidence per criterion | ❌ |
| `AgentArchitect` | Designs and generates specialist teams for new domains | ❌ (writes agent files) |
| `codex-agent` *(optional)* | Bridge to Codex: plan, implement, review, debug, browser, coordinate | sandboxed |

Each agent's model is set in its own file (`model:`), and you decide it. The Conductor never overrides it.

---

## 🔄 How a task flows

**1. Effort by size**

| Tier | Signal | Flow |
|---|---|---|
| S | 1–2 files, clear fix | Done directly, no orchestration |
| M | 3–6 files, one area | Plan, then implement and review per phase |
| L | New module, cross-component refactor, design choice | The same, with the plan written by the council |

**2. Who writes the plan**

| Plan level | When | Who |
|---|---|---|
| single | Clear approach, precise request | `planning-agent` |
| duo | Open design choice or vague request | architect + lateral, blind drafts, architect synthesizes |
| council | Tier L, or anything touching security, a public API, data or money | the four members, with a debate round |

```
council   R1  blind drafts ── spec · architect · lateral · risk (nobody reads anyone)
          R2a objections   ── sent directly between members, logged in debate.log
          R2b replies      ── each answers what was objected to them
          R3  synthesis    ── architect: plans/{task}-draft.md + decisions.md
```

The Conductor only signals the rounds; the debate content never passes through it. Without the agent-teams flag the same rounds run through files. Full protocol: [council.md](skills/subagent-pool/assets/council.md).

**3. Per phase:** `implement-agent` → `review-agent`, plus a Codex review in parallel if Codex is on. Phases that touch security also get a security review. NEEDS_REVISION gets two retries, then you decide. A checkpoint goes to `plans/{task}-state.md` after every approved phase.

**4. Close:** a final report covering what changed, what was verified, what wasn't, and the risks. The commit waits for your OK.

---

## 🧠 The ten non-obvious things

### 1. The plan is a team decision, and the team must not agree too early

Agents from the same model that see each other's ideas converge on one answer. So council drafts are blind, there is a single debate round with hard limits, and every lateral proposal ends up in `decisions.md`, kept or not, for you to overrule.

### 2. Effort scales with the task

A multi-agent system spends about 15× the tokens of a chat. Orchestrating something small is a mistake, not rigor.

### 3. Fork or fresh subagent: the context size decides

A fork inherits the Conductor's context. Below **~75k tokens** it costs about 50 % less than a fresh subagent; above that it costs about 2× more. Accuracy didn't change in our tests.

### 4. The Conductor can run on Sonnet

On a task with 19 hidden criteria, Sonnet matched Opus at **−39 % cost**. Opus pays off for tier L design choices.

### 5. No `/advisor` with this skill

The advisor re-reads the whole conversation uncached on every call, and every subagent inherits it. Sonnet with an Opus advisor cost **+150 %**, with the same accuracy and erratic delegation.

### 6. "Avoid the predictable" raises originality

Across 290 generations, explicitly asking to avoid the first idea raised originality by **+2.00 (Sonnet) and +2.80 (Opus)**. Praise or insults didn't help. Every creative prompt in the skill carries that line.

### 7. A claim needs evidence, and its level is written down

Every acceptance criterion is marked `[OBSERVED]`, `[DERIVED]`, `[INFERRED]` or `[UNKNOWN]`. Behavior counts as met only when someone ran it and saw the result. Agents also list what they did **not** verify.

### 8. Codex never reviews Codex

An LLM judge tends to prefer its own text ([arXiv 2410.21819](https://arxiv.org/abs/2410.21819)), so review always crosses vendors. Model slugs aren't hardcoded either: the latest version per family is read from the local Codex cache.

### 9. Codex can nest agents; Claude subagents can't

Claude subagents have no tool to spawn agents. A Codex session can, so `codex-agent mode=coordinate` fans independent phases out inside Codex, using roles synced from our agent files, and Claude still reviews every phase. New Claude agents load only after a restart; new Codex roles are usable at once.

### 10. The main model never reads an outside skill

Third-party skills are reviewed in two isolated containers: an offline pre-scan, then a reviewer whose only exit is an allow-list proxy. You approve each run, with its cost estimate. The Conductor receives only the verdict and the report path.

---

## 📊 Measured, not estimated

Measurements on test tasks, from [`research.md`](skills/subagent-pool/assets/research.md) and the [CHANGELOG](CHANGELOG.md). They are not guarantees for your project.

| Measure | Result | Detail |
|---|---|---|
| Same prompt in English vs Spanish | **−30 %** input tokens | [research](skills/subagent-pool/assets/research.md#language-and-tokens-own-measurement-2026-10-10) |
| Fork vs fresh subagent | Fork ~50 % cheaper under ~75k context, ~2× above; same accuracy | [research](skills/subagent-pool/assets/research.md#fork-vs-fresh-subagent-own-measurement-2026-10-10) |
| Conductor Sonnet vs Opus | 19/19 on both; **−39 %** cost (n = 5) | [research](skills/subagent-pool/assets/research.md#conductor-model-and-the-advisor-tool-own-measurement-2026-10-11) |
| `/advisor` on top of Sonnet | **+150 %** cost, same accuracy | [research](skills/subagent-pool/assets/research.md#conductor-model-and-the-advisor-tool-own-measurement-2026-10-11) |
| "Avoid the predictable" | **+2.00** Sonnet (p = .005), **+2.80** Opus (p < .001); 290 samples | [research](skills/subagent-pool/assets/research.md#own-experiment-2026-10-0910-spelling-and-tone-vs-creativity) |
| Multi-agent vs chat | ~15× tokens (Anthropic reference) | [research §2](skills/subagent-pool/assets/research.md#2-effort-scaling-and-multi-agent-cost) |

The council's cost (about +4–6× a single plan) is still an estimate; see [What's missing](#%EF%B8%8F-whats-missing).

---

## 🧪 Tests

```bash
python3 -B -m unittest discover -s skills/subagent-pool/scripts
```

**182 tests**, standard library only. Two are skipped on Python < 3.11 because they need `tomllib`.

| File | Tests | Covers |
|---|---|---|
| `test_skills_lib.py` | 103 | Reviewed-skills library: schema, veto rules, lookup, re-review on source change |
| `test_codex_models.py` | 15 | Codex model registry: version order, missing, corrupt or stale cache |
| `test_skill_prescan.py` | 13 | Offline pre-scan over a benign and a malicious fixture |
| `test_trim_output.py` | 12 | Test-output trimming never drops a failure line (real unittest/pytest output) |
| `test_cost_tracker.py` | 9 | Cost ledger: dedup of streamed ids, subagents, report |
| `test_doctor.py` | 9 | Install health check: drift, remotes, Codex roles, council, teams flag |
| `test_sync_codex_agents.py` | 9 | Agent → Codex role sync: TOML escaping, YAML blocks, foreign files |
| `test_instincts.py` | 4 | Per-project lessons store |
| `test_mutate.py` | 4 | Mutation check runs in an isolated copy |
| `test_council.py` | 4 | Council agents have `SendMessage`, and the protocol matches the skill |

`skill-review.sh` has no automated tests; its `--dry-run` prints every command without running it.

---

## 🔒 Security

- **Approval tiers.** Edits inside the approved scope and tests are automatic. Anything outside it is reported. Delete, migrate, secrets, push, publish and deploy come back as `BLOCKED` until you approve them.
- **Codex** runs sandboxed (`read-only`, `workspace-write` at most). The council's lateral member only calls Codex `read-only`.
- **Outside skills** are fetched from official sources only (`anthropics/skills`, `openai/skills`, `vercel-labs/agent-skills`) and reviewed in two containers:
  - Pre-scan: `--network none`, the skill mounted read-only.
  - Reviewer: its only exit is a squid allow-list proxy to the model API.
  - Both run with `--read-only`, `--cap-drop ALL`, `no-new-privileges`, a non-root user, and memory and process limits.
  - Any doubt (symlinks, opaque files, a truncated pre-scan) turns APPROVED into DOUBTFUL.

**Accepted residual risk:** the reviewer holds a read-only credential next to untrusted text. Use a dedicated, scoped key. Details in [skills-library.md](skills/subagent-pool/assets/skills-library.md).

---

## 📁 Structure

```
Orquestacion_Agentes_claude/
├── AGENTS.md · CHANGELOG.md · LICENSE · FUNDING.md
├── README.md · README.es.md · docs/banner.png
├── agents/
│   ├── planning-agent.agent.md        # Phased plan (graphify)
│   ├── implement-agent.agent.md       # Code and tests, one phase at a time
│   ├── review-agent.agent.md          # Verdict with evidence levels
│   ├── council-spec.agent.md          # Council: acceptance criteria
│   ├── council-architect.agent.md     # Council: phases + final synthesis
│   ├── council-lateral.agent.md       # Council: the non-obvious option (asks Codex)
│   ├── council-risk.agent.md          # Council: risks and verification
│   ├── AgentArchitect.agent.md        # Designs new specialist teams
│   └── optional/codex-agent.agent.md  # Bridge to OpenAI Codex
└── skills/
    ├── subagent-pool/                 # The Conductor
    │   ├── SKILL.md
    │   ├── assets/
    │   │   ├── prompts.md             # Templates and return contracts
    │   │   ├── council.md             # Plan council protocol
    │   │   ├── agent-definitions.md · interview-protocol.md
    │   │   ├── research.md            # Evidence behind each rule
    │   │   ├── hooks.md               # Optional cost-ledger hook
    │   │   ├── codex-modes.md · codex-verdict.schema.json
    │   │   ├── skills-library.md · skill-review-prompt.md · official-sources.json
    │   │   └── skills-probadas-template/
    │   └── scripts/
    │       ├── doctor.py              # Read-only install health check
    │       ├── trim_output.py         # Shrinks test output, keeps every failure
    │       ├── cost_tracker.py        # Token ledger (Stop hook) and report
    │       ├── instincts.py           # Per-project lessons
    │       ├── mutate.py              # Do the tests catch injected bugs?
    │       ├── sync_codex_agents.py   # Agents → Codex roles
    │       ├── codex-models.py        # Latest Codex model per family
    │       ├── skills_lib.py · skill_prescan.py · skill-review.sh
    │       ├── test_*.py              # 182 tests
    │       └── fixtures/
    ├── arquitec-dev-ia/               # AI context docs; writes project-context.md
    └── graphify/                      # Knowledge-graph skill
```

---

## 📚 Documentation

| Document | Contents |
|---|---|
| [SKILL.md](skills/subagent-pool/SKILL.md) | The Conductor: tiers, plan levels, governance, flow, Codex, skill review |
| [council.md](skills/subagent-pool/assets/council.md) | Plan council: rounds, message limits, file-mode fallback |
| [prompts.md](skills/subagent-pool/assets/prompts.md) | Templates and return contracts for every agent |
| [agent-definitions.md](skills/subagent-pool/assets/agent-definitions.md) | Roles, tools, troubleshooting |
| [interview-protocol.md](skills/subagent-pool/assets/interview-protocol.md) | Designing new teams with AgentArchitect |
| [research.md](skills/subagent-pool/assets/research.md) | Evidence and sources behind each rule |
| [hooks.md](skills/subagent-pool/assets/hooks.md) | Cost-ledger hook |
| [codex-modes.md](skills/subagent-pool/assets/codex-modes.md) | Codex `debug` (Docker) and `browser` (Flatpak Chrome) recipes |
| [skills-library.md](skills/subagent-pool/assets/skills-library.md) | Reviewed-skills library and gated review |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

---

## 🗺️ What's missing

- **The council hasn't been measured on a real project yet.** We still need a run comparing a council plan with a single planner, and its real cost; +4–6× is an estimate.
- **Agent teams are an experimental Claude Code flag** and may change. If they do, the council falls back to file mode.
- **The container-2 reviewer hasn't run end to end** on a real skill.
- **`codex debug` inside Docker:** whether Codex can be reached from the container is unverified.
- **Model release dates:** the table in `skills-library.md` has `TODO` entries, so for now the freshness rule flags a candidate instead of discarding it.

---

## 🤝 Contributing

1. Fork the repo and create a branch (`feat/…`, `docs/…`).
2. Use commits in the form `type(scope): message`.
3. Run the tests before opening a PR.
4. Describe the change in the Pull Request.

Ideas welcome: specialist agents, usage examples, orchestration scenarios with tests. Report bugs in [GitHub Issues](https://github.com/elisaul77/Orquestacion_Agentes_claude/issues).

## 💖 Support the project

If it saves you time, star the repo, share it, and report what you find. Financial support options are in [FUNDING.md](FUNDING.md).

## 📄 License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Elisaul Florez ([@elisaul77](https://github.com/elisaul77)).

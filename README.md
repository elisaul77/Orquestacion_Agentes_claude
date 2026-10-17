# 🤖 Orquestacion Agentes Claude

![Banner](docs/banner.png)

🌐 **English** · [Español](README.es.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-v9.9.0-blueviolet.svg)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-131%20passing-3fb950.svg)](#-tests)
[![Claude Code](https://img.shields.io/badge/brain-Claude%20Code-8a63f0.svg)](https://claude.com/claude-code)
[![Codex](https://img.shields.io/badge/Codex-optional-412991.svg)](#optional-codex)

[![GitHub Sponsors](https://img.shields.io/badge/GitHub-Sponsors-pink?style=for-the-badge&logo=githubsponsors)](https://github.com/sponsors/elisaul77)
[![PayPal](https://img.shields.io/badge/PayPal-Donate-blue?style=for-the-badge&logo=paypal)](https://paypal.me/eflorezp)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Support-yellow?style=for-the-badge&logo=buymeacoffee)](https://buymeacoffee.com/elisaul77)

**The Conductor plans and delegates; subagents execute, and another agent reviews every phase.**
For complex Claude Code work (3 or more files, a new module, a refactor) with a plan you approve, automatic review per phase, and clear rules about what each agent may do without asking.

```
you ──> Conductor (plans, never touches code)
         |
         |--> plan council (tier L): spec · architect · lateral · risk
         |      blind drafts ─> they debate each other ─> plan + decision record
         |--> planning-agent ──> plans/*.md ──> (your approval)
         |
         |--> implement-agent ──> review-agent ──> APPROVED | NEEDS_REVISION
         |                             ^
         |             codex-agent ----+  cross-vendor review (optional)
         |
         |--> AgentArchitect ──> new agent teams
         |
         '--> external skill ──> isolated review ──> private library (by path)
```

---

## 🚀 Getting started

```bash
git clone https://github.com/elisaul77/Orquestacion_Agentes_claude.git
cd Orquestacion_Agentes_claude

cp -r skills/subagent-pool skills/arquitec-dev-ia skills/graphify ~/.claude/skills/
cp agents/*.agent.md ~/.claude/agents/
```

Then, in Claude Code, ask for orchestration with any of these phrases: `use the conductor to…`, `delegate to subagents`, `complex task: …`. To design a new team: `design an agent team for…`.

<details>
<summary>Without git: install with curl (core: Conductor and 4 agents)</summary>

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

For the full install (including the skill-review scripts) use the `git clone` option.

`arquitec-dev-ia` installed this way is only its `SKILL.md` (no `assets/` or `references/`); use `git clone` for the full skill.

</details>

### Requirements

- [Claude Code](https://claude.com/claude-code) and a `~/.claude/` folder.
- [graphify](#-graphify), recommended for repos with more than 20 files: `planning-agent` uses it to map the project before planning.
- Optional: `.claude/project-context.md` in your project. If it is missing, the Conductor suggests `arquitec-dev-ia` before orchestrating.

### Optional: Codex

Only if you also have a ChatGPT/Codex subscription. Without it the skill works with Claude alone, at no extra cost.

```bash
npm i -g @openai/codex && codex login          # once
cp agents/optional/codex-agent.agent.md ~/.claude/agents/
cp skills/subagent-pool/assets/codex-verdict.schema.json ~/.claude/skills/subagent-pool/assets/
```

With the bridge on, the Conductor always crosses vendors: if Claude implements, Claude and Codex review in parallel; if Codex implements, Claude reviews. Models are picked automatically from your local Codex cache (see [The seven non-obvious things](#6-codex-never-reviews-codex)).

---

## 🤔 What it is and what it isn't

**It is not a framework.** It is a set of Markdown files (skills and agents) that Claude Code loads. There is no server and no runtime; the only executable parts are the skill-review scripts in `skills/subagent-pool/scripts/`.

**It is not for fixing one file.** A small task is done directly: orchestration costs several times the tokens of a single agent. The Conductor sets the effort by size (tier S, M or L).

**It does not decide for you.** You approve the plan. Irreversible actions (deleting, migrating, secrets, push, publishing, deploying) always go through you. After two review loops without approval, the Conductor escalates instead of continuing.

**Codex is optional.** It strengthens the review but is never a dependency. And it does not replace Claude Code: the whole flow runs inside Claude Code.

---

## 🧠 The seven non-obvious things

### 1. Effort scales with the task

Tier S (1–2 files, a clear fix): not orchestrated. Tier M (3–6 files in one area): planning, then implement and review per phase, with a single pause for the plan. Tier L (new module or a design choice): also a divergent round before planning. A multi-agent system spends about 15× the tokens of a chat, so orchestrating something small is a mistake, not rigor.

### 2. Fork or fresh subagent: the context size decides

A fork inherits the Conductor's context. Below **~75k tokens** it costs about 50 % less than a fresh subagent; above that it costs about 2× more. In our tests accuracy did not change, so the Conductor chooses based on the context it has at that moment.

### 3. The Conductor can run on Sonnet

On a task with 19 hidden criteria, Sonnet matched Opus with **−39 % cost**. If you are on Opus for a tier S or M task, `/model sonnet` is enough. The decision is yours.

### 4. No `/advisor` with this skill

The advisor re-reads the whole conversation uncached on every call, and every subagent inherits that context. Sonnet with an Opus advisor cost **+150 %** more than Sonnet alone, with the same accuracy and erratic delegation (between 0 and 5 subagents).

### 5. "Avoid the predictable" raises originality

Across 290 generations, explicitly telling the model to avoid the first idea and the typical answer raised originality by **+2.00 with Sonnet and +2.80 with Opus**. Praise, insults or typos did not have the same effect. That is why every creative round in the skill carries that instruction verbatim.

### 6. Codex never reviews Codex

An LLM judge tends to prefer its own text (self-preference bias, [arXiv 2410.21819](https://arxiv.org/abs/2410.21819)), so the reviewer is always from another vendor. And no model slugs are hardcoded: `codex-models.py` takes the latest version of each family (astra, sol, terra, luna) from `~/.codex/models_cache.json`, comparing versions numerically.

### 7. The main model never reads an external skill

Every third-party skill is reviewed in two isolated containers: an offline pre-scan and a reviewer whose only exit is an allow-list proxy. The pre-scan can only downgrade an APPROVED to DOUBTFUL, never the reverse. You approve each run, with its estimated cost. The Conductor receives only the verdict JSON and the report path, never the skill's code.

---

## 📊 Measured, not estimated

Figures taken from [`research.md`](skills/subagent-pool/assets/research.md) and [CHANGELOG.md](CHANGELOG.md). They are measurements on test tasks, not guarantees for your project.

| Measure | Result | Detail |
|---|---|---|
| Same prompt in English vs Spanish | **−30 %** input tokens | [research](skills/subagent-pool/assets/research.md#language-and-tokens-own-measurement-2026-10-10) |
| Fork vs fresh subagent | Fork ~50 % cheaper under ~75k context, ~2× above; same accuracy | [research](skills/subagent-pool/assets/research.md#fork-vs-fresh-subagent-own-measurement-2026-10-10) |
| Conductor Sonnet vs Opus | 19/19 on both; **−39 %** cost (n = 5) | [research](skills/subagent-pool/assets/research.md#conductor-model-and-the-advisor-tool-own-measurement-2026-10-11) |
| `/advisor` on top of Sonnet | **+150 %** cost, same accuracy | [research](skills/subagent-pool/assets/research.md#conductor-model-and-the-advisor-tool-own-measurement-2026-10-11) |
| "Avoid the predictable" | **+2.00** Sonnet (p = .005), **+2.80** Opus (p < .001); 290 samples | [research](skills/subagent-pool/assets/research.md#own-experiment-2026-10-0910-spelling-and-tone-vs-creativity) |
| Multi-agent vs chat | ~15× tokens (Anthropic reference) | [research §2](skills/subagent-pool/assets/research.md#2-effort-scaling-and-multi-agent-cost) |

---

## 🧪 Tests

```bash
python3 -B -m unittest discover -s skills/subagent-pool/scripts
```

**131 tests**, Python standard library only:

- `test_skills_lib.py` (103): validator for the reviewed-skills library. Schema of `index.json` and `vetadas.json`, veto rules, lookup, and re-review when the source changes.
- `test_skill_prescan.py` (13): static pre-scan over the `skill-benign` and `skill-malicious` fixtures.
- `test_codex_models.py` (15): Codex model registry. Version comparison, and missing, corrupt or stale cache.

`skill-review.sh` has no automated tests: its `--dry-run` mode prints every command without running any.

---

## 🔒 Security

External skill review is the only part that handles third-party code:

- **Official sources only:** `anthropics/skills`, `openai/skills` and `vercel-labs/agent-skills`. Aggregators only point to the official repo, they never provide content.
- **Container 1 (pre-scan):** no network (`--network none`), skill mounted read-only.
- **Container 2 (reviewer):** internal network whose only exit is a squid allow-list proxy, reaching only the model API.
- **Both:** `--read-only`, `--cap-drop ALL`, `no-new-privileges`, non-root user, memory and process limits.
- **Approval on every run:** `--approved-by-user`, with no remembered consent. Any doubt (symlinks, opaque files, truncated pre-scan) turns an APPROVED into DOUBTFUL.
- **Codex** runs at most with `workspace-write`; Approve-tier actions come back as `BLOCKED`.

**Accepted residual risk:** the reviewer holds a read-only credential next to untrusted text. Use a dedicated, scoped key for reviews, never your main account credential. Details in [skills-library.md](skills/subagent-pool/assets/skills-library.md).

---

## 📁 Structure

```
Orquestacion_Agentes_claude/
├── .github/FUNDING.yml                # GitHub Sponsors button
├── AGENTS.md                          # Overview, rules and system diagram
├── CHANGELOG.md                       # Version history
├── FUNDING.md                         # Ways to support the project
├── LICENSE
├── README.md · README.es.md
├── agents/
│   ├── planning-agent.agent.md        # Researches and drafts the plan (with graphify)
│   ├── implement-agent.agent.md       # Implements code and tests per phase
│   ├── review-agent.agent.md          # Reviews and validates each phase
│   ├── AgentArchitect.agent.md        # Designs new agent teams
│   ├── council-*.agent.md             # Plan council: spec, architect, lateral, risk
│   └── optional/
│       └── codex-agent.agent.md       # Optional bridge to OpenAI Codex
└── skills/
    ├── subagent-pool/                 # The Conductor (main skill)
    │   ├── SKILL.md
    │   ├── assets/                    # Templates, evidence and skill review
    │   │   ├── prompts.md · agent-definitions.md · interview-protocol.md
    │   │   ├── research.md · codex-modes.md · codex-verdict.schema.json
    │   │   ├── skills-library.md · skill-review-prompt.md · official-sources.json
    │   │   └── skills-probadas-template/   # template for your private skills repo
    │   └── scripts/
    │       ├── codex-models.py        # Codex model registry (latest version per family)
    │       ├── skills_lib.py          # Library validator and lookup
    │       ├── skill_prescan.py       # Offline static pre-scan
    │       ├── skill-review.sh        # Gated review in two containers
    │       ├── test_*.py              # 131 tests (see Tests)
    │       └── fixtures/              # Test skills: one benign, one malicious
    ├── arquitec-dev-ia/
    │   ├── SKILL.md                   # AI context documentation skill
    │   ├── assets/                    # Templates (AGENTS, project-context, skill, Mermaid)
    │   └── references/docs.md
    └── graphify/
        ├── SKILL.md                   # Knowledge graph skill (see Graphify)
        └── .graphify_version
```

---

## 🧭 Graphify

**[graphify](https://github.com/safishamsi/graphify)** is a third-party tool that turns a repo (code, docs, PDFs, images) into a queryable knowledge graph. If `graphify-out/` exists, `planning-agent` uses it to find the central nodes and dependencies before planning.

```bash
uv tool install graphifyy   # the PyPI package is graphifyy; the command is graphify
graphify install            # registers the skill in Claude Code
```

---

## 📚 Documentation

| Document | Contents |
|---|---|
| [SKILL.md](skills/subagent-pool/SKILL.md) | The Conductor: rules, tiers, flow, Codex and skill review |
| [prompts.md](skills/subagent-pool/assets/prompts.md) | Task templates and return contracts |
| [agent-definitions.md](skills/subagent-pool/assets/agent-definitions.md) | Roles, delegation rules and troubleshooting |
| [interview-protocol.md](skills/subagent-pool/assets/interview-protocol.md) | Full protocol for designing teams (AgentArchitect) |
| [council.md](skills/subagent-pool/assets/council.md) | Plan council: rounds, message limits, file-mode fallback |
| [research.md](skills/subagent-pool/assets/research.md) | Evidence and sources behind each rule |
| [codex-modes.md](skills/subagent-pool/assets/codex-modes.md) | Recipes for `debug` (Docker) and `browser` (Flatpak Chrome) |
| [skills-library.md](skills/subagent-pool/assets/skills-library.md) | Reviewed-skills library and gated review |
| [CHANGELOG.md](CHANGELOG.md) | Version history and known limits |

---

## 🗺️ What's missing

- **The container-2 reviewer has not been run end to end** on a real skill.
- **`codex debug` inside Docker:** reachability from the container is unverified.
- **Model release dates:** the table in `skills-library.md` has `TODO` entries. Until they are filled in, the freshness rule flags a candidate instead of discarding it.
- **Decision model** for vetting calls (OpenAI Decisions API or a `luna` decider): deferred until there are measurements.

---

## 🤝 Contributing

1. Fork the repo and create a branch (`feat/my-improvement`, `docs/…`).
2. Follow the project conventions and use commits `type(scope): message`.
3. Run the tests before opening a PR (see [Tests](#-tests)).
4. Open a Pull Request describing the change.

Ideas: specialist agents (frontend, DevOps, ML), usage examples and orchestration scenarios with their tests. Report bugs in [GitHub Issues](https://github.com/elisaul77/Orquestacion_Agentes_claude/issues).

---

## 💖 Support the project

If it saves you time: ⭐ star the repo, share it with other Claude Code users, and report what you find. If you want to contribute financially, the options are in [FUNDING.md](FUNDING.md): GitHub Sponsors, PayPal, Buy Me a Coffee, Ko-fi and Patreon.

---

## 📄 License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Elisaul Florez ([@elisaul77](https://github.com/elisaul77)).

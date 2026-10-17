# INSTALL.md — for agents installing this stack

You are an AI agent asked to install **subagent-pool** (this repo) into the user's Claude Code. Follow these steps in
order. The installer is safe to re-run, but nothing in it is yours to decide on the user's behalf.

## Rules

- **Never overwrite `~/.claude/settings.json`.** The installer merges into it. Don't edit it by hand.
- **Optional add-ons need the user's yes.** Ask once, in plain prose, before step 3.
- **Back up before changing anything.** The installer does this for you; report the backup path.
- **Never push, publish or delete** anything as part of the install.
- You can't restart Claude Code yourself. Tell the user to restart it, and don't treat agents that are missing
  before the restart as a failed install.

## 1. Get the repo

```bash
git clone https://github.com/elisaul77/Orquestacion_Agentes_claude.git ~/Orquestacion_Agentes_claude
cd ~/Orquestacion_Agentes_claude
```

Already cloned → `git pull` instead.

## 2. Preview

```bash
python3 skills/subagent-pool/scripts/install.py --dry-run
```

It prints what it would copy and back up, and changes nothing. It needs Python 3.10 or later.

## 3. Ask the user about add-ons

Ask in one message, briefly explaining each add-on and proposing a default:

| Add-on | Ask | Suggest yes when |
|---|---|---|
| `teams` | "Should the plan council debate by direct messages? It turns on an experimental Claude Code flag." | almost always; without it the council runs through files |
| `cost-hook` | "Should I log token use per session?" | the user tracks cost |
| `codex` | "Do you have Codex (ChatGPT) and want second-vendor reviews?" | `codex` is installed and logged in (`codex login`) |
| `claude-md` | "Should I add a routing table to your `~/.claude/CLAUDE.md`, so orchestration triggers reliably? It goes between markers, so it can be removed later." | the user wants automatic triggering |

## 4. Install

```bash
python3 skills/subagent-pool/scripts/install.py --with teams,cost-hook   # only the add-ons the user accepted
```

The last lines are the result. Report them:

```
STATUS: INSTALLED | FAILED
ADDONS: …
BACKUP: …
RESTART_REQUIRED: yes
```

If the output has a `✗` line, report that line and its `fix:` suggestion. Don't improvise a fix in `~/.claude`.
A `!` warning (for example, `codex CLI not found`) is not a failure.

## 5. Hand over

Tell the user:
1. Restart Claude Code. The agents load when a session starts.
2. After restarting, check the install with `python3 ~/.claude/skills/subagent-pool/scripts/doctor.py`.
3. To use it, ask for complex work in plain words, for example `use the conductor to…`. The README covers the rest.
4. For best results, open Claude Code inside the project folder, so the project's own rules load.

## Undo

Copy the files back from the `BACKUP` folder the installer reported. To remove the CLAUDE.md routing block, delete
everything between `<!-- subagent-pool:begin -->` and `<!-- subagent-pool:end -->`.

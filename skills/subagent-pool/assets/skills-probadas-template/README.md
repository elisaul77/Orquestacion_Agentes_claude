# skills-probadas (TEMPLATE)

This directory is a **template** for the private repository `skills-probadas`.
It contains no skills. The real library lives only in that private repo, never in
the public `Orquestacion_Agentes_claude` repo.

Full rules (lookup order, verdicts, report format, re-review trigger): see
`skills/subagent-pool/assets/skills-library.md` in the subagent-pool skill.

## Layout

```
skills-probadas/
  README.md            this file
  index.json           APPROVED skills, pinned to a commit
  vetadas.json         REJECTED / DOUBTFUL skills, never re-reviewed
  skills/<id>/         verbatim copy of the skill at `commit`
  reports/<id>.md      review report (format below)
```

## index.json

```json
{"version": 1, "skills": [
  {"id": "example-skill", "name": "example-skill",
   "source_url": "https://github.com/<owner>/<repo>/tree/<ref>/<path>",
   "commit": "<40-char lowercase SHA>", "date": "YYYY-MM-DD",
   "reviewer": "<codex model slug or claude-fable-5-1>", "verdict": "APPROVED",
   "report": "reports/example-skill.md", "path": "skills/example-skill/"}
]}
```

## vetadas.json

```json
{"version": 1, "vetadas": [
  {"id": "example-bad", "source_url": "https://github.com/<owner>/<repo>",
   "commit": "<40-char lowercase SHA>", "date": "YYYY-MM-DD",
   "reviewer": "<codex model slug or claude-fable-5-1>", "verdict": "REJECTED",
   "reason": "one line: what the review found"}
]}
```

Field rules: `id` is a slug `[a-z0-9][a-z0-9-]*` and equals `name`; `date` is ISO
`YYYY-MM-DD`; `verdict` is `APPROVED` in index, `REJECTED` or `DOUBTFUL` in vetadas;
`source_url` is `https://`.

## Report format (`reports/<id>.md`)

```markdown
# Review: <id>

- Source: <source_url>
- Commit: <40-char SHA>
- Date: YYYY-MM-DD
- Reviewer: <codex model slug or claude-fable-5-1>
- Verdict: APPROVED | REJECTED | DOUBTFUL

## Files inspected
## Prompt-injection findings
## Exfiltration / network
## Filesystem / shell actions
## Dependencies
## Verdict rationale
```

## Validate

```bash
python3 -B skills/subagent-pool/scripts/skills_lib.py validate <path-to-skills-probadas>
```

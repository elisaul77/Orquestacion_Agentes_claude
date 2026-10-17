# Optional hooks — cost ledger (v9.6)

Off by default. To enable, add to `~/.claude/settings.json` (merge with existing `hooks`):

```json
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "python3 ~/.claude/skills/subagent-pool/scripts/cost_tracker.py hook",
        "timeout": 10,
        "async": true
      }]
    }]
  }
}
```

- Runs after every turn (async, never blocks); each row is a cumulative snapshot, the report keeps the latest per session.
- Counts the main transcript plus `<session>/subagents/*.jsonl`, per model, deduplicating streamed message ids.
- Report: `python3 ~/.claude/skills/subagent-pool/scripts/cost_tracker.py report --days 7` (`--csv` to export).
- Days are UTC.
- Dollars: create `~/.claude/metrics/prices.json` with USD per million tokens per model id, from the official pricing page:
  `{"claude-opus-5-5": {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}}`. No prices are shipped.

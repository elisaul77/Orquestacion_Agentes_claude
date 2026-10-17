import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path

import cost_tracker as ct


def msg(mid, model, i, o, cw=0, cr=0):
    return json.dumps({"type": "assistant", "message": {"id": mid, "model": model, "usage": {
        "input_tokens": i, "output_tokens": o, "cache_creation_input_tokens": cw, "cache_read_input_tokens": cr}}})


class CostTrackerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        ct.METRICS, ct.LEDGER = self.tmp / "m", self.tmp / "m" / "costs.jsonl"

    def test_dedupes_message_ids_and_reads_subagents(self):
        main = self.tmp / "s1.jsonl"
        main.write_text("\n".join([msg("a", "opus", 10, 5), msg("a", "opus", 10, 5), "not json",
                                   msg("b", "<synthetic>", 1, 1)]))
        (self.tmp / "s1" / "subagents").mkdir(parents=True)
        (self.tmp / "s1" / "subagents" / "agent-x.jsonl").write_text(msg("c", "haiku", 3, 2, 7, 9))
        row = ct.hook(json.dumps({"session_id": "s1", "transcript_path": str(main)}))
        self.assertEqual(row["models"]["opus"], {"input": 10, "output": 5, "cache_write": 0, "cache_read": 0})
        self.assertEqual(row["models"]["haiku"]["cache_read"], 9)
        self.assertNotIn("<synthetic>", row["models"])
        self.assertEqual(len(ct.LEDGER.read_text().splitlines()), 1)

    def test_report_uses_latest_snapshot_per_session(self):
        rows = [{"timestamp": "2026-10-16T01:00:00", "session_id": "s", "models": {"opus": {"input": 1, "output": 1, "cache_write": 0, "cache_read": 0}}},
                {"timestamp": "2026-10-16T02:00:00", "session_id": "s", "models": {"opus": {"input": 1_000_000, "output": 0, "cache_write": 0, "cache_read": 0}}}]
        out = ct.report(rows, {"opus": {"input": 5}})
        self.assertIn("5.00", out)
        self.assertIn("sessions: 1", out)

    def test_report_without_prices_is_partial_and_days_filter(self):
        rows = [{"timestamp": "2026-10-01T00:00:00", "session_id": "old", "models": {"x": {"input": 1, "output": 0, "cache_write": 0, "cache_read": 0}}},
                {"timestamp": "2026-10-16T00:00:00", "session_id": "new", "models": {"x": {"input": 2, "output": 0, "cache_write": 0, "cache_read": 0}}}]
        out = ct.report(rows, {}, days=3, today=dt.date(2026, 10, 16))
        self.assertIn("partial", out)
        self.assertIn("sessions: 1", out)

    def test_hook_main_never_fails(self):
        import io, sys
        sys.stdin = io.StringIO("{broken")
        self.assertEqual(ct.main(["hook"]), 0)


if __name__ == "__main__":
    unittest.main()

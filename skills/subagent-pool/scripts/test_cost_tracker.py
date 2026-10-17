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



class CostTrackerEdgeTest(unittest.TestCase):
    def row(self, ts, sid, model="m", **t):
        return {"timestamp": ts, "session_id": sid,
                "models": {model: {f: t.get(f, 0) for f in ct.FIELDS}}}

    def test_days_window_is_inclusive_of_cutoff_only(self):
        rows = [self.row("2026-10-14T23:00:00", "a", input=1), self.row("2026-10-15T00:00:00", "b", input=1),
                self.row("2026-10-16T00:00:00", "c", input=1)]
        out = ct.report(rows, {}, days=2, today=dt.date(2026, 10, 16))
        self.assertIn("sessions: 2", out)
        self.assertNotIn("2026-10-14", out)
        self.assertIn("2026-10-15", out)

    def test_aggregates_sessions_and_all_fields_with_price(self):
        rows = [self.row("2026-10-16T01:00:00", "a", input=1_000_000, output=1_000_000),
                self.row("2026-10-16T02:00:00", "b", cache_write=1_000_000, cache_read=1_000_000)]
        prices = {"m": {"input": 1, "output": 2, "cache_write": 3, "cache_read": 4}}
        csv = ct.report(rows, prices, as_csv=True).splitlines()
        self.assertEqual(csv[0], "day,model,sessions,input,output,cache_write,cache_read,usd")
        self.assertEqual(csv[1], "2026-10-16,m,2,1000000,1000000,1000000,1000000,10.00")
        self.assertIn("total usd: 10.00", ct.report(rows, prices))

    def test_partial_prices_flagged(self):
        rows = [self.row("2026-10-16T01:00:00", "a", "m", input=1_000_000),
                self.row("2026-10-16T01:00:00", "b", "z", input=1_000_000)]
        out = ct.report(rows, {"m": {"input": 1}})
        self.assertIn("1.00 (partial", out)

    def test_ignores_non_assistant_and_null_usage(self):
        p = Path(tempfile.mkdtemp()) / "s.jsonl"
        p.write_text("\n".join([
            json.dumps({"type": "user", "message": {"id": "u", "model": "m", "usage": {"input_tokens": 99}}}),
            json.dumps({"type": "assistant", "message": "not a dict"}),
            json.dumps({"type": "assistant", "message": {"id": "a", "model": "m", "usage": {
                "input_tokens": None, "output_tokens": 3, "cache_creation_input_tokens": None,
                "cache_read_input_tokens": 4}}})]))
        self.assertEqual(ct.usage_by_model([p]), {"m": {"input": 0, "output": 3, "cache_write": 0, "cache_read": 4}})

    def test_session_id_falls_back_to_transcript_stem(self):
        tmp = Path(tempfile.mkdtemp())
        ct.METRICS, ct.LEDGER = tmp / "m", tmp / "m" / "costs.jsonl"
        main = tmp / "abc123.jsonl"
        main.write_text(msg("x", "m", 1, 1))
        self.assertEqual(ct.hook(json.dumps({"transcript_path": str(main)}))["session_id"], "abc123")
        self.assertIsNone(ct.hook("{}"))

if __name__ == "__main__":
    unittest.main()

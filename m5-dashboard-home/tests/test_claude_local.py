import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bridge.claude_local import build_local_claude_payload, collect_local_claude_usage
from bridge.claude_client import normalize_claude_stats


def _assistant(message_id, timestamp, **usage):
    return {
        "type": "assistant",
        "timestamp": timestamp.isoformat(),
        "message": {"id": message_id, "usage": usage},
    }


class LocalClaudeUsageTests(unittest.TestCase):
    def test_deduplicates_streaming_rows_and_splits_windows(self):
        now = datetime(2026, 8, 14, 20, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            rows = [
                _assistant(
                    "today",
                    now - timedelta(hours=1),
                    input_tokens=10,
                    cache_creation_input_tokens=20,
                    cache_read_input_tokens=30,
                    output_tokens=40,
                ),
                # Claude Code writes repeated streaming snapshots for one API
                # message. Only the last row for the same message id counts.
                _assistant(
                    "today",
                    now - timedelta(minutes=59),
                    input_tokens=10,
                    cache_creation_input_tokens=20,
                    cache_read_input_tokens=30,
                    output_tokens=40,
                ),
                _assistant(
                    "week",
                    now - timedelta(days=2),
                    input_tokens=5,
                    cache_creation_input_tokens=0,
                    cache_read_input_tokens=0,
                    output_tokens=5,
                ),
                _assistant(
                    "old",
                    now - timedelta(days=8),
                    input_tokens=1,
                    cache_creation_input_tokens=2,
                    cache_read_input_tokens=3,
                    output_tokens=4,
                ),
                {"type": "assistant", "timestamp": "broken"},
            ]
            (project / "session.jsonl").write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
            )
            usage = collect_local_claude_usage(root, now, now - timedelta(hours=3))

        self.assertEqual(usage["today_tokens"], 100)
        self.assertEqual(usage["today_messages"], 1)
        self.assertEqual(usage["five_hour_tokens"], 100)
        self.assertEqual(usage["seven_day_tokens"], 110)
        self.assertEqual(usage["lifetime_tokens"], 120)
        self.assertEqual(usage["lifetime_messages"], 3)
        self.assertEqual(usage["checkpoint_delta_tokens"], 100)

    def test_builds_payload_from_official_limits(self):
        now = datetime(2026, 8, 14, 20, tzinfo=timezone.utc)
        reset = now + timedelta(hours=3)
        with tempfile.TemporaryDirectory() as temporary:
            payload = build_local_claude_payload(
                {
                    "projects_root": temporary,
                    "account_lifetime_checkpoint_tokens": 12_345,
                    "account_lifetime_checkpoint_at": "2026-08-14T14:00:00+00:00",
                },
                now,
                {
                    "limits": [
                        {"kind": "session", "percent": 12, "resets_at": reset.isoformat()},
                        {
                            "kind": "weekly_all",
                            "percent": 34,
                            "resets_at": reset.isoformat(),
                        },
                    ]
                },
            )
        normalized = normalize_claude_stats(payload, now)
        self.assertEqual(normalized["short_used_percent"], 12)
        self.assertEqual(normalized["week_used_percent"], 34)
        self.assertEqual(normalized["week_resets_at"], int(reset.timestamp()))
        self.assertEqual(normalized["lifetime_tokens"], 12_345)

    def test_default_payload_does_not_fetch_official_limits(self):
        now = datetime(2026, 8, 14, 20, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temporary:
            payload = build_local_claude_payload({"projects_root": temporary}, now)

        self.assertFalse(payload["claude"]["official_usage"]["available"])
        self.assertEqual(payload["claude"]["official_usage"]["limits"], [])


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime, timedelta, timezone

from bridge.claude_client import local_claude_state, normalize_claude_stats


class ClaudeUsageTests(unittest.TestCase):
    def test_local_only_state_is_online_without_remote_usage(self):
        result = local_claude_state(123)
        self.assertTrue(result["connected"])
        self.assertEqual(result["active_count"], 0)
        self.assertEqual(result["today_tokens"], 0)
        self.assertEqual(result["week_used_percent"], -1)
        self.assertEqual(result["updated_at"], 123)

    def test_normalizes_existing_ai_usage_payload(self):
        now = datetime(2026, 8, 14, 12, tzinfo=timezone.utc).astimezone()
        result = normalize_claude_stats(
            {
                "generated_at": now.isoformat(),
                "claude": {
                    "today": {
                        "msg_count": 41,
                        "total_tokens": 2_071_318,
                        "day_over_day": {"pct": -59.4},
                    },
                    "total": {"msg_count": 6974, "total_tokens": 1_676_694_016},
                    "windows": {
                        "five_hours": {"used_tokens": 2_071_318},
                        "seven_days": {"used_tokens": 16_381_060},
                    },
                    "official_usage": {"available": False},
                    "rate_limits": {"primary": None, "secondary": None},
                },
            },
            now,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["today_tokens"], 2_071_318)
        self.assertEqual(result["today_messages"], 41)
        self.assertEqual(result["seven_day_tokens"], 16_381_060)
        self.assertEqual(result["lifetime_tokens"], 1_676_694_016)
        self.assertEqual(result["short_used_percent"], -1)
        self.assertEqual(result["day_over_day_percent"], -59.4)

    def test_normalizes_official_quota_when_available(self):
        now = datetime(2026, 8, 14, 12, tzinfo=timezone.utc).astimezone()
        reset = now + timedelta(hours=2)
        result = normalize_claude_stats(
            {
                "generated_at": now.isoformat(),
                "claude": {
                    "today": {},
                    "total": {},
                    "windows": {},
                    "official_usage": {
                        "five_hour": {"utilization": 18.2, "resets_at": reset.isoformat()},
                        "seven_day": {"used_pct": 37, "reset_at": reset.timestamp()},
                    },
                },
            },
            now,
        )
        self.assertEqual(result["short_used_percent"], 18)
        self.assertEqual(result["week_used_percent"], 37)
        self.assertEqual(result["short_resets_at"], int(reset.timestamp()))
        self.assertEqual(result["week_resets_at"], int(reset.timestamp()))

    def test_rejects_previous_day_cache(self):
        now = datetime(2026, 8, 14, 12, tzinfo=timezone.utc).astimezone()
        result = normalize_claude_stats(
            {
                "generated_at": (now - timedelta(days=1)).isoformat(),
                "claude": {"today": {}, "total": {}, "windows": {}},
            },
            now,
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()

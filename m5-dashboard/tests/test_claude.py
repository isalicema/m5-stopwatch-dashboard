import unittest
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from bridge.claude_client import (
    ClaudeMonitor,
    hook_completion_results,
    jsonl_completion_results,
    local_claude_state,
    normalize_claude_stats,
)
from bridge.claude_hook import notify_bridge


class ClaudeUsageTests(unittest.TestCase):
    def test_jsonl_visible_end_turn_is_the_default_completion_source(self):
        candidates = [
            {"id": "session-12345678", "title": "真实完成的 Claude 任务", "completed_at": 123}
        ]
        visible = jsonl_completion_results(candidates, True)
        hidden = jsonl_completion_results(candidates, False)

        self.assertEqual(
            visible[0],
            {
                "id": "12345678",
                "title": "真实完成的 Claude 任务",
                "completed_at": 123,
            },
        )
        self.assertEqual(hidden[0]["title"], "Claude 1")

        monitor = ClaudeMonitor({}, lambda _: None)
        self.assertEqual(monitor._completion_results(candidates, False), hidden)

    def test_completion_wake_interrupts_poll_delay(self):
        monitor = ClaudeMonitor({}, lambda _: None)
        self.assertEqual(monitor.wake(), {"provider": "claude", "woken": True})
        self.assertTrue(monitor._wake_event.is_set())
        monitor._wait(10)
        self.assertFalse(monitor._wake_event.is_set())

    def test_hook_notifies_authenticated_local_bridge(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config.json"
            config.write_text(
                json.dumps({"server": {"api_token": "secret", "port": 9998}}),
                encoding="utf-8",
            )
            response = mock.MagicMock()
            response.__enter__.return_value.status = 200
            with mock.patch.dict(os.environ, {"M5_DASH_CONFIG": str(config)}), mock.patch(
                "bridge.claude_hook.urllib.request.urlopen", return_value=response
            ) as request:
                self.assertTrue(
                    notify_bridge({"id": "stop-1", "title": "Claude", "completed_at": 123})
                )
            sent = request.call_args.args[0]
            self.assertEqual(sent.full_url, "http://127.0.0.1:9998/api/internal/completion/claude")
            self.assertEqual(sent.get_header("X-dashboard-token"), "secret")
            self.assertEqual(
                json.loads(sent.data),
                {"id": "stop-1", "title": "Claude", "completed_at": 123},
            )

    def test_completion_results_require_stop_hook_receipt(self):
        now = datetime(2026, 8, 24, 12, tzinfo=timezone.utc).astimezone()
        sessions = {
            "session-done-12345678": {
                "completed_at": int(now.timestamp()),
                "completion_id": "session-done:1",
            }
        }
        transcript_candidates = [
            {"id": "12345678", "title": "真实完成的 Claude 任务", "completed_at": 1}
        ]

        visible = hook_completion_results(sessions, transcript_candidates, True, now=now)
        hidden = hook_completion_results(sessions, transcript_candidates, False, now=now)

        self.assertEqual(visible[0]["title"], "真实完成的 Claude 任务")
        self.assertEqual(visible[0]["completed_at"], int(now.timestamp()))
        self.assertEqual(hidden[0]["title"], "Claude 1")

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

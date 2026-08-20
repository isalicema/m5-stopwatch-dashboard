import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bridge.codex_client import (
    collect_local_daily_usage,
    format_rate_limits,
    merge_daily_usage,
    merge_sessions,
    normalize_peer_daily_usage,
)


class CodexMergeTests(unittest.TestCase):
    def test_hides_titles_by_default(self):
        sessions = {"thr_123": {"status": "working", "last_event_at": 100}}
        threads = [{"id": "thr_123", "name": "Private project title"}]
        result = merge_sessions(sessions, threads, False, 10**12)
        self.assertEqual(result[0]["title"], "Codex 1")

    def test_can_expose_titles(self):
        sessions = {"thr_123": {"status": "idle", "last_event_at": 100}}
        threads = [{"id": "thr_123", "name": "Dashboard task"}]
        result = merge_sessions(sessions, threads, True, 10**12)
        self.assertEqual(result[0]["title"], "Dashboard task")

    def test_actionable_sessions_sort_first(self):
        sessions = {
            "thr_idle": {"status": "idle", "last_event_at": 300},
            "thr_work": {"status": "working", "last_event_at": 100},
            "thr_approval": {"status": "waiting_approval", "last_event_at": 50},
        }
        result = merge_sessions(sessions, [], False, 10**12)
        self.assertEqual(
            [row["status"] for row in result],
            ["waiting_approval", "working", "idle"],
        )

    def test_flattens_primary_and_secondary_rate_windows(self):
        result = format_rate_limits(
            {
                "codex": {
                    "primary": {
                        "usedPercent": 46,
                        "windowDurationMins": 10080,
                        "resetsAt": 200,
                    },
                    "secondary": {
                        "usedPercent": 12,
                        "windowDurationMins": 300,
                        "resetsAt": 100,
                    },
                }
            }
        )
        self.assertEqual([row["id"] for row in result], ["codex", "codex:secondary"])
        self.assertEqual([row["window_minutes"] for row in result], [10080, 300])


class LocalUsageTests(unittest.TestCase):
    @staticmethod
    def _token_row(stamp, total, input_tokens, cached, output):
        return {
            "timestamp": stamp,
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {
                        "total_tokens": total,
                        "input_tokens": input_tokens,
                        "cached_input_tokens": cached,
                        "output_tokens": output,
                    }
                },
            },
        }

    def _write_session(self, root, name, rows, mtime):
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n{truncated\n",
            encoding="utf-8",
        )
        os.utime(path, (mtime, mtime))

    def test_counts_each_sessions_daily_delta_once(self):
        local_tz = timezone.utc
        now = datetime(2026, 8, 14, 12, tzinfo=local_tz)
        with tempfile.TemporaryDirectory() as root:
            self._write_session(
                root,
                "old/continued.jsonl",
                [
                    self._token_row("2026-08-13T23:59:00Z", 1000, 800, 100, 200),
                    self._token_row("2026-08-14T00:01:00Z", 1300, 1080, 180, 220),
                    self._token_row("2026-08-14T08:00:00Z", 2000, 1700, 600, 300),
                    self._token_row("2026-08-15T00:01:00Z", 9000, 8000, 7000, 1000),
                ],
                now.timestamp(),
            )
            self._write_session(
                root,
                "new.jsonl",
                [self._token_row("2026-08-14T06:00:00Z", 50, 40, 0, 10)],
                now.timestamp(),
            )

            result = collect_local_daily_usage(root, now)

        self.assertEqual(result["today_total_tokens"], 1050)
        self.assertEqual(result["today_input_tokens"], 940)
        self.assertEqual(result["today_cached_input_tokens"], 500)
        self.assertEqual(result["today_output_tokens"], 110)
        self.assertEqual(result["today_sessions"], 2)

    def test_missing_session_directory_is_zero(self):
        result = collect_local_daily_usage("/path/that/does/not/exist")
        self.assertEqual(result["today_total_tokens"], 0)
        self.assertEqual(result["today_sessions"], 0)


class PeerUsageTests(unittest.TestCase):
    def test_normalizes_current_local_day(self):
        now = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc).astimezone()
        generated = now.replace(hour=10).isoformat()
        result = normalize_peer_daily_usage(
            {
                "generated_at": generated,
                "today": {
                    "thread_count": 6,
                    "raw_total_tokens": 38_506_598,
                    "input_tokens": 38_351_989,
                    "cached_input_tokens": 37_066_496,
                    "output_tokens": 154_609,
                },
            },
            now,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["today_total_tokens"], 38_506_598)
        self.assertEqual(result["today_output_tokens"], 154_609)

    def test_rejects_previous_local_day(self):
        now = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc).astimezone()
        result = normalize_peer_daily_usage(
            {
                "generated_at": (now - timedelta(days=1)).isoformat(),
                "today": {"raw_total_tokens": 99},
            },
            now,
        )
        self.assertIsNone(result)

    def test_merges_local_and_peer_without_changing_account_total(self):
        result = merge_daily_usage(
            {
                "today_total_tokens": 10,
                "today_input_tokens": 8,
                "today_cached_input_tokens": 6,
                "today_output_tokens": 2,
                "today_sessions": 1,
            },
            [
                {
                    "today_total_tokens": 20,
                    "today_input_tokens": 17,
                    "today_cached_input_tokens": 15,
                    "today_output_tokens": 3,
                    "today_sessions": 2,
                }
            ],
        )
        self.assertEqual(result["today_total_tokens"], 30)
        self.assertEqual(result["today_input_tokens"], 25)
        self.assertEqual(result["today_output_tokens"], 5)
        self.assertEqual(result["today_local_tokens"], 10)
        self.assertEqual(result["today_peer_tokens"], 20)
        self.assertEqual(result["today_peer_count"], 1)


if __name__ == "__main__":
    unittest.main()

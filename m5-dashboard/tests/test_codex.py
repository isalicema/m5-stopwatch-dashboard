import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from bridge.codex_client import (
    CodexMonitor,
    apply_thread_titles,
    collect_local_daily_usage,
    format_rate_limits,
    hook_completion_results,
    merge_daily_usage,
    merge_sessions,
    normalize_peer_daily_usage,
)
from bridge.codex_hook import notify_bridge


class CodexMergeTests(unittest.TestCase):
    def test_completion_wake_interrupts_poll_delay(self):
        monitor = CodexMonitor({}, lambda _: None)
        self.assertEqual(monitor.wake(), {"provider": "codex", "woken": True})
        self.assertTrue(monitor._wake_event.is_set())
        monitor._wait(10)
        self.assertFalse(monitor._wake_event.is_set())

    def test_hook_notifies_authenticated_local_bridge(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config.json"
            config.write_text(
                json.dumps({"server": {"api_token": "secret", "port": 9999}}),
                encoding="utf-8",
            )
            response = mock.MagicMock()
            response.__enter__.return_value.status = 200
            with mock.patch.dict(os.environ, {"M5_DASH_CONFIG": str(config)}), mock.patch(
                "bridge.codex_hook.urllib.request.urlopen", return_value=response
            ) as request:
                self.assertTrue(
                    notify_bridge({"id": "turn-1", "title": "Codex", "completed_at": 123})
                )
            sent = request.call_args.args[0]
            self.assertEqual(sent.full_url, "http://127.0.0.1:9999/api/internal/completion/codex")
            self.assertEqual(sent.get_header("X-dashboard-token"), "secret")
            self.assertEqual(
                json.loads(sent.data),
                {"id": "turn-1", "title": "Codex", "completed_at": 123},
            )

    def test_completion_results_only_use_notify_receipts(self):
        now = datetime.now().astimezone().replace(microsecond=0)
        sessions = {
            "thr_done": {
                "status": "idle",
                "completed_at": int(now.timestamp()),
                "completion_id": "turn_done",
            },
            "thr_tool": {"status": "working", "last_event": "PostToolUse"},
            "thr_stop": {"status": "idle", "turn_stopped_at": int(now.timestamp())},
        }
        threads = [{"id": "thr_done", "name": "完成动画修复"}]

        result = hook_completion_results(sessions, threads, True, now=now)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "turn_done")
        self.assertEqual(result[0]["title"], "完成动画修复")
        self.assertEqual(result[0]["completed_at"], int(now.timestamp()))

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

    def test_waiting_input_must_be_recent_and_loaded(self):
        sessions = {
            "thr_live": {"status": "waiting_input", "last_event_at": 9_900},
            "thr_unloaded": {"status": "waiting_input", "last_event_at": 9_900},
            "thr_expired": {"status": "waiting_input", "last_event_at": 8_000},
        }
        threads = [
            {"id": "thr_live", "status": {"type": "idle"}},
            {"id": "thr_unloaded", "status": {"type": "notLoaded"}},
            {"id": "thr_expired", "status": {"type": "active", "activeFlags": []}},
        ]
        with mock.patch("bridge.codex_client.time.time", return_value=10_000):
            result = merge_sessions(
                sessions, threads, False, stale_seconds=1_000,
                waiting_stale_seconds=600,
            )

        statuses = {row["id"]: row["status"] for row in result}
        self.assertEqual(statuses["thr_live"], "waiting_input")
        self.assertEqual(statuses["unloaded"], "idle")
        self.assertEqual(statuses["_expired"], "idle")

    def test_codex_transcript_prefers_user_facing_task_title(self):
        transcripts = [{"id": "12345678", "title": "第一句话", "messages": []}]
        threads = [
            {
                "id": "thr-12345678",
                "name": "修复等待确认恢复",
                "preview": "第一句话",
            }
        ]
        self.assertEqual(
            apply_thread_titles(transcripts, threads, True)[0]["title"],
            "修复等待确认恢复",
        )
        self.assertEqual(
            apply_thread_titles(transcripts, threads, False)[0]["title"],
            "第一句话",
        )

    def test_codex_transcript_hides_child_agents_from_the_watch(self):
        transcripts = [{"id": "12345678", "title": "delegated prompt"}]
        threads = [
            {
                "id": "child-12345678",
                "name": "delegated prompt",
                "parentThreadId": "parent-thread",
            }
        ]
        self.assertEqual(apply_thread_titles(transcripts, threads, True), [])

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

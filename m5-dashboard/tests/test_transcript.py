import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from bridge.transcript import LocalClaudeTranscripts, LocalCodexTranscripts


class TranscriptTests(unittest.TestCase):
    @staticmethod
    def _write(path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        now = datetime.now(timezone.utc).timestamp()
        os.utime(path, (now, now))

    def test_codex_exposes_only_visible_messages_while_active(self):
        stamp = datetime.now(timezone.utc).isoformat()
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "today" / "session.jsonl"
            rows = [
                {"timestamp": stamp, "type": "session_meta", "payload": {"id": "thr_12345678"}},
                {"timestamp": stamp, "type": "event_msg", "payload": {"type": "task_started"}},
                {
                    "timestamp": stamp,
                    "type": "event_msg",
                    "payload": {
                        "type": "user_message",
                        "client_id": "prompt-1",
                        "message": "帮我检查固件",
                    },
                },
                {
                    "timestamp": stamp,
                    "type": "event_msg",
                    "payload": {"type": "agent_reasoning", "text": "private reasoning"},
                },
                {
                    "timestamp": stamp,
                    "type": "event_msg",
                    "payload": {"type": "agent_message", "message": "正在检查固件。"},
                },
            ]
            self._write(path, rows)
            tracker = LocalCodexTranscripts(root, stale_seconds=300)

            private = tracker.snapshots(False)
            self.assertEqual(private[0]["title"], "Codex 1")
            self.assertEqual(private[0]["messages"], [])
            self.assertFalse(private[0]["content_visible"])
            result = tracker.snapshots(True)

            self.assertEqual(result[0]["id"], "12345678")
            self.assertEqual(result[0]["title"], "帮我检查固件")
            self.assertTrue(result[0]["content_visible"])
            self.assertEqual(
                [(item["role"], item["text"]) for item in result[0]["messages"]],
                [("user", "帮我检查固件"), ("assistant", "正在检查固件。")],
            )
            self.assertNotIn("private reasoning", json.dumps(result))

            rows.append(
                {"timestamp": stamp, "type": "event_msg", "payload": {"type": "task_complete"}}
            )
            self._write(path, rows)
            self.assertEqual(tracker.snapshots(True), [])

            rows.append(
                {"timestamp": stamp, "type": "event_msg", "payload": {"type": "agent_reasoning"}}
            )
            self._write(path, rows)
            self.assertEqual(len(tracker.snapshots(True)), 1)

    def test_claude_filters_thinking_tools_and_tool_results(self):
        stamp = datetime.now(timezone.utc).isoformat()
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "project" / "session.jsonl"
            rows = [
                {
                    "timestamp": stamp,
                    "type": "user",
                    "uuid": "user-1",
                    "sessionId": "claude-87654321",
                    "message": {"content": "优化麦克风界面"},
                },
                {
                    "timestamp": stamp,
                    "type": "assistant",
                    "message": {
                        "id": "msg-1",
                        "content": [{"type": "thinking", "thinking": "private"}],
                        "stop_reason": "tool_use",
                    },
                },
                {
                    "timestamp": stamp,
                    "type": "user",
                    "uuid": "tool-result",
                    "message": {"content": [{"type": "tool_result", "content": "secret"}]},
                },
                {
                    "timestamp": stamp,
                    "type": "assistant",
                    "message": {
                        "id": "msg-2",
                        "content": [{"type": "text", "text": "我先调整颜色。"}],
                        "stop_reason": "tool_use",
                    },
                },
                {
                    "timestamp": stamp,
                    "type": "assistant",
                    "message": {
                        "id": "msg-2",
                        "content": [{"type": "text", "text": "我先调整颜色和图标。"}],
                        "stop_reason": "tool_use",
                    },
                },
            ]
            self._write(path, rows)
            tracker = LocalClaudeTranscripts(root, stale_seconds=300)

            result = tracker.snapshots(True)

            self.assertEqual(result[0]["id"], "87654321")
            self.assertEqual(
                [(item["role"], item["text"]) for item in result[0]["messages"]],
                [("user", "优化麦克风界面"), ("assistant", "我先调整颜色和图标。")],
            )
            serialized = json.dumps(result)
            self.assertNotIn("private", serialized)
            self.assertNotIn("secret", serialized)

    def test_completed_today_exposes_only_finished_visible_tasks(self):
        stamp = datetime.now(timezone.utc).isoformat()
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "today" / "finished.jsonl"
            self._write(
                path,
                [
                    {"timestamp": stamp, "type": "event_msg", "payload": {"type": "task_started"}},
                    {
                        "timestamp": stamp,
                        "type": "event_msg",
                        "payload": {"type": "user_message", "message": "完成动态时钟"},
                    },
                    {"timestamp": stamp, "type": "event_msg", "payload": {"type": "task_complete"}},
                ],
            )
            tracker = LocalCodexTranscripts(root, stale_seconds=300)
            self.assertEqual(tracker.completed_today(False), [])
            result = tracker.completed_today(True)
            self.assertEqual(result[0]["title"], "完成动态时钟")
            self.assertGreater(result[0]["completed_at"], 0)


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from bridge.local_activity import LocalClaudeActivity, LocalCodexActivity


def stamp():
    return datetime.now().astimezone().isoformat()


class LocalActivityTests(unittest.TestCase):
    def test_codex_task_lifecycle_works_without_notify_hook(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "today" / "session.jsonl"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {"timestamp": stamp(), "type": "event_msg", "payload": {"type": "task_started"}}
                )
                + "\n",
                encoding="utf-8",
            )
            tracker = LocalCodexActivity(root, stale_seconds=60)
            self.assertEqual(tracker.active_count(), 1)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {"timestamp": stamp(), "type": "event_msg", "payload": {"type": "task_complete"}}
                    )
                    + "\n"
                )
            self.assertEqual(tracker.active_count(), 0)

            # Codex Desktop can start another turn in the same JSONL without
            # emitting a new task_started marker.
            with path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {"timestamp": stamp(), "type": "event_msg", "payload": {"type": "agent_reasoning"}}
                    )
                    + "\n"
                )
            self.assertEqual(tracker.active_count(), 1)

    def test_claude_prompt_tool_use_and_end_turn_lifecycle(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "project" / "session.jsonl"
            path.parent.mkdir(parents=True)
            rows = [
                {"timestamp": stamp(), "type": "user", "message": {"content": "修改这个文件"}},
                {"timestamp": stamp(), "type": "assistant", "message": {"stop_reason": "tool_use"}},
                {
                    "timestamp": stamp(),
                    "type": "user",
                    "message": {"content": [{"type": "tool_result", "content": "ok"}]},
                },
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            tracker = LocalClaudeActivity(root, stale_seconds=60)
            self.assertEqual(tracker.active_count(), 1)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "timestamp": stamp(),
                            "type": "assistant",
                            "message": {
                                "content": [{"type": "thinking", "thinking": "private"}],
                                "stop_reason": "end_turn",
                            },
                        }
                    )
                    + "\n"
                )
            self.assertEqual(tracker.active_count(), 1)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "timestamp": stamp(),
                            "type": "assistant",
                            "message": {
                                "content": [{"type": "text", "text": "已经修改完成。"}],
                                "stop_reason": "end_turn",
                            },
                        }
                    )
                    + "\n"
                )
            self.assertEqual(tracker.active_count(), 0)


if __name__ == "__main__":
    unittest.main()

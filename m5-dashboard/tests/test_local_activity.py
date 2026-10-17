import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from bridge.local_activity import LocalClaudeActivity, LocalCodexActivity
from bridge.session_files import recent_session_files
from bridge.transcript import LocalCodexTranscripts


def stamp():
    return datetime.now().astimezone().isoformat()


class LocalActivityTests(unittest.TestCase):
    def test_codex_activity_and_transcripts_share_one_inventory(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "today" / "session.jsonl"
            path.parent.mkdir(parents=True)
            path.write_text("\n".join(json.dumps(row) for row in [
                {"timestamp": stamp(), "type": "session_meta", "payload": {"id": "thread-12345678"}},
                {"timestamp": stamp(), "type": "turn_context", "payload": {"approvals_reviewer": "user_review"}},
                {"timestamp": stamp(), "type": "event_msg", "payload": {"type": "task_started"}},
            ]) + "\n", encoding="utf-8")
            files = recent_session_files(Path(root), datetime.now().timestamp(), 60)
            activity = LocalCodexActivity(root, stale_seconds=60)
            transcripts = LocalCodexTranscripts(root, stale_seconds=60)
            self.assertEqual(activity.status_snapshot(files), (1, {
                "thread-12345678": "user_review", "12345678": "user_review",
            }))
            self.assertEqual(len(transcripts.snapshots(True, files)), 1)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "timestamp": stamp(), "type": "event_msg", "payload": {"type": "task_complete"},
                }) + "\n")
            files = recent_session_files(Path(root), datetime.now().timestamp(), 60)
            self.assertEqual(activity.status_snapshot(files)[0], 0)
            self.assertEqual(transcripts.snapshots(True, files), [])

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

    def test_codex_child_agent_is_not_a_user_facing_active_task(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "today" / "child.jsonl"
            path.parent.mkdir(parents=True)
            rows = [
                {
                    "timestamp": stamp(),
                    "type": "session_meta",
                    "payload": {"id": "child", "parent_thread_id": "parent"},
                },
                {"timestamp": stamp(), "type": "event_msg", "payload": {"type": "task_started"}},
            ]
            path.write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
            )

            self.assertEqual(LocalCodexActivity(root, stale_seconds=60).active_count(), 0)

    def test_codex_approval_reviewer_follows_latest_turn_settings(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "today" / "session.jsonl"
            path.parent.mkdir(parents=True)
            rows = [
                {
                    "timestamp": stamp(),
                    "type": "session_meta",
                    "payload": {"id": "thread-12345678"},
                },
                {
                    "timestamp": stamp(),
                    "type": "turn_context",
                    "payload": {"approvals_reviewer": "auto_review"},
                },
            ]
            path.write_text(
                "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
            )
            tracker = LocalCodexActivity(root, stale_seconds=60)
            self.assertEqual(
                tracker.approval_reviewers(),
                {
                    "thread-12345678": "auto_review",
                    "12345678": "auto_review",
                },
            )

            with path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "timestamp": stamp(),
                            "type": "event_msg",
                            "payload": {
                                "type": "thread_settings_applied",
                                "thread_id": "thread-12345678",
                                "thread_settings": {
                                    "approvals_reviewer": "user_review"
                                },
                            },
                        }
                    )
                    + "\n"
                )
            self.assertEqual(
                tracker.approval_reviewers()["thread-12345678"], "user_review"
            )

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

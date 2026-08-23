import unittest

from bridge.codex_hook import apply_event, normalize_event


class HookStateTests(unittest.TestCase):
    def test_turn_lifecycle(self):
        state = {}
        common = {"session_id": "thr_123", "cwd": "/tmp/project", "model": "gpt-test"}
        apply_event(state, {**common, "hook_event_name": "SessionStart"}, 100)
        self.assertEqual(state["sessions"]["thr_123"]["status"], "idle")
        apply_event(
            state,
            {**common, "hook_event_name": "UserPromptSubmit", "turn_id": "turn_1", "prompt": "secret"},
            110,
        )
        session = state["sessions"]["thr_123"]
        self.assertEqual(session["status"], "working")
        self.assertNotIn("prompt", session)
        apply_event(state, {**common, "hook_event_name": "PermissionRequest"}, 120)
        self.assertEqual(session["status"], "waiting_approval")
        apply_event(state, {**common, "hook_event_name": "PreToolUse"}, 125)
        self.assertEqual(session["status"], "working")
        apply_event(state, {**common, "hook_event_name": "PostToolUse"}, 130)
        self.assertEqual(session["status"], "working")
        apply_event(
            state,
            {**common, "hook_event_name": "Stop", "last_assistant_message": "Which option?"},
            140,
        )
        self.assertEqual(session["status"], "waiting_input")
        self.assertNotIn("last_assistant_message", session)

    def test_regular_stop_becomes_idle(self):
        state = {}
        apply_event(
            state,
            {"session_id": "thr_abc", "hook_event_name": "Stop", "last_assistant_message": "Done."},
            200,
        )
        self.assertEqual(state["sessions"]["thr_abc"]["status"], "idle")

    def test_legacy_notify_payload_marks_authoritative_turn_completion(self):
        event = normalize_event(
            {
                "type": "agent-turn-complete",
                "thread-id": "thr_notify",
                "turn-id": "turn_notify",
                "cwd": "/tmp/project",
                "last-assistant-message": "Done.",
            }
        )
        self.assertEqual(event["hook_event_name"], "TurnEnded")
        self.assertEqual(event["session_id"], "thr_notify")
        self.assertEqual(event["turn_id"], "turn_notify")

        state = {}
        apply_event(state, event, 300)
        session = state["sessions"]["thr_notify"]
        self.assertEqual(session["status"], "idle")
        self.assertEqual(session["completed_at"], 300)
        self.assertEqual(session["completion_id"], "turn_notify")

    def test_tool_and_stop_hooks_do_not_create_completion_receipts(self):
        state = {}
        common = {"session_id": "thr_tool", "cwd": "/tmp/project"}
        apply_event(state, {**common, "hook_event_name": "PreToolUse"}, 400)
        apply_event(state, {**common, "hook_event_name": "PostToolUse"}, 410)
        apply_event(state, {**common, "hook_event_name": "Stop"}, 420)
        self.assertNotIn("completed_at", state["sessions"]["thr_tool"])


if __name__ == "__main__":
    unittest.main()

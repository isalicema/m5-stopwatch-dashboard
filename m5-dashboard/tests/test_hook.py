import unittest

from bridge.codex_hook import apply_event


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


if __name__ == "__main__":
    unittest.main()

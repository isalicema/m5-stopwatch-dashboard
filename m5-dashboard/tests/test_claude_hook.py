import unittest

from bridge.claude_hook import apply_event


class ClaudeHookTests(unittest.TestCase):
    def test_stop_creates_authoritative_completion_receipt(self):
        state = {}
        apply_event(
            state,
            {"hook_event_name": "Stop", "session_id": "claude-session"},
            100,
        )

        session = state["sessions"]["claude-session"]
        self.assertEqual(session["status"], "idle")
        self.assertEqual(session["completed_at"], 100)
        self.assertEqual(session["completion_id"], "claude-session:100")

    def test_non_stop_events_never_create_completion_receipt(self):
        state = {}
        apply_event(
            state,
            {"hook_event_name": "PreToolUse", "session_id": "claude-session"},
            100,
        )
        self.assertNotIn("sessions", state)

    def test_two_fast_stops_keep_monotonic_firmware_watermark(self):
        state = {}
        event = {"hook_event_name": "Stop", "session_id": "claude-session"}
        apply_event(state, event, 100)
        apply_event(state, event, 100)
        self.assertEqual(state["sessions"]["claude-session"]["completed_at"], 101)


if __name__ == "__main__":
    unittest.main()

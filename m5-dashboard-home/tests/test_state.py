import unittest

from bridge.state import DashboardState


class DashboardStateTests(unittest.TestCase):
    def test_companion_exposes_primary_owned_ticktick_state(self):
        state = DashboardState()
        snapshot = state.snapshot()
        self.assertFalse(snapshot["ticktick"]["connected"])
        self.assertEqual(snapshot["ticktick"]["countdown"]["remaining_seconds"], 1500)

    def test_dashboard_snapshots_claude_independently(self):
        state = DashboardState()
        value = {"connected": True, "today_tokens": 123, "lifetime_tokens": 456}
        state.set_claude(value)
        value["today_tokens"] = 999
        snapshot = state.snapshot()
        self.assertEqual(snapshot["claude"]["today_tokens"], 123)
        self.assertEqual(snapshot["claude"]["lifetime_tokens"], 456)
        self.assertIn("codex", snapshot)


if __name__ == "__main__":
    unittest.main()

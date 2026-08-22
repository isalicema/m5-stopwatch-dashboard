import unittest

from bridge.app import dispatch_dashboard_action, dispatch_ticktick_action


class DashboardHttpTests(unittest.TestCase):
    def setUp(self):
        self.actions = []
        self.action = lambda value: self.actions.append(value) or {"connected": True}

    def test_authenticated_ticktick_action_returns_dashboard_state(self):
        status, body = dispatch_ticktick_action(
            "/api/ticktick/countdown-click", "secret", "secret", self.action
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(self.actions, ["countdown-click"])

    def test_action_rejects_wrong_token(self):
        status, body = dispatch_ticktick_action(
            "/api/ticktick/stopwatch-click", "wrong", "secret", self.action
        )
        self.assertEqual(status, 401)
        self.assertFalse(body["ok"])
        self.assertEqual(self.actions, [])

    def test_action_rejects_unknown_route(self):
        status, body = dispatch_ticktick_action(
            "/api/ticktick/delete-everything", "secret", "secret", self.action
        )
        self.assertEqual(status, 404)
        self.assertFalse(body["ok"])

    def test_authenticated_feature_actions_dispatch(self):
        actions = []
        callbacks = {
            "ai-ack": lambda: actions.append("ai-ack") or {"active": False},
            "obsidian-roll": lambda: actions.append("obsidian-roll") or {"selected": {}},
            "typeless-start": lambda: actions.append("typeless-start") or {"active": True},
        }
        status, body = dispatch_dashboard_action(
            "/api/ai/ack", "secret", "secret", callbacks
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        status, _ = dispatch_dashboard_action(
            "/api/obsidian/roll", "secret", "secret", callbacks
        )
        self.assertEqual(status, 200)
        status, _ = dispatch_dashboard_action(
            "/api/typeless/start", "secret", "secret", callbacks
        )
        self.assertEqual(status, 200)
        self.assertEqual(actions, ["ai-ack", "obsidian-roll", "typeless-start"])

    def test_extra_action_rejects_wrong_token(self):
        status, body = dispatch_dashboard_action(
            "/api/ai/open", "wrong", "secret", {"ai-open": lambda: {}}
        )
        self.assertEqual(status, 401)
        self.assertFalse(body["ok"])


if __name__ == "__main__":
    unittest.main()

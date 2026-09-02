import unittest

from bridge.app import (
    build_handler,
    dispatch_completion_action,
    dispatch_dashboard_action,
    dispatch_ticktick_action,
)


class DashboardHttpTests(unittest.TestCase):
    def setUp(self):
        self.actions = []
        self.action = lambda value: self.actions.append(value) or {"connected": True}

    def test_authenticated_ticktick_action_returns_compact_callback_result(self):
        status, body = dispatch_ticktick_action(
            "/api/ticktick/countdown-click", "secret", "secret", self.action
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertTrue(body["connected"])
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
            "typeless-start-mac": lambda: actions.append("typeless-start-mac") or {"active": True},
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
        status, body = dispatch_dashboard_action(
            "/api/typeless/start-mac", "secret", "secret", callbacks
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertTrue(body["active"])
        self.assertEqual(
            actions,
            ["ai-ack", "obsidian-roll", "typeless-start", "typeless-start-mac"],
        )

    def test_authenticated_completion_is_dispatched_with_content_free_receipt(self):
        receipts = []
        payload = {"id": "turn-1", "title": "Codex", "completed_at": 123}
        status, body = dispatch_completion_action(
            "/api/internal/completion/codex",
            "secret",
            "secret",
            payload,
            {"codex": lambda value: receipts.append(value) or {"accepted": True}},
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["accepted"])
        self.assertEqual(receipts, [payload])

    def test_completion_rejects_wrong_token(self):
        status, body = dispatch_completion_action(
            "/api/internal/completion/claude",
            "wrong",
            "secret",
            {"id": "stop-1", "completed_at": 123},
            {"claude": lambda _: {}},
        )
        self.assertEqual(status, 401)
        self.assertFalse(body["ok"])

    def test_extra_action_rejects_wrong_token(self):
        status, body = dispatch_dashboard_action(
            "/api/ai/open", "wrong", "secret", {"ai-open": lambda: {}}
        )
        self.assertEqual(status, 401)
        self.assertFalse(body["ok"])

    def test_post_returns_compact_ack_without_serializing_dashboard_state(self):
        class StateMustNotBeRead:
            def snapshot(self):
                raise AssertionError("POST must not serialize the full dashboard state")

        handler = build_handler(
            StateMustNotBeRead(),
            "secret",
            action_callbacks={
                "typeless-start-mac": lambda: {"active": True, "pending": True}
            },
        )
        request = handler.__new__(handler)
        request.path = "/api/typeless/start-mac"
        request.headers = {"X-Dashboard-Token": "secret"}
        response = {}
        request._json = lambda status, body: response.update(status=status, body=body)
        request.do_POST()
        self.assertEqual(response["status"], 200)
        self.assertEqual(
            response["body"], {"ok": True, "active": True, "pending": True}
        )

    def test_device_view_uses_compact_snapshot_without_changing_full_route(self):
        class State:
            def snapshot(self):
                return {"ok": True, "view": "full"}

            def device_snapshot(self):
                return {"ok": True, "view": "device"}

        handler = build_handler(State(), "secret")

        def request(path):
            instance = handler.__new__(handler)
            instance.path = path
            instance.headers = {"X-Dashboard-Token": "secret"}
            instance.client_address = ("127.0.0.1", 1234)
            response = {}
            instance._json = lambda status, body: response.update(status=status, body=body)
            instance.do_GET()
            return response

        self.assertEqual(request("/api/state")["body"]["view"], "full")
        self.assertEqual(
            request("/api/state?view=device")["body"]["view"], "device"
        )


if __name__ == "__main__":
    unittest.main()

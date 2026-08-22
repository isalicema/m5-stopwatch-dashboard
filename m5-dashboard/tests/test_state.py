import unittest

from bridge.state import DashboardState


class DashboardStateTests(unittest.TestCase):
    def test_dashboard_snapshots_ticktick_independently(self):
        state = DashboardState("Air")
        value = {
            "connected": True,
            "stopwatch": {"state": "running", "elapsed_seconds": 42},
            "countdown": {"state": "idle", "duration_seconds": 1500, "remaining_seconds": 1500},
        }
        state.set_ticktick(value)
        value["stopwatch"]["elapsed_seconds"] = 999
        self.assertEqual(state.snapshot()["ticktick"]["stopwatch"]["elapsed_seconds"], 42)

    def test_dashboard_snapshots_claude_independently(self):
        state = DashboardState("Air")
        value = {"connected": True, "today_tokens": 123, "lifetime_tokens": 456}
        state.set_claude(value)
        value["today_tokens"] = 999

        snapshot = state.snapshot()
        self.assertEqual(snapshot["claude"]["today_tokens"], 123)
        self.assertEqual(snapshot["claude"]["lifetime_tokens"], 456)
        self.assertIn("codex", snapshot)

    def test_dashboard_snapshots_ai_hotspot_and_obsidian_independently(self):
        state = DashboardState("Air")
        hotspot = {"active": True, "alert": {"title": "GPT-6 正式发布"}}
        obsidian = {"available_count": 12, "selected": {"title": "幸运笔记"}}
        state.set_ai_hotspot(hotspot)
        state.set_obsidian(obsidian)
        hotspot["alert"]["title"] = "changed"
        obsidian["selected"]["title"] = "changed"

        snapshot = state.snapshot()
        self.assertEqual(snapshot["ai_hotspot"]["alert"]["title"], "GPT-6 正式发布")
        self.assertEqual(snapshot["obsidian"]["selected"]["title"], "幸运笔记")

    def test_dashboard_snapshots_ai_usage_independently(self):
        state = DashboardState("Air")
        usage = {
            "connected": True,
            "complete": True,
            "today_total_tokens": 518_089_323,
            "channels": [{"id": "codex", "tokens": 517_407_867}],
        }
        state.set_ai_usage(usage)
        usage["channels"][0]["tokens"] = 0

        snapshot = state.snapshot()
        self.assertEqual(snapshot["ai_usage"]["today_total_tokens"], 518_089_323)
        self.assertEqual(snapshot["ai_usage"]["channels"][0]["tokens"], 517_407_867)

    def test_usage_board_enriches_provider_tokens_quota_and_online_state(self):
        state = DashboardState("Air")
        state.set_codex({"connected": False, "limits": [], "usage": {}})
        state.set_claude(
            {
                "connected": True,
                "today_tokens": 0,
                "short_used_percent": -1,
                "week_used_percent": -1,
            }
        )
        state.set_ai_usage(
            {
                "connected": True,
                "channels": [
                    {"id": "codex", "tokens": 500},
                    {"id": "claude", "tokens": 400},
                ],
                "provider_quotas": {
                    "codex": {
                        "status": "online",
                        "windows": [
                            {
                                "label": "7天",
                                "window_seconds": 604800,
                                "used_percent": 20,
                                "resets_at": 9999,
                            }
                        ],
                    },
                    "claude": {
                        "status": "online",
                        "windows": [
                            {
                                "label": "7天",
                                "window_seconds": 604800,
                                "used_percent": 87,
                                "resets_at": 0,
                            }
                        ],
                    },
                },
            }
        )

        snapshot = state.snapshot()
        self.assertTrue(snapshot["codex"]["connected"])
        self.assertEqual(snapshot["codex"]["usage"]["today_tokens"], 500)
        self.assertEqual(snapshot["codex"]["limits"][0]["used_percent"], 20)
        self.assertEqual(snapshot["claude"]["today_tokens"], 400)
        self.assertEqual(snapshot["claude"]["week_used_percent"], 87)


if __name__ == "__main__":
    unittest.main()

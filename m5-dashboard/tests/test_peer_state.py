import io
import json
import unittest
from unittest.mock import Mock, patch

from bridge.peer_state import (
    fetch_peer_state,
    merge_provider_states,
    normalize_peer_snapshot,
    resolve_peer_auth,
)
from bridge.state import DashboardState


class PeerStateTests(unittest.TestCase):
    def test_merges_live_state_without_replacing_local_usage_or_limits(self):
        local = {
            "connected": True,
            "active_count": 1,
            "waiting_count": 0,
            "error_count": 0,
            "sessions": [
                {"id": "air-1", "title": "本机任务", "status": "working", "updated_at": 100}
            ],
            "transcripts": [
                {"id": "air-1", "title": "本机任务", "status": "working", "updated_at": 100}
            ],
            "results": [{"id": "air-old", "title": "本机完成", "completed_at": 80}],
            "usage": {"today_tokens": 123, "lifetime_tokens": 456},
            "limits": [{"id": "codex", "used_percent": 25}],
            "updated_at": 100,
        }
        peers = [
            {
                "label": "iMac",
                "codex": {
                    "connected": True,
                    "active_count": 2,
                    "waiting_count": 1,
                    "error_count": 0,
                    "sessions": [
                        {
                            "id": "imac-1",
                            "title": "远端任务",
                            "status": "waiting_approval",
                            "updated_at": 120,
                        }
                    ],
                    "transcripts": [
                        {
                            "id": "imac-1",
                            "title": "远端任务",
                            "status": "working",
                            "updated_at": 120,
                            "messages": [{"role": "assistant", "text": "处理中"}],
                        }
                    ],
                    "results": [{"id": "imac-new", "title": "远端完成", "completed_at": 130}],
                    "usage": {"today_tokens": 999999},
                    "limits": [{"id": "wrong"}],
                    "updated_at": 120,
                },
            }
        ]

        merged = merge_provider_states(local, peers, "codex", "Air")

        self.assertEqual(merged["active_count"], 3)
        self.assertEqual(merged["waiting_count"], 1)
        self.assertEqual(merged["usage"], local["usage"])
        self.assertEqual(merged["limits"], local["limits"])
        self.assertEqual(merged["sessions"][0]["title"], "iMac · 远端任务")
        self.assertEqual(merged["transcripts"][0]["title"], "iMac · 远端任务")
        self.assertEqual(merged["transcripts"][1]["title"], "Air · 本机任务")
        self.assertEqual(merged["results"][0]["title"], "iMac · 远端完成")

    def test_dashboard_removes_disconnected_peer_activity_immediately(self):
        state = DashboardState("P2S", device_label="Air", aggregate_peers=True)
        state.set_codex(
            {
                "connected": True,
                "active_count": 0,
                "waiting_count": 0,
                "error_count": 0,
                "sessions": [],
                "transcripts": [],
                "results": [],
                "updated_at": 100,
            }
        )
        state.set_peer_states(
            [
                {
                    "label": "iMac",
                    "codex": {
                        "connected": True,
                        "active_count": 1,
                        "waiting_count": 0,
                        "error_count": 0,
                        "sessions": [],
                        "transcripts": [],
                        "results": [],
                        "updated_at": 120,
                    },
                }
            ]
        )
        self.assertEqual(state.snapshot()["codex"]["active_count"], 1)

        state.set_peer_states([])

        self.assertEqual(state.snapshot()["codex"]["active_count"], 0)

    def test_rejects_unhealthy_peer_response(self):
        with self.assertRaises(ValueError):
            normalize_peer_snapshot({"ok": False}, "iMac")

    @patch("bridge.peer_state.urllib.request.build_opener")
    def test_fetch_uses_dashboard_token_without_system_proxy(self, build_opener):
        opener = Mock()
        opener.open.return_value = io.BytesIO(
            json.dumps({"ok": True, "device_label": "iMac", "codex": {}}).encode()
        )
        build_opener.return_value = opener

        result = fetch_peer_state({"base_url": "http://peer:8765"}, "private-token")

        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_header("X-dashboard-token"), "private-token")
        self.assertEqual(result["label"], "iMac")
        build_opener.assert_called_once()

    def test_resolves_existing_usage_password_only_in_memory(self):
        configured = [
            {
                "base_url": "http://peer:8765",
                "usage_auth_source": "office-usage",
            }
        ]

        resolved = resolve_peer_auth(
            configured,
            [{"id": "office-usage", "password": "private-password"}],
        )

        self.assertNotIn("api_token", configured[0])
        self.assertEqual(resolved[0]["api_token"], "private-password")


if __name__ == "__main__":
    unittest.main()

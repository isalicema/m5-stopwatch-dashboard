import unittest

from bridge.ai_usage_client import normalize_ai_usage, normalize_provider_quotas


class AIUsageTests(unittest.TestCase):
    def test_normalizes_today_total_and_channel_breakdown(self):
        result = normalize_ai_usage(
            {
                "today": {
                    "date": "2026-08-21",
                    "total": 518_089_323,
                    "auth": 21_093_819,
                    "breakdown": {
                        "input": 18_562_729,
                        "output": 2_531_090,
                        "cacheRead": 496_987_338,
                        "cacheWrite": 8_166,
                    },
                },
                "channels": [
                    {"id": "claude", "name": "Claude Code", "daily": [20_480]},
                    {"id": "codex", "name": "Codex", "daily": [517_407_867]},
                    {"id": "kimi", "name": "Kimi Code", "daily": [0]},
                    {"id": "deepseek", "name": "DeepSeek", "daily": [0]},
                    {"id": "openrouter", "name": "OpenRouter", "daily": [660_976]},
                    {"id": "grok", "name": "Grok", "daily": [0]},
                ],
            },
            {"channels": [{"id": "kimi", "state": "degraded"}]},
            expected_date="2026-08-21",
            now=123,
        )

        self.assertIsNotNone(result)
        self.assertTrue(result["connected"])
        self.assertTrue(result["complete"])
        self.assertEqual(result["today_total_tokens"], 518_089_323)
        self.assertEqual(result["today_authoritative_tokens"], 21_093_819)
        self.assertEqual(result["breakdown"]["cache_read"], 496_987_338)
        self.assertFalse(result["approximate"])
        self.assertEqual(result["updated_at"], 123)

    def test_marks_offline_or_approximate_sources(self):
        payload = {
            "today": {"date": "2026-08-21", "total": 10, "auth": 4},
            "channels": [
                {"id": channel, "name": channel, "daily": [10 if channel == "grok" else 0]}
                for channel in ("claude", "codex", "kimi", "deepseek", "openrouter", "grok")
            ],
        }
        result = normalize_ai_usage(
            payload,
            {"channels": [{"id": "openrouter", "state": "offline"}]},
            expected_date="2026-08-21",
        )

        self.assertFalse(result["complete"])
        self.assertTrue(result["approximate"])
        self.assertEqual(result["incomplete_channels"], ["openrouter"])

    def test_rejects_previous_day_payload(self):
        result = normalize_ai_usage(
            {"today": {"date": "2026-08-20"}, "channels": []},
            expected_date="2026-08-21",
        )
        self.assertIsNone(result)

    def test_normalizes_provider_quota_windows_and_reset_deadline(self):
        result = normalize_provider_quotas(
            {
                "channels": [
                    {
                        "id": "codex",
                        "status": "online",
                        "source": "wham",
                        "windows": [
                            {
                                "label": "7天",
                                "windowSec": 604800,
                                "usedPct": 20.4,
                                "resetInSec": 483159,
                            }
                        ],
                    }
                ]
            },
            now=1000,
        )
        self.assertEqual(result["codex"]["windows"][0]["used_percent"], 20)
        self.assertEqual(result["codex"]["windows"][0]["resets_at"], 484159)


if __name__ == "__main__":
    unittest.main()

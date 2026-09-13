from pathlib import Path
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class CompletionLatencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (PROJECT / "firmware/M5Dashboard/M5Dashboard.ino").read_text(
            encoding="utf-8"
        )

    def test_completion_beacon_preserves_the_low_frequency_idle_poll(self):
        self.assertIn("constexpr uint32_t kUsbRequestIntervalMs = 2000;", self.source)
        self.assertNotIn("kActiveAiRequestIntervalMs", self.source)
        start = self.source.index("uint32_t dashboardStateRefreshInterval()")
        end = self.source.index("\n}\n", start)
        function = self.source[start:end]
        self.assertIn("return kUsbRequestIntervalMs;", function)
        self.assertIn("kFocusReconcileRefreshMs", function)

    def test_authenticated_bridge_beacon_triggers_one_immediate_state_fetch(self):
        self.assertIn('"M5DASH_EVENT_V1|completion|"', self.source)
        self.assertIn("sender == activeBridgeHost", self.source)
        self.assertIn("completionFetchPending = true", self.source)
        start = self.source.index("void updateCompletionFetchHint()")
        end = self.source.index("\n}\n", start)
        function = self.source[start:end]
        self.assertIn("sendUsbStateRequest();", function)
        self.assertIn("if (!fetchState()) bridgeOnline = false;", function)

    def test_codex_history_cannot_starve_newer_claude_completions(self):
        start = self.source.index("void appendDashboardResults(")
        end = self.source.index("\n}\n", start)
        function = self.source[start:end]
        self.assertIn("dashboardCompletionReplacementIndex", function)
        self.assertIn("completedAt", function)
        self.assertNotIn("dashboardResults.count >= kMaxDashboardResults", function)


if __name__ == "__main__":
    unittest.main()

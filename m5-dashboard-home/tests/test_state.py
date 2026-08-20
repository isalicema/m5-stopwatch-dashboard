import unittest
from unittest.mock import patch

from bridge.state import DashboardState, deep_merge, normalize_printer_state


class PrinterStateTests(unittest.TestCase):
    def test_delta_reports_preserve_old_fields(self):
        target = {"mc_percent": 20, "ams": {"humidity": 3, "temp": 24}}
        deep_merge(target, {"mc_percent": 21, "ams": {"temp": 25}})
        self.assertEqual(target["mc_percent"], 21)
        self.assertEqual(target["ams"]["humidity"], 3)
        self.assertEqual(target["ams"]["temp"], 25)

    def test_normalizes_printer_values(self):
        value = normalize_printer_state(
            {
                "gcode_state": "RUNNING",
                "mc_percent": "63",
                "mc_remaining_time": 91,
                "nozzle_temper": "220.4",
                "bed_temper": 55,
                "layer_num": 42,
                "total_layer_num": 100,
            },
            True,
            "P2S",
        )
        self.assertTrue(value["connected"])
        self.assertEqual(value["state_label"], "PRINTING")
        self.assertEqual(value["progress"], 63)
        self.assertEqual(value["remaining_min"], 91)
        self.assertEqual(value["nozzle_temp"], 220.4)

    def test_dashboard_accepts_print_envelope(self):
        state = DashboardState("P2S")
        state.merge_printer({"print": {"gcode_state": "PAUSE", "mc_percent": 9}})
        snapshot = state.snapshot()
        self.assertEqual(snapshot["printer"]["state"], "PAUSE")
        self.assertEqual(snapshot["printer"]["progress"], 9)

    def test_idle_cloud_connection_does_not_expire_between_reports(self):
        with patch("bridge.state.time.time", return_value=1000):
            state = DashboardState("P2S")
            state.merge_printer({"print": {"gcode_state": "FINISH", "mc_percent": 100}})
        with patch("bridge.state.time.time", return_value=1600):
            self.assertTrue(state.snapshot()["printer"]["connected"])

        state.set_printer_connected(False)
        with patch("bridge.state.time.time", return_value=1601):
            self.assertFalse(state.snapshot()["printer"]["connected"])

    def test_dashboard_snapshots_claude_independently(self):
        state = DashboardState("P2S")
        value = {"connected": True, "today_tokens": 123, "lifetime_tokens": 456}
        state.set_claude(value)
        value["today_tokens"] = 999

        snapshot = state.snapshot()
        self.assertEqual(snapshot["claude"]["today_tokens"], 123)
        self.assertEqual(snapshot["claude"]["lifetime_tokens"], 456)
        self.assertIn("codex", snapshot)


if __name__ == "__main__":
    unittest.main()

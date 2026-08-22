import json
import unittest
from io import BytesIO
from unittest import mock

from bridge.ticktick_client import TickTickMonitor


def response(value):
    item = mock.MagicMock()
    item.__enter__.return_value = BytesIO(json.dumps(value).encode("utf-8"))
    return item


class TickTickMonitorTests(unittest.TestCase):
    def setUp(self):
        self.states = []
        self.monitor = TickTickMonitor(
            {"base_url": "http://127.0.0.1:8787", "duration_seconds": 1500},
            self.states.append,
        )

    def test_refresh_normalizes_both_timers(self):
        self.monitor._opener.open = mock.Mock(
            side_effect=[
                response({"ok": True, "state": "running", "elapsed_seconds": 81}),
                response({"ok": True, "state": "paused", "duration_seconds": 1500, "remaining_seconds": 900}),
            ]
        )
        value = self.monitor.refresh()
        self.assertTrue(value["connected"])
        self.assertEqual(value["stopwatch"]["elapsed_seconds"], 81)
        self.assertEqual(value["countdown"]["remaining_seconds"], 900)

    def test_starting_countdown_pauses_running_stopwatch_first(self):
        self.monitor.refresh = mock.Mock(
            side_effect=[
                {"stopwatch": {"state": "running"}, "countdown": {"state": "idle"}},
                {"connected": True},
            ]
        )
        self.monitor._request = mock.Mock(return_value={"ok": True})
        self.monitor.perform("countdown-click")
        self.assertEqual(
            self.monitor._request.call_args_list,
            [
                mock.call("/focus/click", {}),
                mock.call("/pomo/start", {"duration_seconds": 1500}),
            ],
        )

    def test_resuming_stopwatch_pauses_running_countdown_first(self):
        self.monitor.refresh = mock.Mock(
            side_effect=[
                {"stopwatch": {"state": "paused"}, "countdown": {"state": "running"}},
                {"connected": True},
            ]
        )
        self.monitor._request = mock.Mock(return_value={"ok": True})
        self.monitor.perform("stopwatch-click")
        self.assertEqual(
            self.monitor._request.call_args_list,
            [mock.call("/pomo/pause", {}), mock.call("/focus/click", {})],
        )


if __name__ == "__main__":
    unittest.main()

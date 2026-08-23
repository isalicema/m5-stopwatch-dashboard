import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock

from bridge.ticktick_client import DailyFocusLedger, TickTickMonitor


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
        self.assertEqual(value["today_focus_seconds"], 681)

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
                mock.call("/focus/click", {}, self.monitor.action_timeout),
                mock.call(
                    "/pomo/start",
                    {"duration_seconds": 1500},
                    self.monitor.action_timeout,
                ),
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
            [
                mock.call("/pomo/pause", {}, self.monitor.action_timeout),
                mock.call("/focus/click", {}, self.monitor.action_timeout),
            ],
        )

    def test_ui_actions_get_a_longer_timeout_than_state_reads(self):
        self.assertEqual(self.monitor.timeout, 2)
        self.assertEqual(self.monitor.action_timeout, 12)


class DailyFocusLedgerTests(unittest.TestCase):
    def test_seeds_visible_sessions_then_accumulates_new_progress_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "daily.json"
            ledger = DailyFocusLedger(str(path))
            stopwatch = {"state": "idle", "elapsed_seconds": 39}
            countdown = {
                "state": "done",
                "duration_seconds": 1500,
                "remaining_seconds": 0,
            }
            self.assertEqual(ledger.update(stopwatch, countdown, "2026-08-22"), 1539)
            self.assertEqual(ledger.update(stopwatch, countdown, "2026-08-22"), 1539)

            reset_countdown = {
                "state": "idle",
                "duration_seconds": 1500,
                "remaining_seconds": 1500,
            }
            self.assertEqual(
                ledger.update({"elapsed_seconds": 0}, reset_countdown, "2026-08-22"),
                1539,
            )
            self.assertEqual(
                ledger.update(
                    {"elapsed_seconds": 120}, reset_countdown, "2026-08-22"
                ),
                1659,
            )
            ledger.flush()
            self.assertEqual(DailyFocusLedger(str(path)).total("2026-08-22"), 1659)

    def test_midnight_rollover_starts_a_clean_day(self):
        ledger = DailyFocusLedger()
        self.assertEqual(
            ledger.update(
                {"elapsed_seconds": 600},
                {"duration_seconds": 1500, "remaining_seconds": 900},
                "2026-08-22",
            ),
            1200,
        )
        self.assertEqual(
            ledger.update(
                {"elapsed_seconds": 600},
                {"duration_seconds": 1500, "remaining_seconds": 900},
                "2026-08-23",
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()

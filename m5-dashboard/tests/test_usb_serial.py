import errno
import json
import os
import select
import threading
import time
import unittest
from io import BytesIO
from unittest import mock

from bridge.usb_serial import (
    USB_REQUEST_PREFIX,
    USB_ACTION_PREFIX,
    USB_PAIR_REQUEST_PREFIX,
    USB_PAIR_RESPONSE_PREFIX,
    USB_RESPONSE_PREFIX,
    USB_DIAGNOSTIC_PREFIX,
    UsbSnapshotSource,
    UsbSerialResponder,
    _write_all,
    build_response,
    diagnostic_text,
    diagnostic_trigger,
    build_pair_response,
    parse_pair_request,
    parse_diagnostic,
    parse_request,
    parse_action_request,
)


class UsbSerialProtocolTests(unittest.TestCase):
    def test_upstream_snapshot_requests_device_view_and_falls_back_locally(self):
        source = UsbSnapshotSource(
            lambda: {"ok": True, "device_label": "iMac"},
            {
                "base_url": "http://air.local:8765",
                "api_token": "private",
                "timeout_seconds": 1,
            },
        )
        response = mock.MagicMock()
        response.__enter__.return_value = BytesIO(
            json.dumps({"ok": True, "weather": {"available": True}}).encode("utf-8")
        )
        opener = mock.MagicMock()
        opener.open.return_value = response
        with mock.patch("bridge.usb_serial.urllib.request.build_opener", return_value=opener):
            self.assertEqual(source(), {"ok": True, "weather": {"available": True}})
        requested_url = opener.open.call_args.args[0].full_url
        self.assertEqual(requested_url, "http://air.local:8765/api/state?view=device")
        opener.open.side_effect = OSError("offline")
        with mock.patch("bridge.usb_serial.urllib.request.build_opener", return_value=opener):
            self.assertEqual(source(), {"ok": True, "device_label": "iMac"})

    def test_protocol_constants_are_ascii_and_versioned(self):
        self.assertEqual(USB_REQUEST_PREFIX, b"M5DASH_USB_V1|GET|")
        self.assertEqual(USB_ACTION_PREFIX, b"M5DASH_USB_V1|POST|")
        self.assertEqual(USB_PAIR_REQUEST_PREFIX, b"M5DASH_USB_V1|PAIR|")
        self.assertEqual(USB_PAIR_RESPONSE_PREFIX, b"M5DASH_USB_V1|PAIRED|")
        self.assertEqual(USB_RESPONSE_PREFIX, b"M5DASH_USB_V1|OK|")
        self.assertEqual(USB_DIAGNOSTIC_PREFIX, b"M5DASH_USB_V1|DIAG|")

    def test_reset_diagnostic_accepts_only_bounded_numeric_fields(self):
        self.assertEqual(
            parse_diagnostic(USB_DIAGNOSTIC_PREFIX + b"7|204|2"),
            (7, 204, 2),
        )
        self.assertIsNone(parse_diagnostic(USB_DIAGNOSTIC_PREFIX + b"7|204|Codex"))
        self.assertIsNone(parse_diagnostic(USB_DIAGNOSTIC_PREFIX + b"99|204|2"))
        self.assertIsNone(parse_diagnostic(USB_DIAGNOSTIC_PREFIX + b"7|1000|2"))

    def test_panic_capture_never_logs_dashboard_protocol_or_token(self):
        self.assertTrue(diagnostic_trigger(b"Guru Meditation Error: Core 1 panic'ed"))
        self.assertTrue(diagnostic_trigger(b"Backtrace: 0x42001234:0x3fca0000"))
        secret = USB_REQUEST_PREFIX + b"do-not-log-this-token"
        self.assertFalse(diagnostic_trigger(secret))
        self.assertEqual(diagnostic_text(secret), "")
        self.assertEqual(
            diagnostic_text(b"Backtrace: 0x42001234\xff"),
            "Backtrace: 0x42001234?",
        )

    def test_pairing_accepts_a_physical_device_id_and_urlsafe_token(self):
        self.assertEqual(parse_pair_request(USB_PAIR_REQUEST_PREFIX + b"M5-ABC123"), "M5-ABC123")
        self.assertIsNone(parse_pair_request(USB_PAIR_REQUEST_PREFIX + b"bad device"))
        token = "abcdefghijklmnopqrstuvwxyz_123456"
        self.assertEqual(build_pair_response(token), USB_PAIR_RESPONSE_PREFIX + token.encode() + b"\n")
        with self.assertRaises(ValueError):
            build_pair_response("too-short")

    def test_request_requires_matching_token(self):
        self.assertTrue(parse_request(USB_REQUEST_PREFIX + b"secret-token", "secret-token"))
        self.assertFalse(parse_request(USB_REQUEST_PREFIX + b"wrong-token", "secret-token"))
        self.assertFalse(parse_request(b"unrelated", "secret-token"))

    def test_action_request_requires_token_and_known_action(self):
        self.assertEqual(
            parse_action_request(USB_ACTION_PREFIX + b"secret-token|stopwatch-click", "secret-token"),
            "stopwatch-click",
        )
        self.assertEqual(
            parse_action_request(USB_ACTION_PREFIX + b"secret-token|ai-ack", "secret-token"),
            "ai-ack",
        )
        self.assertEqual(
            parse_action_request(USB_ACTION_PREFIX + b"secret-token|obsidian-roll", "secret-token"),
            "obsidian-roll",
        )
        self.assertEqual(
            parse_action_request(USB_ACTION_PREFIX + b"secret-token|typeless-start", "secret-token"),
            "typeless-start",
        )
        self.assertEqual(
            parse_action_request(USB_ACTION_PREFIX + b"secret-token|typeless-stop", "secret-token"),
            "typeless-stop",
        )
        self.assertIsNone(parse_action_request(USB_ACTION_PREFIX + b"wrong|stopwatch-click", "secret-token"))
        self.assertIsNone(parse_action_request(USB_ACTION_PREFIX + b"secret-token|unknown", "secret-token"))

    def test_response_is_compact_single_line_json(self):
        snapshot = {"ok": True, "ticktick": {"stopwatch": {"state": "idle"}}}
        response = build_response(snapshot)
        self.assertTrue(response.startswith(USB_RESPONSE_PREFIX))
        self.assertEqual(response.count(b"\n"), 1)
        payload = response[len(USB_RESPONSE_PREFIX) : -1]
        self.assertEqual(json.loads(payload), snapshot)

    def test_nonblocking_large_write_waits_until_serial_is_writable(self):
        writes = []

        def write(_fd, remaining):
            writes.append(bytes(remaining))
            if len(writes) == 1:
                return 2
            if len(writes) == 2:
                raise BlockingIOError(errno.EAGAIN, "temporarily unavailable")
            return len(remaining)

        with mock.patch("bridge.usb_serial.os.write", side_effect=write), mock.patch(
            "bridge.usb_serial.select.select", return_value=([], [7], [])
        ) as wait_for_writable:
            _write_all(7, b"large-response")

        self.assertEqual(writes, [b"large-response", b"rge-response", b"rge-response"])
        wait_for_writable.assert_called_once_with([], [7], [], 0.5)

    def test_responder_round_trip_over_pseudo_terminal(self):
        master_fd, slave_fd = os.openpty()
        slave_name = os.ttyname(slave_fd)
        responder = UsbSerialResponder(lambda: {"ok": True}, "secret-token")
        thread = threading.Thread(target=responder._serve, args=(slave_name,), daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 2
            while responder._fd is None and time.monotonic() < deadline:
                time.sleep(0.01)
            time.sleep(0.05)
            os.write(master_fd, USB_REQUEST_PREFIX + b"secret-token\n")
            readable, _, _ = select.select([master_fd], [], [], 2)
            self.assertTrue(readable)
            response = os.read(master_fd, 4096)
            self.assertTrue(response.startswith(USB_RESPONSE_PREFIX))
            self.assertEqual(json.loads(response[len(USB_RESPONSE_PREFIX) :]), {"ok": True})
            self.assertEqual(responder.notify_state(), {"usb_pushed": True})
            readable, _, _ = select.select([master_fd], [], [], 2)
            self.assertTrue(readable)
            pushed = os.read(master_fd, 4096)
            self.assertTrue(pushed.startswith(USB_RESPONSE_PREFIX))
        finally:
            responder.stop()
            thread.join(timeout=2)
            os.close(master_fd)
            os.close(slave_fd)

    def test_responder_pairs_then_authenticates_over_pseudo_terminal(self):
        master_fd, slave_fd = os.openpty()
        slave_name = os.ttyname(slave_fd)
        token = "abcdefghijklmnopqrstuvwxyz_123456"
        responder = UsbSerialResponder(lambda: {"ok": True}, token)
        thread = threading.Thread(target=responder._serve, args=(slave_name,), daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 2
            while responder._fd is None and time.monotonic() < deadline:
                time.sleep(0.01)
            time.sleep(0.05)
            os.write(master_fd, USB_PAIR_REQUEST_PREFIX + b"M5-ABC123\n")
            readable, _, _ = select.select([master_fd], [], [], 2)
            self.assertTrue(readable)
            self.assertEqual(os.read(master_fd, 4096), build_pair_response(token))
            os.write(master_fd, USB_REQUEST_PREFIX + token.encode() + b"\n")
            readable, _, _ = select.select([master_fd], [], [], 2)
            self.assertTrue(readable)
            self.assertTrue(os.read(master_fd, 4096).startswith(USB_RESPONSE_PREFIX))
        finally:
            responder.stop()
            thread.join(timeout=2)
            os.close(master_fd)
            os.close(slave_fd)


if __name__ == "__main__":
    unittest.main()

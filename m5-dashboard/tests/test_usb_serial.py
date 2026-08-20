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
    USB_RESPONSE_PREFIX,
    UsbSnapshotSource,
    UsbSerialResponder,
    _write_all,
    build_response,
    parse_request,
)


class UsbSerialProtocolTests(unittest.TestCase):
    def test_upstream_snapshot_preserves_full_state_and_falls_back_locally(self):
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
        opener.open.side_effect = OSError("offline")
        with mock.patch("bridge.usb_serial.urllib.request.build_opener", return_value=opener):
            self.assertEqual(source(), {"ok": True, "device_label": "iMac"})

    def test_protocol_constants_are_ascii_and_versioned(self):
        self.assertEqual(USB_REQUEST_PREFIX, b"M5DASH_USB_V1|GET|")
        self.assertEqual(USB_RESPONSE_PREFIX, b"M5DASH_USB_V1|OK|")

    def test_request_requires_matching_token(self):
        self.assertTrue(parse_request(USB_REQUEST_PREFIX + b"secret-token", "secret-token"))
        self.assertFalse(parse_request(USB_REQUEST_PREFIX + b"wrong-token", "secret-token"))
        self.assertFalse(parse_request(b"unrelated", "secret-token"))

    def test_response_is_compact_single_line_json(self):
        snapshot = {"ok": True, "printer": {"state_label": "空闲"}}
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
        finally:
            responder.stop()
            thread.join(timeout=2)
            os.close(master_fd)
            os.close(slave_fd)


if __name__ == "__main__":
    unittest.main()

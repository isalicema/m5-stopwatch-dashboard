import json
import os
import select
import threading
import time
import unittest

from bridge.usb_serial import (
    USB_REQUEST_PREFIX,
    USB_PAIR_REQUEST_PREFIX,
    USB_PAIR_RESPONSE_PREFIX,
    USB_RESPONSE_PREFIX,
    UsbSerialResponder,
    build_response,
    build_pair_response,
    parse_pair_request,
    parse_request,
)


class UsbSerialProtocolTests(unittest.TestCase):
    def test_protocol_constants_are_ascii_and_versioned(self):
        self.assertEqual(USB_REQUEST_PREFIX, b"M5DASH_USB_V1|GET|")
        self.assertEqual(USB_PAIR_REQUEST_PREFIX, b"M5DASH_USB_V1|PAIR|")
        self.assertEqual(USB_PAIR_RESPONSE_PREFIX, b"M5DASH_USB_V1|PAIRED|")
        self.assertEqual(USB_RESPONSE_PREFIX, b"M5DASH_USB_V1|OK|")

    def test_pair_request_returns_the_local_token(self):
        token = "abcdefghijklmnopqrstuvwxyz_123456"
        self.assertEqual(parse_pair_request(USB_PAIR_REQUEST_PREFIX + b"M5-ABC123"), "M5-ABC123")
        self.assertEqual(build_pair_response(token), USB_PAIR_RESPONSE_PREFIX + token.encode() + b"\n")

    def test_request_requires_matching_token(self):
        self.assertTrue(parse_request(USB_REQUEST_PREFIX + b"secret-token", "secret-token"))
        self.assertFalse(parse_request(USB_REQUEST_PREFIX + b"wrong-token", "secret-token"))
        self.assertFalse(parse_request(b"unrelated", "secret-token"))

    def test_response_is_compact_single_line_json(self):
        snapshot = {"ok": True, "ticktick": {"stopwatch": {"state": "idle"}}}
        response = build_response(snapshot)
        self.assertTrue(response.startswith(USB_RESPONSE_PREFIX))
        self.assertEqual(response.count(b"\n"), 1)
        payload = response[len(USB_RESPONSE_PREFIX) : -1]
        self.assertEqual(json.loads(payload), snapshot)

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

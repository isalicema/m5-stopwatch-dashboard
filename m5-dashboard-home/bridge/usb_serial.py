from __future__ import annotations

import glob
import hmac
import json
import os
import select
import termios
import threading
from typing import Any, Callable, Dict, Optional


USB_REQUEST_PREFIX = b"M5DASH_USB_V1|GET|"
USB_PAIR_REQUEST_PREFIX = b"M5DASH_USB_V1|PAIR|"
USB_PAIR_RESPONSE_PREFIX = b"M5DASH_USB_V1|PAIRED|"
USB_RESPONSE_PREFIX = b"M5DASH_USB_V1|OK|"
USB_ERROR_RESPONSE = b"M5DASH_USB_V1|ERR|unauthorized\n"
MAX_REQUEST_BYTES = 512
MAX_RESPONSE_BYTES = 32768


def parse_request(line: bytes, api_token: str) -> bool:
    if not line.startswith(USB_REQUEST_PREFIX):
        return False
    supplied = line[len(USB_REQUEST_PREFIX) :].decode("utf-8", errors="replace")
    return hmac.compare_digest(supplied, api_token)


def parse_pair_request(line: bytes) -> Optional[str]:
    if not line.startswith(USB_PAIR_REQUEST_PREFIX):
        return None
    device_id = line[len(USB_PAIR_REQUEST_PREFIX) :].decode("ascii", errors="ignore")
    if not device_id or len(device_id) > 64:
        return None
    if any(not (character.isalnum() or character in "-_:.") for character in device_id):
        return None
    return device_id


def build_pair_response(api_token: str) -> bytes:
    encoded = api_token.encode("ascii", errors="strict")
    if not 16 <= len(encoded) <= 128 or any(
        not (byte in b"-_" or 48 <= byte <= 57 or 65 <= byte <= 90 or 97 <= byte <= 122)
        for byte in encoded
    ):
        raise ValueError("USB pairing requires a 16-128 character URL-safe token")
    return USB_PAIR_RESPONSE_PREFIX + encoded + b"\n"


def build_response(snapshot: Dict[str, Any]) -> bytes:
    payload = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ValueError("USB dashboard response is too large")
    return USB_RESPONSE_PREFIX + payload + b"\n"


def serial_ports() -> list[str]:
    patterns = ("/dev/cu.usbmodem*", "/dev/cu.usbserial*", "/dev/cu.SLAB_USBtoUART*")
    return sorted({item for pattern in patterns for item in glob.glob(pattern)})


def _configure_port(fd: int) -> None:
    attributes = termios.tcgetattr(fd)
    attributes[0] = 0
    attributes[1] = 0
    attributes[2] = (
        (attributes[2] & ~(termios.CSIZE | termios.PARENB | termios.CSTOPB))
        | termios.CS8
        | termios.CREAD
        | termios.CLOCAL
    )
    attributes[3] = 0
    attributes[4] = termios.B115200
    attributes[5] = termios.B115200
    attributes[6][termios.VMIN] = 0
    attributes[6][termios.VTIME] = 5
    termios.tcsetattr(fd, termios.TCSANOW, attributes)
    termios.tcflush(fd, termios.TCIOFLUSH)


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("USB serial write returned no data")
        view = view[written:]


class UsbSerialResponder(threading.Thread):
    """Serve authenticated dashboard snapshots over the M5 native USB CDC port."""

    daemon = True

    def __init__(self, snapshot: Callable[[], Dict[str, Any]], api_token: str) -> None:
        super().__init__(name="m5-dashboard-usb")
        self.snapshot = snapshot
        self.api_token = api_token
        self._stop_event = threading.Event()
        self._fd: Optional[int] = None

    def stop(self) -> None:
        self._stop_event.set()
        fd = self._fd
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
            self._fd = None

    def _serve(self, port: str) -> None:
        fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        self._fd = fd
        buffer = bytearray()
        authenticated = False
        try:
            _configure_port(fd)
            print("M5 USB bridge opened %s" % port, flush=True)
            while not self._stop_event.is_set():
                try:
                    readable, _, _ = select.select([fd], [], [], 0.5)
                except OSError:
                    if self._stop_event.is_set():
                        break
                    raise
                if not readable:
                    continue
                try:
                    chunk = os.read(fd, 1024)
                except OSError:
                    if self._stop_event.is_set():
                        break
                    raise
                if not chunk:
                    raise OSError("USB serial port disconnected")
                buffer.extend(chunk)
                while b"\n" in buffer:
                    raw, _, remainder = buffer.partition(b"\n")
                    buffer = bytearray(remainder)
                    line = raw.rstrip(b"\r")
                    device_id = parse_pair_request(line)
                    if device_id is not None:
                        _write_all(fd, build_pair_response(self.api_token))
                        print("M5 USB dashboard paired with %s" % device_id, flush=True)
                    elif parse_request(line, self.api_token):
                        if not authenticated:
                            print("M5 USB dashboard client authenticated", flush=True)
                            authenticated = True
                        _write_all(fd, build_response(self.snapshot()))
                    elif line.startswith(USB_REQUEST_PREFIX):
                        _write_all(fd, USB_ERROR_RESPONSE)
                if len(buffer) > MAX_REQUEST_BYTES:
                    buffer.clear()
        finally:
            if self._fd == fd:
                self._fd = None
            try:
                os.close(fd)
            except OSError:
                pass

    def run(self) -> None:
        while not self._stop_event.is_set():
            found_port = False
            for port in serial_ports():
                found_port = True
                if self._stop_event.is_set():
                    break
                try:
                    self._serve(port)
                except OSError:
                    continue
            self._stop_event.wait(0.5 if found_port else 1.0)

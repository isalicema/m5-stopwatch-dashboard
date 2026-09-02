from __future__ import annotations

import glob
import hmac
import json
import os
import select
import termios
import threading
import urllib.request
from typing import Any, Callable, Dict, Optional

from .ticktick_client import ACTIONS


USB_REQUEST_PREFIX = b"M5DASH_USB_V1|GET|"
USB_ACTION_PREFIX = b"M5DASH_USB_V1|POST|"
USB_PAIR_REQUEST_PREFIX = b"M5DASH_USB_V1|PAIR|"
USB_PAIR_RESPONSE_PREFIX = b"M5DASH_USB_V1|PAIRED|"
USB_RESPONSE_PREFIX = b"M5DASH_USB_V1|OK|"
USB_DIAGNOSTIC_PREFIX = b"M5DASH_USB_V1|DIAG|"
USB_ERROR_RESPONSE = b"M5DASH_USB_V1|ERR|unauthorized\n"
MAX_REQUEST_BYTES = 512
MAX_RESPONSE_BYTES = 32768
MAX_DIAGNOSTIC_LINE_BYTES = 768
DIAGNOSTIC_FOLLOW_LINES = 24
DASHBOARD_PROTOCOL_PREFIX = b"M5DASH_USB_V1|"
PANIC_MARKERS = (
    b"Guru Meditation Error",
    b"assert failed:",
    b"abort() was called",
    b"Backtrace:",
    b"Stack smashing protect failure",
    b"CORRUPT HEAP",
    b"watchdog timeout",
)
DASHBOARD_ACTIONS = set(ACTIONS) | {
    "ai-ack",
    "ai-open",
    "obsidian-roll",
    "obsidian-open",
    "typeless-start",
    "typeless-stop",
}


class UsbSnapshotSource:
    """Use a device-sized upstream dashboard state, with local state as fallback."""

    def __init__(
        self, local_snapshot: Callable[[], Dict[str, Any]], upstream: Optional[Dict[str, Any]]
    ) -> None:
        self.local_snapshot = local_snapshot
        self.upstream = upstream if isinstance(upstream, dict) else {}

    def __call__(self) -> Dict[str, Any]:
        base_url = str(self.upstream.get("base_url") or "").rstrip("/")
        api_token = str(self.upstream.get("api_token") or "")
        if not base_url or not api_token:
            return self.local_snapshot()
        timeout = max(0.2, min(5.0, float(self.upstream.get("timeout_seconds", 2))))
        request = urllib.request.Request(
            base_url + str(self.upstream.get("state_path") or "/api/state?view=device"),
            headers={"X-Dashboard-Token": api_token},
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(request, timeout=timeout) as response:
                payload = json.load(response)
            if not isinstance(payload, dict) or payload.get("ok") is not True:
                raise ValueError("upstream dashboard state is not healthy")
            return payload
        except (OSError, ValueError, json.JSONDecodeError):
            return self.local_snapshot()


def parse_request(line: bytes, api_token: str) -> bool:
    if not line.startswith(USB_REQUEST_PREFIX):
        return False
    supplied = line[len(USB_REQUEST_PREFIX) :].decode("utf-8", errors="replace")
    return hmac.compare_digest(supplied, api_token)


def parse_action_request(line: bytes, api_token: str) -> Optional[str]:
    if not line.startswith(USB_ACTION_PREFIX):
        return None
    fields = line[len(USB_ACTION_PREFIX) :].decode("utf-8", errors="replace").split("|", 1)
    if len(fields) != 2 or not hmac.compare_digest(fields[0], api_token):
        return None
    return fields[1] if fields[1] in DASHBOARD_ACTIONS else None


def parse_pair_request(line: bytes) -> Optional[str]:
    """Accept a first-use request only from the physical USB CDC channel."""
    if not line.startswith(USB_PAIR_REQUEST_PREFIX):
        return None
    device_id = line[len(USB_PAIR_REQUEST_PREFIX) :].decode("ascii", errors="ignore")
    if not device_id or len(device_id) > 64:
        return None
    if any(not (character.isalnum() or character in "-_:.") for character in device_id):
        return None
    return device_id


def parse_diagnostic(line: bytes) -> Optional[tuple[int, int, int]]:
    """Accept only three bounded integers; diagnostics never contain user data."""
    if not line.startswith(USB_DIAGNOSTIC_PREFIX):
        return None
    fields = line[len(USB_DIAGNOSTIC_PREFIX) :].split(b"|")
    if len(fields) != 3 or any(not field.isdigit() for field in fields):
        return None
    reset_reason, render_stage, page = (int(field) for field in fields)
    if reset_reason > 32 or render_stage > 999 or page > 7:
        return None
    return reset_reason, render_stage, page


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
    # Do not discard input here: after a device fault the short-lived ROM CDC
    # port may already contain the panic reason and backtrace when macOS opens it.
    # Dropping pending output is enough to prevent stale host writes.
    termios.tcflush(fd, termios.TCOFLUSH)


def diagnostic_trigger(line: bytes) -> bool:
    return not line.startswith(DASHBOARD_PROTOCOL_PREFIX) and any(
        marker in line for marker in PANIC_MARKERS
    )


def diagnostic_text(line: bytes) -> str:
    if line.startswith(DASHBOARD_PROTOCOL_PREFIX):
        return ""
    clipped = line[:MAX_DIAGNOSTIC_LINE_BYTES]
    return "".join(chr(byte) if byte == 9 or 32 <= byte <= 126 else "?" for byte in clipped)


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        try:
            written = os.write(fd, view)
        except BlockingIOError:
            _, writable, _ = select.select([], [fd], [], 0.5)
            if not writable:
                raise TimeoutError("USB serial write timed out")
            continue
        if written <= 0:
            raise OSError("USB serial write returned no data")
        view = view[written:]


class UsbSerialResponder(threading.Thread):
    """Serve authenticated dashboard snapshots over the M5 native USB CDC port."""

    daemon = True

    def __init__(
        self,
        snapshot: Callable[[], Dict[str, Any]],
        api_token: str,
        action: Optional[Callable[[str], Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(name="m5-dashboard-usb")
        self.snapshot = snapshot
        self.api_token = api_token
        self.action = action
        self._stop_event = threading.Event()
        self._fd: Optional[int] = None
        self._authenticated = False
        self._write_lock = threading.Lock()

    def _send(self, fd: int, payload: bytes) -> None:
        with self._write_lock:
            _write_all(fd, payload)

    def notify_state(self) -> Dict[str, Any]:
        """Push one fresh snapshot over an already authenticated USB session."""
        fd = self._fd
        if fd is None or not self._authenticated:
            return {"usb_pushed": False}
        try:
            self._send(fd, build_response(self.snapshot()))
            return {"usb_pushed": True}
        except (OSError, ValueError):
            return {"usb_pushed": False}

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
        self._authenticated = False
        diagnostic_lines_remaining = 0
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
                    diagnostic = parse_diagnostic(line)
                    action = parse_action_request(line, self.api_token)
                    if diagnostic is not None:
                        print(
                            "M5 USB reset diagnostic reason=%d stage=%d page=%d"
                            % diagnostic,
                            flush=True,
                        )
                    elif device_id is not None:
                        self._send(fd, build_pair_response(self.api_token))
                        print("M5 USB dashboard paired with %s" % device_id, flush=True)
                    elif action is not None and self.action is not None:
                        print("M5 USB action received %s" % action, flush=True)
                        try:
                            self.action(action)
                            self._send(fd, build_response(self.snapshot()))
                            print("M5 USB action completed %s" % action, flush=True)
                        except (OSError, ValueError) as exc:
                            print(
                                "M5 USB action failed %s: %s" % (action, exc),
                                flush=True,
                            )
                            self._send(fd, b"M5DASH_USB_V1|ERR|action\n")
                    elif parse_request(line, self.api_token):
                        if not authenticated:
                            print("M5 USB dashboard client authenticated", flush=True)
                            authenticated = True
                            self._authenticated = True
                        self._send(fd, build_response(self.snapshot()))
                    elif line.startswith((USB_REQUEST_PREFIX, USB_ACTION_PREFIX)):
                        if line.startswith(USB_ACTION_PREFIX):
                            print("M5 USB action rejected", flush=True)
                        self._send(fd, USB_ERROR_RESPONSE)
                    elif diagnostic_trigger(line):
                        diagnostic_lines_remaining = DIAGNOSTIC_FOLLOW_LINES
                        print("M5 USB panic: %s" % diagnostic_text(line), flush=True)
                    elif diagnostic_lines_remaining > 0:
                        text = diagnostic_text(line)
                        if text:
                            print("M5 USB panic: %s" % text, flush=True)
                        diagnostic_lines_remaining -= 1
                if len(buffer) > MAX_REQUEST_BYTES:
                    buffer.clear()
        finally:
            if self._fd == fd:
                self._fd = None
            self._authenticated = False
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

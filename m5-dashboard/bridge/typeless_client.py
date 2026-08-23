from __future__ import annotations

import subprocess
import threading
import time
from queue import Queue
from pathlib import Path
from typing import Any, Dict


SHORTCUTS = {"fn", "ctrl-cmd-shift-space"}
ACTIONS = {"start", "stop"}
AUDIO_MODES = {"m5", "system"}


class TypelessController:
    """Run a Stopwatch-owned Typeless session without stealing the Mac mic."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.helper = Path(str(config.get("helper_path") or "")).expanduser()
        self.audio_helper = Path(str(config.get("audio_helper_path") or "")).expanduser()
        self.shortcut = str(config.get("shortcut") or "ctrl-cmd-shift-space")
        if self.shortcut not in SHORTCUTS:
            raise ValueError("unsupported Typeless shortcut: %s" % self.shortcut)
        self.timeout = max(1, min(15, int(config.get("command_timeout_seconds", 5))))
        self.startup_delay = max(
            0.2, min(3.0, float(config.get("startup_delay_seconds", 1.0)))
        )
        self.lock = threading.Lock()
        # Typeless exposes a toggle shortcut rather than separate start/stop
        # commands. Track only shortcuts successfully sent by this controller
        # so a lost start can never turn a later stop into an accidental start.
        self.active = False
        self.active_audio_mode: str | None = None
        self.previous_input: str | None = None
        self.request_lock = threading.Lock()
        self.desired_active = False
        self.commands: Queue[tuple[str, str]] = Queue()
        self.worker: threading.Thread | None = None

    def _run_commands(self) -> None:
        while True:
            action, audio_mode = self.commands.get()
            try:
                self.perform(action, audio_mode)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                print("Typeless %s failed: %s" % (action, exc), flush=True)
            finally:
                self.commands.task_done()

    def request(self, action: str, audio_mode: str = "m5") -> Dict[str, Any]:
        """Queue a desired state change and acknowledge the watch immediately."""
        if action not in ACTIONS:
            raise ValueError("unsupported Typeless action: %s" % action)
        if audio_mode not in AUDIO_MODES:
            raise ValueError("unsupported Typeless audio mode: %s" % audio_mode)
        if not self.helper.is_file() or not self.helper.stat().st_mode & 0o111:
            raise ValueError("Typeless key helper is not installed")

        desired_active = action == "start"
        with self.request_lock:
            if self.desired_active == desired_active:
                return {"active": desired_active, "pending": not self.commands.empty()}
            self.desired_active = desired_active
            if self.worker is None:
                self.worker = threading.Thread(
                    target=self._run_commands,
                    name="m5-typeless-actions",
                    daemon=True,
                )
                self.worker.start()
            self.commands.put((action, audio_mode))
        return {"active": desired_active, "pending": True}

    def _is_running(self) -> bool:
        completed = subprocess.run(
            ["/usr/bin/pgrep", "-x", "Typeless"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return completed.returncode == 0

    def _ensure_ready(self) -> None:
        if self._is_running():
            return
        subprocess.run(
            ["/usr/bin/open", "-gj", "-a", "Typeless"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if self._is_running():
                # Process creation happens before Typeless registers its global
                # shortcut. Give Electron's main process a short readiness window.
                time.sleep(self.startup_delay)
                return
            time.sleep(0.1)
        raise ValueError("Typeless did not finish launching")

    def _shortcut_command(self) -> list[str]:
        # Execute the signed helper itself so its exit status reaches the
        # Bridge. LaunchServices only reports that the app launch was accepted;
        # it hides a later Accessibility denial and caused a false HTTP 200.
        return [str(self.helper), self.shortcut]

    def _capture_audio_input(self) -> str:
        if not self.audio_helper.is_file() or not self.audio_helper.stat().st_mode & 0o111:
            raise ValueError("M5 audio input helper is not installed")
        completed = subprocess.run(
            [str(self.audio_helper), "capture"],
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        device = completed.stdout.strip()
        if completed.returncode != 0 or not device.isdecimal():
            detail = (completed.stderr or completed.stdout or "").strip()
            raise ValueError(detail or "M5 microphone is unavailable")
        return device

    def _restore_audio_input(self, device: str) -> None:
        completed = subprocess.run(
            [str(self.audio_helper), "restore", device],
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise ValueError(detail or "previous microphone could not be restored")

    def _send_shortcut(self) -> None:
        completed = subprocess.run(
            self._shortcut_command(),
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if completed.returncode == 70:
            raise ValueError("Typeless key helper needs macOS Accessibility permission")
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            raise ValueError(detail or "Typeless shortcut failed")

    def perform(self, action: str, audio_mode: str = "m5") -> Dict[str, Any]:
        if action not in ACTIONS:
            raise ValueError("unsupported Typeless action: %s" % action)
        if audio_mode not in AUDIO_MODES:
            raise ValueError("unsupported Typeless audio mode: %s" % audio_mode)
        if not self.helper.is_file() or not self.helper.stat().st_mode & 0o111:
            raise ValueError("Typeless key helper is not installed")

        with self.lock:
            effective_audio_mode = self.active_audio_mode or audio_mode
            if action == "start" and self.active:
                return {"connected": self._is_running(), "active": True}
            if action == "stop" and not self.active:
                return {"connected": self._is_running(), "active": False}
            if action == "start":
                previous = self._capture_audio_input() if audio_mode == "m5" else None
                try:
                    self._ensure_ready()
                    self._send_shortcut()
                except Exception:
                    if previous is not None:
                        self._restore_audio_input(previous)
                    raise
                self.previous_input = previous
                self.active_audio_mode = audio_mode
                self.active = True
            else:
                shortcut_error: Exception | None = None
                try:
                    self._send_shortcut()
                except Exception as exc:
                    shortcut_error = exc
                try:
                    if self.previous_input is not None:
                        self._restore_audio_input(self.previous_input)
                finally:
                    self.previous_input = None
                    self.active_audio_mode = None
                    self.active = False
                if shortcut_error is not None:
                    raise shortcut_error
        print(
            "Typeless %s shortcut sent (%s mic)" % (action, effective_audio_mode),
            flush=True,
        )
        return {"connected": True, "active": self.active}

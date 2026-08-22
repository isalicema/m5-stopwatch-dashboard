from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict


SHORTCUTS = {"fn", "ctrl-cmd-shift-space"}
ACTIONS = {"start", "stop"}


class TypelessController:
    """Open Typeless and toggle dictation through the trusted native helper."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.helper = Path(str(config.get("helper_path") or "")).expanduser()
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

    def perform(self, action: str) -> Dict[str, Any]:
        if action not in ACTIONS:
            raise ValueError("unsupported Typeless action: %s" % action)
        if not self.helper.is_file() or not self.helper.stat().st_mode & 0o111:
            raise ValueError("Typeless key helper is not installed")

        with self.lock:
            if action == "start" and self.active:
                return {"connected": self._is_running(), "active": True}
            if action == "stop" and not self.active:
                return {"connected": self._is_running(), "active": False}
            self._ensure_ready()
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
        self.active = action == "start"
        print("Typeless %s shortcut sent" % action, flush=True)
        return {"connected": True, "active": self.active}

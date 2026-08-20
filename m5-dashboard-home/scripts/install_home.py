from __future__ import annotations

import json
import os
import plistlib
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict


HOME_LABEL = "com.local.m5dashboard.home.bridge"
LEGACY_LABEL = "com.local.m5dashboard.bridge"


def _paths() -> Dict[str, Path]:
    project = Path(__file__).resolve().parent.parent
    target = Path.home() / "Library/Application Support/M5Dashboard-Home"
    return {
        "project": project,
        "target": target,
        "app": target / "app",
        "config": target / "config.json",
        "venv": target / "venv",
        "plist": Path.home() / ("Library/LaunchAgents/%s.plist" % HOME_LABEL),
        "legacy_config": Path.home()
        / "Library/Application Support/M5Dashboard/config.json",
    }


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("Cannot read %s: %s" % (path, exc))
    if not isinstance(value, dict):
        raise SystemExit("Invalid config root in %s" % path)
    return value


def _home_config(paths: Dict[str, Path]) -> Dict[str, Any]:
    if paths["config"].exists():
        config = _load_json(paths["config"])
    else:
        config = _load_json(paths["legacy_config"])
    server = config.setdefault("server", {})
    server.setdefault("discovery_port", 8766)
    if not server.get("api_token"):
        raise SystemExit("The existing home dashboard token is missing")
    config["claude"] = {
        "enabled": True,
        "refresh_seconds": 300,
        "activity_refresh_seconds": 1,
        "activity_stale_seconds": 1800,
        # This private installer deliberately enables local conversation previews.
        # Public example configs keep them disabled by default.
        "expose_transcript": True,
        "source": {
            "mode": "local_claude_desktop",
            "projects_root": "~/.claude/projects",
        },
    }
    codex = config.setdefault("codex", {})
    codex.setdefault("local_activity_stale_seconds", 1800)
    # This private installer deliberately enables local conversation previews.
    # Public example configs keep them disabled by default.
    codex["expose_transcript"] = True
    codex.setdefault("transcript_refresh_seconds", 1)
    return config


def _write_json(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(list(args), check=check)


def install() -> None:
    paths = _paths()
    paths["target"].mkdir(parents=True, exist_ok=True)
    config = _home_config(paths)

    if paths["app"].exists():
        shutil.rmtree(paths["app"])
    shutil.copytree(paths["project"] / "bridge", paths["app"] / "bridge")
    _write_json(paths["config"], config)

    python = paths["venv"] / "bin/python"
    if not python.exists():
        _run("/usr/bin/python3", "-m", "venv", str(paths["venv"]))
    _run(
        str(python),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "-r",
        str(paths["project"] / "requirements.txt"),
    )

    logs = paths["target"] / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    payload = {
        "Label": HOME_LABEL,
        "ProgramArguments": [
            str(python),
            "-m",
            "bridge",
            "--config",
            str(paths["config"]),
        ],
        "WorkingDirectory": str(paths["app"]),
        "EnvironmentVariables": {"PYTHONPATH": str(paths["app"])},
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "StandardOutPath": str(logs / "bridge.log"),
        "StandardErrorPath": str(logs / "bridge-error.log"),
    }
    paths["plist"].parent.mkdir(parents=True, exist_ok=True)
    with paths["plist"].open("wb") as target:
        plistlib.dump(payload, target, sort_keys=True)

    domain = "gui/%d" % os.getuid()
    _run("/bin/launchctl", "bootout", domain + "/" + HOME_LABEL, check=False)
    _run("/bin/launchctl", "bootout", domain + "/" + LEGACY_LABEL, check=False)
    _run("/bin/launchctl", "disable", domain + "/" + LEGACY_LABEL, check=False)
    # launchd can retain the old label briefly after bootout. A bounded retry
    # prevents an update from leaving the home bridge stopped.
    time.sleep(0.4)
    bootstrapped = _run(
        "/bin/launchctl", "bootstrap", domain, str(paths["plist"]), check=False
    )
    if bootstrapped.returncode != 0:
        _run("/bin/launchctl", "bootout", domain, str(paths["plist"]), check=False)
        time.sleep(0.8)
        _run("/bin/launchctl", "bootstrap", domain, str(paths["plist"]))
    _run("/bin/launchctl", "enable", domain + "/" + HOME_LABEL)
    _run("/bin/launchctl", "kickstart", "-k", domain + "/" + HOME_LABEL)
    print("Home M5 Dashboard installed: %s" % paths["target"])


if __name__ == "__main__":
    install()

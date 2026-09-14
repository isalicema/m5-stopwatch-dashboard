#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import plistlib
import secrets
import shlex
import shutil
import subprocess
import tempfile
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict


APP_NAME = "M5Dashboard"
LAUNCH_LABEL = "com.local.m5dashboard.bridge"
AUDIO_LAUNCH_LABEL = "com.local.m5dashboard.audio-input"
PEER_APP_NAME = "M5Dashboard-Peer"
PEER_LAUNCH_LABEL = "com.local.m5dashboard.peer"


def paths() -> Dict[str, Path]:
    project = Path(__file__).resolve().parent.parent
    target = Path.home() / "Library/Application Support" / APP_NAME
    return {
        "project": project,
        "target": target,
        "installed_app": target / "app",
        "config": target / "config.json",
        "hooks": Path.home() / ".codex/hooks.json",
        "claude_settings": Path.home() / ".claude/settings.json",
        "launch_agent": Path.home() / "Library/LaunchAgents" / (LAUNCH_LABEL + ".plist"),
        "audio_launch_agent": Path.home() / "Library/LaunchAgents" / (AUDIO_LAUNCH_LABEL + ".plist"),
        "typeless_settings": Path.home() / "Library/Application Support/Typeless/app-settings.json",
        "audio_helper": target / "bin/m5_audio_input",
        "codex_notify_helper": target / "bin/M5CodexNotify",
        "claude_notify_helper": target / "bin/M5ClaudeNotify",
        "claude_stop_fanout_helper": target / "bin/M5ClaudeStopFanout",
        "typeless_helper": target / "TypelessKeySender.app/Contents/MacOS/TypelessKeySender",
        "typeless_helper_info": target / "TypelessKeySender.app/Contents/Info.plist",
    }


def peer_paths() -> Dict[str, Path]:
    project = Path(__file__).resolve().parent.parent
    target = Path.home() / "Library/Application Support" / PEER_APP_NAME
    return {
        "project": project,
        "target": target,
        "installed_app": target / "app",
        "config": target / "config.json",
        "launch_agent": Path.home() / "Library/LaunchAgents" / (PEER_LAUNCH_LABEL + ".plist"),
    }


def copy_app(p: Dict[str, Path]) -> None:
    destination = p["installed_app"]
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(p["project"] / "bridge", destination / "bridge", dirs_exist_ok=True)
    notify_source = p["project"] / "mac/M5CodexNotify.sh"
    if notify_source.is_file():
        notify_target = p.get("codex_notify_helper") or p["target"] / "bin/M5CodexNotify"
        notify_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(notify_source, notify_target)
        notify_target.chmod(0o755)
    claude_notify_source = p["project"] / "mac/M5ClaudeNotify.sh"
    if claude_notify_source.is_file():
        claude_notify_target = p.get("claude_notify_helper") or p["target"] / "bin/M5ClaudeNotify"
        claude_notify_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(claude_notify_source, claude_notify_target)
        claude_notify_target.chmod(0o755)
    claude_fanout_source = p["project"] / "mac/M5ClaudeStopFanout.sh"
    if claude_fanout_source.is_file():
        claude_fanout_target = (
            p.get("claude_stop_fanout_helper")
            or p["target"] / "bin/M5ClaudeStopFanout"
        )
        claude_fanout_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(claude_fanout_source, claude_fanout_target)
        claude_fanout_target.chmod(0o755)
    source_config = p["project"] / "config.json"
    # Never replace this Mac's working token/cloud settings with a config
    # synced from another location. Seed the config only on a fresh install.
    if source_config.exists() and not p["config"].exists():
        shutil.copy2(source_config, p["config"])
    elif not p["config"].exists():
        shutil.copy2(p["project"] / "config.example.json", p["config"])
    _normalize_installed_config(p)


def _normalize_installed_config(p: Dict[str, Path]) -> None:
    """Replace machine-specific paths after seeding or updating an install."""
    try:
        config = json.loads(p["config"].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("Cannot read installed config %s: %s" % (p["config"], exc))

    config.pop("bambu", None)
    server = config.setdefault("server", {})
    token = str(server.get("api_token") or "")
    if not token or token == "CHANGE_ME_TO_A_LONG_RANDOM_VALUE":
        server["api_token"] = secrets.token_urlsafe(32)
    server.setdefault("usb_enabled", True)
    ticktick = config.setdefault("ticktick", {})
    ticktick.setdefault("enabled", True)
    ticktick.setdefault("base_url", "http://127.0.0.1:8787")
    ticktick.setdefault("duration_seconds", 1500)
    ticktick["daily_state_path"] = str(p["target"] / "ticktick-daily-focus.json")
    typeless = config.setdefault("typeless", {})
    typeless.setdefault("enabled", True)
    typeless["helper_path"] = str(
        p.get("typeless_helper")
        or p["target"] / "TypelessKeySender.app/Contents/MacOS/TypelessKeySender"
    )
    typeless["audio_helper_path"] = str(
        p.get("audio_helper") or p["target"] / "bin/m5_audio_input"
    )
    typeless.setdefault("shortcut", "ctrl-cmd-shift-space")
    typeless.setdefault("command_timeout_seconds", 5)
    typeless.setdefault("startup_delay_seconds", 1.0)
    codex = config.setdefault("codex", {})
    codex["hook_state_path"] = str(p["target"] / "codex_hooks.json")
    codex.setdefault("waiting_input_stale_seconds", 21600)
    codex.setdefault("missing_thread_grace_seconds", 30)
    # Keep transcript sharing opt-in. A copied package must not silently widen
    # what this Mac exposes to the dashboard.
    codex.setdefault("expose_transcript", False)
    codex.setdefault("transcript_refresh_seconds", 1)
    claude = config.setdefault("claude", {})
    claude["hook_state_path"] = str(p["target"] / "claude_hooks.json")
    claude.setdefault("completion_source", "jsonl")
    example_source = claude.get("source") if isinstance(claude.get("source"), dict) else {}
    if str(example_source.get("base_url") or "").startswith("http://IMAC-IP:"):
        claude.pop("source", None)
        claude["enabled"] = True
        claude["local_only"] = True
    claude.setdefault("expose_transcript", False)
    claude.setdefault("activity_refresh_seconds", 1)
    ai_usage = config.setdefault("ai_usage", {})
    ai_usage.setdefault("enabled", True)
    ai_usage.setdefault("base_url", "http://127.0.0.1:8177")
    ai_usage.setdefault("timezone", "Asia/Shanghai")
    ai_usage.setdefault("refresh_seconds", 30)
    ai_usage.setdefault("timeout_seconds", 10)
    ai_usage.setdefault("quota_timeout_seconds", 30)
    ai_usage.setdefault("history_days", 380)
    ai_hotspot = config.setdefault("ai_hotspot", {})
    ai_hotspot.setdefault("enabled", True)
    ai_hotspot.setdefault("refresh_seconds", 60)
    ai_hotspot.setdefault(
        "state_path", str(p["target"] / "ai_hotspots.json")
    )
    ai_hotspot.setdefault(
        "keywords",
        ["Codex", "GPT", "OpenAI", "Claude", "Anthropic", "Gemini", "发布", "重置", "上线"],
    )
    ai_hotspot.setdefault(
        "sources",
        [
            {"name": "OpenAI", "url": "https://openai.com/news/rss.xml"},
            {"name": "Google AI", "url": "https://blog.google/technology/ai/rss/"},
        ],
    )
    ota = config.setdefault("ota", {})
    ota.setdefault("enabled", True)
    ota["directory"] = str(p["target"] / "ota")
    ota.setdefault("max_firmware_bytes", 0x4F0000)
    obsidian = config.setdefault("obsidian", {})
    obsidian.setdefault("enabled", True)
    obsidian.setdefault("roots", [str(Path.home() / "Smart Workspace")])
    obsidian.setdefault(
        "exclude_names", [".obsidian", ".trash", ".git", "node_modules", "Alice Writing"]
    )
    obsidian.setdefault("refresh_seconds", 900)
    obsidian.setdefault("max_files", 5000)

    configured = Path(os.path.expanduser(str(codex.get("codex_binary") or "")))
    if not configured.is_file():
        candidates = [
            Path("/Applications/Codex.app/Contents/Resources/codex"),
            Path("/Applications/ChatGPT.app/Contents/Resources/codex"),
            Path.home() / "Applications/Codex.app/Contents/Resources/codex",
            Path.home() / "Applications/ChatGPT.app/Contents/Resources/codex",
        ]
        command = shutil.which("codex")
        if command:
            candidates.append(Path(command))
        replacement = next((candidate for candidate in candidates if candidate.is_file()), None)
        if replacement is not None:
            codex["codex_binary"] = str(replacement)

    _atomic_json_write(p["config"], config)
    p["config"].chmod(0o600)


def _backup(path: Path) -> None:
    if not path.exists():
        return
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(path, path.with_name(path.name + ".bak-" + stamp))


def _is_ours(handler: Dict[str, Any]) -> bool:
    command = str(handler.get("command") or "")
    return any(marker in command for marker in ("M5Dashboard", "M5CodexNotify", "M5ClaudeNotify"))


def _load_service(label: str, launch_file: Path) -> None:
    domain = "gui/%d" % os.getuid()
    service = "%s/%s" % (domain, label)
    loaded = subprocess.run(
        ["launchctl", "print", service], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0
    if loaded:
        subprocess.run(
            ["launchctl", "bootout", domain, str(launch_file)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
    subprocess.run(["launchctl", "bootstrap", domain, str(launch_file)], check=True)
    subprocess.run(["launchctl", "kickstart", "-k", service], check=True)


def _atomic_json_write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as target:
            json.dump(payload, target, ensure_ascii=False, indent="\t")
            target.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _codex_binary(current: Any = "") -> str:
    configured = Path(os.path.expanduser(str(current or "")))
    if configured.is_file():
        return str(configured)
    candidates = [
        Path("/Applications/Codex.app/Contents/Resources/codex"),
        Path("/Applications/ChatGPT.app/Contents/Resources/codex"),
        Path.home() / "Applications/Codex.app/Contents/Resources/codex",
        Path.home() / "Applications/ChatGPT.app/Contents/Resources/codex",
    ]
    command = shutil.which("codex")
    if command:
        candidates.append(Path(command))
    replacement = next((candidate for candidate in candidates if candidate.is_file()), None)
    return str(replacement or current or "codex")


def copy_peer_app(p: Dict[str, Path], enable_usb: bool = False) -> None:
    destination = p["installed_app"]
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(p["project"] / "bridge", destination / "bridge", dirs_exist_ok=True)
    if p["config"].exists():
        try:
            config = json.loads(p["config"].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit("Cannot read peer config %s: %s" % (p["config"], exc))
    else:
        token = str(os.environ.get("M5_PEER_API_TOKEN") or "")
        if not token:
            try:
                shared = json.loads((p["project"] / "config.json").read_text(encoding="utf-8"))
                token = str((shared.get("server") or {}).get("api_token") or "")
            except (OSError, json.JSONDecodeError) as exc:
                raise SystemExit("Cannot read the private shared bridge config: %s" % exc)
        if not token or token == "CHANGE_ME_TO_A_LONG_RANDOM_VALUE":
            raise SystemExit("The private shared bridge token is not configured")
        config = {
            "server": {"bind": "0.0.0.0", "port": 8765, "api_token": token},
            "ticktick": {"enabled": False},
            "weather": {"enabled": False},
            "codex": {"enabled": True},
            "claude": {"enabled": True},
            "peers": [],
        }

    server = config.setdefault("server", {})
    server.update(
        {
            "device_label": "iMac",
            "discovery_enabled": False,
            "usb_enabled": enable_usb,
        }
    )
    if enable_usb:
        usb_token = str(os.environ.get("M5_PEER_USB_API_TOKEN") or "")
        upstream_token = str(os.environ.get("M5_PEER_USB_UPSTREAM_TOKEN") or usb_token)
        upstream_url = str(os.environ.get("M5_PEER_USB_UPSTREAM_URL") or "").rstrip("/")
        parsed_upstream = urllib.parse.urlparse(upstream_url)
        if not usb_token or not upstream_token:
            raise SystemExit("The iMac USB bridge token is not configured")
        if parsed_upstream.scheme not in ("http", "https") or not parsed_upstream.hostname:
            raise SystemExit("The iMac USB upstream URL is not configured")
        server["usb_api_token"] = usb_token
        server["usb_upstream"] = {
            "base_url": upstream_url,
            "api_token": upstream_token,
            "timeout_seconds": 2,
        }
    else:
        server.pop("usb_api_token", None)
        server.pop("usb_upstream", None)
    codex = config.setdefault("codex", {})
    codex.update(
        {
            "enabled": True,
            "codex_binary": _codex_binary(codex.get("codex_binary")),
            "hook_state_path": str(p["target"] / "codex_hooks.json"),
            "expose_titles": True,
            "expose_transcript": True,
            "transcript_refresh_seconds": 1,
            "threads_refresh_seconds": 2,
            "local_activity_stale_seconds": 1800,
        }
    )
    claude = config.setdefault("claude", {})
    claude.update(
        {
            "enabled": True,
            "local_only": True,
            "activity_projects_root": "~/.claude/projects",
            "activity_refresh_seconds": 1,
            "activity_stale_seconds": 1800,
            "expose_transcript": True,
        }
    )
    config.pop("bambu", None)
    config.setdefault("ticktick", {})["enabled"] = False
    config.setdefault("weather", {})["enabled"] = False
    config["peers"] = []
    _atomic_json_write(p["config"], config)
    p["config"].chmod(0o600)


def configure_peer_from_usage(p: Dict[str, Path]) -> None:
    try:
        config = json.loads(p["config"].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("Cannot read installed config %s: %s" % (p["config"], exc))
    usage_sources = (config.get("codex") or {}).get("peer_usage_sources") or []
    source = next((item for item in usage_sources if isinstance(item, dict)), None)
    parsed = urllib.parse.urlparse(str((source or {}).get("base_url") or ""))
    if not parsed.hostname:
        raise SystemExit("No configured Codex peer usage host was found")
    host = "[%s]" % parsed.hostname if ":" in parsed.hostname else parsed.hostname
    base_url = "%s://%s:8765" % (parsed.scheme or "http", host)
    source_id = str((source or {}).get("id") or "company-imac")
    peers = config.setdefault("peers", [])
    existing = next(
        (item for item in peers if isinstance(item, dict) and item.get("base_url") == base_url),
        None,
    )
    changed = False
    if existing is None:
        peers.append(
            {
                "id": source_id,
                "label": "iMac",
                "base_url": base_url,
                "timeout_seconds": 3,
                "usage_auth_source": source_id,
            }
        )
        changed = True
    elif existing.get("usage_auth_source") != source_id:
        existing["usage_auth_source"] = source_id
        changed = True
    if changed:
        _backup(p["config"])
        _atomic_json_write(p["config"], config)
    print("Configured the existing company usage host as an activity peer.")


def install_peer_node(p: Dict[str, Path], enable_usb: bool = False) -> None:
    copy_peer_app(p, enable_usb=enable_usb)
    launch_file = p["launch_agent"]
    launch_file.parent.mkdir(parents=True, exist_ok=True)
    _backup(launch_file)
    logs = p["target"] / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    payload = {
        "Label": PEER_LAUNCH_LABEL,
        "ProgramArguments": [
            "/usr/bin/python3",
            "-m",
            "bridge",
            "--config",
            str(p["config"]),
        ],
        "WorkingDirectory": str(p["installed_app"]),
        "EnvironmentVariables": {"PYTHONPATH": str(p["installed_app"])},
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "StandardOutPath": str(logs / "bridge.log"),
        "StandardErrorPath": str(logs / "bridge-error.log"),
    }
    with launch_file.open("wb") as target:
        plistlib.dump(payload, target, sort_keys=True)
    _load_service(PEER_LAUNCH_LABEL, launch_file)
    if enable_usb:
        print("Installed the iMac activity peer with physical USB enabled; discovery stays disabled.")
    else:
        print("Installed the headless iMac activity peer; USB and discovery are disabled.")


def install_hooks(p: Dict[str, Path]) -> None:
    copy_app(p)
    hook_file = p["hooks"]
    hook_file.parent.mkdir(parents=True, exist_ok=True)
    if hook_file.exists():
        try:
            config = json.loads(hook_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit("Refusing to edit invalid %s: %s" % (hook_file, exc))
        _backup(hook_file)
    else:
        config = {"description": "Personal Codex lifecycle hooks.", "hooks": {}}
    hooks = config.setdefault("hooks", {})
    command = "/usr/bin/python3 '%s'" % (p["installed_app"] / "bridge/codex_hook.py")
    events = {
        "SessionStart": {"type": "command", "command": command, "timeout": 2},
        "SessionEnd": {"type": "command", "command": command, "timeout": 2},
        "UserPromptSubmit": {"type": "command", "command": command, "timeout": 2},
        "PermissionRequest": {"type": "command", "command": command, "timeout": 2},
        "PreToolUse": {"type": "command", "command": command, "timeout": 2},
        "PostToolUse": {"type": "command", "command": command, "timeout": 2},
        "PreCompact": {"type": "command", "command": command, "timeout": 2},
        "PostCompact": {"type": "command", "command": command, "timeout": 2},
        "Stop": {"type": "command", "command": command, "timeout": 2},
    }
    for event, handler in events.items():
        groups = hooks.setdefault(event, [])
        cleaned = []
        for group in groups:
            handlers = [h for h in group.get("hooks", []) if not _is_ours(h)]
            if handlers:
                updated = dict(group)
                updated["hooks"] = handlers
                cleaned.append(updated)
        cleaned.append({"hooks": [handler]})
        hooks[event] = cleaned
    hook_file.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Installed Codex hooks: %s" % hook_file)
    print("Next: restart the desktop app and trust the new hooks in the hooks review UI.")


def install_claude_completion_hook(p: Dict[str, Path]) -> None:
    """Fan one authoritative Claude Stop payload out to peon-ping and M5."""
    copy_app(p)
    settings_file = p["claude_settings"]
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    if settings_file.exists():
        try:
            config = json.loads(settings_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit("Refusing to edit invalid %s: %s" % (settings_file, exc))
        _backup(settings_file)
    else:
        config = {}
    hooks = config.setdefault("hooks", {})
    groups = hooks.setdefault("Stop", [])
    cleaned = []
    peon_handler = None
    peon_group_index = None
    fallback_group_index = None
    for group in groups:
        handlers = []
        selected_peon_here = False
        for handler in group.get("hooks", []):
            command = str(handler.get("command") or "")
            if "M5ClaudeStopFanout" in command:
                try:
                    fanout_parts = shlex.split(command)
                except ValueError:
                    fanout_parts = []
                if peon_handler is None and len(fanout_parts) >= 3:
                    peon_handler = dict(handler)
                    peon_handler["command"] = fanout_parts[1]
                    selected_peon_here = True
                continue
            if _is_ours(handler):
                continue
            if peon_handler is None and "peon-ping" in command:
                peon_handler = dict(handler)
                selected_peon_here = True
                continue
            handlers.append(handler)
        if handlers or selected_peon_here:
            updated = dict(group)
            updated["hooks"] = handlers
            cleaned.append(updated)
            if selected_peon_here:
                peon_group_index = len(cleaned) - 1
            if str(updated.get("matcher") or "") == "":
                current_index = len(cleaned) - 1
                if fallback_group_index is None:
                    fallback_group_index = current_index
    command = str(p.get("claude_notify_helper") or p["target"] / "bin/M5ClaudeNotify")
    if peon_handler is not None and peon_group_index is not None:
        fanout = str(
            p.get("claude_stop_fanout_helper")
            or p["target"] / "bin/M5ClaudeStopFanout"
        )
        fanout_handler = dict(peon_handler)
        fanout_handler["command"] = " ".join(
            shlex.quote(item)
            for item in (fanout, str(peon_handler.get("command") or ""), command)
        )
        shared_group = dict(cleaned[peon_group_index])
        shared_group["hooks"] = [fanout_handler] + list(shared_group["hooks"])
        cleaned[peon_group_index] = shared_group
    else:
        handler = {"type": "command", "command": command, "timeout": 2, "async": True}
        if fallback_group_index is None:
            cleaned.append({"matcher": "", "hooks": [handler]})
        else:
            shared_group = dict(cleaned[fallback_group_index])
            shared_group["hooks"] = [handler] + list(shared_group["hooks"])
            cleaned[fallback_group_index] = shared_group
    hooks["Stop"] = cleaned
    settings_file.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Installed Claude Stop fanout beside the existing sound hook: %s" % settings_file)


def install_launch_agent(p: Dict[str, Path]) -> None:
    copy_app(p)
    launch_file = p["launch_agent"]
    launch_file.parent.mkdir(parents=True, exist_ok=True)
    _backup(launch_file)
    logs = p["target"] / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    payload = {
        "Label": LAUNCH_LABEL,
        "ProgramArguments": [
            "/usr/bin/python3",
            "-m",
            "bridge",
            "--config",
            str(p["config"]),
        ],
        "WorkingDirectory": str(p["installed_app"]),
        "EnvironmentVariables": {"PYTHONPATH": str(p["installed_app"])},
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "StandardOutPath": str(logs / "bridge.log"),
        "StandardErrorPath": str(logs / "bridge-error.log"),
    }
    with launch_file.open("wb") as target:
        plistlib.dump(payload, target, sort_keys=True)
    _load_service(LAUNCH_LABEL, launch_file)
    print("Installed LaunchAgent file: %s" % launch_file)
    print("M5 Dashboard bridge is running.")


def _quit_typeless() -> None:
    running = subprocess.run(
        ["/usr/bin/pgrep", "-x", "Typeless"], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0
    if not running:
        return
    subprocess.run(
        ["/usr/bin/osascript", "-e", 'tell application "Typeless" to quit'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    for _ in range(20):
        if subprocess.run(
            ["/usr/bin/pgrep", "-x", "Typeless"], stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, check=False,
        ).returncode != 0:
            return
        time.sleep(0.25)
    raise SystemExit("Typeless is still running. Quit it once, then rerun the installer.")


def _updated_typeless_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    devices = settings.get("microphoneDevices") or []
    default_device = next(
        (item for item in devices if item.get("kind") == "audioinput" and item.get("deviceId") == "default"),
        None,
    )
    m5_device = next(
        (item for item in devices if item.get("kind") == "audioinput" and item.get("label") == "TinyUSB UAC1"),
        None,
    )
    group_id = (default_device or m5_device or {}).get("groupId", "")
    settings["selectedMicrophoneDevice"] = {
        "deviceId": "default",
        "kind": "audioinput",
        "label": "Auto-detect (TinyUSB UAC1)",
        "groupId": group_id,
        "description": "Uses system default microphone",
    }
    settings["preferredBuiltInMicId"] = None
    settings["enabledMuteBackgroundAudio"] = False
    settings["launchAtSystemStartup"] = True
    bindings = settings.setdefault("featureShortcutBindings", {})
    bindings["dictationMode"] = ["Fn", "LeftCtrl+LeftCmd+LeftShift+Space"]
    return settings


def configure_typeless(p: Dict[str, Path]) -> None:
    settings_file = p["typeless_settings"]
    if not settings_file.exists():
        raise SystemExit(
            "Typeless has not created its settings yet. Open Typeless once, sign in, "
            "approve the macOS microphone prompt, then run this installer again."
        )
    _quit_typeless()
    try:
        settings = json.loads(settings_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit("Refusing to edit invalid %s: %s" % (settings_file, exc))
    _backup(settings_file)
    settings = _updated_typeless_settings(settings)
    _atomic_json_write(settings_file, settings)
    print("Configured Typeless: system-default microphone, Fn shortcut, startup enabled.")


def _audio_helper_prerequisites(p: Dict[str, Path]) -> Dict[str, Path]:
    bundled = p["project"] / "dist/M5Workstation/m5_audio_input"
    if bundled.is_file():
        return {"bundled": bundled}

    source = p["project"] / "mac/M5AudioInput.c"
    if not source.is_file():
        raise SystemExit(
            "Missing both the bundled audio helper and its source: %s" % source
        )
    compiler = shutil.which("clang")
    if not compiler:
        raise SystemExit(
            "Cannot build the M5 audio helper because clang is unavailable. "
            "Install the Xcode Command Line Tools first."
        )
    return {"source": source, "compiler": Path(compiler)}


def _typeless_helper_prerequisites(p: Dict[str, Path]) -> Dict[str, Path]:
    source = p["project"] / "mac/TypelessKeySender.c"
    if not source.is_file():
        raise SystemExit("Missing Typeless key helper source: %s" % source)
    system_compiler = Path("/usr/bin/clang")
    compiler = str(system_compiler) if system_compiler.is_file() else shutil.which("clang")
    if not compiler:
        raise SystemExit(
            "Cannot build the Typeless key helper because clang is unavailable. "
            "Install the Xcode Command Line Tools first."
        )
    return {"source": source, "compiler": Path(compiler)}


def _native_macos_architecture() -> str:
    """Return the hardware architecture even when Python runs via Rosetta."""
    sysctl = Path("/usr/sbin/sysctl")
    if sysctl.is_file():
        checked = subprocess.run(
            [str(sysctl), "-n", "hw.optional.arm64"],
            check=False,
            capture_output=True,
            text=True,
        )
        if checked.returncode == 0 and checked.stdout.strip() == "1":
            return "arm64"
    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64"):
        return "arm64"
    if machine in ("x86_64", "amd64"):
        return "x86_64"
    raise SystemExit("Unsupported macOS architecture for TypelessKeySender: %s" % machine)


def _macho_architectures(binary: Path) -> set[str]:
    lipo = shutil.which("lipo") or "/usr/bin/lipo"
    checked = subprocess.run(
        [str(lipo), "-archs", str(binary)],
        check=False,
        capture_output=True,
        text=True,
    )
    if checked.returncode != 0:
        return set()
    return set(checked.stdout.split())


def _typeless_helper_fingerprint(source: Path, target_arch: str) -> str:
    # Keep this description in lockstep with the compile command below. The
    # architecture and explicit thin-native strategy prevent a helper built in
    # a Rosetta parent process from being mistaken for a current Apple-Silicon
    # build merely because the C source has not changed.
    strategy = (
        "m5-typeless-helper-v3\0"
        "strategy=thin-native\0"
        f"target={target_arch}\0"
        "flags=-O2,-Wall,-Wextra,-arch,ApplicationServices\0"
        "signing=adhoc-stable-designated-requirement-v1\0"
    ).encode("utf-8")
    return hashlib.sha256(strategy + source.read_bytes()).hexdigest()


def preflight_typeless_install(p: Dict[str, Path]) -> None:
    """Reject predictable failures before --all changes hooks or agents."""
    settings_file = p["typeless_settings"]
    if not settings_file.is_file():
        raise SystemExit(
            "Typeless has not created its settings yet. Open Typeless once, sign in, "
            "approve the macOS microphone prompt, then run this installer again."
        )
    try:
        json.loads(settings_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("Refusing to edit invalid %s: %s" % (settings_file, exc))
    _audio_helper_prerequisites(p)
    _typeless_helper_prerequisites(p)


def install_typeless_key_sender(p: Dict[str, Path]) -> None:
    inputs = _typeless_helper_prerequisites(p)
    target_arch = _native_macos_architecture()
    helper = p["typeless_helper"]
    info = p["typeless_helper_info"]
    app_bundle = helper.parents[2]
    marker = app_bundle.parent / ".TypelessKeySender.source-sha256"
    fingerprint = _typeless_helper_fingerprint(inputs["source"], target_arch)

    if helper.is_file() and info.is_file():
        installed_architectures = _macho_architectures(helper)
        architecture_is_current = target_arch in installed_architectures
        try:
            installed_fingerprint = marker.read_text(encoding="utf-8").strip()
        except OSError:
            installed_fingerprint = ""
        if installed_fingerprint == fingerprint and architecture_is_current:
            print("Typeless key helper is already current; preserved its Accessibility identity.")
            return
        if not installed_fingerprint and architecture_is_current:
            # Migration for helpers installed before the external build marker
            # existed. Preserve only a binary that actually supports this
            # Mac; an Intel-only helper on Apple Silicon must be rebuilt even
            # when replacing it invalidates the old Accessibility approval.
            marker.write_text(fingerprint + "\n", encoding="utf-8")
            print("Preserved the existing Typeless key helper and recorded its source fingerprint.")
            return
        if not architecture_is_current:
            found = ",".join(sorted(installed_architectures)) or "unknown"
            print(
                "Rebuilding Typeless key helper for %s; installed architecture is %s."
                % (target_arch, found)
            )

    signer = shutil.which("codesign") or "/usr/bin/codesign"
    helper.parent.mkdir(parents=True, exist_ok=True)
    temporary = helper.with_name(helper.name + ".tmp-%d" % os.getpid())
    try:
        subprocess.run(
            [
                str(inputs["compiler"]),
                "-arch",
                target_arch,
                "-O2",
                "-Wall",
                "-Wextra",
                str(inputs["source"]),
                "-framework",
                "ApplicationServices",
                "-o",
                str(temporary),
            ],
            check=True,
        )
        built_architectures = _macho_architectures(temporary)
        if target_arch not in built_architectures:
            found = ",".join(sorted(built_architectures)) or "unknown"
            raise SystemExit(
                "Built Typeless key helper does not contain %s (found: %s)."
                % (target_arch, found)
            )
        os.replace(temporary, helper)
    except subprocess.CalledProcessError as exc:
        raise SystemExit("Failed to build the Typeless key helper: %s" % exc)
    finally:
        if temporary.exists():
            temporary.unlink()
    helper.chmod(0o755)
    info.parent.mkdir(parents=True, exist_ok=True)
    with info.open("wb") as target:
        plistlib.dump(
            {
                "CFBundleDevelopmentRegion": "zh_CN",
                "CFBundleExecutable": "TypelessKeySender",
                "CFBundleIdentifier": "studio.machiwhale.m5stopwatch.typeless-key-sender",
                "CFBundleInfoDictionaryVersion": "6.0",
                "CFBundleName": "TypelessKeySender",
                "CFBundlePackageType": "APPL",
                "CFBundleShortVersionString": "1.0",
                "CFBundleVersion": "1",
            },
            target,
            sort_keys=True,
        )
    bundle_identifier = "studio.machiwhale.m5stopwatch.typeless-key-sender"
    designated_requirement = '=designated => identifier "%s"' % bundle_identifier
    try:
        subprocess.run(
            [
                str(signer),
                "--force",
                "--deep",
                "--sign",
                "-",
                "--identifier",
                bundle_identifier,
                "--requirements",
                designated_requirement,
                str(app_bundle),
            ],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise SystemExit("Failed to sign the Typeless key helper app: %s" % exc)
    marker.write_text(fingerprint + "\n", encoding="utf-8")
    print("Installed Typeless key helper: %s" % helper)


def request_typeless_accessibility(p: Dict[str, Path]) -> bool:
    helper = p["typeless_helper"]
    checked = subprocess.run(
        [str(helper), "check"],
        check=False,
        capture_output=True,
        text=True,
    )
    if "accessibility_trusted=true" in checked.stdout:
        print("Typeless key helper Accessibility permission is ready.")
        return True
    subprocess.run([str(helper), "request-accessibility"], check=False)
    print(
        "Typeless key helper needs Accessibility permission. "
        "Approve TypelessKeySender in System Settings > Privacy & Security > Accessibility."
    )
    return False


def _install_audio_helper_binary(p: Dict[str, Path]) -> None:
    inputs = _audio_helper_prerequisites(p)
    helper = p["audio_helper"]
    helper.parent.mkdir(parents=True, exist_ok=True)
    if "bundled" in inputs:
        shutil.copy2(inputs["bundled"], helper)
    else:
        temporary = helper.with_name(helper.name + ".tmp-%d" % os.getpid())
        try:
            subprocess.run(
                [
                    str(inputs["compiler"]),
                    "-O2",
                    "-Wall",
                    "-Wextra",
                    str(inputs["source"]),
                    "-framework",
                    "CoreAudio",
                    "-framework",
                    "CoreFoundation",
                    "-o",
                    str(temporary),
                ],
                check=True,
            )
            os.replace(temporary, helper)
        except subprocess.CalledProcessError as exc:
            raise SystemExit("Failed to build the M5 audio helper: %s" % exc)
        finally:
            if temporary.exists():
                temporary.unlink()
    helper.chmod(0o755)


def install_session_audio_helper(p: Dict[str, Path]) -> None:
    """Replace the legacy global selector with an on-demand session helper."""
    launch_file = p["audio_launch_agent"]
    domain = "gui/%d" % os.getuid()
    service = "%s/%s" % (domain, AUDIO_LAUNCH_LABEL)
    subprocess.run(
        ["launchctl", "bootout", service],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if launch_file.exists():
        launch_file.unlink()
    _install_audio_helper_binary(p)
    subprocess.run(
        [str(p["audio_helper"]), "release"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    print("Installed on-demand M5 microphone session helper: %s" % p["audio_helper"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Install the M5 Dashboard bridge integration")
    parser.add_argument(
        "--hooks", action="store_true",
        help="install Codex status hooks",
    )
    parser.add_argument(
        "--claude-hook", action="store_true",
        help="append only the Claude Stop completion hook",
    )
    parser.add_argument("--launch-agent", action="store_true", help="install the macOS startup plist")
    parser.add_argument("--typeless", action="store_true", help="configure Typeless and on-demand M5 audio input")
    parser.add_argument("--all", action="store_true", help="install bridge, hooks, Typeless, and session audio helper")
    parser.add_argument(
        "--add-peer-from-usage", action="store_true",
        help="add the existing LAN usage host as a live activity peer",
    )
    parser.add_argument(
        "--peer-node", action="store_true",
        help="install a headless iMac activity node without M5 discovery or USB",
    )
    parser.add_argument(
        "--peer-usb", action="store_true",
        help="install the iMac activity node with physical M5 USB and no discovery",
    )
    args = parser.parse_args()
    if not (
        args.hooks or args.claude_hook or args.launch_agent or args.typeless or args.all
        or args.add_peer_from_usage or args.peer_node or args.peer_usb
    ):
        parser.error(
            "choose --hooks, --claude-hook, --launch-agent, --typeless, --all, "
            "--add-peer-from-usage, --peer-node, or --peer-usb"
        )
    if args.peer_node or args.peer_usb:
        if any(
            (
                args.hooks, args.claude_hook, args.launch_agent, args.typeless,
                args.all, args.add_peer_from_usage,
            )
        ):
            parser.error("--peer-node and --peer-usb must be used by themselves")
        if args.peer_node and args.peer_usb:
            parser.error("choose only one of --peer-node or --peer-usb")
        install_peer_node(peer_paths(), enable_usb=args.peer_usb)
        return
    p = paths()
    if args.typeless or args.all:
        preflight_typeless_install(p)
    if args.add_peer_from_usage:
        configure_peer_from_usage(p)
    if args.hooks or args.all:
        install_hooks(p)
    if args.claude_hook:
        install_claude_completion_hook(p)
    if args.launch_agent or args.all:
        install_launch_agent(p)
    if args.typeless or args.all:
        copy_app(p)
        configure_typeless(p)
        install_typeless_key_sender(p)
        install_session_audio_helper(p)
        if not args.all and p["launch_agent"].exists():
            _load_service(LAUNCH_LABEL, p["launch_agent"])
        subprocess.run(["/usr/bin/open", "-a", "Typeless"], check=False)
        request_typeless_accessibility(p)


if __name__ == "__main__":
    main()

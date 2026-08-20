#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import plistlib
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
        "credentials": target / "bambu-cloud.json",
        "hooks": Path.home() / ".codex/hooks.json",
        "launch_agent": Path.home() / "Library/LaunchAgents" / (LAUNCH_LABEL + ".plist"),
        "audio_launch_agent": Path.home() / "Library/LaunchAgents" / (AUDIO_LAUNCH_LABEL + ".plist"),
        "typeless_settings": Path.home() / "Library/Application Support/Typeless/app-settings.json",
        "audio_helper": target / "bin/m5_audio_input",
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
    source_config = p["project"] / "config.json"
    # Never replace this Mac's working token/cloud settings with a config
    # synced from another location. Seed the config only on a fresh install.
    if source_config.exists() and not p["config"].exists():
        shutil.copy2(source_config, p["config"])
    elif not p["config"].exists():
        shutil.copy2(p["project"] / "config.example.json", p["config"])
    bundled_credentials = p["project"] / "dist/M5Workstation/private/bambu-cloud.json"
    if bundled_credentials.exists() and not p["credentials"].exists():
        shutil.copy2(bundled_credentials, p["credentials"])
        p["credentials"].chmod(0o600)
    _normalize_installed_config(p)


def _normalize_installed_config(p: Dict[str, Path]) -> None:
    """Replace machine-specific paths after seeding or updating an install."""
    try:
        config = json.loads(p["config"].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("Cannot read installed config %s: %s" % (p["config"], exc))

    bambu = config.setdefault("bambu", {})
    bambu["credentials_file"] = str(p["credentials"])
    codex = config.setdefault("codex", {})
    codex["hook_state_path"] = str(p["target"] / "codex_hooks.json")
    # This private two-location installation intentionally mirrors only visible
    # user/assistant text. Reasoning and tool payloads are filtered in the bridge.
    codex["expose_transcript"] = True
    codex.setdefault("transcript_refresh_seconds", 1)
    claude = config.setdefault("claude", {})
    claude["expose_transcript"] = True
    claude["activity_refresh_seconds"] = 1

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


def _backup(path: Path) -> None:
    if not path.exists():
        return
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(path, path.with_name(path.name + ".bak-" + stamp))


def _is_ours(handler: Dict[str, Any]) -> bool:
    return "M5Dashboard" in str(handler.get("command") or "")


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
            "bambu": {"enabled": False, "name": "P2S"},
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
    config.setdefault("bambu", {})["enabled"] = False
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
    bindings["dictationMode"] = ["Fn"]
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


def install_audio_agent(p: Dict[str, Path]) -> None:
    bundled = p["project"] / "dist/M5Workstation/m5_audio_input"
    if not bundled.exists():
        raise SystemExit("Missing audio helper: %s" % bundled)
    helper = p["audio_helper"]
    helper.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bundled, helper)
    helper.chmod(0o755)
    launch_file = p["audio_launch_agent"]
    launch_file.parent.mkdir(parents=True, exist_ok=True)
    _backup(launch_file)
    logs = p["target"] / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    payload = {
        "Label": AUDIO_LAUNCH_LABEL,
        "ProgramArguments": [str(helper), "--watch"],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "StandardOutPath": str(logs / "audio-input.log"),
        "StandardErrorPath": str(logs / "audio-input-error.log"),
    }
    with launch_file.open("wb") as target:
        plistlib.dump(payload, target, sort_keys=True)
    _load_service(AUDIO_LAUNCH_LABEL, launch_file)
    print("Installed automatic M5 microphone selector: %s" % launch_file)


def main() -> None:
    parser = argparse.ArgumentParser(description="Install the M5 Dashboard bridge integration")
    parser.add_argument("--hooks", action="store_true", help="install global read-only Codex status hooks")
    parser.add_argument("--launch-agent", action="store_true", help="install the macOS startup plist")
    parser.add_argument("--typeless", action="store_true", help="configure Typeless and automatic M5 audio input")
    parser.add_argument("--all", action="store_true", help="install bridge, hooks, Typeless, and audio selector")
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
        args.hooks or args.launch_agent or args.typeless or args.all
        or args.add_peer_from_usage or args.peer_node or args.peer_usb
    ):
        parser.error(
            "choose --hooks, --launch-agent, --typeless, --all, "
            "--add-peer-from-usage, --peer-node, or --peer-usb"
        )
    if args.peer_node or args.peer_usb:
        if any((args.hooks, args.launch_agent, args.typeless, args.all, args.add_peer_from_usage)):
            parser.error("--peer-node and --peer-usb must be used by themselves")
        if args.peer_node and args.peer_usb:
            parser.error("choose only one of --peer-node or --peer-usb")
        install_peer_node(peer_paths(), enable_usb=args.peer_usb)
        return
    p = paths()
    if args.add_peer_from_usage:
        configure_peer_from_usage(p)
    if args.hooks or args.all:
        install_hooks(p)
    if args.launch_agent or args.all:
        install_launch_agent(p)
    if args.typeless or args.all:
        configure_typeless(p)
        install_audio_agent(p)
        subprocess.run(["/usr/bin/open", "-a", "Typeless"], check=False)


if __name__ == "__main__":
    main()

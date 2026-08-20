import importlib.util
import json
from pathlib import Path


def load_installer():
    source = Path(__file__).resolve().parents[1] / "scripts/install.py"
    spec = importlib.util.spec_from_file_location("m5_installer", source)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_typeless_uses_system_default_and_fn():
    installer = load_installer()
    settings = {
        "microphoneDevices": [
            {
                "deviceId": "default",
                "kind": "audioinput",
                "label": "Default",
                "groupId": "portable-group",
            }
        ],
        "featureShortcutBindings": {"dictationMode": ["F8"]},
        "enabledMuteBackgroundAudio": True,
    }

    updated = installer._updated_typeless_settings(settings)

    assert updated["selectedMicrophoneDevice"]["deviceId"] == "default"
    assert updated["selectedMicrophoneDevice"]["groupId"] == "portable-group"
    assert updated["featureShortcutBindings"]["dictationMode"] == ["Fn"]
    assert updated["enabledMuteBackgroundAudio"] is False
    assert updated["preferredBuiltInMicId"] is None


def test_copy_app_rewrites_paths_for_each_mac(tmp_path):
    installer = load_installer()
    project = tmp_path / "shared-package"
    target = tmp_path / "different-user" / "Library/Application Support/M5Dashboard"
    (project / "bridge").mkdir(parents=True)
    (project / "bridge/__init__.py").write_text("", encoding="utf-8")
    (project / "dist/M5Workstation/private").mkdir(parents=True)
    (project / "dist/M5Workstation/private/bambu-cloud.json").write_text(
        '{"access_token":"private"}\n', encoding="utf-8"
    )
    (project / "config.json").write_text(
        json.dumps(
            {
                "bambu": {"credentials_file": "/tmp/m5-test-home/M5Dashboard/bambu-cloud.json"},
                "codex": {
                    "hook_state_path": "/tmp/m5-test-home/M5Dashboard/codex_hooks.json",
                    "codex_binary": "/Applications/ChatGPT.app/Contents/Resources/codex",
                },
            }
        ),
        encoding="utf-8",
    )
    p = {
        "project": project,
        "target": target,
        "installed_app": target / "app",
        "config": target / "config.json",
        "credentials": target / "bambu-cloud.json",
    }

    installer.copy_app(p)

    installed = json.loads(p["config"].read_text(encoding="utf-8"))
    assert installed["bambu"]["credentials_file"] == str(p["credentials"])
    assert installed["codex"]["hook_state_path"] == str(target / "codex_hooks.json")
    assert p["credentials"].read_text(encoding="utf-8").startswith("{")
    assert p["credentials"].stat().st_mode & 0o777 == 0o600

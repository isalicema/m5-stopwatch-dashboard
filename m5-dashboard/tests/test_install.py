import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def load_installer():
    source = Path(__file__).resolve().parents[1] / "scripts/install.py"
    spec = importlib.util.spec_from_file_location("m5_installer", source)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.installer = load_installer()

    def test_typeless_follows_session_selected_default_and_stopwatch_shortcuts(self):
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

        updated = self.installer._updated_typeless_settings(settings)

        self.assertEqual(updated["selectedMicrophoneDevice"]["deviceId"], "default")
        self.assertEqual(updated["selectedMicrophoneDevice"]["groupId"], "portable-group")
        self.assertEqual(
            updated["featureShortcutBindings"]["dictationMode"],
            ["Fn", "LeftCtrl+LeftCmd+LeftShift+Space"],
        )
        self.assertFalse(updated["enabledMuteBackgroundAudio"])
        self.assertIsNone(updated["preferredBuiltInMicId"])

    def test_copy_app_rewrites_paths_and_keeps_transcripts_private(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "shared-package"
            target = root / "different-user/Library/Application Support/M5Dashboard"
            (project / "bridge").mkdir(parents=True)
            (project / "bridge/__init__.py").write_text("", encoding="utf-8")
            (project / "config.json").write_text(
                json.dumps(
                    {
                        "bambu": {"credentials_file": "/tmp/old/bambu-cloud.json"},
                        "codex": {
                            "hook_state_path": "/tmp/old/codex_hooks.json",
                            "codex_binary": "/Applications/ChatGPT.app/Contents/Resources/codex",
                            "expose_transcript": False,
                        },
                        "claude": {"expose_transcript": False},
                    }
                ),
                encoding="utf-8",
            )
            p = {
                "project": project,
                "target": target,
                "installed_app": target / "app",
                "config": target / "config.json",
            }

            with mock.patch.object(
                self.installer.secrets, "token_urlsafe", return_value="generated-local-token_123456"
            ):
                self.installer.copy_app(p)

            installed = json.loads(p["config"].read_text(encoding="utf-8"))
            self.assertNotIn("bambu", installed)
            self.assertTrue(installed["ticktick"]["enabled"])
            self.assertEqual(installed["ticktick"]["duration_seconds"], 1500)
            self.assertEqual(
                installed["ticktick"]["daily_state_path"],
                str(target / "ticktick-daily-focus.json"),
            )
            self.assertEqual(installed["codex"]["hook_state_path"], str(target / "codex_hooks.json"))
            self.assertEqual(
                installed["claude"]["hook_state_path"], str(target / "claude_hooks.json")
            )
            self.assertFalse(installed["codex"]["expose_transcript"])
            self.assertFalse(installed["claude"]["expose_transcript"])
            self.assertTrue(installed["ai_usage"]["enabled"])
            self.assertEqual(installed["ai_usage"]["base_url"], "http://127.0.0.1:8177")
            self.assertEqual(installed["ai_usage"]["history_days"], 380)
            self.assertTrue(installed["ai_hotspot"]["enabled"])
            self.assertEqual(
                installed["ai_hotspot"]["state_path"], str(target / "ai_hotspots.json")
            )
            self.assertTrue(installed["ota"]["enabled"])
            self.assertEqual(installed["ota"]["directory"], str(target / "ota"))
            self.assertEqual(installed["ota"]["max_firmware_bytes"], 0x4F0000)
            self.assertTrue(installed["obsidian"]["enabled"])
            self.assertEqual(
                installed["obsidian"]["roots"], [str(Path.home() / "Smart Workspace")]
            )
            self.assertIn("Alice Writing", installed["obsidian"]["exclude_names"])
            self.assertEqual(installed["server"]["api_token"], "generated-local-token_123456")
            self.assertTrue(installed["server"]["usb_enabled"])
            self.assertEqual(
                installed["typeless"]["audio_helper_path"],
                str(target / "bin/m5_audio_input"),
            )
            self.assertEqual(p["config"].stat().st_mode & 0o777, 0o600)

    def test_copy_app_preserves_an_existing_private_token(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "package"
            target = root / "installed"
            (project / "bridge").mkdir(parents=True)
            (project / "bridge/__init__.py").write_text("", encoding="utf-8")
            target.mkdir(parents=True)
            config = target / "config.json"
            config.write_text(
                json.dumps({"server": {"api_token": "existing-private-token_123456"}}),
                encoding="utf-8",
            )
            p = {
                "project": project,
                "target": target,
                "installed_app": target / "app",
                "config": config,
            }

            with mock.patch.object(self.installer.secrets, "token_urlsafe") as generate:
                self.installer.copy_app(p)

            installed = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(installed["server"]["api_token"], "existing-private-token_123456")
            generate.assert_not_called()

    def test_copy_app_installs_codex_notify_helper_as_executable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "package"
            target = root / "installed"
            (project / "bridge").mkdir(parents=True)
            (project / "bridge/__init__.py").write_text("", encoding="utf-8")
            (project / "mac").mkdir()
            source = project / "mac/M5CodexNotify.sh"
            source.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
            (project / "config.example.json").write_text("{}\n", encoding="utf-8")
            helper = target / "bin/M5CodexNotify"
            p = {
                "project": project,
                "target": target,
                "installed_app": target / "app",
                "config": target / "config.json",
                "codex_notify_helper": helper,
            }

            self.installer.copy_app(p)

            self.assertEqual(helper.read_text(encoding="utf-8"), source.read_text(encoding="utf-8"))
            self.assertTrue(os.access(helper, os.X_OK))

    def test_copy_app_installs_claude_notify_helper_as_executable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "package"
            target = root / "installed"
            (project / "bridge").mkdir(parents=True)
            (project / "bridge/__init__.py").write_text("", encoding="utf-8")
            (project / "mac").mkdir()
            source = project / "mac/M5ClaudeNotify.sh"
            source.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
            (project / "config.example.json").write_text("{}\n", encoding="utf-8")
            helper = target / "bin/M5ClaudeNotify"
            p = {
                "project": project,
                "target": target,
                "installed_app": target / "app",
                "config": target / "config.json",
                "claude_notify_helper": helper,
            }

            self.installer.copy_app(p)

            self.assertEqual(helper.read_text(encoding="utf-8"), source.read_text(encoding="utf-8"))
            self.assertTrue(os.access(helper, os.X_OK))

    def test_claude_completion_hook_preserves_peon_ping_stop_handler(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "package"
            target = root / "installed"
            settings = root / ".claude/settings.json"
            settings.parent.mkdir(parents=True)
            peon = "/Users/example/.claude/hooks/peon-ping/peon.sh"
            settings.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "Stop": [
                                {
                                    "matcher": "",
                                    "hooks": [
                                        {"type": "command", "command": peon, "timeout": 10}
                                    ],
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            (project / "bridge").mkdir(parents=True)
            (project / "bridge/__init__.py").write_text("", encoding="utf-8")
            (project / "config.example.json").write_text("{}\n", encoding="utf-8")
            helper = target / "bin/M5ClaudeNotify"
            p = {
                "project": project,
                "target": target,
                "installed_app": target / "app",
                "config": target / "config.json",
                "claude_settings": settings,
                "claude_notify_helper": helper,
            }

            self.installer.install_claude_completion_hook(p)
            self.installer.install_claude_completion_hook(p)

            installed = json.loads(settings.read_text(encoding="utf-8"))
            handlers = [
                handler
                for group in installed["hooks"]["Stop"]
                for handler in group["hooks"]
            ]
            self.assertEqual(sum(handler["command"] == peon for handler in handlers), 1)
            self.assertEqual(sum(handler["command"] == str(helper) for handler in handlers), 1)

    def test_audio_helper_builds_from_tracked_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "project/mac/M5AudioInput.c"
            source.parent.mkdir(parents=True)
            source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
            helper = root / "installed/bin/m5_audio_input"
            p = {"project": root / "project", "audio_helper": helper}

            def fake_run(command, check):
                self.assertTrue(check)
                output = Path(command[command.index("-o") + 1])
                output.write_bytes(b"compiled")
                return mock.Mock(returncode=0)

            with mock.patch.object(self.installer.shutil, "which", return_value="/usr/bin/clang"), mock.patch.object(
                self.installer.subprocess, "run", side_effect=fake_run
            ):
                self.installer._install_audio_helper_binary(p)

            self.assertEqual(helper.read_bytes(), b"compiled")
            self.assertTrue(os.access(helper, os.X_OK))

    def test_session_audio_install_removes_the_legacy_global_agent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            launch_file = root / "com.local.m5dashboard.audio-input.plist"
            launch_file.write_text("legacy", encoding="utf-8")
            p = {
                "audio_helper": root / "m5_audio_input",
                "audio_launch_agent": launch_file,
            }
            with mock.patch.object(
                self.installer, "_install_audio_helper_binary"
            ) as install, mock.patch.object(
                self.installer.subprocess, "run", return_value=mock.Mock(returncode=0)
            ) as run:
                self.installer.install_session_audio_helper(p)
            self.assertFalse(launch_file.exists())
            install.assert_called_once_with(p)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertIn("bootout", commands[0])
            self.assertEqual(commands[1], [str(p["audio_helper"]), "release"])

    def test_typeless_key_helper_builds_as_a_stable_app_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "project/mac/TypelessKeySender.c"
            source.parent.mkdir(parents=True)
            source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
            helper = root / "installed/TypelessKeySender.app/Contents/MacOS/TypelessKeySender"
            info = root / "installed/TypelessKeySender.app/Contents/Info.plist"
            p = {
                "project": root / "project",
                "typeless_helper": helper,
                "typeless_helper_info": info,
            }

            commands = []

            def fake_run(command, check):
                self.assertTrue(check)
                commands.append(command)
                if "-o" in command:
                    output = Path(command[command.index("-o") + 1])
                    output.write_bytes(b"compiled")
                return mock.Mock(returncode=0)

            with mock.patch.object(
                self.installer.shutil, "which", return_value="/usr/bin/clang"
            ), mock.patch.object(
                self.installer.subprocess, "run", side_effect=fake_run
            ):
                self.installer.install_typeless_key_sender(p)

            self.assertEqual(helper.read_bytes(), b"compiled")
            self.assertTrue(os.access(helper, os.X_OK))
            self.assertEqual(
                self.installer.plistlib.loads(info.read_bytes())["CFBundleExecutable"],
                "TypelessKeySender",
            )
            self.assertTrue(
                any(
                    "--sign" in command
                    and "studio.machiwhale.m5stopwatch.typeless-key-sender" in command
                    for command in commands
                )
            )

    def test_typeless_key_helper_is_not_resigned_when_source_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "project/mac/TypelessKeySender.c"
            source.parent.mkdir(parents=True)
            source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
            app = root / "installed/TypelessKeySender.app"
            helper = app / "Contents/MacOS/TypelessKeySender"
            info = app / "Contents/Info.plist"
            helper.parent.mkdir(parents=True)
            helper.write_bytes(b"approved-existing-helper")
            info.write_bytes(b"existing-plist")
            p = {
                "project": root / "project",
                "typeless_helper": helper,
                "typeless_helper_info": info,
            }

            with mock.patch.object(
                self.installer.shutil, "which", return_value="/usr/bin/clang"
            ), mock.patch.object(self.installer.subprocess, "run") as run:
                self.installer.install_typeless_key_sender(p)
                self.installer.install_typeless_key_sender(p)

            run.assert_not_called()
            self.assertEqual(helper.read_bytes(), b"approved-existing-helper")
            self.assertTrue(
                (app.parent / ".TypelessKeySender.source-sha256").is_file()
            )

    def test_typeless_preflight_fails_before_install_without_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            p = {
                "project": root / "project",
                "typeless_settings": root / "missing-settings.json",
            }
            with self.assertRaisesRegex(SystemExit, "Open Typeless once"):
                self.installer.preflight_typeless_install(p)


if __name__ == "__main__":
    unittest.main()

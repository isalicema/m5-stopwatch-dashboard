import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from bridge.typeless_client import TypelessController


class TypelessControllerTests(unittest.TestCase):
    @staticmethod
    def successful_run(command, **_kwargs):
        stdout = "42\n" if len(command) > 1 and command[1] == "capture" else ""
        return subprocess.CompletedProcess(command, 0, stdout, "")

    def controller(self, directory: str) -> TypelessController:
        helper = Path(directory) / "TypelessKeySender"
        helper.write_bytes(b"helper")
        helper.chmod(0o755)
        audio_helper = Path(directory) / "m5_audio_input"
        audio_helper.write_bytes(b"audio helper")
        audio_helper.chmod(0o755)
        return TypelessController(
            {
                "helper_path": str(helper),
                "audio_helper_path": str(audio_helper),
                "shortcut": "ctrl-cmd-shift-space",
                "command_timeout_seconds": 4,
            }
        )

    def test_start_does_not_reopen_running_typeless_and_toggles_shortcut(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            with mock.patch.object(controller, "_is_running", return_value=True), mock.patch(
                "bridge.typeless_client.subprocess.run", side_effect=self.successful_run
            ) as run:
                state = controller.perform("start")
            self.assertEqual(state, {"connected": True, "active": True})
            self.assertEqual(
                run.call_args_list[1].args[0],
                [str(controller.helper), "ctrl-cmd-shift-space"],
            )
            self.assertEqual(
                run.call_args_list[0].args[0],
                [str(controller.audio_helper), "capture"],
            )

    def test_start_waits_for_a_new_typeless_process_before_sending_shortcut(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            with mock.patch.object(
                controller, "_is_running", side_effect=[False, False, True]
            ), mock.patch(
                "bridge.typeless_client.subprocess.run", side_effect=self.successful_run
            ) as run, mock.patch("bridge.typeless_client.time.sleep") as sleep:
                controller.perform("start")
            self.assertEqual(run.call_args_list[1].args[0], ["/usr/bin/open", "-gj", "-a", "Typeless"])
            self.assertEqual(
                run.call_args_list[2].args[0],
                [str(controller.helper), "ctrl-cmd-shift-space"],
            )
            self.assertIn(mock.call(controller.startup_delay), sleep.call_args_list)

    def test_successful_start_then_stop_uses_the_same_typeless_toggle(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            with mock.patch.object(controller, "_is_running", return_value=True), mock.patch(
                "bridge.typeless_client.subprocess.run", side_effect=self.successful_run
            ) as run:
                self.assertTrue(controller.perform("start")["active"])
                self.assertFalse(controller.perform("stop")["active"])
            self.assertEqual(run.call_count, 4)
            self.assertEqual(
                run.call_args_list[-1].args[0],
                [str(controller.audio_helper), "restore", "42"],
            )

    def test_system_mode_uses_the_existing_mac_microphone_without_capture_or_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            with mock.patch.object(controller, "_is_running", return_value=True), mock.patch(
                "bridge.typeless_client.subprocess.run", side_effect=self.successful_run
            ) as run:
                self.assertTrue(controller.perform("start", "system")["active"])
                self.assertFalse(controller.perform("stop")["active"])
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(
                commands,
                [
                    [str(controller.helper), "ctrl-cmd-shift-space"],
                    [str(controller.helper), "ctrl-cmd-shift-space"],
                ],
            )
            self.assertFalse(any(controller.audio_helper in map(Path, command) for command in commands))

    def test_request_acknowledges_immediately_and_serializes_start_then_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            completed = threading.Event()
            actions = []

            def perform(action, audio_mode="m5"):
                actions.append((action, audio_mode))
                if action == "stop":
                    completed.set()
                return {"connected": True, "active": action == "start"}

            with mock.patch.object(controller, "perform", side_effect=perform):
                started = controller.request("start", "system")
                stopped = controller.request("stop", "system")
                self.assertTrue(completed.wait(1))

            self.assertEqual(started, {"active": True, "pending": True})
            self.assertEqual(stopped, {"active": False, "pending": True})
            self.assertEqual(actions, [("start", "system"), ("stop", "system")])

    def test_installed_app_helper_reports_its_own_exit_status(self):
        with tempfile.TemporaryDirectory() as directory:
            helper = (
                Path(directory)
                / "TypelessKeySender.app/Contents/MacOS/TypelessKeySender"
            )
            helper.parent.mkdir(parents=True)
            helper.write_bytes(b"helper")
            helper.chmod(0o755)
            audio_helper = Path(directory) / "m5_audio_input"
            audio_helper.write_bytes(b"audio helper")
            audio_helper.chmod(0o755)
            controller = TypelessController(
                {
                    "helper_path": str(helper),
                    "audio_helper_path": str(audio_helper),
                    "shortcut": "ctrl-cmd-shift-space",
                }
            )
            with mock.patch.object(
                controller, "_is_running", return_value=True
            ), mock.patch(
                "bridge.typeless_client.subprocess.run", side_effect=self.successful_run
            ) as run:
                controller.perform("start")
            self.assertEqual(
                run.call_args_list[1].args[0],
                [str(helper), "ctrl-cmd-shift-space"],
            )

    def test_stop_is_idempotent_when_start_was_never_confirmed(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            with mock.patch.object(controller, "_is_running", return_value=True), mock.patch(
                "bridge.typeless_client.subprocess.run"
            ) as run:
                self.assertEqual(
                    controller.perform("stop"),
                    {"connected": True, "active": False},
                )
            run.assert_not_called()

    def test_accessibility_failure_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            def denied_then_restore(command, **kwargs):
                if len(command) > 1 and command[1] == "capture":
                    return self.successful_run(command, **kwargs)
                if len(command) > 1 and command[1] == "restore":
                    return self.successful_run(command, **kwargs)
                return subprocess.CompletedProcess(command, 70, "", "accessibility_trusted=false")

            with mock.patch.object(controller, "_is_running", return_value=True), mock.patch(
                "bridge.typeless_client.subprocess.run", side_effect=denied_then_restore
            ) as run:
                with self.assertRaisesRegex(ValueError, "Accessibility"):
                    controller.perform("start")
            self.assertEqual(
                run.call_args_list[-1].args[0],
                [str(controller.audio_helper), "restore", "42"],
            )

    def test_failed_typeless_launch_restores_the_previous_input(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            with mock.patch.object(
                controller, "_ensure_ready", side_effect=ValueError("launch failed")
            ), mock.patch(
                "bridge.typeless_client.subprocess.run", side_effect=self.successful_run
            ) as run:
                with self.assertRaisesRegex(ValueError, "launch failed"):
                    controller.perform("start")
            self.assertEqual(
                [call.args[0] for call in run.call_args_list],
                [
                    [str(controller.audio_helper), "capture"],
                    [str(controller.audio_helper), "restore", "42"],
                ],
            )

    def test_unknown_shortcut_and_action_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported Typeless shortcut"):
            TypelessController({"shortcut": "F13"})
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            with self.assertRaisesRegex(ValueError, "unsupported Typeless action"):
                controller.perform("erase")
            with self.assertRaisesRegex(ValueError, "unsupported Typeless audio mode"):
                controller.perform("start", "bluetooth")


if __name__ == "__main__":
    unittest.main()

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bridge.typeless_client import TypelessController


class TypelessControllerTests(unittest.TestCase):
    def controller(self, directory: str) -> TypelessController:
        helper = Path(directory) / "TypelessKeySender"
        helper.write_bytes(b"helper")
        helper.chmod(0o755)
        return TypelessController(
            {
                "helper_path": str(helper),
                "shortcut": "ctrl-cmd-shift-space",
                "command_timeout_seconds": 4,
            }
        )

    def test_start_does_not_reopen_running_typeless_and_toggles_shortcut(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            completed = subprocess.CompletedProcess([], 0, "", "")
            with mock.patch.object(controller, "_is_running", return_value=True), mock.patch(
                "bridge.typeless_client.subprocess.run", return_value=completed
            ) as run:
                state = controller.perform("start")
            self.assertEqual(state, {"connected": True, "active": True})
            self.assertEqual(
                run.call_args_list[0].args[0],
                [str(controller.helper), "ctrl-cmd-shift-space"],
            )

    def test_start_waits_for_a_new_typeless_process_before_sending_shortcut(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            completed = subprocess.CompletedProcess([], 0, "", "")
            with mock.patch.object(
                controller, "_is_running", side_effect=[False, False, True]
            ), mock.patch(
                "bridge.typeless_client.subprocess.run", return_value=completed
            ) as run, mock.patch("bridge.typeless_client.time.sleep") as sleep:
                controller.perform("start")
            self.assertEqual(run.call_args_list[0].args[0], ["/usr/bin/open", "-gj", "-a", "Typeless"])
            self.assertEqual(
                run.call_args_list[1].args[0],
                [str(controller.helper), "ctrl-cmd-shift-space"],
            )
            self.assertIn(mock.call(controller.startup_delay), sleep.call_args_list)

    def test_successful_start_then_stop_uses_the_same_typeless_toggle(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            completed = subprocess.CompletedProcess([], 0, "", "")
            with mock.patch.object(controller, "_is_running", return_value=True), mock.patch(
                "bridge.typeless_client.subprocess.run", return_value=completed
            ) as run:
                self.assertTrue(controller.perform("start")["active"])
                self.assertFalse(controller.perform("stop")["active"])
            self.assertEqual(run.call_count, 2)

    def test_installed_app_helper_reports_its_own_exit_status(self):
        with tempfile.TemporaryDirectory() as directory:
            helper = (
                Path(directory)
                / "TypelessKeySender.app/Contents/MacOS/TypelessKeySender"
            )
            helper.parent.mkdir(parents=True)
            helper.write_bytes(b"helper")
            helper.chmod(0o755)
            controller = TypelessController(
                {
                    "helper_path": str(helper),
                    "shortcut": "ctrl-cmd-shift-space",
                }
            )
            completed = subprocess.CompletedProcess([], 0, "", "")
            with mock.patch.object(
                controller, "_is_running", return_value=True
            ), mock.patch(
                "bridge.typeless_client.subprocess.run", return_value=completed
            ) as run:
                controller.perform("start")
            self.assertEqual(
                run.call_args_list[0].args[0],
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
            denied = subprocess.CompletedProcess([], 70, "", "accessibility_trusted=false")
            with mock.patch.object(controller, "_is_running", return_value=True), mock.patch(
                "bridge.typeless_client.subprocess.run", side_effect=[denied]
            ):
                with self.assertRaisesRegex(ValueError, "Accessibility"):
                    controller.perform("start")

    def test_unknown_shortcut_and_action_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported Typeless shortcut"):
            TypelessController({"shortcut": "F13"})
        with tempfile.TemporaryDirectory() as directory:
            controller = self.controller(directory)
            with self.assertRaisesRegex(ValueError, "unsupported Typeless action"):
                controller.perform("erase")


if __name__ == "__main__":
    unittest.main()

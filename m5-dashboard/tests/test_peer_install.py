import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def load_installer():
    source = Path(__file__).resolve().parents[1] / "scripts/install.py"
    spec = importlib.util.spec_from_file_location("m5_peer_installer", source)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PeerInstallTests(unittest.TestCase):
    def test_peer_node_disables_m5_transports_and_keeps_local_activity(self):
        installer = load_installer()
        with tempfile.TemporaryDirectory() as root:
            project = Path(root) / "shared-package"
            target = Path(root) / "Library/Application Support/M5Dashboard-Peer"
            (project / "bridge").mkdir(parents=True)
            (project / "bridge/__init__.py").write_text("", encoding="utf-8")
            (project / "config.json").write_text(
                json.dumps({"server": {"api_token": "shared-test-token"}}),
                encoding="utf-8",
            )
            paths = {
                "project": project,
                "target": target,
                "installed_app": target / "app",
                "config": target / "config.json",
            }

            installer.copy_peer_app(paths)

            installed = json.loads(paths["config"].read_text(encoding="utf-8"))
            self.assertEqual(installed["server"]["api_token"], "shared-test-token")
            self.assertEqual(installed["server"]["device_label"], "iMac")
            self.assertFalse(installed["server"]["discovery_enabled"])
            self.assertFalse(installed["server"]["usb_enabled"])
            self.assertNotIn("bambu", installed)
            self.assertFalse(installed["ticktick"]["enabled"])
            self.assertFalse(installed["weather"]["enabled"])
            self.assertTrue(installed["codex"]["expose_transcript"])
            self.assertTrue(installed["claude"]["local_only"])
            self.assertEqual(installed["peers"], [])
            self.assertEqual(paths["config"].stat().st_mode & 0o777, 0o600)

    def test_configures_activity_peer_from_existing_usage_host(self):
        installer = load_installer()
        with tempfile.TemporaryDirectory() as root:
            config_path = Path(root) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "server": {"api_token": "unchanged"},
                        "codex": {
                            "peer_usage_sources": [
                                {
                                    "id": "office-usage",
                                    "base_url": "http://192.0.2.60:8787",
                                    "password": "private",
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )

            installer.configure_peer_from_usage({"config": config_path})
            installer.configure_peer_from_usage({"config": config_path})

            installed = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(installed["server"]["api_token"], "unchanged")
            self.assertEqual(
                installed["codex"]["peer_usage_sources"][0]["password"], "private"
            )
            self.assertEqual(
                installed["peers"],
                [
                    {
                        "id": "office-usage",
                        "label": "iMac",
                        "base_url": "http://192.0.2.60:8765",
                        "timeout_seconds": 3,
                        "usage_auth_source": "office-usage",
                    }
                ],
            )

    def test_peer_usb_uses_separate_m5_token_and_air_upstream(self):
        installer = load_installer()
        with tempfile.TemporaryDirectory() as root:
            project = Path(root) / "safe-package"
            target = Path(root) / "M5Dashboard-Peer"
            (project / "bridge").mkdir(parents=True)
            (project / "bridge/__init__.py").write_text("", encoding="utf-8")
            target.mkdir(parents=True)
            config = target / "config.json"
            config.write_text(
                json.dumps({"server": {"api_token": "peer-http-token"}}),
                encoding="utf-8",
            )
            paths = {
                "project": project,
                "target": target,
                "installed_app": target / "app",
                "config": config,
            }
            environment = {
                "M5_PEER_USB_API_TOKEN": "m5-work-token",
                "M5_PEER_USB_UPSTREAM_URL": "http://air.local:8765",
            }
            with patch.dict("os.environ", environment, clear=False):
                installer.copy_peer_app(paths, enable_usb=True)

            installed = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(installed["server"]["api_token"], "peer-http-token")
            self.assertTrue(installed["server"]["usb_enabled"])
            self.assertFalse(installed["server"]["discovery_enabled"])
            self.assertEqual(installed["server"]["usb_api_token"], "m5-work-token")
            self.assertEqual(
                installed["server"]["usb_upstream"],
                {
                    "base_url": "http://air.local:8765",
                    "api_token": "m5-work-token",
                    "timeout_seconds": 2,
                },
            )

    def test_peer_node_can_receive_token_without_a_shared_private_config(self):
        installer = load_installer()
        with tempfile.TemporaryDirectory() as root:
            project = Path(root) / "safe-package"
            target = Path(root) / "M5Dashboard-Peer"
            (project / "bridge").mkdir(parents=True)
            (project / "bridge/__init__.py").write_text("", encoding="utf-8")
            paths = {
                "project": project,
                "target": target,
                "installed_app": target / "app",
                "config": target / "config.json",
            }

            with patch.dict("os.environ", {"M5_PEER_API_TOKEN": "local-runtime-token"}):
                installer.copy_peer_app(paths)

            installed = json.loads(paths["config"].read_text(encoding="utf-8"))
            self.assertEqual(installed["server"]["api_token"], "local-runtime-token")


if __name__ == "__main__":
    unittest.main()

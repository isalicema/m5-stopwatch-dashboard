import importlib.util
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from bridge.app import build_handler
from bridge.ota import FACTORY_OTA_PARTITION_SIZE, FirmwareCatalog


def load_publisher():
    source = Path(__file__).resolve().parents[1] / "scripts/publish_ota.py"
    spec = importlib.util.spec_from_file_location("m5_publish_ota", source)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class OtaBridgeTests(unittest.TestCase):
    def setUp(self):
        self.publisher = load_publisher()

    def _release(self, root: Path, payload: bytes = b"\xe9firmware"):
        firmware = root / "candidate.bin"
        firmware.write_bytes(payload)
        directory = root / "ota"
        manifest = self.publisher.publish(firmware, directory)
        catalog = FirmwareCatalog(
            {
                "enabled": True,
                "directory": str(directory),
                "max_firmware_bytes": FACTORY_OTA_PARTITION_SIZE,
            }
        )
        return payload, manifest, catalog

    def test_publish_is_immutable_and_catalog_rechecks_sha(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload, manifest, catalog = self._release(root)
            release = catalog.current()
            self.assertIsNotNone(release)
            self.assertEqual(release.path.read_bytes(), payload)
            self.assertEqual(release.release_id, manifest["sha256"])
            release.path.write_bytes(payload + b"tampered")
            self.assertIsNone(catalog.current())

    def test_publish_rejects_non_esp_and_oversized_images(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            invalid = root / "invalid.bin"
            invalid.write_bytes(b"not-an-image")
            with self.assertRaisesRegex(ValueError, "ESP application image"):
                self.publisher.publish(invalid, root / "ota")
            oversized = root / "oversized.bin"
            with oversized.open("wb") as handle:
                handle.seek(FACTORY_OTA_PARTITION_SIZE)
                handle.write(b"\0")
            with self.assertRaisesRegex(ValueError, "does not fit"):
                self.publisher.publish(oversized, root / "ota")

    def test_manifest_and_firmware_require_dashboard_token(self):
        with tempfile.TemporaryDirectory() as temporary:
            payload, manifest, catalog = self._release(Path(temporary))
            handler = build_handler(object(), "secret", ota_catalog=catalog)

            unauthorized = handler.__new__(handler)
            unauthorized.path = "/api/ota/manifest"
            unauthorized.headers = {"X-Dashboard-Token": "wrong"}
            response = {}
            unauthorized._json = lambda status, body: response.update(status=status, body=body)
            unauthorized.do_GET()
            self.assertEqual(response["status"], 401)

            manifest_request = handler.__new__(handler)
            manifest_request.path = "/api/ota/manifest"
            manifest_request.headers = {"X-Dashboard-Token": "secret"}
            response = {}
            manifest_request._json = lambda status, body: response.update(status=status, body=body)
            manifest_request.do_GET()
            self.assertEqual(response["status"], 200)
            self.assertEqual(response["body"]["size"], len(payload))
            self.assertEqual(response["body"]["sha256"], manifest["sha256"])

            download = handler.__new__(handler)
            download.path = "/api/ota/firmware/" + manifest["sha256"]
            download.headers = {"X-Dashboard-Token": "secret"}
            download.wfile = BytesIO()
            headers = {}
            download.send_response = lambda status: headers.update(status=status)
            download.send_header = lambda name, value: headers.update({name: value})
            download.end_headers = lambda: None
            download.do_GET()
            self.assertEqual(headers["status"], 200)
            self.assertEqual(headers["Content-Length"], str(len(payload)))
            self.assertEqual(headers["X-Firmware-SHA256"], manifest["sha256"])
            self.assertEqual(download.wfile.getvalue(), payload)

    def test_missing_candidate_returns_no_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            catalog = FirmwareCatalog({"enabled": True, "directory": temporary})
            handler = build_handler(object(), "secret", ota_catalog=catalog)
            request = handler.__new__(handler)
            request.path = "/api/ota/manifest"
            request.headers = {"X-Dashboard-Token": "secret"}
            response = {"headers": {}}
            request.send_response = lambda status: response.update(status=status)
            request.send_header = lambda name, value: response["headers"].update({name: value})
            request.end_headers = lambda: None
            request.do_GET()
            self.assertEqual(response["status"], 204)


if __name__ == "__main__":
    unittest.main()

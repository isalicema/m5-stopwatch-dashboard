import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bridge.mqtt_client import resolve_connection
from scripts.cloud_setup import decode_user_id, normalize_devices, request_json, verification_request


TEST_PHONE = "138" + "00000000"
TEST_EMAIL = "user" + "@example.com"


class EmptyResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return b""


class CloudSetupTests(unittest.TestCase):
    def test_decodes_uid_from_jwt_without_exposing_token(self):
        payload = base64.urlsafe_b64encode(json.dumps({"uid": "12345"}).encode()).decode().rstrip("=")
        self.assertEqual(decode_user_id("header.%s.signature" % payload), "u_12345")

    def test_normalizes_bound_devices(self):
        result = normalize_devices(
            {
                "data": [
                    {"dev_id": "SERIAL1", "name": "Workshop", "dev_product_name": "P2S"}
                ]
            }
        )
        self.assertEqual(
            result,
            [{"serial": "SERIAL1", "name": "Workshop", "model": "P2S"}],
        )

    def test_cloud_credentials_stay_in_separate_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bambu-cloud.json"
            path.write_text(
                json.dumps(
                    {
                        "mode": "cloud",
                        "region": "cn",
                        "user_id": "42",
                        "access_token": "secret-token",
                        "serial": "SERIAL1",
                    }
                )
            )
            result = resolve_connection(
                {"mode": "cloud", "credentials_file": str(path), "full_refresh_seconds": 10}
            )
        self.assertEqual(result["host"], "cn.mqtt.bambulab.com")
        self.assertEqual(result["username"], "u_42")
        self.assertEqual(result["password"], "secret-token")
        self.assertTrue(result["verify_tls"])
        self.assertEqual(result["full_refresh_seconds"], 300)

    def test_cn_phone_uses_sms_endpoint(self):
        url, payload, channel = verification_request(TEST_PHONE, "cn")
        self.assertEqual(url, "https://bambulab.cn/api/v1/user-service/user/sendsmscode")
        self.assertEqual(payload, {"phone": TEST_PHONE, "type": "codeLogin"})
        self.assertEqual(channel, "短信")

    def test_email_uses_email_endpoint(self):
        url, payload, channel = verification_request(TEST_EMAIL, "global")
        self.assertTrue(url.endswith("/v1/user-service/user/sendemail/code"))
        self.assertEqual(payload, {"email": TEST_EMAIL, "type": "codeLogin"})
        self.assertEqual(channel, "邮箱")

    @patch("scripts.cloud_setup.urllib.request.urlopen", return_value=EmptyResponse())
    def test_sms_empty_2xx_response_is_success(self, _urlopen):
        result = request_json(
            "https://bambulab.cn/api/v1/user-service/user/sendsmscode",
            method="POST",
            payload={"phone": TEST_PHONE, "type": "codeLogin"},
            allow_empty=True,
        )
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()

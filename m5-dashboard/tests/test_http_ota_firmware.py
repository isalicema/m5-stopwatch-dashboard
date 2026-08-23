import csv
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
SOURCE = (PROJECT / "firmware/M5Dashboard/M5Dashboard.ino").read_text(encoding="utf-8")


class HttpOtaFirmwareTests(unittest.TestCase):
    def test_factory_partition_contract_has_two_equal_ota_slots(self):
        path = PROJECT / "firmware/stopwatch_factory_16MB.csv"
        rows = {}
        with path.open(encoding="utf-8") as handle:
            for row in csv.reader(line for line in handle if not line.lstrip().startswith("#")):
                if row:
                    rows[row[0].strip()] = [item.strip() for item in row]
        self.assertEqual(rows["ota_0"][3:5], ["0x20000", "0x4f0000"])
        self.assertEqual(rows["ota_1"][3:5], ["0x510000", "0x4f0000"])
        self.assertEqual(rows["otadata"][3:5], ["0xd000", "0x2000"])

    def test_manifest_and_binary_use_authenticated_bridge_routes(self):
        self.assertIn('"/api/ota/manifest"', SOURCE)
        self.assertIn('"/api/ota/firmware/" + sha256', SOURCE)
        self.assertGreaterEqual(SOURCE.count('http.addHeader("X-Dashboard-Token"'), 4)
        self.assertIn('http.header("X-Firmware-SHA256") != sha256', SOURCE)
        self.assertIn('http.header("X-Firmware-Release") != sha256', SOURCE)

    def test_sha_and_image_validation_precede_boot_partition_switch(self):
        stream = SOURCE[SOURCE.index("bool streamOtaFirmware(") : SOURCE.index("void updateHttpOta()")]
        self.assertIn("mbedtls_sha256_update", stream)
        self.assertIn("received != imageSize", stream)
        self.assertIn("sha256 != String(actualHex)", stream)
        self.assertIn("esp_ota_end(handle)", stream)
        self.assertIn("esp_ota_set_boot_partition(target)", stream)
        self.assertLess(stream.index("sha256 != String(actualHex)"), stream.index("esp_ota_end(handle)"))
        self.assertLess(stream.index("esp_ota_end(handle)"), stream.index("esp_ota_set_boot_partition(target)"))

    def test_ota_is_deferred_during_interactive_or_low_power_work(self):
        update = SOURCE[SOURCE.index("void updateHttpOta()") : SOURCE.index("bool fetchState()")]
        self.assertIn("timerRunning(ticktick.stopwatchState)", update)
        self.assertIn("voiceSessionActive || voiceCaptureActive", update)
        self.assertIn("completionAnimationRunning", update)
        self.assertIn("deviceBatteryLevel", update)
        self.assertIn("currentPage != 0", update)

    def test_new_image_is_marked_valid_only_after_setup_completes(self):
        setup = SOURCE[SOURCE.index("void setup()") : SOURCE.index("void loop()")]
        self.assertIn("esp_ota_mark_app_valid_cancel_rollback();", setup)
        self.assertGreater(
            setup.index("esp_ota_mark_app_valid_cancel_rollback();"),
            setup.index("drawCurrentPage();"),
        )

    def test_ota_status_owns_the_full_physical_frame(self):
        status = SOURCE[
            SOURCE.index("void drawOtaStatus(") : SOURCE.index(
                "bool fetchOtaManifest("
            )
        ]
        self.assertIn("editorialFrameAccentActive = false;", status)
        self.assertIn("editorialFrameBurstActive = false;", status)
        self.assertIn("composeRenderedFrame(background);", status)
        self.assertIn("pushRenderedFrame(background);", status)

    def test_ota_progress_never_holds_the_motor_during_blocking_transfer(self):
        pulse = SOURCE[
            SOURCE.index("bool forceVibrationOffVerified(") : SOURCE.index(
                "void startCompletionAnimation("
            )
        ]
        self.assertIn("kRequiredConfirmations = 3", pulse)
        self.assertIn("kMaximumAttempts = 12", pulse)
        self.assertIn("ioe1.writeRegister(kMotorPwmRegister", pulse)
        self.assertIn("ioe1.readRegister(kMotorPwmRegister", pulse)
        self.assertIn("actualPwm[0] == 0x00 && actualPwm[1] == 0x00", pulse)
        self.assertIn("delay(durationMs);", pulse)
        self.assertIn("forceVibrationOffVerified();", pulse)
        self.assertIn("delay(40);", pulse)

        update = SOURCE[SOURCE.index("void updateHttpOta()") : SOURCE.index("bool fetchState()")]
        self.assertNotIn("startVibration(", update)
        self.assertEqual(update.count("pulseVibrationBlocking("), 3)
        self.assertIn("if (!pulseVibrationBlocking(120, 100))", update)
        self.assertLess(
            update.index("if (!pulseVibrationBlocking(120, 100))"),
            update.index("streamOtaFirmware(sha256, imageSize)"),
        )
        self.assertIn('drawOtaStatus("MOTOR ERROR", -1);', update)
        self.assertIn("pulseVibrationBlocking(150, 180);", update)
        self.assertIn("pulseVibrationBlocking(190, 220);", update)


if __name__ == "__main__":
    unittest.main()

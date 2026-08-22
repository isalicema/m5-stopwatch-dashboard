from pathlib import Path
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class AppShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (PROJECT / "firmware/M5Dashboard/M5Dashboard.ino").read_text(
            encoding="utf-8"
        )
        cls.logic = (PROJECT / "firmware/M5Dashboard/app_shell_logic.h").read_text(
            encoding="utf-8"
        )
        cls.interaction_logic = (
            PROJECT / "firmware/M5Dashboard/interaction_logic.h"
        ).read_text(encoding="utf-8")
        cls.device_config = (
            PROJECT / "firmware/M5Dashboard/device_config.cpp"
        ).read_text(encoding="utf-8")

    def test_boots_into_two_program_launcher(self):
        self.assertIn("DashboardAppMode appMode = DashboardAppMode::launcher", self.source)
        self.assertIn('canvas.drawString("选择程序"', self.source)
        self.assertIn('"DASHBOARD" : "STOPWATCH"', self.source)
        self.assertIn("enterDashboardApp();", self.source)
        self.assertIn("enterLocalStopwatchApp();", self.source)

    def test_local_stopwatch_preserves_factory_button_semantics(self):
        self.assertIn("localStopwatchLap(model, now)", self.logic)
        self.assertIn("localStopwatchReset(model)", self.logic)
        self.assertIn("localStopwatchPause(model, now)", self.logic)
        self.assertIn("localStopwatchStart(model, now)", self.logic)
        self.assertIn('state == LocalStopwatchState::paused ? "RESET" : "LAP"', self.logic)
        self.assertIn('state == LocalStopwatchState::running ? "STOP" : "START"', self.logic)

    def test_power_short_sleeps_double_opens_launcher_and_usb_hold_is_reserved(self):
        normalized_logic = " ".join(self.interaction_logic.split())
        self.assertIn("DashboardPowerAction::toggleScreen", self.source)
        self.assertIn("DashboardPowerAction::openLauncher", self.source)
        self.assertIn("setScreenLocked(!screenLocked);", self.source)
        self.assertIn("enterAppLauncher();", self.source)
        self.assertIn(
            "kPowerButtonDoubleClickMs, kPowerButtonLongPressMs, deviceUsbConnected",
            self.source,
        )
        self.assertIn("M5.Power.getVBUSVoltage()", self.source)
        self.assertIn(
            "if (!usbConnected) action = DashboardPowerAction::powerOff",
            normalized_logic,
        )

    def test_screen_standby_keeps_bridge_and_arms_ai_hotspot_wake(self):
        lock_block = self.source.split("void setScreenLocked(bool locked)", 1)[1].split(
            "void updatePowerButton()", 1
        )[0]
        self.assertIn("stopVoiceForStandby();", lock_block)
        self.assertIn("setAmoledHardwareSleep(true);", lock_block)
        self.assertNotIn("WiFi.mode(WIFI_OFF)", lock_block)
        self.assertNotIn("WiFi.disconnect(true, false)", lock_block)
        self.assertIn(
            "newAiHotspot && (screenLocked || appMode == DashboardAppMode::dashboard)",
            self.source,
        )
        self.assertIn("pendingAiHotspotWake = true;", self.source)
        self.assertIn("currentPage = 5;", lock_block)
        locked_loop = self.source.split("void loop()", 1)[1].split(
            "if (screenLocked) {", 1
        )[1].split("updateOverlayTimeout();", 1)[0]
        self.assertIn("updateUsbBridge();", locked_loop)
        self.assertIn("updateBridgeDiscovery();", locked_loop)

    def test_usb_first_boot_never_forces_wifi_provisioning(self):
        self.assertIn('kUsbPairRequestPrefix[] = "M5DASH_USB_V1|PAIR|"', self.source)
        self.assertIn('kUsbPairResponsePrefix[] = "M5DASH_USB_V1|PAIRED|"', self.source)
        self.assertIn("dashboardUsbPairingTokenValid", self.source)
        no_wifi_block = self.source.split(
            "if (!homeConfigured && !workConfigured) {", 1
        )[1].split("}", 1)[0]
        self.assertIn("USB-first is a complete operating mode", no_wifi_block)
        self.assertNotIn("startProvisioning", no_wifi_block)
        self.assertIn("startProvisioning();", self.source)
        self.assertIn('prefs.getString("ssid", "\\x01") == settings.ssid', self.device_config)
        self.assertNotIn('prefs.putString("ssid", settings.ssid) > 0', self.device_config)

    def test_stopwatch_animation_uses_partial_high_frequency_rendering(self):
        self.assertIn("kStopwatchFrameIntervalMs = 20", self.source)
        self.assertIn("requireHighPerformance();\n      drawLocalStopwatchTimeOnly();", self.source)
        self.assertIn("stopwatchTimeCanvas.pushSprite", self.source)
        self.assertIn("canvas.fillSmoothRoundRect(98, 54, 105, 72, 34", self.source)
        self.assertNotIn("canvas.setFont(&fonts::Font8);\n  canvas.setTextSize(0.82f);", self.source)

    def test_stopwatch_time_uses_one_fixed_baseline_for_full_and_partial_frames(self):
        self.assertIn("kStopwatchTimeBaselineY = 226", self.source)
        self.assertIn("target.setTextDatum(baseline_center)", self.source)
        self.assertIn(
            "kStopwatchTimeBaselineY - kStopwatchTimeY", self.source
        )
        self.assertIn(
            "drawLocalStopwatchTimeText(canvas, 225, kStopwatchTimeBaselineY)",
            self.source,
        )

    def test_stopwatch_laps_page_through_the_list_region(self):
        self.assertIn("localStopwatchLapRegionContains(designX, designY)", self.source)
        self.assertIn("touch.distanceY() < 0 ? 1 : -1", self.source)
        self.assertIn("localStopwatchLapPageOffset(", self.source)
        self.assertIn("上滑回看 · 双击电源键", self.source)
        self.assertIn("下滑返回最新 · 双击电源键", self.source)
        self.assertIn("localStopwatchLapOffset = 0", self.source)
        self.assertIn("kStopwatchFooterY = 408", self.source)
        self.assertIn("canvas.drawString(footer, 225, kStopwatchFooterY)", self.source)
        footer_block = self.source.split('String footer = "双击电源键返回"', 1)[0]
        footer_setup = footer_block.rsplit("useChinese16();", 1)[1]
        self.assertIn("canvas.setTextSize(1);", footer_setup)
        self.assertNotIn("canvas.setTextSize(0.9f);", footer_setup)


if __name__ == "__main__":
    unittest.main()

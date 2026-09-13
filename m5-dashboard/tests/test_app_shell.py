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

    def test_boots_into_three_program_launcher(self):
        self.assertIn("DashboardAppMode appMode = DashboardAppMode::launcher", self.source)
        self.assertIn('canvas.drawString("选择程序"', self.source)
        self.assertIn('"DASHBOARD" : "STOPWATCH"', self.source)
        self.assertIn('canvas.drawString("TIMER"', self.source)
        self.assertIn("enterDashboardApp();", self.source)
        self.assertIn("enterLocalStopwatchApp();", self.source)
        self.assertIn("enterLocalCountdownApp();", self.source)

    def test_local_stopwatch_preserves_factory_button_semantics(self):
        self.assertIn("localStopwatchLap(model, now)", self.logic)
        self.assertIn("localStopwatchReset(model)", self.logic)
        self.assertIn("localStopwatchPause(model, now)", self.logic)
        self.assertIn("localStopwatchStart(model, now)", self.logic)
        self.assertIn('state == LocalStopwatchState::paused ? "RESET" : "LAP"', self.logic)
        self.assertIn('state == LocalStopwatchState::running ? "STOP" : "START"', self.logic)

    def test_countdown_timer_has_two_persistent_adjustable_presets(self):
        self.assertIn("uint16_t presetMinutes[2] = {8, 10};", self.logic)
        self.assertIn("kLocalCountdownMinimumMinutes = 1", self.logic)
        self.assertIn("kLocalCountdownMaximumMinutes = 99", self.logic)
        self.assertIn("LocalCountdownEditorModel", self.logic)
        self.assertIn("localCountdownBeginEditing", self.logic)
        self.assertIn("localCountdownAdjustEditorMinutes", self.logic)
        self.assertIn("localCountdownCommitEditing", self.logic)
        self.assertIn("localCountdownPresetAction", self.logic)
        self.assertIn('prefs.begin("m5dash-timer", true)', self.source)
        self.assertIn('prefs.putUShort("presetA"', self.source)
        self.assertIn('prefs.putUShort("presetB"', self.source)

    def test_countdown_timer_is_local_wakes_and_alerts_at_deadline(self):
        update = self.source.split("void updateLocalCountdownTimer()", 1)[1].split(
            "void updateAppShellButtons()", 1
        )[0]
        self.assertIn("localCountdownUpdate(localCountdown, now)", update)
        self.assertIn("appMode = DashboardAppMode::countdownTimer;", update)
        self.assertIn("if (screenLocked)", update)
        self.assertIn("setScreenLocked(false);", update)
        self.assertIn("startVibration(205, 520);", update)
        self.assertIn("startTonePattern(kCountdownDoneTones", update)
        self.assertIn("localCountdownActive(localCountdown)", self.source)
        self.assertIn(
            "{988, 180, 60}, {659, 420, 320}, {988, 180, 60}, {659, 780, 0}",
            self.source,
        )
        self.assertIn("kAiScreamTones", self.source)

    def test_countdown_timer_keeps_stopwatch_style_and_large_touch_actions(self):
        timer_page = self.source.split("void drawLocalCountdownPage()", 1)[1].split(
            "void renderCurrentPage", 1
        )[0]
        self.assertIn('canvas.drawString("TIMER"', timer_page)
        self.assertIn("rgb(0, 0, 0)", timer_page)
        self.assertIn("rgb(65, 72, 75)", timer_page)
        self.assertIn('canvas.drawString("RESET"', timer_page)
        self.assertIn('canvas.drawString("SET"', timer_page)
        self.assertIn("localCountdownTouchTarget", self.source)
        self.assertIn("fillSmoothRoundRect(72, 58, 118, 58, 28", timer_page)
        self.assertIn("fillSmoothRoundRect(76, 340, 144, 76, 36", timer_page)
        self.assertIn('canvas.drawString("PHYSICAL PRESETS", 225, 132)', timer_page)
        self.assertIn("localCountdownCanReset(localCountdown.state)", timer_page)
        self.assertIn("LocalCountdownState::overtimePaused", timer_page)
        self.assertIn("canvas.textWidth(heroClock)", timer_page)
        self.assertIn("plusX - 11", timer_page)
        self.assertNotIn('"+%02llu:%02llu"', timer_page)
        self.assertNotIn("FreeSans", timer_page)
        self.assertIn("useEditorialBold18();", timer_page)
        self.assertIn("useEditorialMicro14();", timer_page)
        self.assertIn("useEditorialBold24();", timer_page)

    def test_countdown_timer_set_page_uses_a_touch_wheel_and_explicit_save(self):
        settings_page = self.source.split(
            "void drawLocalCountdownSettingsPage()", 1
        )[1].split("void renderCurrentPage", 1)[0]
        settings_touch = self.source.split(
            "void updateLocalCountdownSettingsTouch", 1
        )[1].split("void updateAppShellTouch", 1)[0]
        self.assertIn('canvas.drawString("SET TIMER"', settings_page)
        self.assertIn('selected == 0 ? "PRESET A" : "PRESET B"', settings_page)
        self.assertIn('canvas.drawString("MIN"', settings_page)
        self.assertIn('canvas.drawString("CANCEL"', settings_page)
        self.assertIn('canvas.drawString("SAVE"', settings_page)
        self.assertIn("localCountdownSettingsTouchTarget", settings_touch)
        self.assertIn("localCountdownWheelSteps(distance)", settings_touch)
        self.assertIn("localCountdownSetEditorMinutes", settings_touch)
        self.assertIn("localCountdownCommitEditing", settings_touch)
        self.assertIn("saveCountdownPreferences();", settings_touch)
        self.assertIn("kFinePixelsPerMinute = 32", self.logic)
        self.assertIn("kFastPixelsPerMinute = 12", self.logic)
        self.assertNotIn("FreeSans", settings_page)

    def test_power_short_sleeps_double_opens_launcher_and_usb_hold_is_reserved(self):
        normalized_logic = " ".join(self.interaction_logic.split())
        self.assertIn("DashboardPowerAction::toggleScreen", self.source)
        self.assertIn("DashboardPowerAction::openLauncher", self.source)
        self.assertIn("DashboardPowerAction::beginPowerOffHold", self.source)
        self.assertIn("DashboardPowerAction::cancelPowerOffHold", self.source)
        self.assertIn("setScreenLocked(!screenLocked);", self.source)
        self.assertIn("enterAppLauncher();", self.source)
        self.assertIn(
            "kPowerButtonDoubleClickMs, kPowerButtonHoldPreviewMs,",
            self.source,
        )
        self.assertIn("kPowerButtonPowerOffMs, deviceUsbConnected", self.source)
        self.assertIn('canvas.drawString("KEEP HOLDING", 225, 331)', self.source)
        self.assertIn('canvas.drawString("RELEASE TO CANCEL", 225, 353)', self.source)
        self.assertIn("M5.Power.getVBUSVoltage()", self.source)
        self.assertIn(
            "heldMs >= holdPreviewMs", normalized_logic
        )
        self.assertIn(
            "action = DashboardPowerAction::cancelPowerOffHold", normalized_logic
        )
        self.assertIn(
            "if (!usbConnected) action = DashboardPowerAction::powerOff",
            normalized_logic,
        )

    def test_standby_and_true_power_cycles_have_distinct_feedback(self):
        self.assertIn("void playBootTransition()", self.source)
        self.assertIn("void playPowerOffTransition()", self.source)
        self.assertIn('starting ? "M5 DASHBOARD" : "POWER OFF"', self.source)
        self.assertIn('starting ? "STARTING" : "SHUTTING DOWN"', self.source)
        self.assertIn("playBootTransition();", self.source)
        self.assertIn("playPowerOffTransition();", self.source)
        self.assertIn("pulseVibrationBlocking(38, 18);", self.source)
        self.assertIn("pulseVibrationBlocking(135, 75);", self.source)
        self.assertIn("pulseVibrationBlocking(190, 115);", self.source)
        self.assertIn("for (int frame = 1; frame <= 18; ++frame)", self.source)
        power_off = self.source.split(
            "action == DashboardPowerAction::powerOff", 1
        )[1].split("void updateDevicePower", 1)[0]
        self.assertLess(
            power_off.index("disableSpeakerOutput();"),
            power_off.index("playPowerOffTransition();"),
        )
        self.assertLess(
            power_off.index("playPowerOffTransition();"),
            power_off.index("M5.Power.powerOff();"),
        )

    def test_boot_reenables_the_stopwatch_battery_charger(self):
        setup = self.source.split("void setup()", 1)[1].split("void loop()", 1)[0]
        self.assertIn("M5.begin(config);", setup)
        self.assertIn("M5.Power.setBatteryCharge(true);", setup)
        self.assertLess(
            setup.index("M5.begin(config);"),
            setup.index("M5.Power.setBatteryCharge(true);"),
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

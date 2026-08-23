from pathlib import Path
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class TypelessPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (PROJECT / "firmware/M5Dashboard/M5Dashboard.ino").read_text(
            encoding="utf-8"
        )
        cls.interaction_source = (
            PROJECT / "firmware/M5Dashboard/interaction_logic.h"
        ).read_text(encoding="utf-8")

    def test_typeless_is_the_fifth_page(self):
        self.assertIn("constexpr int pageCount = 7;", self.source)
        self.assertIn('drawEditorialHeader("Typeless", modeLabel, ink);', self.source)
        self.assertIn(': macMode ? "MAC MIC"', self.source)
        self.assertIn('usbMode ? "USB MIC"', self.source)
        self.assertIn("currentPage == 4", self.source)
        self.assertIn("dashboardVoiceTouchTarget(designX, designY)", self.source)
        self.assertIn("toggleVoiceSession();", self.source)

    def test_typeless_status_uses_complete_native_antialiased_word_font(self):
        start = self.source.index("void drawVoiceOverlay()")
        end = self.source.index("\n}\n", start)
        overlay = self.source[start:end]
        self.assertIn("useEditorialHero80()", overlay)
        self.assertIn('canvas.drawString("BRIDGE", 18, 235);', overlay)
        self.assertNotIn("drawEditorialHero(", overlay)

    def test_typeless_uses_touch_instead_of_the_b_button(self):
        self.assertIn('"轻触使用手表麦克风"', self.source)
        self.assertIn('"轻触使用电脑麦克风"', self.source)
        self.assertIn('performTickTickAction("countdown-click")', self.source)
        self.assertNotIn("voiceButtonTracking", self.source)

    def test_typeless_touch_controls_both_usb_audio_and_the_mac_app(self):
        self.assertIn('performTypelessAction("start", mode)', self.source)
        self.assertIn('performTypelessAction("stop", endedMode)', self.source)
        self.assertIn('"typeless-start"', self.source)
        self.assertIn('"/api/typeless/start"', self.source)
        self.assertIn('"/api/typeless/start-mac"', self.source)

    def test_mac_mic_waits_for_the_bridge_readiness_window(self):
        self.assertIn("kTypelessHttpActionTimeoutMs = 8000", self.source)
        self.assertIn(
            'action == "start" ? "/api/typeless/start-mac" : "/api/typeless/stop",\n'
            "        kTypelessHttpActionTimeoutMs",
            self.source,
        )

    def test_mac_mic_has_distinct_success_failure_and_stop_haptics(self):
        self.assertIn("startVibration(55, 28);", self.source)
        self.assertIn("startVibration(120, 90);", self.source)
        self.assertIn("startVibration(185, 160);", self.source)
        self.assertIn("startVibration(105, 70);", self.source)

    def test_mac_mic_keeps_stop_control_when_acknowledgement_is_lost(self):
        self.assertIn("voiceSessionActive = true;", self.source)
        self.assertIn('bool acknowledged = performTypelessAction("start", mode);', self.source)
        self.assertNotIn(
            "voiceSessionMode = DashboardTypelessMode::unavailable;\n"
            "        voiceCaptureFailed = true;",
            self.source,
        )

    def test_stop_acknowledges_locally_before_remote_cleanup(self):
        state_clear = self.source.index("voiceSessionActive = false;", self.source.index("void endVoiceCapture()"))
        redraw = self.source.index("drawCurrentPage();", state_clear)
        remote_stop = self.source.index('performTypelessAction("stop", endedMode);', redraw)
        self.assertLess(state_clear, redraw)
        self.assertLess(redraw, remote_stop)

    def test_typeless_prefers_usb_mic_then_falls_back_to_mac_mic_over_wifi(self):
        self.assertIn("bool typelessUsbAvailable()", self.source)
        self.assertIn("usbAudioReady, deviceUsbConnected", self.source)
        self.assertIn("usbLinkUsable.load(std::memory_order_acquire), usbBridgeOnline", self.source)
        self.assertIn("DashboardTypelessMode availableTypelessMode()", self.source)
        self.assertIn("WiFi.status() == WL_CONNECTED", self.source)
        self.assertIn('usbMode ? "USB MIC"', self.source)
        self.assertIn(': macMode ? "MAC MIC"', self.source)
        self.assertIn('canvas.drawString("NO", 18, 170);', self.source)
        self.assertIn('canvas.drawString("BRIDGE", 18, 235);', self.source)
        self.assertIn('mode == DashboardTypelessMode::unavailable', self.source)
        self.assertIn('mode == DashboardTypelessMode::usbMic', self.source)
        self.assertIn('voiceSessionMode == DashboardTypelessMode::usbMic', self.source)

    def test_typeless_unavailable_copy_uses_native_unscaled_font(self):
        start = self.source.index("void drawVoiceOverlay()")
        end = self.source.index("\n}\n", start)
        overlay = self.source[start:end]
        self.assertIn("useEditorialHero80()", overlay)
        self.assertIn('canvas.drawString("NO", 18, 170);', overlay)
        self.assertIn('canvas.drawString("BRIDGE", 18, 235);', overlay)
        self.assertNotIn("setTextSize(0.", overlay)

    def test_usb_and_mac_mode_labels_share_one_native_typographic_grid(self):
        start = self.source.index("void drawVoiceOverlay()")
        end = self.source.index("\n}\n", start)
        overlay = self.source[start:end]
        self.assertIn('usbMode ? "USB MIC"', overlay)
        self.assertIn(': macMode ? "MAC MIC"', overlay)
        self.assertIn('drawEditorialHeader("Typeless", modeLabel, ink);', overlay)
        self.assertIn('voiceSessionActive ? "LIVE" : "READY"', overlay)
        self.assertIn('"BUILT-IN · WI-FI"', overlay)
        self.assertIn('usbMode ? "轻触使用手表麦克风"', overlay)
        self.assertIn(': "轻触使用电脑麦克风"', overlay)

    def test_typeless_footer_capsule_is_also_a_touch_target(self):
        self.assertIn("const bool inCentralTarget", self.interaction_source)
        self.assertIn("const bool inFooterTarget", self.interaction_source)
        self.assertIn("x >= kEditorialFooterX", self.interaction_source)
        self.assertIn("y >= kEditorialFooterY", self.interaction_source)
        self.assertIn("return inCentralTarget || inFooterTarget;", self.interaction_source)

    def test_typeless_live_frame_keeps_the_editorial_paper_margin(self):
        self.assertIn(
            "if (overlayMode == OverlayMode::voice) return editorialPaperColor();",
            self.source,
        )

    def test_typeless_microphone_matches_the_approved_svg_geometry(self):
        self.assertIn("drawMicrophoneIcon(325, 147, ink, coral);", self.source)
        self.assertIn("canvas.fillRoundRect(left + 8, top, 42, 67, 21, color);", self.source)
        self.assertIn(
            "drawQuadraticThickRoundedLine(left, top + 42,",
            self.source,
        )
        self.assertIn(
            "drawQuadraticThickRoundedLine(left + 29, top + 82,",
            self.source,
        )
        self.assertIn(
            "drawThickRoundedLine(left + 29, top + 82, left + 29, top + 103",
            self.source,
        )
        self.assertIn("drawThickRoundedLine(left + 14, top + 104", self.source)


if __name__ == "__main__":
    unittest.main()

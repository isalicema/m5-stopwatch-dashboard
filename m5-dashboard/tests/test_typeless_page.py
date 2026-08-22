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
        self.assertIn('drawEditorialHeader("Typeless", title, ink);', self.source)
        self.assertIn('!usbAvailable ? "NO USB"', self.source)
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
        self.assertIn('"轻触中央开启麦克风"', self.source)
        self.assertIn('performTickTickAction("countdown-click")', self.source)
        self.assertNotIn("voiceButtonTracking", self.source)

    def test_typeless_touch_controls_both_usb_audio_and_the_mac_app(self):
        self.assertIn('performTypelessAction("start")', self.source)
        self.assertIn('performTypelessAction("stop")', self.source)
        self.assertIn('"typeless-start"', self.source)
        self.assertIn('"/api/typeless/start"', self.source)

    def test_typeless_requires_physical_usb_and_a_live_usb_bridge(self):
        self.assertIn("bool typelessUsbAvailable()", self.source)
        self.assertIn("usbAudioReady, deviceUsbConnected", self.source)
        self.assertIn("usbLinkUsable.load(std::memory_order_acquire), usbBridgeOnline", self.source)
        self.assertIn('!deviceUsbConnected ? "NO USB"', self.source)
        self.assertIn('!usbAvailable     ? "NO BRIDGE"', self.source)
        self.assertIn('canvas.drawString("NO", 18, 170);', self.source)
        self.assertIn('canvas.drawString("BRIDGE", 18, 235);', self.source)
        self.assertIn('!usbAvailable ? "NO USB"', self.source)
        self.assertIn('if (!typelessUsbAvailable()) {', self.source)
        self.assertIn("if (voiceSessionActive && !usbAvailable)", self.source)

    def test_typeless_unavailable_copy_uses_native_unscaled_font(self):
        start = self.source.index("void drawVoiceOverlay()")
        end = self.source.index("\n}\n", start)
        overlay = self.source[start:end]
        self.assertIn("useEditorialHero80()", overlay)
        self.assertIn('!usbAvailable ? "NO USB"', overlay)
        self.assertIn('canvas.drawString("NO", 18, 170);', overlay)
        self.assertIn('canvas.drawString("BRIDGE", 18, 235);', overlay)
        self.assertNotIn("setTextSize(0.", overlay)

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

from pathlib import Path
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class FeaturePageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (PROJECT / "firmware/M5Dashboard/M5Dashboard.ino").read_text(
            encoding="utf-8"
        )
        cls.interaction = (
            PROJECT / "firmware/M5Dashboard/interaction_logic.h"
        ).read_text(encoding="utf-8")

    def test_ai_hotspot_is_sixth_page_with_alert_feedback(self):
        self.assertIn("currentPage == 5", self.source)
        self.assertIn("drawAIHotspotPage();", self.source)
        self.assertIn("kAiScreamTones", self.source)
        self.assertIn("startVibration(220, 650);", self.source)
        self.assertIn("performAIHotspotAction(const String &action)", self.source)
        self.assertIn('"/api/ai/ack"', self.source)

    def test_obsidian_dice_is_seventh_page_with_touch_and_shake(self):
        self.assertIn("drawObsidianDicePage();", self.source)
        self.assertIn("currentPage = 6;", self.source)
        self.assertIn("updateObsidianDiceShake();", self.source)
        self.assertIn('performObsidianAction("roll")', self.source)
        self.assertIn("dashboardFeatureTouchTarget", self.interaction)
        self.assertIn("dashboardShakeDetected", self.interaction)

    def test_feature_action_geometry_is_inside_round_safe_areas(self):
        self.assertIn("feature primary action must stay inside the visual safe circle", self.interaction)
        self.assertIn("feature secondary action must stay inside the visual safe circle", self.interaction)
        self.assertIn("feature hero touch target must stay inside the physical circle", self.interaction)

    def test_selected_raster_assets_are_used(self):
        self.assertIn("ai_hotspot_burst_png", self.source)
        self.assertIn("ai_hotspot_burst_source_png", self.source)
        self.assertIn("obsidian_dice_png", self.source)
        self.assertIn("constexpr int outputSize = 360;", self.source)
        self.assertIn("constexpr int outputX = 130;", self.source)
        self.assertIn("constexpr int outputY = -35;", self.source)
        self.assertIn("editorialFrameBurstActive = true;", self.source)
        self.assertIn("drawAIHotspotBurst(frameCanvas, offset);", self.source)
        self.assertIn("drawEditorialBackdrop(yellow);", self.source)

    def test_obsidian_dynamic_title_and_count_have_separate_safe_rows(self):
        start = self.source.index("void drawObsidianDicePage()")
        end = self.source.index("\n}\n", start)
        page = self.source[start:end]
        self.assertIn("useEditorialHero80();", page)
        self.assertNotIn("canvas.setTextSize(0.76f);", page)
        self.assertIn("pushRotateZoomWithAA", self.source)
        self.assertIn('canvas.drawString("篇可抽", 58, 250);', self.source)
        self.assertIn("useChinese24();", self.source)
        self.assertIn("canvas.drawString(lines[0], 58, 280);", self.source)

    def test_all_editorial_pages_share_the_hardware_calibrated_paper(self):
        self.assertIn("constexpr uint8_t kEditorialPaperR = 245;", self.source)
        self.assertIn("constexpr uint8_t kEditorialPaperG = 234;", self.source)
        self.assertIn("constexpr uint8_t kEditorialPaperB = 214;", self.source)
        self.assertIn("uint16_t editorialPaperColor()", self.source)
        self.assertNotIn("rgb(248, 245, 237)", self.source)
        self.assertGreaterEqual(self.source.count("editorialPaperColor()"), 13)

    def test_b_long_press_returns_home_without_replacing_countdown_clicks(self):
        self.assertIn("kBButtonLongPressMs = 800", self.source)
        self.assertIn("returnToClockPage();", self.source)
        self.assertIn('performTickTickAction("countdown-click")', self.source)
        self.assertIn('performTickTickAction("countdown-end")', self.source)
        self.assertIn("dashboardHomePageDelta", self.interaction)

    def test_clock_overview_uses_multi_ai_daily_total(self):
        self.assertIn("struct AIUsageData", self.source)
        self.assertIn('JsonObject u = doc["ai_usage"]', self.source)
        self.assertIn('" · AI" + usageText', self.source)
        self.assertIn("aiUsage.todayTotalTokens", self.source)

    def test_clock_shortcuts_do_not_overlap_the_information_pills(self):
        self.assertIn("constexpr int kClockActionTouchY = 340;", self.interaction)
        self.assertIn("constexpr int kClockActionTouchHeight = 60;", self.interaction)
        self.assertIn("ordinary taps on weather/AI usage", self.interaction)

    def test_clock_seconds_use_larger_integrated_geometry_and_refresh_only_the_patch(self):
        self.assertIn("constexpr int kClockSecondTextX = 342;", self.source)
        self.assertIn("constexpr int kClockSecondTextY = 225;", self.source)
        self.assertIn("constexpr int kClockSecondUnderlineX = 316;", self.source)
        self.assertIn("constexpr int kClockSecondUnderlineY = 253;", self.source)
        self.assertIn("constexpr int kClockSecondUnderlineWidth = 52;", self.source)
        self.assertIn("editorialBold32DigitsFont", self.source)
        self.assertIn("useClockSecondFont(target);", self.source)
        self.assertIn("drawClockSecondValue(canvas, 0, 0, local.tm_sec", self.source)
        self.assertIn("clockSecondCanvas.createSprite", self.source)
        self.assertIn("void drawClockSecondOnly(const struct tm &local)", self.source)
        self.assertIn("clockSecondCanvas.pushSprite", self.source)
        self.assertIn("DashboardClockRefresh::secondsOnly", self.source)
        self.assertIn("DashboardClockRefresh::fullPage", self.source)
        self.assertIn("appMode == DashboardAppMode::dashboard", self.source)
        self.assertIn("overlayMode == OverlayMode::none", self.source)
        self.assertIn("!completionAnimationActive(millis())", self.source)
        self.assertIn("bool deferClockStateRedraw", self.source)
        self.assertIn("if (!deferClockStateRedraw) drawCurrentPage();", self.source)
        self.assertIn("normal two-second state-sync redraw", self.source)


if __name__ == "__main__":
    unittest.main()

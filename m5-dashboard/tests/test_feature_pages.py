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

    def test_feature_footer_tolerates_fingertip_drift_without_stealing_swipes(self):
        self.assertIn("kFeatureActionTouchY = 330", self.interaction)
        self.assertIn("kFeatureActionTouchHeight = 78", self.interaction)
        self.assertIn("kFeatureActionLowerEdgeCompensation = 32", self.interaction)
        self.assertIn("kFeatureActionTapSlop = 32", self.interaction)
        self.assertIn("dashboardFeatureTapAccepted", self.interaction)
        self.assertIn("bool featureTap = (currentPage == 5 || currentPage == 6)", self.source)
        self.assertIn("gestureThreshold = kFeatureActionTapSlop + 1", self.source)
        self.assertIn("abs(touch.distanceX()) >= kSwipeThreshold", self.source)

    def test_page_swipes_prioritize_touch_over_background_refresh(self):
        self.assertIn("constexpr int kSwipeThreshold = 45;", self.source)
        self.assertIn("constexpr int kPageTransitionFrameCount = 8;", self.source)
        self.assertIn("constexpr int kPageTransitionFrameDelayMs = 2;", self.source)
        loop_start = self.source.index("void loop()")
        loop = self.source[loop_start:]
        self.assertLess(
            loop.index("updateTouchInteraction(touch);"),
            loop.index("if (!touchPending) updateUsbBridge();"),
        )
        self.assertIn("if (touchPending) return;", self.source)
        self.assertIn("if (!touchPending &&\n      millis() - lastFetchAt", loop)
        completion_touch = self.source[
            self.source.index("void updateTouchInteraction(") :
            self.source.index("if (overlayMode == OverlayMode::orbit", self.source.index("void updateTouchInteraction("))
        ]
        self.assertIn("activeGesture = DashboardGesture::none;", completion_touch)
        self.assertIn("touchPending = false;", completion_touch)

    def test_obsidian_open_has_clear_haptic_feedback(self):
        self.assertIn(
            'startVibration(action == "roll" ? 125 : 130, action == "roll" ? 90 : 90);',
            self.source,
        )

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
        self.assertIn('"m · AI " + usageText', self.source)
        self.assertIn("aiUsage.todayTotalTokens", self.source)
        self.assertIn("ticktick.todayFocusSeconds / 60", self.source)
        self.assertIn('String(focusMinutes) + "m · AI "', self.source)
        self.assertNotIn("int focusPercent = 0;", self.source)
        self.assertIn("String formatChineseCountNumber(int64_t value)", self.source)
        self.assertIn('snprintf(buffer, sizeof(buffer), "%.2f"', self.source)
        self.assertIn("countUsesChineseHundredMillions", self.source)
        self.assertIn("return value >= 100000000;", self.source)
        self.assertIn('focusText += "亿";', self.source)
        self.assertIn('canvas.drawString(focusText, 311, 303);', self.source)
        self.assertNotIn('canvas.drawString("亿", left + prefixWidth, 303);', self.source)

    def test_provider_usage_pills_share_the_chinese_hundred_million_formatter(self):
        self.assertIn(
            'drawEditorialMetricPill(52, "今日用量", provider.todayTokens,',
            self.source,
        )
        self.assertIn(
            'drawEditorialMetricPill(225, "累计", provider.lifetimeTokens,',
            self.source,
        )
        self.assertIn('value += "亿";', self.source)
        self.assertIn('canvas.drawString(value, x + 103, y + 34);', self.source)
        self.assertNotIn('canvas.drawString("亿", left + numberWidth, y + 34);', self.source)

    def test_clock_shortcuts_do_not_overlap_the_information_pills(self):
        self.assertIn("constexpr int kClockActionTouchY = 336;", self.interaction)
        self.assertIn("constexpr int kClockActionTouchHeight = 64;", self.interaction)
        self.assertIn(
            "constexpr int kClockActionLowerEdgeCompensation = 32;",
            self.interaction,
        )
        self.assertIn("constexpr int kClockActionTapSlop = 34;", self.interaction)
        self.assertIn("dashboardClockTapAccepted", self.interaction)
        self.assertIn("ordinary taps on weather/AI usage", self.interaction)
        self.assertIn("Physical samples from the C152 lower edge", self.interaction)

    def test_clock_shortcuts_win_over_small_global_gesture_drift(self):
        self.assertIn("bool clockShortcutTap =", self.source)
        self.assertLess(
            self.source.index("if (clockShortcutTap)"),
            self.source.index("abs(touch.distanceX()) >= kSwipeThreshold"),
        )
        self.assertIn("gestureThreshold = kClockActionTapSlop + 1;", self.source)
        self.assertIn(
            "clockTarget == DashboardClockTouchTarget::results ? 64 : 55",
            self.source,
        )

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
        self.assertIn("!completionAnimationRunning", self.source)
        self.assertIn("bool hadDataBeforeUsbUpdate = haveData;", self.source)
        self.assertIn("if (!hadDataBeforeUsbUpdate && haveData", self.source)
        self.assertIn("bool hadDataBeforeFetch = haveData;", self.source)
        self.assertIn("bool deferClockStateRedraw", self.source)
        self.assertIn("hadDataBeforeFetch && haveData", self.source)
        self.assertIn("if (!deferClockStateRedraw) drawCurrentPage();", self.source)
        self.assertIn("normal two-second state-sync redraw", self.source)


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import unittest


PROJECT = Path(__file__).resolve().parents[1]


def function_source(source: str, signature: str) -> str:
    start = source.index(signature)
    end = source.index("\n}\n", start) + 3
    return source[start:end]


class QuotaRingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (PROJECT / "firmware/M5Dashboard/M5Dashboard.ino").read_text(
            encoding="utf-8"
        )

    def test_clock_uses_multi_ai_daily_total_instead_of_provider_quota(self):
        clock = function_source(self.source, "void drawClockPage(")
        self.assertIn("aiUsage.connected && aiUsage.complete", clock)
        self.assertIn("formatChineseCountNumber(aiUsage.todayTotalTokens)", clock)
        self.assertIn('"m · AI " + usageText', clock)
        self.assertNotIn("clockUsagePercent", clock)

    def test_clock_uses_a_distinct_mint_identity_instead_of_ticktick_coral(self):
        clock = function_source(self.source, "void drawClockPage(")
        self.assertIn("const uint16_t mint = rgb(24, 229, 161);", clock)
        self.assertIn("drawEditorialBackdrop(mint);", clock)
        self.assertIn("drawBatteryStatusAt(mint, ink, 326, 76, false);", clock)
        self.assertIn("deviceCharging && useChargingAccent", self.source)
        self.assertIn("canvas.fillCircle(236, 303, 7, mint);", clock)
        self.assertNotIn("const uint16_t coral = rgb(255, 59, 48);", clock)

    def test_clock_uses_summary_aligned_lower_arcs_for_weekly_provider_usage(self):
        clock = function_source(self.source, "void drawClockPage(")
        segment = function_source(self.source, "void drawClockProgressSegment(")
        cap = function_source(self.source, "void drawClockProgressCap(")

        self.assertIn(
            "int codexWeekUsed = max(0, min(100, codex.weekUsedPercent));", clock
        )
        self.assertIn(
            "int claudeWeekUsed = max(0, min(100, claude.weekUsedPercent));", clock
        )
        self.assertNotIn("dashboardRemainingPercent", clock)
        self.assertIn("const uint16_t codexBlue = rgb(95, 103, 255);", clock)
        self.assertIn("const uint16_t claudeOrange = rgb(226, 122, 86);", clock)
        self.assertIn("const uint16_t codexTrack = rgb(200, 203, 255);", clock)
        self.assertIn("const uint16_t claudeTrack = rgb(243, 198, 181);", clock)
        self.assertNotIn("const uint16_t quotaTrack = rgb(94, 96, 91);", clock)
        self.assertIn(
            "drawClockProgressSegment(95.0f, 162.7f, codexWeekUsed, false",
            clock,
        )
        self.assertIn(
            "drawClockProgressSegment(17.3f, 85.0f, claudeWeekUsed, true",
            clock,
        )
        self.assertIn("codexTrack, codexBlue", clock)
        self.assertIn("claudeTrack, claudeOrange", clock)
        self.assertIn("kClockQuotaArcOuterRadius", segment)
        self.assertIn("kClockQuotaArcInnerRadius", segment)
        self.assertIn("constexpr int kClockQuotaArcOuterRadius = 222;", self.source)
        self.assertIn("constexpr int kClockQuotaArcInnerRadius = 208;", self.source)
        self.assertIn("constexpr int kClockQuotaArcCapRadius = 7;", self.source)
        self.assertIn("if (fillFromEnd)", segment)
        self.assertIn("activeStart = endAngle - activeSweep", segment)
        self.assertIn("activeEnd = startAngle + activeSweep", segment)
        self.assertIn(
            "canvas.fillSmoothCircle(x, y, kClockQuotaArcCapRadius, color)", cap
        )

    def test_ai_editorial_layout_is_retained_behind_the_regression_gate(self):
        provider = function_source(self.source, "void drawProviderEditorialPage(")
        self.assertIn("drawEditorialBackdrop(accent)", provider)
        self.assertIn("drawEditorialHeader", provider)
        self.assertIn("drawProviderQuotaHero(mainPercent, ink)", provider)
        self.assertIn("drawEditorialMetricPill", provider)
        self.assertIn("drawProviderEditorialFooter", provider)
        self.assertNotIn("drawRoundScreenBase", provider)
        self.assertIn(
            "drawProviderEditorialPage(codex, false)",
            function_source(self.source, "void drawCodexPage("),
        )
        self.assertIn(
            "drawProviderEditorialPage(claude, true)",
            function_source(self.source, "void drawClaudePage("),
        )

    def test_provider_percent_uses_the_large_stack_safe_rgba_glyph(self):
        hero = function_source(self.source, "void drawProviderQuotaHero(")
        self.assertIn("useEditorialHero104()", hero)
        self.assertIn("String digits(remainingPercent)", hero)
        self.assertIn("provider_percent_96_png_height", hero)
        self.assertIn("canvas.drawPng(provider_percent_96_png", hero)
        self.assertIn("provider_percent_96_png_width, provider_percent_96_png_height", hero)
        self.assertNotIn("useEditorialHero80()", hero)
        self.assertNotIn('canvas.drawString("%"', hero)
        self.assertNotIn('String(remainingPercent) + "%"', hero)
        self.assertNotIn("canvas.fillArc", hero)
        self.assertNotIn("drawThickRoundedLine", hero)

    def test_proven_provider_renderer_remains_as_a_disabled_fallback(self):
        self.assertIn("constexpr bool kProviderRegressionSafeRenderer = false", self.source)
        safe = function_source(self.source, "void drawRegressionSafeProviderPage(")
        self.assertIn("drawRoundScreenBase", safe)
        self.assertIn("drawFooterPill", safe)
        self.assertIn("formatDurationCN(mainReset)", safe)
        codex = function_source(self.source, "void drawCodexPage(")
        claude = function_source(self.source, "void drawClaudePage(")
        self.assertIn("drawRegressionSafeProviderPage(codex, false)", codex)
        self.assertIn("drawRegressionSafeProviderPage(claude, true)", claude)

    def test_editorial_accent_is_antialiased_and_full_screen_overlays_clear_frame_bleed(self):
        backdrop = function_source(
            self.source, "void drawEditorialBackdrop(uint16_t accent) {"
        )
        self.assertIn("canvas.fillSmoothCircle(364, 130, 164, accent)", backdrop)
        frame = function_source(self.source, "void composeRenderedFrame(")
        self.assertIn("frameCanvas.fillSmoothCircle", frame)
        overlay = function_source(self.source, "void drawOverlay(")
        self.assertIn("overlayMode == OverlayMode::orbit", overlay)
        self.assertIn("overlayMode == OverlayMode::results", overlay)
        self.assertIn("editorialFrameAccentActive = false", overlay)

    def test_all_editorial_pages_share_antialiased_capsules(self):
        self.assertIn(
            "canvas.fillSmoothRoundRect(x, y, width, height, height / 2, color)",
            self.source,
        )
        self.assertIn("void drawAntialiasedCapsule(", self.source)
        expected_calls = (
            "fillAntialiasedCapsule(58, 282, 143, 42, ink)",
            "drawAntialiasedCapsule(213, 282, 179, 42, background, yellow)",
            "fillAntialiasedCapsule(x, y, width, height, fill)",
            "fillAntialiasedCapsule(kEditorialFooterX, kEditorialFooterY",
            "fillAntialiasedCapsule(kFocusPrimaryActionX, kFocusActionY",
            "drawAntialiasedCapsule(kFocusEndActionX, kFocusActionY",
            "fillAntialiasedCapsule(kFeaturePrimaryActionX, kFeatureActionY",
            "drawAntialiasedCapsule(kFeatureSecondaryActionX, kFeatureActionY",
        )
        for call in expected_calls:
            self.assertIn(call, self.source)

    def test_editorial_provider_icons_use_the_prepared_official_app_assets(self):
        codex = function_source(self.source, "void drawCodexIcon(")
        claude = function_source(self.source, "void drawClaudeIcon(")
        brand = function_source(self.source, "void drawProviderBrandIcon(")
        self.assertIn("codex_brand_icon_rgb565", codex)
        self.assertIn("claude_brand_icon_rgb565", claude)
        self.assertIn("canvas.getSwapBytes()", brand)
        self.assertIn("canvas.setSwapBytes(true)", brand)
        self.assertIn("canvas.pushImage", brand)
        self.assertIn("canvas.setSwapBytes(previousSwap)", brand)
        self.assertNotIn("iconCanvas", codex)
        self.assertNotIn("iconCanvas", claude)
        self.assertNotIn("codex_icon_png", codex)
        self.assertNotIn("claude_icon_png", claude)

    def test_provider_icons_have_no_intermediate_sprite_or_post_render_refresh(self):
        self.assertNotIn("M5Canvas iconCanvas", self.source)
        self.assertNotIn("iconCanvas.createSprite", self.source)
        animation = function_source(self.source, "void updateCenterIconAnimation(")
        self.assertIn("Provider icons are intentionally static", animation)
        self.assertNotIn("drawCodexIcon", animation)
        self.assertNotIn("drawClaudeIcon", animation)

    def test_provider_reset_uses_vector_arrow_and_compact_shared_format(self):
        compact = function_source(self.source, "String formatDurationCompact(")
        self.assertIn('String(days) + "d" + String(hours) + "h"', compact)
        arrow = function_source(self.source, "void drawProviderResetArrow(")
        self.assertIn("canvas.fillArc", arrow)
        self.assertIn("canvas.fillTriangle", arrow)
        footer = function_source(self.source, "void drawProviderEditorialFooter(")
        self.assertIn("firstLine = formatDurationCompact(resetMinutes)", footer)
        self.assertIn("drawProviderResetArrow", footer)
        self.assertNotIn('String("↺")', footer)
        self.assertIn('"重置待同步"', footer)
        self.assertNotIn("周额", footer)
        self.assertNotIn("后重置", footer)

    def test_focus_page_uses_editorial_poster_layout_instead_of_dashboard_ring(self):
        focus = function_source(self.source, "void drawFocusPage(")
        self.assertNotIn("drawRoundScreenBase", focus)
        self.assertIn("drawEditorialBackdrop(coral)", focus)
        self.assertIn("drawFocusHeroTime(heroValue, ink)", focus)
        self.assertIn('drawFocusModeOption(52, 175, "A", "正计时"', focus)
        self.assertIn('drawFocusModeOption(225, 175, "B", "25分钟"', focus)
        self.assertIn("drawFocusActions", focus)

    def test_focus_touch_buttons_dispatch_the_current_timer_mode(self):
        touch = function_source(self.source, "void finishTouchGesture(")
        self.assertIn("dashboardFocusTouchTarget(designX, designY)", touch)
        self.assertIn('"stopwatch-click"', touch)
        self.assertIn('"countdown-click"', touch)
        self.assertIn('"stopwatch-end"', touch)
        self.assertIn('"countdown-end"', touch)
        self.assertIn("performTickTickAction(action)", touch)


if __name__ == "__main__":
    unittest.main()

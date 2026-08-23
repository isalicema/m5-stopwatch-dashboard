from pathlib import Path
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class CompletionFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (PROJECT / "firmware/M5Dashboard/M5Dashboard.ino").read_text(
            encoding="utf-8"
        )

    def test_ai_completion_animation_is_silent_and_has_no_haptic(self):
        start = self.source.index("void startCompletionAnimation(")
        end = self.source.index("\n}\n", start) + 3
        completion = self.source[start:end]

        self.assertIn("completionAnimationRunning = true", completion)
        self.assertNotIn("startVibration", completion)
        self.assertNotIn("startTonePattern", completion)
        self.assertNotIn("kCodexDoneTones", self.source)
        self.assertNotIn("completionSecondHaptic", self.source)

    def test_ai_completion_visual_has_no_text_or_trailing_highlight(self):
        start = self.source.index("void drawCompletionOverlay(")
        end = self.source.index("\n}\n", start) + 3
        overlay = self.source[start:end]

        self.assertIn("frame.ringDegrees", overlay)
        self.assertIn("frame.successRadius", overlay)
        self.assertIn("claudeProvider ? 217 : 95", overlay)
        self.assertIn("editorialFrameAccentActive = false", overlay)
        self.assertIn("editorialFrameBurstActive = false", overlay)
        self.assertIn(
            "drawCompletionProviderIcon(claudeProvider, frame.providerIconStep)",
            overlay,
        )
        self.assertIn("drawCompletionCheck(frame.successRadius, checkColor)", overlay)
        self.assertNotIn("drawString", overlay)
        self.assertNotIn("drawPng", overlay)
        self.assertNotIn("claude_mark_png", overlay)
        self.assertNotIn("codex_pet_done_frames", overlay)
        self.assertNotIn("completionIconCenterY", overlay)
        self.assertNotIn("showToast", overlay)
        self.assertNotIn("highlight", overlay)

    def test_provider_icon_exits_before_success_check_begins(self):
        contract = (
            PROJECT / "firmware/M5Dashboard/icon_animation.h"
        ).read_text(encoding="utf-8")
        self.assertIn("else if (elapsedMs < 850)", contract)
        self.assertIn("frame.providerIconStep = 4", contract)
        self.assertIn("if (elapsedMs >= 1000 && elapsedMs < 1140)", contract)
        self.assertNotIn("providerIconStep = 5", contract)

    def test_full_screen_check_has_a_visible_hold_before_fading(self):
        contract = (
            PROJECT / "firmware/M5Dashboard/icon_animation.h"
        ).read_text(encoding="utf-8")
        self.assertIn("kDashboardCompletionFullHoldUntilMs = 2200", contract)
        self.assertIn("kDashboardCompletionDurationMs = 2600", contract)
        self.assertIn(
            "elapsedMs >= kDashboardCompletionFullHoldUntilMs", contract
        )

    def test_ai_completion_physical_frame_never_falls_back_to_paper(self):
        start = self.source.index("uint16_t currentRenderedBackground(uint32_t now)")
        end = self.source.index("\n}\n", start) + 3
        background = self.source[start:end]

        self.assertIn("if (frame.visible)", background)
        self.assertIn(
            "if (frame.successRadius < kDashboardCompletionFullRadius)",
            background,
        )
        self.assertIn("return rgb(backgroundR, backgroundG, backgroundB);", background)

    def test_ai_completion_uses_one_clock_and_background_for_the_whole_frame(self):
        start = self.source.index("void drawCurrentPage() {")
        end = self.source.index("\n}\n", start) + 3
        draw = self.source[start:end]

        self.assertIn("uint32_t now = millis();", draw)
        self.assertIn("uint16_t background = currentRenderedBackground(now);", draw)
        self.assertIn("renderCurrentPage(now, background);", draw)
        self.assertIn("pushRenderedFrame(background);", draw)
        self.assertEqual(draw.count("uint32_t now = millis();"), 1)

    def test_clock_patch_waits_for_completion_state_machine_to_exit(self):
        self.assertIn("!completionAnimationRunning) {", self.source)
        self.assertIn(
            "overlayMode == OverlayMode::none && !completionAnimationRunning;",
            self.source,
        )
        self.assertNotIn("!completionAnimationActive(millis())", self.source)

    def test_non_completion_haptics_are_preserved(self):
        self.assertIn("startVibration(190, 300)", self.source)
        self.assertIn("startVibration(170, 220)", self.source)
        self.assertIn("startTonePattern(kFocusDoneTones", self.source)
        self.assertIn("updateControlHaptic(value)", self.source)

    def test_waiting_haptic_is_suppressed_when_a_task_just_completed(self):
        transition_start = self.source.index("void notifyTransitions(")
        transition_end = self.source.index("\n}\n", transition_start) + 3
        transition = self.source[transition_start:transition_end]

        self.assertIn("bool completionStarted", transition)
        self.assertIn("if (!completionStarted) startVibration(190, 300)", transition)
        self.assertIn("startTonePattern(kCodexWaitingTones", transition)
        self.assertIn("bool completionStarted = updateCompletionResults();", self.source)
        self.assertIn("notifyTransitions(oldTickTick, oldCodex, hadData, completionStarted);", self.source)


if __name__ == "__main__":
    unittest.main()

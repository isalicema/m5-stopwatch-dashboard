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
        self.assertNotIn("drawString", overlay)
        self.assertNotIn("showToast", overlay)
        self.assertNotIn("highlight", overlay)

    def test_non_completion_haptics_are_preserved(self):
        self.assertIn("startVibration(190, 300)", self.source)
        self.assertIn("startVibration(printer.state ==", self.source)
        self.assertIn("startTonePattern(kPrinterDoneTones", self.source)
        self.assertIn("startTonePattern(kPrinterErrorTones", self.source)
        self.assertIn("updateControlHaptic(value)", self.source)

    def test_waiting_haptic_is_suppressed_when_a_task_just_completed(self):
        transition_start = self.source.index("void notifyTransitions(")
        transition_end = self.source.index("\n}\n", transition_start) + 3
        transition = self.source[transition_start:transition_end]

        self.assertIn("bool completionStarted", transition)
        self.assertIn("if (!completionStarted) startVibration(190, 300)", transition)
        self.assertIn("startTonePattern(kCodexWaitingTones", transition)
        self.assertIn("bool completionStarted = updateCompletionResults();", self.source)
        self.assertIn("notifyTransitions(oldPrinter, oldCodex, hadData, completionStarted);", self.source)


if __name__ == "__main__":
    unittest.main()

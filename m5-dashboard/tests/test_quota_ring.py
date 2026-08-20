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

    def test_clock_ai_segments_use_remaining_quota(self):
        clock_percent = function_source(self.source, "int clockUsagePercent(")
        self.assertIn(
            "dashboardRemainingPercent(value)",
            clock_percent,
        )
        clock = function_source(self.source, "void drawClockPage(")
        self.assertIn("clockUsagePercent(claude)", clock)
        self.assertIn("clockUsagePercent(codex)", clock)

    def test_individual_ai_pages_keep_their_existing_ring_direction(self):
        self.assertIn(
            "drawRoundScreenBase(background, track, mainPercent, active)",
            function_source(self.source, "void drawCodexPage("),
        )
        self.assertIn(
            "drawRoundScreenBase(background, track, mainPercent, active)",
            function_source(self.source, "void drawClaudePage("),
        )

    def test_printer_progress_keeps_forward_direction(self):
        printer = function_source(self.source, "void drawPrinterPage(")
        self.assertIn(
            "drawRoundScreenBase(background, track, printer.progress, active)", printer
        )


if __name__ == "__main__":
    unittest.main()

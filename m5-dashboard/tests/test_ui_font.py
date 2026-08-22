from __future__ import annotations

import importlib.util
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


font_generator = load_module("generate_ui_font", PROJECT / "scripts/generate_ui_font.py")
flash_compiled = load_module("flash_compiled", PROJECT / "scripts/flash_compiled.py")


class UiFontTests(unittest.TestCase):
    def test_gb2312_set_has_full_coverage_and_ui_probes(self):
        characters = set(font_generator.gb2312_characters())
        self.assertGreaterEqual(len(characters), 7500)
        self.assertTrue(set("麦克风正在收音对话你任务关闭").issubset(characters))

    def test_committed_vlw_matches_verified_manifest(self):
        vlw = PROJECT / "firmware/M5Dashboard/ui_font_noto_sans_sc_16.vlw"
        manifest = json.loads(
            (PROJECT / "firmware/M5Dashboard/ui_font_noto_sans_sc_16.json").read_text(
                encoding="utf-8"
            )
        )
        data = vlw.read_bytes()
        self.assertTrue(manifest["identity_verified"])
        self.assertEqual(len(data), manifest["vlw_size"])
        self.assertEqual(hashlib.sha256(data).hexdigest(), manifest["vlw_sha256"])

    def test_committed_stopwatch_vlw_is_verified_antialiased_subset(self):
        vlw = PROJECT / "firmware/M5Dashboard/stopwatch_font_noto_sans_sc_56.vlw"
        manifest = json.loads(
            (
                PROJECT
                / "firmware/M5Dashboard/stopwatch_font_noto_sans_sc_56.json"
            ).read_text(encoding="utf-8")
        )
        data = vlw.read_bytes()
        self.assertTrue(manifest["identity_verified"])
        self.assertEqual(manifest["pixel_size"], 56)
        self.assertEqual(manifest["glyph_count"], 12)
        self.assertEqual(len(data), manifest["vlw_size"])
        self.assertEqual(hashlib.sha256(data).hexdigest(), manifest["vlw_sha256"])

    def test_editorial_fonts_use_verified_native_sizes(self):
        expected = {
            "editorial_font_medium_14": 14,
            "editorial_font_bold_18": 18,
            "editorial_font_bold_24": 24,
            "editorial_font_bold_32_digits": 32,
            "editorial_font_bold_80": 80,
            "editorial_font_bold_104": 104,
        }
        for name, pixel_size in expected.items():
            vlw = PROJECT / ("firmware/M5Dashboard/" + name + ".vlw")
            manifest = json.loads(
                (PROJECT / ("firmware/M5Dashboard/" + name + ".json")).read_text(
                    encoding="utf-8"
                )
            )
            data = vlw.read_bytes()
            self.assertTrue(manifest["identity_verified"])
            self.assertEqual(manifest["pixel_size"], pixel_size)
            self.assertEqual(len(data), manifest["vlw_size"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), manifest["vlw_sha256"])

    def test_32_px_clock_second_font_is_a_verified_digit_only_subset(self):
        manifest = json.loads(
            (
                PROJECT
                / "firmware/M5Dashboard/editorial_font_bold_32_digits.json"
            ).read_text(encoding="utf-8")
        )
        data = (
            PROJECT / "firmware/M5Dashboard/editorial_font_bold_32_digits.vlw"
        ).read_bytes()
        glyph_count = struct.unpack_from(">I", data, 0)[0]
        codepoints = {
            struct.unpack_from(">I", data, 24 + index * 28)[0]
            for index in range(glyph_count)
        }
        self.assertTrue(manifest["identity_verified"])
        self.assertEqual(manifest["pixel_size"], 32)
        self.assertEqual(codepoints, {ord(character) for character in "0123456789"})

    def test_104_px_hero_font_excludes_stack_overflowing_percent_glyph(self):
        data = (
            PROJECT / "firmware/M5Dashboard/editorial_font_bold_104.vlw"
        ).read_bytes()
        glyph_count = struct.unpack_from(">I", data, 0)[0]
        codepoints = {
            struct.unpack_from(">I", data, 24 + index * 28)[0]
            for index in range(glyph_count)
        }
        self.assertNotIn(ord("%"), codepoints)

    def test_80_px_word_and_number_font_contains_native_status_and_digits(self):
        data = (
            PROJECT / "firmware/M5Dashboard/editorial_font_bold_80.vlw"
        ).read_bytes()
        glyph_count = struct.unpack_from(">I", data, 0)[0]
        records = [
            struct.unpack_from(">7I", data, 24 + index * 28)
            for index in range(glyph_count)
        ]
        self.assertEqual(
            {record[0] for record in records},
            {ord(character) for character in " 0123456789ABDEGILNORSUVY"},
        )
        characters = {chr(record[0]) for record in records}
        self.assertTrue(set("NO USB").issubset(characters))
        self.assertTrue(set("NO BRIDGE").issubset(characters))
        self.assertLessEqual(max(record[1] * record[2] for record in records), 5082)

    def test_flash_guard_rejects_firmware_without_verified_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            firmware = Path(directory) / "firmware.bin"
            firmware.write_bytes(b"ordinary firmware")
            with self.assertRaisesRegex(SystemExit, "拒绝烧录"):
                flash_compiled.require_noto_ui_font(firmware)

    def test_flash_guard_accepts_verified_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            firmware = Path(directory) / "firmware.bin"
            firmware.write_bytes(b"prefix" + flash_compiled.REQUIRED_UI_FONT_MARKER + b"suffix")
            flash_compiled.require_noto_ui_font(firmware)

    def test_flash_targets_factory_ota_zero_partition(self):
        self.assertEqual(flash_compiled.APP_FLASH_OFFSET, 0x20000)
        self.assertEqual(flash_compiled.APP_PARTITION_SIZE, 0x4F0000)

    def test_firmware_reads_font_directly_from_flash(self):
        source = (PROJECT / "firmware/M5Dashboard/M5Dashboard.ino").read_text(
            encoding="utf-8"
        )
        self.assertIn("uiChineseFontData.set(kUiFontVlw, kUiFontVlwSize)", source)
        self.assertIn(
            "stopwatchDigitFontData.set(kStopwatchFontVlw, kStopwatchFontVlwSize)",
            source,
        )
        self.assertNotIn("lgfx_tinfl_decompress_mem_to_mem", source)

        embed_script = (PROJECT / "firmware/scripts/embed_ui_font.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("ui_font_noto_sans_sc_16.vlw", embed_script)
        self.assertIn("stopwatch_font_noto_sans_sc_56.vlw", embed_script)
        self.assertIn("editorial_font_bold_104.vlw", embed_script)
        self.assertIn("editorial_font_bold_80.vlw", embed_script)
        self.assertIn("hashlib.sha256(font_data).hexdigest()", embed_script)

    def test_native_rom_port_is_not_reset_again(self):
        port, before_mode = flash_compiled.bootloader_port("/dev/cu.usbmodem101")
        self.assertEqual(port, "/dev/cu.usbmodem101")
        self.assertEqual(before_mode, "no_reset")

    def test_flash_pauses_imac_peer_bridge(self):
        self.assertIn(
            "com.local.m5dashboard.peer", flash_compiled.DASHBOARD_SERVICE_LABELS
        )


if __name__ == "__main__":
    unittest.main()

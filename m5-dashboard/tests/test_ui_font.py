from __future__ import annotations

import importlib.util
import hashlib
import json
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

    def test_firmware_reads_font_directly_from_flash(self):
        source = (PROJECT / "firmware/M5Dashboard/M5Dashboard.ino").read_text(
            encoding="utf-8"
        )
        self.assertIn("uiChineseFontData.set(kUiFontVlw, kUiFontVlwSize)", source)
        self.assertNotIn("lgfx_tinfl_decompress_mem_to_mem", source)

        embed_script = (PROJECT / "firmware/scripts/embed_ui_font.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("ui_font_noto_sans_sc_16.vlw", embed_script)
        self.assertIn("hashlib.sha256(data).hexdigest()", embed_script)

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

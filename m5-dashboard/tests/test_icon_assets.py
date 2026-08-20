import re
import struct
import unittest
from pathlib import Path


ASSET_HEADER = (
    Path(__file__).resolve().parents[1]
    / "firmware"
    / "M5Dashboard"
    / "codex_pet_frames.h"
)


def embedded_pngs():
    source = ASSET_HEADER.read_text(encoding="utf-8")
    assets = {}
    for name, body in re.findall(
        r"static const uint8_t (\w+)\[\] PROGMEM = \{(.*?)\n\};",
        source,
        re.DOTALL,
    ):
        assets[name] = bytes(
            int(value, 16)
            for value in re.findall(r"0x([0-9a-fA-F]{2})", body)
        )
    return assets


def png_chunks(data):
    self_check = data[:8] == b"\x89PNG\r\n\x1a\n"
    if not self_check:
        raise ValueError("invalid PNG signature")
    offset = 8
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_data = data[offset + 8 : offset + 8 + length]
        yield chunk_type, chunk_data
        offset += 12 + length


class IconAssetTests(unittest.TestCase):
    def test_all_center_icons_keep_palette_transparency(self):
        assets = embedded_pngs()
        self.assertEqual(len(assets), 28)
        self.assertIn("claude_mark_png", assets)
        self.assertIn("codex_pet_idle_0_png", assets)

        for name, data in assets.items():
            chunks = dict(png_chunks(data))
            self.assertEqual(chunks[b"IHDR"][9], 3, name)
            self.assertIn(b"tRNS", chunks, name)
            self.assertIn(0, chunks[b"tRNS"], name)


if __name__ == "__main__":
    unittest.main()

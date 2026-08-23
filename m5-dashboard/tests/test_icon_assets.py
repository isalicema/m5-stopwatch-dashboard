import re
import struct
import unittest
from pathlib import Path

from PIL import Image


ASSET_HEADER = (
    Path(__file__).resolve().parents[1]
    / "firmware"
    / "M5Dashboard"
    / "codex_pet_frames.h"
)
BRAND_HEADER = ASSET_HEADER.with_name("provider_brand_icons.h")
FEATURE_HEADER = ASSET_HEADER.with_name("feature_assets.h")
FEATURE_ASSET_DIR = Path(__file__).resolve().parents[2] / "design" / "assets"


def embedded_pngs(path=ASSET_HEADER):
    source = path.read_text(encoding="utf-8")
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

    def test_provider_brand_icons_are_device_sized_rgb565_arrays(self):
        source = BRAND_HEADER.read_text(encoding="utf-8")
        assets = {
            name: re.findall(r"0x([0-9a-fA-F]{4})", body)
            for name, body in re.findall(
                r"static const uint16_t (\w+)\[\] PROGMEM = \{(.*?)\n\};",
                source,
                re.DOTALL,
            )
        }
        completion_sizes = (96, 80, 64, 48, 32)
        completion_names = {
            f"{provider}_completion_icon_{size}_rgb565"
            for provider in ("codex", "claude")
            for size in completion_sizes
        }
        self.assertEqual(
            set(assets),
            {"codex_brand_icon_rgb565", "claude_brand_icon_rgb565"}
            | completion_names,
        )
        self.assertEqual(len(assets["codex_brand_icon_rgb565"]), 96 * 96)
        self.assertEqual(len(assets["claude_brand_icon_rgb565"]), 96 * 96)
        for provider in ("codex", "claude"):
            for size in completion_sizes:
                self.assertEqual(
                    len(assets[f"{provider}_completion_icon_{size}_rgb565"]),
                    size * size,
                )
        self.assertIn("codex_brand_icon_rgb565_pixels = 9216", source)
        self.assertIn("claude_brand_icon_rgb565_pixels = 9216", source)

        expected_assets = (
            ("codex_brand_icon_rgb565", "codex-brand-icon-96.png", (95, 103, 255)),
            ("claude_brand_icon_rgb565", "claude-brand-icon-96.png", (226, 122, 86)),
        )
        for array_name, filename, background in expected_assets:
            with Image.open(FEATURE_ASSET_DIR / filename) as image:
                self.assertEqual(image.size, (96, 96), filename)
                self.assertEqual(image.mode, "P", filename)
                self.assertIn("transparency", image.info, filename)
                foreground = image.convert("RGBA")
            base = Image.new("RGBA", (96, 96), (*background, 255))
            flattened = Image.alpha_composite(base, foreground).convert("RGB")
            rgb_pixels = (
                flattened.get_flattened_data()
                if hasattr(flattened, "get_flattened_data")
                else flattened.getdata()
            )
            expected_pixels = [
                ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
                for red, green, blue in rgb_pixels
            ]
            actual_pixels = [int(value, 16) for value in assets[array_name]]
            self.assertEqual(actual_pixels, expected_pixels, filename)

        for provider, filename, background in (
            ("codex", "codex-brand-icon-96.png", (7, 8, 17)),
            ("claude", "claude-brand-icon-96.png", (15, 11, 9)),
        ):
            with Image.open(FEATURE_ASSET_DIR / filename) as image:
                foreground = image.convert("RGBA")
            for size in completion_sizes:
                resized = foreground.resize((size, size), Image.Resampling.LANCZOS)
                base = Image.new("RGBA", (size, size), (*background, 255))
                flattened = Image.alpha_composite(base, resized).convert("RGB")
                rgb_pixels = (
                    flattened.get_flattened_data()
                    if hasattr(flattened, "get_flattened_data")
                    else flattened.getdata()
                )
                expected_pixels = [
                    ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
                    for red, green, blue in rgb_pixels
                ]
                actual_pixels = [
                    int(value, 16)
                    for value in assets[f"{provider}_completion_icon_{size}_rgb565"]
                ]
                self.assertEqual(actual_pixels, expected_pixels, f"{provider}-{size}")

    def test_provider_percent_is_a_tight_antialiased_rgba_glyph(self):
        embedded = embedded_pngs(BRAND_HEADER)
        self.assertEqual(set(embedded), {"provider_percent_96_png"})
        path = FEATURE_ASSET_DIR / "provider-percent-96.png"
        self.assertEqual(embedded["provider_percent_96_png"], path.read_bytes())
        with Image.open(path) as image:
            self.assertEqual(image.size, (87, 73))
            self.assertEqual(image.mode, "RGBA")
            alpha = image.getchannel("A")
            alpha_values = (
                alpha.get_flattened_data()
                if hasattr(alpha, "get_flattened_data")
                else alpha.getdata()
            )
            self.assertEqual(alpha.getbbox(), (0, 0, 87, 73))
            self.assertIn(0, alpha_values)
            self.assertIn(255, alpha_values)
            self.assertTrue(any(0 < opacity < 255 for opacity in alpha_values))
        source = BRAND_HEADER.read_text(encoding="utf-8")
        self.assertIn("provider_percent_96_png_width = 87", source)
        self.assertIn("provider_percent_96_png_height = 73", source)

    def test_feature_assets_preserve_their_intended_background_mode(self):
        expected = {
            "ai_hotspot_burst_source_png": ("ai-hotspot-burst-220.png", (220, 220)),
            "ai_hotspot_burst_png": ("ai-hotspot-burst-360.png", (360, 360)),
            "obsidian_dice_png": ("obsidian-dice-150.png", (150, 150)),
        }
        embedded = embedded_pngs(FEATURE_HEADER)
        self.assertEqual(set(embedded), set(expected))

        for name, (filename, expected_size) in expected.items():
            path = FEATURE_ASSET_DIR / filename
            self.assertEqual(embedded[name], path.read_bytes(), name)
            with Image.open(path) as image:
                self.assertEqual(image.size, expected_size, name)
                self.assertEqual(image.mode, "P", name)
                self.assertEqual(image.info.get("transparency"), 0, name)
                rgba = image.convert("RGBA")
                if name == "ai_hotspot_burst_png":
                    # The burst is preblended against the exact page paper so
                    # its colour-ramp AA survives the device PNG decoder.
                    self.assertNotEqual(image.getpixel((0, 0)), 0, name)
                    self.assertEqual(rgba.getpixel((0, 0)), (245, 234, 214, 255), name)
                else:
                    self.assertEqual(image.getpixel((0, 0)), 0, name)
                    self.assertEqual(rgba.getpixel((0, 0))[3], 0, name)


if __name__ == "__main__":
    unittest.main()

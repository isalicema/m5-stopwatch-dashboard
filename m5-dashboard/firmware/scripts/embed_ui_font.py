"""Expand the committed VLW font binary into a generated C++ header."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


Import("env")

project_dir = Path(env.subst("$PROJECT_DIR"))
source_dir = project_dir / "M5Dashboard"
vlw_path = source_dir / "ui_font_noto_sans_sc_16.vlw"
manifest_path = source_dir / "ui_font_noto_sans_sc_16.json"
stopwatch_vlw_path = source_dir / "stopwatch_font_noto_sans_sc_56.vlw"
stopwatch_manifest_path = source_dir / "stopwatch_font_noto_sans_sc_56.json"
editorial_medium_14_vlw_path = source_dir / "editorial_font_medium_14.vlw"
editorial_medium_14_manifest_path = source_dir / "editorial_font_medium_14.json"
editorial_bold_18_vlw_path = source_dir / "editorial_font_bold_18.vlw"
editorial_bold_18_manifest_path = source_dir / "editorial_font_bold_18.json"
editorial_bold_24_vlw_path = source_dir / "editorial_font_bold_24.vlw"
editorial_bold_24_manifest_path = source_dir / "editorial_font_bold_24.json"
editorial_bold_32_digits_vlw_path = source_dir / "editorial_font_bold_32_digits.vlw"
editorial_bold_32_digits_manifest_path = source_dir / "editorial_font_bold_32_digits.json"
editorial_bold_80_vlw_path = source_dir / "editorial_font_bold_80.vlw"
editorial_bold_80_manifest_path = source_dir / "editorial_font_bold_80.json"
editorial_bold_104_vlw_path = source_dir / "editorial_font_bold_104.vlw"
editorial_bold_104_manifest_path = source_dir / "editorial_font_bold_104.json"
header_path = source_dir / "ui_font_noto_sans_sc_16.h"

if not all(
    path.is_file()
    for path in (
        vlw_path,
        manifest_path,
        stopwatch_vlw_path,
        stopwatch_manifest_path,
        editorial_medium_14_vlw_path,
        editorial_medium_14_manifest_path,
        editorial_bold_18_vlw_path,
        editorial_bold_18_manifest_path,
        editorial_bold_24_vlw_path,
        editorial_bold_24_manifest_path,
        editorial_bold_32_digits_vlw_path,
        editorial_bold_32_digits_manifest_path,
        editorial_bold_80_vlw_path,
        editorial_bold_80_manifest_path,
        editorial_bold_104_vlw_path,
        editorial_bold_104_manifest_path,
    )
):
    raise RuntimeError("Missing committed Noto UI/Stopwatch font VLW or manifest")


def read_verified_font(vlw: Path, manifest_file: Path, label: str):
    font_manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    font_data = vlw.read_bytes()
    font_sha = hashlib.sha256(font_data).hexdigest()
    if not font_manifest.get("identity_verified"):
        raise RuntimeError(f"Refusing to embed an unverified {label} font")
    if (
        font_sha != font_manifest.get("vlw_sha256")
        or len(font_data) != font_manifest.get("vlw_size")
    ):
        raise RuntimeError(f"Committed Noto {label} font does not match its manifest")
    return font_manifest, font_data, font_sha


manifest, data, actual_sha = read_verified_font(vlw_path, manifest_path, "UI")
stopwatch_manifest, stopwatch_data, stopwatch_sha = read_verified_font(
    stopwatch_vlw_path, stopwatch_manifest_path, "Stopwatch"
)
editorial_medium_14_manifest, editorial_medium_14_data, editorial_medium_14_sha = read_verified_font(
    editorial_medium_14_vlw_path, editorial_medium_14_manifest_path, "Editorial Medium 14"
)
editorial_bold_18_manifest, editorial_bold_18_data, editorial_bold_18_sha = read_verified_font(
    editorial_bold_18_vlw_path, editorial_bold_18_manifest_path, "Editorial Bold 18"
)
editorial_bold_24_manifest, editorial_bold_24_data, editorial_bold_24_sha = read_verified_font(
    editorial_bold_24_vlw_path, editorial_bold_24_manifest_path, "Editorial Bold 24"
)
editorial_bold_32_digits_manifest, editorial_bold_32_digits_data, editorial_bold_32_digits_sha = read_verified_font(
    editorial_bold_32_digits_vlw_path,
    editorial_bold_32_digits_manifest_path,
    "Editorial Bold 32 Digits",
)
editorial_bold_80_manifest, editorial_bold_80_data, editorial_bold_80_sha = read_verified_font(
    editorial_bold_80_vlw_path, editorial_bold_80_manifest_path, "Editorial Bold 80"
)
editorial_bold_104_manifest, editorial_bold_104_data, editorial_bold_104_sha = read_verified_font(
    editorial_bold_104_vlw_path, editorial_bold_104_manifest_path, "Editorial Bold 104"
)

marker = str(manifest["font_marker"])
stopwatch_marker = str(stopwatch_manifest["font_marker"])
signature = f'kUiFontVlwSha256[] = "{actual_sha}"'
stopwatch_signature = f'kStopwatchFontVlwSha256[] = "{stopwatch_sha}"'
editorial_signatures = [
    f'kEditorialMedium14VlwSha256[] = "{editorial_medium_14_sha}"',
    f'kEditorialBold18VlwSha256[] = "{editorial_bold_18_sha}"',
    f'kEditorialBold24VlwSha256[] = "{editorial_bold_24_sha}"',
    f'kEditorialBold32DigitsVlwSha256[] = "{editorial_bold_32_digits_sha}"',
    f'kEditorialBold80VlwSha256[] = "{editorial_bold_80_sha}"',
    f'kEditorialBold104VlwSha256[] = "{editorial_bold_104_sha}"',
]
header_current = False
if header_path.is_file() and header_path.stat().st_mtime >= max(
    vlw_path.stat().st_mtime,
    manifest_path.stat().st_mtime,
    stopwatch_vlw_path.stat().st_mtime,
    stopwatch_manifest_path.stat().st_mtime,
    editorial_medium_14_vlw_path.stat().st_mtime,
    editorial_medium_14_manifest_path.stat().st_mtime,
    editorial_bold_18_vlw_path.stat().st_mtime,
    editorial_bold_18_manifest_path.stat().st_mtime,
    editorial_bold_24_vlw_path.stat().st_mtime,
    editorial_bold_24_manifest_path.stat().st_mtime,
    editorial_bold_32_digits_vlw_path.stat().st_mtime,
    editorial_bold_32_digits_manifest_path.stat().st_mtime,
    editorial_bold_80_vlw_path.stat().st_mtime,
    editorial_bold_80_manifest_path.stat().st_mtime,
    editorial_bold_104_vlw_path.stat().st_mtime,
    editorial_bold_104_manifest_path.stat().st_mtime,
):
    prefix = header_path.read_text(encoding="utf-8", errors="ignore")[:8192]
    if (
        marker in prefix
        and signature in prefix
        and stopwatch_marker in prefix
        and stopwatch_signature in prefix
        and all(signature in prefix for signature in editorial_signatures)
    ):
        print(f"Verified generated Noto UI font header: {header_path}")
        header_current = True


def format_cpp_bytes(payload: bytes) -> str:
    rows = []
    for offset in range(0, len(payload), 16):
        row = payload[offset : offset + 16]
        rows.append("  " + ", ".join(f"0x{value:02x}" for value in row) + ",")
    return "\n".join(rows)


if not header_current:
    content = f"""#pragma once

#include <Arduino.h>

// Generated from the committed Noto Sans CJK SC VLW binary before build.
// Noto CJK is distributed under the SIL Open Font License 1.1:
// https://github.com/notofonts/noto-cjk/blob/main/Sans/LICENSE
#define M5DASH_HAS_NOTO_UI_FONT 1
inline constexpr char kUiFontIdentity[] PROGMEM __attribute__((used)) = "{marker}";
inline constexpr char kUiFontSourceSha256[] = "{manifest['source_sha256']}";
inline constexpr char kUiFontVlwSha256[] = "{actual_sha}";
inline constexpr size_t kUiFontGlyphCount = {manifest['glyph_count']};
inline constexpr size_t kUiFontVlwSize = {len(data)};
inline constexpr char kStopwatchFontIdentity[] PROGMEM __attribute__((used)) = "{stopwatch_marker}";
inline constexpr char kStopwatchFontSourceSha256[] = "{stopwatch_manifest['source_sha256']}";
inline constexpr char kStopwatchFontVlwSha256[] = "{stopwatch_sha}";
inline constexpr size_t kStopwatchFontGlyphCount = {stopwatch_manifest['glyph_count']};
inline constexpr size_t kStopwatchFontVlwSize = {len(stopwatch_data)};
inline constexpr char kEditorialMedium14VlwSha256[] = "{editorial_medium_14_sha}";
inline constexpr size_t kEditorialMedium14GlyphCount = {editorial_medium_14_manifest['glyph_count']};
inline constexpr size_t kEditorialMedium14VlwSize = {len(editorial_medium_14_data)};
inline constexpr char kEditorialBold18VlwSha256[] = "{editorial_bold_18_sha}";
inline constexpr size_t kEditorialBold18GlyphCount = {editorial_bold_18_manifest['glyph_count']};
inline constexpr size_t kEditorialBold18VlwSize = {len(editorial_bold_18_data)};
inline constexpr char kEditorialBold24VlwSha256[] = "{editorial_bold_24_sha}";
inline constexpr size_t kEditorialBold24GlyphCount = {editorial_bold_24_manifest['glyph_count']};
inline constexpr size_t kEditorialBold24VlwSize = {len(editorial_bold_24_data)};
inline constexpr char kEditorialBold32DigitsVlwSha256[] = "{editorial_bold_32_digits_sha}";
inline constexpr size_t kEditorialBold32DigitsGlyphCount = {editorial_bold_32_digits_manifest['glyph_count']};
inline constexpr size_t kEditorialBold32DigitsVlwSize = {len(editorial_bold_32_digits_data)};
inline constexpr char kEditorialBold80VlwSha256[] = "{editorial_bold_80_sha}";
inline constexpr size_t kEditorialBold80GlyphCount = {editorial_bold_80_manifest['glyph_count']};
inline constexpr size_t kEditorialBold80VlwSize = {len(editorial_bold_80_data)};
inline constexpr char kEditorialBold104VlwSha256[] = "{editorial_bold_104_sha}";
inline constexpr size_t kEditorialBold104GlyphCount = {editorial_bold_104_manifest['glyph_count']};
inline constexpr size_t kEditorialBold104VlwSize = {len(editorial_bold_104_data)};
inline constexpr uint8_t kUiFontVlw[] PROGMEM = {{
{format_cpp_bytes(data)}
}};
inline constexpr uint8_t kStopwatchFontVlw[] PROGMEM = {{
{format_cpp_bytes(stopwatch_data)}
}};
inline constexpr uint8_t kEditorialMedium14Vlw[] PROGMEM = {{
{format_cpp_bytes(editorial_medium_14_data)}
}};
inline constexpr uint8_t kEditorialBold18Vlw[] PROGMEM = {{
{format_cpp_bytes(editorial_bold_18_data)}
}};
inline constexpr uint8_t kEditorialBold24Vlw[] PROGMEM = {{
{format_cpp_bytes(editorial_bold_24_data)}
}};
inline constexpr uint8_t kEditorialBold32DigitsVlw[] PROGMEM = {{
{format_cpp_bytes(editorial_bold_32_digits_data)}
}};
inline constexpr uint8_t kEditorialBold80Vlw[] PROGMEM = {{
{format_cpp_bytes(editorial_bold_80_data)}
}};
inline constexpr uint8_t kEditorialBold104Vlw[] PROGMEM = {{
{format_cpp_bytes(editorial_bold_104_data)}
}};
"""
    header_path.write_text(content, encoding="utf-8")
    print(f"Generated Noto UI font header: {header_path}")

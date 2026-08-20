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
header_path = source_dir / "ui_font_noto_sans_sc_16.h"

if not vlw_path.is_file() or not manifest_path.is_file():
    raise RuntimeError("Missing committed Noto UI font VLW or manifest")

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
data = vlw_path.read_bytes()
actual_sha = hashlib.sha256(data).hexdigest()
if not manifest.get("identity_verified"):
    raise RuntimeError("Refusing to embed an unverified UI font")
if actual_sha != manifest.get("vlw_sha256") or len(data) != manifest.get("vlw_size"):
    raise RuntimeError("Committed Noto UI font does not match its manifest")

marker = str(manifest["font_marker"])
signature = f'kUiFontVlwSha256[] = "{actual_sha}"'
header_current = False
if header_path.is_file() and header_path.stat().st_mtime >= max(
    vlw_path.stat().st_mtime, manifest_path.stat().st_mtime
):
    prefix = header_path.read_text(encoding="utf-8", errors="ignore")[:2048]
    if marker in prefix and signature in prefix:
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
inline constexpr uint8_t kUiFontVlw[] PROGMEM = {{
{format_cpp_bytes(data)}
}};
"""
    header_path.write_text(content, encoding="utf-8")
    print(f"Generated Noto UI font header: {header_path}")

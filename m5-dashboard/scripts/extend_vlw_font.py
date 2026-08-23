#!/usr/bin/env python3
"""Add glyphs to an existing M5GFX VLW subset without redrawing old glyphs."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from PIL import ImageFont

from generate_ui_font import render_glyph


def read_entries(data: bytes) -> tuple[list[int], dict[int, tuple[tuple[int, ...], bytes]]]:
    header = list(struct.unpack_from(">6I", data, 0))
    count = header[0]
    records = [
        struct.unpack_from(">7I", data, 24 + index * 28)
        for index in range(count)
    ]
    bitmap_offset = 24 + count * 28
    entries: dict[int, tuple[tuple[int, ...], bytes]] = {}
    for record in records:
        bitmap_size = record[1] * record[2]
        bitmap = data[bitmap_offset : bitmap_offset + bitmap_size]
        if len(bitmap) != bitmap_size:
            raise SystemExit("VLW bitmap data is truncated")
        entries[record[0]] = (record, bitmap)
        bitmap_offset += bitmap_size
    if bitmap_offset != len(data):
        raise SystemExit("VLW contains trailing data")
    return header, entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("vlw", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("font", type=Path)
    parser.add_argument("characters")
    args = parser.parse_args()

    data = args.vlw.read_bytes()
    header, entries = read_entries(data)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    pixel_size = int(manifest["pixel_size"])
    font = ImageFont.truetype(str(args.font), size=pixel_size)
    family, style = font.getname()
    if not family.startswith("Noto Sans") or style not in {"Medium", "Bold"}:
        raise SystemExit(f"supplement font identity mismatch: {family} {style}")

    added: list[str] = []
    for character in sorted(set(args.characters), key=ord):
        if ord(character) in entries:
            continue
        bitmap, metrics = render_glyph(font, character)
        entries[ord(character)] = (metrics, bitmap)
        added.append(character)

    ordered = [entries[codepoint] for codepoint in sorted(entries)]
    header[0] = len(ordered)
    output = (
        struct.pack(">6I", *header)
        + b"".join(struct.pack(">7I", *record) for record, _ in ordered)
        + b"".join(bitmap for _, bitmap in ordered)
    )
    args.vlw.write_bytes(output)

    font_sha = hashlib.sha256(args.font.read_bytes()).hexdigest()
    supplemental = manifest.setdefault("supplemental_glyphs", {})
    for character in added:
        supplemental[character] = {
            "source_file": args.font.name,
            "source_sha256": font_sha,
            "font_name": f"{family} {style}",
            "pixel_size": pixel_size,
        }
    manifest["glyph_count"] = len(ordered)
    manifest["first_codepoint"] = min(entries)
    manifest["last_codepoint"] = max(entries)
    manifest["vlw_size"] = len(output)
    manifest["vlw_sha256"] = hashlib.sha256(output).hexdigest()
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("added=" + "".join(added))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

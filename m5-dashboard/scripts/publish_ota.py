#!/usr/bin/env python3
"""Atomically publish one M5 Dashboard application image to the local Bridge."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path


FACTORY_OTA_PARTITION_SIZE = 0x4F0000
ESP_IMAGE_MAGIC = 0xE9


def firmware_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_firmware(path: Path) -> int:
    if not path.is_file():
        raise ValueError("firmware file does not exist: %s" % path)
    size = path.stat().st_size
    if size <= 0 or size > FACTORY_OTA_PARTITION_SIZE:
        raise ValueError(
            "firmware does not fit the factory OTA partition (%d > %d bytes)"
            % (size, FACTORY_OTA_PARTITION_SIZE)
        )
    with path.open("rb") as handle:
        if handle.read(1) != bytes([ESP_IMAGE_MAGIC]):
            raise ValueError("firmware is not an ESP application image")
    return size


def _atomic_json(path: Path, value: dict) -> None:
    handle, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as target:
            json.dump(value, target, ensure_ascii=False, indent=2)
            target.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def publish(firmware: Path, directory: Path) -> dict:
    firmware = firmware.expanduser().resolve()
    directory = directory.expanduser().resolve()
    size = validate_firmware(firmware)
    sha256 = firmware_sha256(firmware)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / ("firmware-" + sha256 + ".bin")
    destination_valid = (
        destination.is_file()
        and destination.stat().st_size == size
        and firmware_sha256(destination) == sha256
    )
    if not destination_valid:
        handle, temporary = tempfile.mkstemp(prefix="firmware.", dir=str(directory))
        os.close(handle)
        try:
            shutil.copyfile(firmware, temporary)
            if firmware_sha256(Path(temporary)) != sha256:
                raise ValueError("copied firmware failed SHA-256 verification")
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    manifest = {
        "schema": 1,
        "release_id": sha256,
        "size": size,
        "sha256": sha256,
        "filename": destination.name,
    }
    _atomic_json(directory / "current.json", manifest)
    return manifest


def main() -> None:
    project = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Publish an M5 Dashboard HTTP OTA candidate")
    parser.add_argument(
        "--firmware",
        type=Path,
        default=project / "firmware/.pio/build/m5stack-stopwatch-uac/firmware.bin",
    )
    parser.add_argument(
        "--directory",
        type=Path,
        default=Path.home() / "Library/Application Support/M5Dashboard/ota",
    )
    args = parser.parse_args()
    manifest = publish(args.firmware, args.directory)
    print(
        "OTA candidate published: %s bytes sha256=%s"
        % (manifest["size"], manifest["sha256"])
    )


if __name__ == "__main__":
    main()

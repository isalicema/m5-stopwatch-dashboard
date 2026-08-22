#!/usr/bin/env python3
"""Read the StopWatch partition table and latest ESP32 core dump.

This helper is deliberately read-only: it uses the firmware's 1200-bps ROM
handoff, reads flash, and then watchdog-resets back into the installed app.  It
never erases or writes flash.
"""

from __future__ import annotations

import argparse
import struct
import subprocess
from pathlib import Path

from flash_compiled import (
    bootloader_port,
    esptool_command,
    pause_dashboard_services,
    resume_dashboard_services,
    serial_ports,
)


PARTITION_TABLE_OFFSET = 0x8000
PARTITION_TABLE_SIZE = 0x1000
PARTITION_MAGIC = 0x50AA
DATA_TYPE = 0x01
COREDUMP_SUBTYPE = 0x03


def parse_partitions(raw: bytes) -> list[tuple[int, int, int, int, str]]:
    entries: list[tuple[int, int, int, int, str]] = []
    entry_size = 32
    for index in range(0, len(raw) - entry_size + 1, entry_size):
        magic, part_type, subtype, offset, size, label, _flags = struct.unpack_from(
            "<HBBII16sI", raw, index
        )
        if magic == 0xFFFF:
            break
        if magic != PARTITION_MAGIC:
            continue
        entries.append(
            (
                part_type,
                subtype,
                offset,
                size,
                label.split(b"\0", 1)[0].decode("ascii", errors="replace"),
            )
        )
    return entries


def main() -> None:
    project = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="只读提取 M5 StopWatch 的 ESP32 coredump"
    )
    parser.add_argument("--port", help="应用或 ROM 串口；留空时自动识别")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/private/tmp/m5-stopwatch-coredump.bin"),
    )
    args = parser.parse_args()

    ports = serial_ports()
    port = args.port
    if not port:
        if len(ports) != 1:
            shown = "、".join(ports) if ports else "无"
            raise SystemExit(f"无法唯一识别 M5 串口（当前：{shown}）")
        port = ports[0]

    output = args.output.expanduser().resolve()
    table_output = output.with_name(output.stem + "-partitions.bin")
    paused_services = pause_dashboard_services()
    rom_port: str | None = None
    returned_to_app = False
    try:
        rom_port, before_mode = bootloader_port(port)
        base = esptool_command(project) + [
            "--chip",
            "esp32s3",
            "--port",
            rom_port,
            "--baud",
            "115200",
            "--before",
            before_mode,
        ]
        subprocess.run(
            base
            + [
                "--after",
                "no_reset",
                "read_flash",
                hex(PARTITION_TABLE_OFFSET),
                hex(PARTITION_TABLE_SIZE),
                str(table_output),
            ],
            check=True,
        )
        partitions = parse_partitions(table_output.read_bytes())
        if not partitions:
            raise SystemExit("没有从设备读到有效分区表")
        for part_type, subtype, offset, size, label in partitions:
            print(
                f"{label or '(unnamed)'}: type=0x{part_type:02x} "
                f"subtype=0x{subtype:02x} offset=0x{offset:x} size=0x{size:x}"
            )
        coredump = next(
            (
                (offset, size)
                for part_type, subtype, offset, size, _label in partitions
                if part_type == DATA_TYPE and subtype == COREDUMP_SUBTYPE
            ),
            None,
        )
        if coredump is None:
            raise SystemExit("设备原厂分区表没有 coredump 分区")
        offset, size = coredump
        subprocess.run(
            base
            + [
                "--after",
                "watchdog_reset",
                "read_flash",
                hex(offset),
                hex(size),
                str(output),
            ],
            check=True,
        )
        returned_to_app = True
    finally:
        # The first read intentionally leaves the chip in ROM mode.  Even if
        # partition parsing or coredump discovery fails, issue a harmless
        # one-byte read with watchdog_reset so the installed app comes back.
        if rom_port is not None and not returned_to_app:
            subprocess.run(
                esptool_command(project)
                + [
                    "--chip",
                    "esp32s3",
                    "--port",
                    rom_port,
                    "--baud",
                    "115200",
                    "--before",
                    "no_reset",
                    "--after",
                    "watchdog_reset",
                    "read_flash",
                    hex(PARTITION_TABLE_OFFSET),
                    "0x1",
                    "/private/tmp/m5-stopwatch-reset-probe.bin",
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        resume_dashboard_services(paused_services)
    print(f"coredump 已只读保存：{output}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Flash the prebuilt M5 Dashboard app image without erasing saved NVS settings."""

from __future__ import annotations

import argparse
import glob
import importlib.util
import os
import shutil
import subprocess
import sys
import termios
import time
from pathlib import Path
from typing import List, Tuple


REQUIRED_UI_FONT_MARKER = b"M5DASH_FONT_NOTO_SANS_CJK_SC_16_V1"
DASHBOARD_SERVICE_LABELS = (
    "com.local.m5dashboard.bridge",
    "com.local.m5dashboard.home.bridge",
    "com.local.m5dashboard.peer",
)


def require_noto_ui_font(firmware: Path) -> None:
    if REQUIRED_UI_FONT_MARKER not in firmware.read_bytes():
        raise SystemExit(
            "拒绝烧录：这个应用固件没有嵌入 Noto Sans CJK SC 字体标记，"
            "继续烧录会出现界面改了但字体没变的问题"
        )


def serial_ports() -> List[str]:
    patterns = ("/dev/cu.usbmodem*", "/dev/cu.usbserial*", "/dev/cu.SLAB_USBtoUART*")
    return sorted({item for pattern in patterns for item in glob.glob(pattern)})


def esptool_command(project: Path) -> List[str]:
    executable = shutil.which("esptool.py") or shutil.which("esptool")
    if executable:
        return [executable]

    if importlib.util.find_spec("esptool") is not None:
        return [sys.executable, "-m", "esptool"]

    platformio_tool = Path.home() / ".platformio/packages/tool-esptoolpy/esptool.py"
    platformio_python = Path.home() / ".platformio/penv/bin/python"
    if platformio_tool.exists() and platformio_python.exists():
        return [str(platformio_python), str(platformio_tool)]

    environment = project / ".flash-env"
    python = environment / "bin/python"
    if not python.exists():
        print("未找到 esptool，正在创建一次性烧录环境……")
        subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
        subprocess.run(
            [str(python), "-m", "pip", "install", "--disable-pip-version-check", "esptool==4.9.0"],
            check=True,
        )
    return [str(python), "-m", "esptool"]


def pause_dashboard_services() -> List[Path]:
    """Release the CDC port so the 1200-bps bootloader handoff cannot be stolen."""
    domain = "gui/%d" % os.getuid()
    agents = Path.home() / "Library/LaunchAgents"
    paused: List[Path] = []
    for label in DASHBOARD_SERVICE_LABELS:
        plist = agents / (label + ".plist")
        loaded = subprocess.run(
            ["launchctl", "print", "%s/%s" % (domain, label)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
        if loaded and plist.is_file():
            result = subprocess.run(
                ["launchctl", "bootout", domain, str(plist)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if result.returncode == 0:
                paused.append(plist)
    if paused:
        time.sleep(0.5)
    return paused


def resume_dashboard_services(plists: List[Path]) -> None:
    domain = "gui/%d" % os.getuid()
    for plist in plists:
        subprocess.run(
            ["launchctl", "bootstrap", domain, str(plist)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def bootloader_port(port: str, timeout_seconds: float = 10.0) -> Tuple[str, str]:
    """Use the firmware's 1200-bps touch and return the newly enumerated ROM port."""
    if "M5DASH" not in Path(port).name.upper():
        # The ESP32-S3 native USB ROM port has no external DTR/RTS reset wiring.
        # If the caller selected this port, the device must already be in the
        # official download mode; resetting it again can make esptool miss it.
        return port, "no_reset"

    before = set(serial_ports())
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        attrs = termios.tcgetattr(fd)
        attrs[4] = termios.B1200
        attrs[5] = termios.B1200
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
    finally:
        os.close(fd)

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        current = set(serial_ports())
        new_ports = sorted(current - before)
        if len(new_ports) == 1:
            return new_ports[0], "no_reset"
        if port not in current and len(current) == 1:
            return next(iter(current)), "no_reset"
        time.sleep(0.2)
    raise SystemExit("M5 已请求进入下载模式，但没有发现新串口；请检查 USB 线后重试")


def main() -> None:
    project = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="烧录已编译的 M5 双地点监控固件（保留现有配置）")
    parser.add_argument("--port", help="M5 串口；留空时自动识别唯一的 USB 串口")
    parser.add_argument(
        "--firmware",
        type=Path,
        default=project / "dist/M5Dashboard-voice-uac.bin",
        help="已编译的应用固件",
    )
    args = parser.parse_args()

    firmware = args.firmware.expanduser().resolve()
    if not firmware.is_file():
        raise SystemExit("找不到固件：%s" % firmware)
    require_noto_ui_font(firmware)

    ports = serial_ports()
    port = args.port
    if not port:
        if len(ports) != 1:
            shown = "、".join(ports) if ports else "无"
            raise SystemExit("无法唯一识别 M5 串口（当前：%s），请加 --port /dev/cu.xxx" % shown)
        port = ports[0]

    paused_services = pause_dashboard_services()
    try:
        port, before_mode = bootloader_port(port)
        command = esptool_command(project) + [
            "--chip",
            "esp32s3",
            "--port",
            port,
            "--baud",
            # The direct-flash Noto image is larger than the previous build.
            # Prefer the board's proven-stable native USB rate over speed.
            "115200",
            "--before",
            before_mode,
            "--after",
            # The 1200-bps handoff uses the ESP32-S3 native USB ROM port.
            # A watchdog reset reliably leaves ROM download mode and returns
            # to the composite dashboard device; RTS can leave this board in ROM.
            "watchdog_reset",
            "write_flash",
            "-z",
            "--flash_mode",
            "qio",
            "--flash_freq",
            "80m",
            "--flash_size",
            "16MB",
            "0x10000",
            str(firmware),
        ]
        print("正在烧录 %s；只更新应用分区，家庭 Wi-Fi 和现有令牌会保留。" % port)
        subprocess.run(command, check=True)
    finally:
        resume_dashboard_services(paused_services)
    print("烧录完成。")


if __name__ == "__main__":
    main()

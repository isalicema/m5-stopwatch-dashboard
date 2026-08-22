#!/usr/bin/env python3
"""Run non-destructive software checks before an M5 StopWatch is connected."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def run(command: list[str], cwd: Path) -> None:
    print("\n+", " ".join(command), "[%s]" % cwd.relative_to(ROOT))
    subprocess.run(command, cwd=cwd, check=True)


def check_json(path: Path) -> None:
    with path.open(encoding="utf-8") as source:
        json.load(source)
    print("OK JSON:", path.relative_to(ROOT))


def check_audio_helper() -> None:
    compiler = shutil.which("clang")
    if not compiler:
        raise SystemExit("clang 不可用；请先安装 Xcode Command Line Tools")
    source = ROOT / "m5-dashboard/mac/M5AudioInput.c"
    with tempfile.TemporaryDirectory(prefix="m5-stopwatch-ready-") as temporary:
        output = Path(temporary) / "m5_audio_input"
        run(
            [
                compiler,
                "-O2",
                "-Wall",
                "-Wextra",
                str(source),
                "-framework",
                "CoreAudio",
                "-framework",
                "CoreFoundation",
                "-o",
                str(output),
            ],
            ROOT,
        )
        if not output.is_file():
            raise SystemExit("音频助手没有生成预期文件")
    print("OK macOS audio helper")


def platformio_command() -> str:
    local = ROOT / ".pio/cli/bin/pio"
    if local.is_file():
        return str(local)
    command = shutil.which("pio")
    if command:
        return command
    raise SystemExit("找不到 pio；请先安装 PlatformIO Core")


def main() -> None:
    parser = argparse.ArgumentParser(description="M5 StopWatch 烧录前软件自检")
    parser.add_argument(
        "--firmware",
        choices=("none", "standard", "uac", "all"),
        default="none",
        help="同时编译哪套固件；默认 none 只做快速检查",
    )
    args = parser.parse_args()

    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], ROOT / "m5-dashboard")
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], ROOT / "m5-dashboard-home")
    check_json(ROOT / "m5-dashboard/config.example.json")
    check_json(ROOT / "m5-dashboard-home/config.example.json")
    check_audio_helper()

    environments: list[str] = []
    if args.firmware in ("standard", "all"):
        environments.append("m5stack-stopwatch")
    if args.firmware in ("uac", "all"):
        environments.append("m5stack-stopwatch-uac")
    pio = platformio_command() if environments else ""
    for environment in environments:
        run([pio, "run", "-e", environment], ROOT / "m5-dashboard/firmware")

    label = "、".join(environments) if environments else "未请求固件编译"
    print("\nREADY：桥接、配置和音频助手检查通过；%s。" % label)


if __name__ == "__main__":
    main()

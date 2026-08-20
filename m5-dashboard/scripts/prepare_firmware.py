#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


def cpp_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare private StopWatch firmware settings")
    parser.add_argument("--ssid", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()

    project = Path(__file__).resolve().parent.parent
    config_path = Path(args.config).expanduser().resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    token = str((config.get("server") or {}).get("api_token") or "")
    if not token:
        raise SystemExit("server.api_token is missing")

    result = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-D",
            "AirPort network password",
            "-a",
            args.ssid,
            "-w",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    password = result.stdout.rstrip("\n") if result.returncode == 0 else ""
    if not password:
        raise SystemExit("Wi-Fi password is not available in macOS Keychain")

    output = project / "firmware/M5Dashboard/secrets.h"
    temporary = output.with_suffix(".h.tmp")
    content = "\n".join(
        (
            "#pragma once",
            "",
            "// Generated locally. Do not share or commit this file.",
            "#define WIFI_SSID %s" % cpp_string(args.ssid),
            "#define WIFI_PASSWORD %s" % cpp_string(password),
            "#define BRIDGE_HOST %s" % cpp_string(args.host),
            "#define BRIDGE_PORT %d" % args.port,
            "#define BRIDGE_TOKEN %s" % cpp_string(token),
            "",
        )
    )
    temporary.write_text(content, encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, output)
    print("Prepared private firmware settings: %s" % output)
    print("SSID=%s bridge=%s:%d secrets_permissions=600" % (args.ssid, args.host, args.port))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

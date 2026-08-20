#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import secrets
import shutil
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_CREDENTIALS = Path.home() / "Library/Application Support/M5Dashboard/bambu-cloud.json"


class CloudApiError(RuntimeError):
    pass


def region_urls(region: str) -> tuple[str, str]:
    if region == "cn":
        return "https://api.bambulab.cn", "https://bambulab.cn"
    return "https://api.bambulab.com", "https://bambulab.com"


def request_json(
    url: str,
    method: str = "GET",
    payload: Optional[Dict[str, Any]] = None,
    token: str = "",
    allow_empty: bool = False,
) -> Dict[str, Any]:
    raw = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "M5Dashboard/0.2 (read-only personal status display)",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, data=raw, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20, context=ssl.create_default_context()) as response:
            response_body = response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read(240).decode("utf-8", errors="replace").replace("\n", " ")
        raise CloudApiError("HTTP %d from Bambu Cloud: %s" % (exc.code, body)) from exc
    except OSError as exc:
        raise CloudApiError("Bambu Cloud request failed: %s" % exc) from exc
    if not response_body.strip():
        if allow_empty:
            return {}
        raise CloudApiError("Bambu Cloud returned an empty response where JSON was required")
    try:
        value = json.loads(response_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        text = response_body[:80].decode("utf-8", errors="replace").strip()
        if allow_empty and text.lower() in ("ok", "success"):
            return {"message": text}
        raise CloudApiError("Bambu Cloud returned a non-JSON response: %s" % text) from exc
    if not isinstance(value, dict):
        raise CloudApiError("Bambu Cloud returned an unexpected response")
    return value


def extract_token(value: Dict[str, Any]) -> str:
    token = value.get("accessToken")
    nested = value.get("data")
    if not token and isinstance(nested, dict):
        token = nested.get("accessToken")
    return str(token or "")


def decode_user_id(token: str) -> str:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return ""
        payload = parts[1].replace("-", "+").replace("_", "/")
        payload += "=" * ((4 - len(payload) % 4) % 4)
        value = json.loads(base64.b64decode(payload).decode("utf-8"))
        uid = value.get("username") or value.get("uid") or value.get("sub") or value.get("user_id")
        if not uid:
            return ""
        uid_text = str(uid)
        return uid_text if uid_text.startswith("u_") else "u_" + uid_text
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return ""


def fetch_user_id(token: str, region: str) -> str:
    api_base, _ = region_urls(region)
    for path in ("/v1/user-service/my/profile", "/v1/design-user-service/my/preference"):
        try:
            value = request_json(api_base + path, token=token)
        except CloudApiError:
            continue
        nested = value.get("data") if isinstance(value.get("data"), dict) else {}
        uid = (
            value.get("uidStr")
            or value.get("uid")
            or value.get("userId")
            or nested.get("uidStr")
            or nested.get("uid")
            or nested.get("userId")
        )
        if uid:
            return "u_" + str(uid)
    return ""


def normalize_devices(value: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates: Any = value.get("data")
    if isinstance(candidates, dict):
        candidates = candidates.get("devices") or candidates.get("data")
    if not isinstance(candidates, list):
        candidates = value.get("devices")
    if not isinstance(candidates, list):
        return []
    output = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        serial = item.get("dev_id") or item.get("deviceId") or item.get("serial")
        if serial:
            output.append(
                {
                    "serial": str(serial),
                    "name": str(item.get("name") or item.get("dev_name") or "Bambu printer"),
                    "model": str(item.get("dev_product_name") or item.get("model") or ""),
                }
            )
    return output


def fetch_devices(token: str, region: str) -> List[Dict[str, Any]]:
    api_base, site_base = region_urls(region)
    urls = (
        api_base + "/v1/iot-service/api/user/bind",
        site_base + "/api/v1/iot-service/api/user/bind",
    )
    for url in urls:
        try:
            devices = normalize_devices(request_json(url, token=token))
        except CloudApiError:
            continue
        if devices:
            return devices
    return []


def verification_request(account: str, region: str) -> tuple[str, Dict[str, str], str]:
    api_base, _ = region_urls(region)
    if "@" in account:
        return (
            api_base + "/v1/user-service/user/sendemail/code",
            {"email": account, "type": "codeLogin"},
            "邮箱",
        )
    return (
        "https://bambulab.cn/api/v1/user-service/user/sendsmscode"
        if region == "cn"
        else api_base + "/v1/user-service/user/sendsmscode",
        {"phone": account, "type": "codeLogin"},
        "短信",
    )


def request_code_token(account: str, region: str, send_code: bool = True) -> str:
    url, payload, channel = verification_request(account, region)
    if send_code:
        request_json(
            url,
            method="POST",
            payload=payload,
            allow_empty=True,
        )
        print("验证码请求已被拓竹接受，请查看账号%s。" % channel)
    code = getpass.getpass("6 位%s验证码：" % channel).strip()
    api_base, _ = region_urls(region)
    result = request_json(
        api_base + "/v1/user-service/user/login",
        method="POST",
        payload={"account": account, "code": code},
    )
    token = extract_token(result)
    if not token:
        raise CloudApiError("Bambu Cloud accepted the request but did not return an access token")
    return token


def choose_device(devices: List[Dict[str, Any]], configured_serial: str = "") -> Dict[str, Any]:
    if configured_serial:
        match = next((row for row in devices if row["serial"] == configured_serial), None)
        return match or {"serial": configured_serial, "name": "P2S", "model": ""}
    if not devices:
        serial = input("未能自动读取设备列表，请输入 P2S 序列号：").strip()
        if not serial:
            raise CloudApiError("printer serial cannot be empty")
        return {"serial": serial, "name": "P2S", "model": ""}
    if len(devices) == 1:
        return devices[0]
    print("请选择打印机：")
    for index, row in enumerate(devices, 1):
        print("  %d. %s %s (%s)" % (index, row["name"], row["model"], row["serial"]))
    while True:
        answer = input("序号：").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(devices):
            return devices[int(answer) - 1]


def write_private_json(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def update_config(path: Path, credentials_path: Path, printer: Dict[str, Any], region: str) -> None:
    if path.exists():
        value = json.loads(path.read_text(encoding="utf-8"))
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    else:
        example = Path(__file__).resolve().parent.parent / "config.example.json"
        value = json.loads(example.read_text(encoding="utf-8"))
    server = value.setdefault("server", {})
    if server.get("api_token") in (None, "", "CHANGE_ME_TO_A_LONG_RANDOM_VALUE"):
        server["api_token"] = secrets.token_urlsafe(32)
    value["bambu"] = {
        "enabled": True,
        "name": printer.get("name") or "P2S",
        "mode": "cloud",
        "region": region,
        "credentials_file": str(credentials_path),
        "full_refresh_seconds": 300,
    }
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure read-only Bambu Cloud monitoring")
    parser.add_argument("--region", choices=("global", "cn"), help="Bambu account region")
    parser.add_argument("--paste-token", action="store_true", help="paste an existing token")
    parser.add_argument(
        "--use-existing-code",
        action="store_true",
        help="do not request a new code; enter one already received",
    )
    parser.add_argument("--serial", default="", help="printer serial if device discovery is blocked")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--credentials", default=str(DEFAULT_CREDENTIALS))
    args = parser.parse_args()

    region = args.region
    if not region:
        answer = input("拓竹账号区域 [1=中国大陆, 2=全球]（默认 1）：").strip()
        region = "global" if answer == "2" else "cn"
    try:
        if args.paste_token:
            token = getpass.getpass("粘贴 Bambu Cloud token（输入不可见）：").strip()
        else:
            label = "拓竹账号手机号或邮箱" if region == "cn" else "拓竹账号邮箱"
            account = input(label + "（不会保存）：").strip()
            token = request_code_token(account, region, send_code=not args.use_existing_code)
        if not token:
            raise CloudApiError("access token cannot be empty")
        user_id = decode_user_id(token) or fetch_user_id(token, region)
        if not user_id:
            user_id = input("无法自动取得账号 UID，请输入 UID（不含或包含 u_ 均可）：").strip()
            if user_id and not user_id.startswith("u_"):
                user_id = "u_" + user_id
        if not user_id:
            raise CloudApiError("account UID cannot be empty")
        printer = choose_device(fetch_devices(token, region), args.serial)
        credentials_path = Path(args.credentials).expanduser().resolve()
        write_private_json(
            credentials_path,
            {
                "mode": "cloud",
                "region": region,
                "user_id": user_id,
                "access_token": token,
                "serial": printer["serial"],
            },
        )
        config_path = Path(args.config).expanduser().resolve()
        update_config(config_path, credentials_path, printer, region)
    except (CloudApiError, OSError, json.JSONDecodeError) as exc:
        print("云端配置失败：%s" % exc, file=sys.stderr)
        print(
            "若验证码接口被 Cloudflare 拦截，请从已登录的拓竹网页 cookie 复制 token，"
            "然后加 --paste-token 重试。",
            file=sys.stderr,
        )
        return 1

    print("已启用 Bambu Cloud 只读监控：%s (%s)" % (printer["name"], printer["serial"]))
    print("令牌仅保存在权限为 600 的文件：%s" % credentials_path)
    print("主配置已更新：%s" % config_path)
    print("令牌通常约 3 个月后过期；届时重新运行本脚本即可。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

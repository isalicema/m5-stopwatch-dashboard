from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


FACTORY_OTA_PARTITION_SIZE = 0x4F0000
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class FirmwareRelease:
    release_id: str
    size: int
    sha256: str
    path: Path

    def manifest(self) -> Dict[str, Any]:
        return {
            "schema": 1,
            "release_id": self.release_id,
            "size": self.size,
            "sha256": self.sha256,
            "download_path": "/api/ota/firmware/" + self.sha256,
        }


class FirmwareCatalog:
    """Expose an atomically published, immutable firmware release."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.enabled = bool(config.get("enabled", False))
        directory = str(config.get("directory") or "~/Library/Application Support/M5Dashboard/ota")
        self.directory = Path(directory).expanduser()
        self.manifest_path = self.directory / "current.json"
        self.max_size = max(
            1,
            min(
                FACTORY_OTA_PARTITION_SIZE,
                int(config.get("max_firmware_bytes", FACTORY_OTA_PARTITION_SIZE)),
            ),
        )
        self._cached_key: tuple[str, int, int] | None = None
        self._cached_release: FirmwareRelease | None = None

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def current(self) -> Optional[FirmwareRelease]:
        if not self.enabled:
            return None
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(value, dict) or value.get("schema") != 1:
            return None
        sha256 = str(value.get("sha256") or "").lower()
        release_id = str(value.get("release_id") or "")
        filename = str(value.get("filename") or "")
        size = int(value.get("size") or 0)
        if (
            not SHA256_RE.fullmatch(sha256)
            or release_id != sha256
            or filename != "firmware-" + sha256 + ".bin"
            or size <= 0
            or size > self.max_size
        ):
            return None
        path = self.directory / filename
        try:
            stat = path.stat()
        except OSError:
            return None
        if not path.is_file() or stat.st_size != size:
            return None
        key = (sha256, stat.st_size, stat.st_mtime_ns)
        if key != self._cached_key:
            if self._sha256(path) != sha256:
                self._cached_key = None
                self._cached_release = None
                return None
            self._cached_key = key
            self._cached_release = FirmwareRelease(release_id, size, sha256, path)
        return self._cached_release

    def resolve(self, sha256: str) -> Optional[FirmwareRelease]:
        release = self.current()
        if release is None or release.sha256 != str(sha256 or "").lower():
            return None
        return release

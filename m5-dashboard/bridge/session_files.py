from __future__ import annotations

from pathlib import Path
from typing import List, Tuple


SessionFile = Tuple[Path, float, int]


def recent_session_files(root: Path, now: float, stale_seconds: int) -> List[SessionFile]:
    """Take one path/mtime/size inventory for local activity and transcripts."""
    if not root.is_dir():
        return []
    candidates: List[SessionFile] = []
    try:
        for path in root.rglob("*.jsonl"):
            try:
                stat = path.stat()
            except OSError:
                continue
            if stat.st_mtime >= now - stale_seconds:
                candidates.append((path, stat.st_mtime, stat.st_size))
    except OSError:
        return []
    candidates.sort(key=lambda item: item[1], reverse=True)
    return candidates

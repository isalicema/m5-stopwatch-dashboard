from __future__ import annotations

import copy
import hashlib
import json
import random
import re
import subprocess
import threading
import time
import unicodedata
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional


DEFAULT_EXCLUDES = (".obsidian", ".trash", ".git", "node_modules", "Alice Writing")
# Never eligible, even when a note declares `lucky: true`.
DEFAULT_NEVER_INCLUDE = ("Alice Writing",)
DEFAULT_POOLS: tuple[Dict[str, Any], ...] = (
    {
        "name": "核心洞察",
        "weight": 4.0,
        "folders": (
            {"path": "Insights", "weight": 1.0},
            {"path": "Machiwhale Studio", "weight": 1.0},
            {"path": "Alice兴趣研究", "weight": 1.0},
            {"path": "Tech History", "weight": 1.0},
            {"path": "妙蛙种子进化史", "weight": 1.0},
        ),
    },
    {
        "name": "灵感探索",
        "weight": 1.0,
        "folders": (
            {"path": "妙蛙种子收藏夹", "weight": 1.0},
            {"path": "Newsletter Digests", "weight": 0.8},
            {"path": "HCI arXiv", "weight": 0.6},
            {"path": "rabbitT dream", "weight": 0.35},
            {"path": "Codex Report", "weight": 0.25},
        ),
    },
)


@dataclass(frozen=True)
class ObsidianNote:
    path: Path
    root: Path
    title: str
    pool: str = "全部笔记"
    pool_weight: float = 1.0
    folder_key: str = ""
    folder_weight: float = 1.0

    @property
    def relative_path(self) -> str:
        return self.path.relative_to(self.root).as_posix()

    @property
    def note_id(self) -> str:
        value = "%s\0%s" % (self.root, self.relative_path)
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]

    @property
    def folder(self) -> str:
        parent = self.path.relative_to(self.root).parent.as_posix()
        return self.root.name if parent == "." else "%s · %s" % (self.root.name, parent)

    def as_dict(self, reason: str = "") -> Dict[str, str]:
        return {
            "id": self.note_id,
            "title": _device_title(self.title)[:96],
            "folder": self.folder[:96],
            "relative_path": self.relative_path,
            "pool": self.pool[:32],
            "reason": reason[:32],
        }


def _device_title(value: str) -> str:
    """Keep arbitrary Markdown titles legible on the device's compact CJK font."""
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    cleaned = []
    for character in text:
        category = unicodedata.category(character)
        if category in {"Cf", "Mn"} or category.startswith("C"):
            continue
        # Color emoji are not available in the embedded monochrome CJK font.
        if category == "So":
            continue
        cleaned.append(character)
    text = re.sub(r"\s+", " ", "".join(cleaned)).strip()
    return text or "未命名笔记"


def _names(values: Iterable[str]) -> set[str]:
    return {str(value).strip().casefold() for value in values if str(value).strip()}


def _excluded(relative: Path, excluded_names: Iterable[str]) -> bool:
    denied = _names(excluded_names)
    return any(part.casefold() in denied or part.startswith(".") for part in relative.parts[:-1])


def _frontmatter_and_title(path: Path) -> tuple[str, Optional[bool]]:
    try:
        # Only inspect a small header. The body is not retained or sent to the device.
        text = path.read_text(encoding="utf-8", errors="replace")[:8192]
    except OSError:
        return path.stem, None
    title = ""
    lucky: Optional[bool] = None
    frontmatter = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", text, flags=re.DOTALL)
    if frontmatter:
        title_match = re.search(r"(?mi)^title:\s*[\"']?(.*?)[\"']?\s*$", frontmatter.group(1))
        if title_match:
            title = title_match.group(1).strip()
        lucky_match = re.search(r"(?mi)^lucky:\s*(true|false|yes|no|1|0)\s*$", frontmatter.group(1))
        if lucky_match:
            lucky = lucky_match.group(1).casefold() in {"true", "yes", "1"}
    if not title:
        heading = re.search(r"(?m)^#\s+(.+?)\s*$", text)
        if heading:
            title = heading.group(1).strip()
    return (title or path.stem)[:96], lucky


def _normalise_pools(configured: Any) -> list[Dict[str, Any]]:
    source = configured if isinstance(configured, (list, tuple)) else DEFAULT_POOLS
    pools: list[Dict[str, Any]] = []
    for raw_pool in source:
        if not isinstance(raw_pool, dict):
            continue
        name = str(raw_pool.get("name") or "灵感探索").strip()
        try:
            pool_weight = max(0.0, float(raw_pool.get("weight", 1.0)))
        except (TypeError, ValueError):
            pool_weight = 1.0
        folders = []
        for raw_folder in raw_pool.get("folders") or []:
            if isinstance(raw_folder, str):
                folder_path, folder_weight = raw_folder, 1.0
            elif isinstance(raw_folder, dict):
                folder_path = str(raw_folder.get("path") or "")
                try:
                    folder_weight = max(0.0, float(raw_folder.get("weight", 1.0)))
                except (TypeError, ValueError):
                    folder_weight = 1.0
            else:
                continue
            folder_path = folder_path.strip().strip("/")
            if folder_path and folder_weight > 0:
                folders.append({"path": folder_path, "weight": folder_weight})
        if name and pool_weight > 0 and folders:
            pools.append({"name": name, "weight": pool_weight, "folders": folders})
    return pools


def _classify(relative: Path, pools: list[Dict[str, Any]]) -> Optional[tuple[str, float, str, float]]:
    relative_text = relative.as_posix().casefold()
    for pool in pools:
        for folder in pool["folders"]:
            folder_path = str(folder["path"]).casefold()
            root_file_match = folder_path == "." and "/" not in relative_text
            if root_file_match or relative_text == folder_path or relative_text.startswith(folder_path + "/"):
                return pool["name"], pool["weight"], folder["path"], folder["weight"]
    return None


def scan_notes(
    roots: Iterable[Path],
    excluded_names: Iterable[str],
    max_files: int = 5000,
    *,
    pools: Any = None,
    never_include_names: Iterable[str] = DEFAULT_NEVER_INCLUDE,
) -> list[ObsidianNote]:
    notes: list[ObsidianNote] = []
    parsed_pools = _normalise_pools(pools) if pools is not None else []
    exclusions = tuple(DEFAULT_EXCLUDES) + tuple(excluded_names)
    never_include = tuple(DEFAULT_NEVER_INCLUDE) + tuple(never_include_names)
    for root_value in roots:
        root = root_value.expanduser().resolve()
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            if len(notes) >= max_files:
                return notes
            relative = path.relative_to(root)
            if _excluded(relative, never_include) or _excluded(relative, exclusions):
                continue
            title, lucky = _frontmatter_and_title(path)
            if lucky is False:
                continue
            classification = _classify(relative, parsed_pools) if parsed_pools else None
            if classification is None and parsed_pools and lucky is not True:
                continue
            if classification is None:
                folder_key = relative.parts[0] if len(relative.parts) > 1 else "."
                classification = ("手动精选" if lucky is True and parsed_pools else "全部笔记", 1.0, folder_key, 1.0)
            notes.append(
                ObsidianNote(
                    path=path,
                    root=root,
                    title=title,
                    pool=classification[0],
                    pool_weight=classification[1],
                    folder_key=classification[2],
                    folder_weight=classification[3],
                )
            )
    return notes


class ObsidianDice(threading.Thread):
    """Index explicitly configured Markdown roots and return one lucky note."""

    daemon = True

    def __init__(
        self,
        config: Dict[str, Any],
        callback: Callable[[Dict[str, Any]], None],
        *,
        chooser: Optional[Callable[[list[ObsidianNote]], ObsidianNote]] = None,
        launcher: Optional[Callable[[Path], None]] = None,
        random_value: Optional[Callable[[], float]] = None,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        super().__init__(name="m5-obsidian-dice")
        self.config = copy.deepcopy(config)
        self.callback = callback
        system_random = random.SystemRandom()
        self._chooser = chooser or system_random.choice
        self._random_value = random_value or system_random.random
        self._launcher = launcher
        self._clock = clock or time.time
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._notes: list[ObsidianNote] = []
        self._selected: Optional[ObsidianNote] = None
        self._recent_ids: list[str] = []
        self._history: Dict[str, Dict[str, int]] = {}
        self._state: Dict[str, Any] = {
            "connected": False,
            "available_count": 0,
            "pool_counts": {},
            "selected": {},
            "rolled_at": 0,
            "updated_at": 0,
            "error": "starting",
        }
        self._load_persistent_state()

    @staticmethod
    def _open_on_mac(note: ObsidianNote) -> None:
        encoded_path = urllib.parse.quote(str(note.path.resolve()), safe="")
        uri = "obsidian://open?path=" + encoded_path
        try:
            subprocess.run(
                ["/usr/bin/open", uri],
                check=True,
                timeout=5,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise OSError("Obsidian could not open the selected note") from exc

    def _roots(self) -> list[Path]:
        configured = self.config.get("roots")
        if not isinstance(configured, list):
            return []
        return [Path(str(value)).expanduser() for value in configured if str(value).strip()]

    def _state_path(self) -> Optional[Path]:
        value = str(self.config.get("state_path") or "").strip()
        return Path(value).expanduser() if value else None

    def _load_persistent_state(self) -> None:
        path = self._state_path()
        if path is None:
            return
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return
        recent = value.get("recent_ids") if isinstance(value, dict) else None
        history = value.get("history") if isinstance(value, dict) else None
        if isinstance(recent, list):
            self._recent_ids = [str(note_id) for note_id in recent if str(note_id)]
        if isinstance(history, dict):
            for note_id, raw in history.items():
                if not isinstance(raw, dict):
                    continue
                try:
                    self._history[str(note_id)] = {
                        "rolled_at": max(0, int(raw.get("rolled_at", 0))),
                        "opened_at": max(0, int(raw.get("opened_at", 0))),
                        "roll_count": max(0, int(raw.get("roll_count", 0))),
                    }
                except (TypeError, ValueError):
                    continue

    def _save_persistent_state(self) -> None:
        path = self._state_path()
        if path is None:
            return
        payload = {"version": 1, "recent_ids": self._recent_ids, "history": self._history}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(path)
        except OSError:
            return

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state)

    def _publish(self) -> Dict[str, Any]:
        value = self.snapshot()
        self.callback(value)
        return value

    def refresh(self) -> Dict[str, Any]:
        roots = self._roots()
        excludes = self.config.get("exclude_names") or ()
        never_include = self.config.get("never_include_names") or DEFAULT_NEVER_INCLUDE
        max_files = max(1, min(20000, int(self.config.get("max_files", 5000))))
        notes = scan_notes(
            roots,
            excludes,
            max_files,
            pools=self.config.get("pools", DEFAULT_POOLS),
            never_include_names=never_include,
        )
        now = int(self._clock())
        pool_counts: Dict[str, int] = {}
        for note in notes:
            pool_counts[note.pool] = pool_counts.get(note.pool, 0) + 1
        with self._lock:
            self._notes = notes
            indexed_ids = {note.note_id for note in notes}
            if self._selected and self._selected.note_id not in indexed_ids:
                self._selected = None
                self._state["selected"] = {}
            self._state["connected"] = bool(roots) and any(root.expanduser().is_dir() for root in roots)
            self._state["available_count"] = len(notes)
            self._state["pool_counts"] = pool_counts
            self._state["updated_at"] = now
            self._state["error"] = "" if notes else "no authorized lucky notes found"
        return self._publish()

    def _weighted_choice(self, values: list[Any], weight: Callable[[Any], float]) -> Any:
        weighted = [(value, max(0.0, float(weight(value)))) for value in values]
        if not weighted:
            raise ValueError("cannot choose from an empty sequence")
        total = sum(item_weight for _, item_weight in weighted)
        if total <= 0:
            return weighted[0][0]
        point = min(max(self._random_value(), 0.0), 0.999999999999) * total
        upto = 0.0
        for value, item_weight in weighted:
            upto += item_weight
            if point < upto:
                return value
        return weighted[-1][0]

    def _choose_note(self, notes: list[ObsidianNote]) -> ObsidianNote:
        pools = sorted({note.pool for note in notes})
        selected_pool = self._weighted_choice(
            pools, lambda name: next(note.pool_weight for note in notes if note.pool == name)
        )
        in_pool = [note for note in notes if note.pool == selected_pool]
        folders = sorted({note.folder_key for note in in_pool})
        selected_folder = self._weighted_choice(
            folders, lambda name: next(note.folder_weight for note in in_pool if note.folder_key == name)
        )
        in_folder = [note for note in in_pool if note.folder_key == selected_folder]

        def last_seen(note: ObsidianNote) -> int:
            history = self._history.get(note.note_id, {})
            return max(int(history.get("rolled_at", 0)), int(history.get("opened_at", 0)))

        ordered = sorted(in_folder, key=lambda note: (last_seen(note), note.note_id))
        oldest_band = ordered[: max(1, (len(ordered) + 1) // 2)]
        return self._chooser(oldest_band)

    def _reason_for(self, note: ObsidianNote, now: int) -> str:
        history = self._history.get(note.note_id, {})
        last_seen = max(int(history.get("rolled_at", 0)), int(history.get("opened_at", 0)))
        if last_seen and now - last_seen >= 30 * 24 * 60 * 60:
            return "久未重访"
        if note.pool == "核心洞察":
            return "来自核心洞察"
        if note.pool == "手动精选":
            return "手动精选"
        return "灵感探索"

    def roll(self) -> Dict[str, Any]:
        with self._lock:
            cooldown_count = max(1, min(200, int(self.config.get("cooldown_count", 30))))
            recent = set(self._recent_ids[-cooldown_count:])
            choices = [note for note in self._notes if note.note_id not in recent]
            if not choices:
                choices = [note for note in self._notes if note != self._selected]
            if not choices:
                choices = list(self._notes)
            if not choices:
                raise ValueError("no authorized Obsidian notes are available")
            selected = self._choose_note(choices)
            now = int(self._clock())
            reason = self._reason_for(selected, now)
            self._selected = selected
            self._recent_ids.append(selected.note_id)
            self._recent_ids = self._recent_ids[-cooldown_count:]
            history = self._history.setdefault(
                selected.note_id, {"rolled_at": 0, "opened_at": 0, "roll_count": 0}
            )
            history["rolled_at"] = now
            history["roll_count"] = int(history.get("roll_count", 0)) + 1
            self._state["selected"] = selected.as_dict(reason)
            self._state["rolled_at"] = now
            self._state["updated_at"] = now
            self._state["error"] = ""
            self._save_persistent_state()
        return self._publish()

    def open_selected(self) -> Dict[str, Any]:
        with self._lock:
            note = self._selected
            indexed_ids = {candidate.note_id for candidate in self._notes}
            if note is None:
                raise ValueError("roll an Obsidian note before opening it")
            if note.note_id not in indexed_ids or not note.path.is_file():
                raise ValueError("the selected Obsidian note is no longer available")
            if self._launcher is None:
                self._open_on_mac(note)
            else:
                self._launcher(note.path)
            now = int(self._clock())
            history = self._history.setdefault(
                note.note_id, {"rolled_at": 0, "opened_at": 0, "roll_count": 0}
            )
            history["opened_at"] = now
            self._state["updated_at"] = now
            self._save_persistent_state()
        return self._publish()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        refresh = max(60, int(self.config.get("refresh_seconds", 900)))
        while not self._stop_event.is_set():
            self.refresh()
            self._stop_event.wait(refresh)

from __future__ import annotations

import copy
import datetime as dt
import email.utils
import hashlib
import http.client
import json
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional
from urllib.parse import urlencode, urlparse, urlunparse


DEFAULT_INTEREST_TERMS = (
    "codex",
    "openai",
    "gpt",
    "chatgpt work",
    "claude",
    "claude code",
    "anthropic",
    "gemini",
    "deepmind",
    "deepseek",
    "kimi",
    "moonshot",
    "月之暗面",
    "agent",
    "mcp",
    "coding agent",
    "模型",
    "额度",
)

DEFAULT_EVENT_TERMS = (
    "正式发布",
    "正式上线",
    "全面上线",
    "发布",
    "上线",
    "重置",
    "额度",
    "价格",
    "套餐",
    "故障",
    "中断",
    "安全事件",
    "多模态",
    "视觉模型",
    "launch",
    "released",
    "generally available",
    "general availability",
    "deprecat",
    "pricing",
    "quota",
    "rate limit",
    "reset",
    "outage",
    "incident",
    "security",
    "multimodal",
    "vision model",
    "vision-exp",
)

DEFAULT_NEGATIVE_TERMS = (
    "融资",
    "合作",
    "加入",
    "收购",
    "招聘",
    "观点",
    "教学",
    "教程",
    "论文",
    "研究",
    "partnership",
    "funding",
    "acquisition",
    "joins",
    "hiring",
    "case study",
    "teaching",
    "learning",
    "paper",
)

DEFAULT_OFFICIAL_DOMAINS = (
    "openai.com",
    "anthropic.com",
    "claude.com",
    "deepmind.google",
    "blog.google",
    "ai.google.dev",
    "deepseek.com",
    "moonshot.cn",
    "moonshot.ai",
    "kimi.com",
    "kimi.ai",
)

# These providers are part of Alice's permanent watch list.  Keep them merged
# even when an older private config overrides the public defaults.
REQUIRED_PROVIDER_INTEREST_TERMS = (
    "deepseek",
    "kimi",
    "moonshot",
    "月之暗面",
)
REQUIRED_MODEL_EVENT_TERMS = (
    "多模态",
    "视觉模型",
    "multimodal",
    "vision model",
    "vision-exp",
)
REQUIRED_PROVIDER_DOMAINS = (
    "deepseek.com",
    "moonshot.cn",
    "moonshot.ai",
    "kimi.com",
    "kimi.ai",
)
DEFAULT_OFFICIAL_URL_PREFIXES = (
    "https://x.com/deepseek_ai/",
    "https://twitter.com/deepseek_ai/",
    "https://github.com/deepseek-ai/",
    "https://huggingface.co/deepseek-ai/",
    "https://x.com/kimi_moonshot/",
    "https://twitter.com/kimi_moonshot/",
    "https://github.com/moonshotai/",
    "https://huggingface.co/moonshotai/",
)

SEVERITY_ORDER = {"inbox": 0, "alert": 1, "scream": 2}
MAX_EXPOSED_EVENTS = 12


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _first_text(node: ET.Element, names: Iterable[str]) -> str:
    wanted = {name.lower() for name in names}
    for child in node.iter():
        if _local_name(child.tag) in wanted and child.text:
            value = child.text.strip()
            if value:
                return value
    return ""


def _entry_link(node: ET.Element) -> str:
    for child in node.iter():
        if _local_name(child.tag) != "link":
            continue
        href = str(child.attrib.get("href") or "").strip()
        if href:
            return href
        if child.text and child.text.strip():
            return child.text.strip()
    return ""


def _published_timestamp(value: Any) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    try:
        parsed = email.utils.parsedate_to_datetime(text)
        return int(parsed.timestamp())
    except (TypeError, ValueError, OverflowError):
        pass
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return int(parsed.timestamp())
    except (TypeError, ValueError, OverflowError):
        return 0


def parse_feed(payload: bytes, source_name: str) -> list[Dict[str, Any]]:
    root = ET.fromstring(payload)
    entries: list[Dict[str, Any]] = []
    for node in root.iter():
        if _local_name(node.tag) not in ("item", "entry"):
            continue
        title = _first_text(node, ("title",))
        link = _entry_link(node)
        published = _first_text(node, ("pubdate", "published", "updated"))
        identity = _first_text(node, ("guid", "id")) or link or title
        if not title or not identity:
            continue
        entry_id = hashlib.sha256(
            (str(source_name) + "\n" + identity).encode("utf-8", errors="replace")
        ).hexdigest()[:24]
        entries.append(
            {
                "id": entry_id,
                "title": title[:160],
                "source": str(source_name)[:48],
                "url": link[:1024],
                "published_at": _published_timestamp(published),
            }
        )
    return entries


def headline_matches(title: str, keywords: Iterable[str]) -> bool:
    folded = str(title or "").casefold()
    return any(str(keyword).casefold() in folded for keyword in keywords if str(keyword))


def _canonical_url(value: Any) -> str:
    text = str(value or "").strip()
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    return urlunparse((parsed.scheme, parsed.netloc.casefold(), parsed.path, "", "", ""))[:1024]


def _host_is_official(url: str, domains: Iterable[str]) -> bool:
    host = (urlparse(url).hostname or "").casefold()
    return any(host == domain.casefold() or host.endswith("." + domain.casefold()) for domain in domains)


def _url_has_official_prefix(url: str, prefixes: Iterable[str]) -> bool:
    canonical = _canonical_url(url).casefold().rstrip("/")
    if not canonical:
        return False
    for prefix in prefixes:
        candidate = _canonical_url(prefix).casefold().rstrip("/")
        if candidate and (canonical == candidate or canonical.startswith(candidate + "/")):
            return True
    return False


def _title_fingerprint(title: str) -> str:
    normalized = re.sub(r"[^0-9a-z\u3400-\u9fff]+", "", str(title).casefold())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]


def _terms(config: Dict[str, Any], key: str, defaults: Iterable[str]) -> tuple[str, ...]:
    configured = config.get(key)
    if not isinstance(configured, list):
        return tuple(defaults)
    return tuple(str(value).strip() for value in configured if str(value).strip())


def _merged_terms(*groups: Iterable[str]) -> tuple[str, ...]:
    values: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for value in group:
            text = str(value).strip()
            folded = text.casefold()
            if not text or folded in seen:
                continue
            seen.add(folded)
            values.append(text)
    return tuple(values)


def classify_ai_event(event: Dict[str, Any], config: Dict[str, Any]) -> tuple[str, int, str]:
    """Return a deterministic severity, score and auditable reason."""

    text = " ".join(
        str(event.get(key) or "")
        for key in ("title", "summary", "original_title", "source")
    ).casefold()
    interest_terms = _merged_terms(
        _terms(config, "interest_terms", DEFAULT_INTEREST_TERMS),
        REQUIRED_PROVIDER_INTEREST_TERMS,
    )
    event_terms = _merged_terms(
        _terms(config, "event_terms", DEFAULT_EVENT_TERMS),
        REQUIRED_MODEL_EVENT_TERMS,
    )
    negative_terms = _terms(config, "negative_terms", DEFAULT_NEGATIVE_TERMS)
    interest_hits = [term for term in interest_terms if term.casefold() in text]
    event_hits = [term for term in event_terms if term.casefold() in text]
    negative_hits = [term for term in negative_terms if term.casefold() in text]
    official = bool(event.get("official"))
    source_count = max(0, int(event.get("source_count") or 0))
    try:
        aggregator_score = float(event.get("aggregator_score") or 0)
    except (TypeError, ValueError):
        aggregator_score = 0

    score = 0
    if official:
        score += 35
    if interest_hits:
        score += 25
    if event_hits:
        score += 20
    if source_count >= 2:
        score += 10
    if aggregator_score >= 75:
        score += 10
    if negative_hits:
        score -= 35
    score = max(0, min(100, score))

    if negative_hits:
        severity = "inbox"
    elif official and interest_hits and event_hits and score >= 75:
        severity = "scream"
    elif interest_hits and score >= 45:
        severity = "alert"
    else:
        severity = "inbox"

    reasons = []
    if official:
        reasons.append("官方原文")
    if interest_hits:
        reasons.append("关注对象:" + ",".join(interest_hits[:3]))
    if event_hits:
        reasons.append("重大事件词:" + ",".join(event_hits[:2]))
    if source_count >= 2:
        reasons.append("%d 个信源佐证" % source_count)
    if negative_hits:
        reasons.append("降级词:" + ",".join(negative_hits[:2]))
    return severity, score, "；".join(reasons) or "未达到提醒阈值"


class RemoteFetchError(OSError):
    def __init__(self, message: str, *, status: int = 0, code: str = "", retry_after: int = 0):
        super().__init__(message)
        self.status = status
        self.code = code
        self.retry_after = retry_after


class AIHotspotMonitor(threading.Thread):
    """Aggregate confirmed Codex resets, AIHOT changes and official AI feeds."""

    daemon = True

    def __init__(
        self,
        config: Dict[str, Any],
        callback: Callable[[Dict[str, Any]], None],
        *,
        opener: Optional[Callable[..., Any]] = None,
        launcher: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(name="m5-ai-hotspots")
        self.config = copy.deepcopy(config)
        self.callback = callback
        self._opener = opener or urllib.request.urlopen
        self._launcher = launcher or self._open_on_mac
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._state_path = Path(
            str(
                self.config.get("state_path")
                or "~/Library/Application Support/M5Dashboard/ai_hotspots.json"
            )
        ).expanduser()
        self._events: list[Dict[str, Any]] = []
        self._rss_seen: list[str] = []
        self._official_baselines: set[str] = set()
        self._codex_last_reset_id = ""
        self._codex_watch_id = ""
        self._aihot_cursor = ""
        self._etags: Dict[str, str] = {}
        self._source_health: Dict[str, Dict[str, Any]] = {}
        self._next_due: Dict[str, int] = {}
        self._failure_counts: Dict[str, int] = {}
        self._hot_topics: Dict[str, Dict[str, Any]] = {}
        self._state: Dict[str, Any] = {
            "connected": False,
            "active": False,
            "unread_count": 0,
            "counts": {"scream": 0, "alert": 0, "inbox": 0},
            "alert": {},
            "events": [],
            "source_health": {},
            "updated_at": 0,
            "error": "starting",
        }
        self._load()
        self._refresh_public_state(int(time.time()))

    @staticmethod
    def _open_on_mac(url: str) -> None:
        if not _canonical_url(url):
            raise ValueError("AI hotspot URL must use http or https")
        subprocess.Popen(["open", url], close_fds=True)

    def _load(self) -> None:
        try:
            value = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(value, dict):
            return
        self._rss_seen = [str(item) for item in value.get("rss_seen", value.get("seen", [])) if item][-1000:]
        self._official_baselines = {
            str(item) for item in value.get("official_baselines", []) if str(item)
        }
        if value.get("baseline_ready") and not self._official_baselines:
            self._official_baselines.add("legacy")
        self._codex_last_reset_id = str(value.get("codex_last_reset_id") or "")
        self._codex_watch_id = str(value.get("codex_watch_id") or "")
        self._aihot_cursor = str(value.get("aihot_cursor") or "")
        self._etags = {
            str(key): str(item)
            for key, item in (value.get("etags") or {}).items()
            if str(key) and str(item)
        }
        events = value.get("events")
        if isinstance(events, list):
            self._events = [copy.deepcopy(item) for item in events if isinstance(item, dict)]
        else:
            alert = value.get("alert")
            if isinstance(alert, dict) and alert.get("id") and not value.get("acknowledged", True):
                migrated = copy.deepcopy(alert)
                migrated.setdefault("event_id", str(alert["id"]))
                migrated.setdefault("severity", "scream")
                migrated.setdefault("status", "unread")
                migrated.setdefault("kind", "ai_news")
                self._events = [migrated]

    def _save(self) -> None:
        with self._lock:
            payload = {
                "version": 2,
                "rss_seen": self._rss_seen[-1000:],
                "official_baselines": sorted(self._official_baselines),
                "codex_last_reset_id": self._codex_last_reset_id,
                "codex_watch_id": self._codex_watch_id,
                "aihot_cursor": self._aihot_cursor,
                "etags": copy.deepcopy(self._etags),
                "events": copy.deepcopy(self._events[-self._max_queue() :]),
            }
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(self._state_path)

    def _max_queue(self) -> int:
        return max(10, min(200, int(self.config.get("max_queue", 50))))

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._state)

    def _publish(self) -> Dict[str, Any]:
        value = self.snapshot()
        self.callback(value)
        return value

    def _timeout(self) -> float:
        return max(1.0, min(30.0, float(self.config.get("timeout_seconds", 12))))

    @staticmethod
    def _header(headers: Any, name: str) -> str:
        if headers is None:
            return ""
        try:
            return str(headers.get(name) or "")
        except AttributeError:
            return ""

    def _fetch(self, url: str, etag_key: str, *, json_body: bool) -> Any:
        headers = {"User-Agent": "M5Dashboard/0.2 (+local AI alerts)"}
        etag = self._etags.get(etag_key)
        if etag:
            headers["If-None-Match"] = etag
        request = urllib.request.Request(url, headers=headers)
        try:
            with self._opener(request, timeout=self._timeout()) as response:
                response_etag = self._header(getattr(response, "headers", None), "ETag")
                if response_etag:
                    self._etags[etag_key] = response_etag
                payload = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                response_etag = self._header(exc.headers, "ETag")
                if response_etag:
                    self._etags[etag_key] = response_etag
                exc.close()
                return None
            raw = exc.read()
            exc.close()
            try:
                problem = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                problem = {}
            retry = self._header(exc.headers, "Retry-After")
            raise RemoteFetchError(
                str(problem.get("detail") or problem.get("title") or exc),
                status=int(exc.code),
                code=str(problem.get("code") or ""),
                retry_after=int(retry) if retry.isdigit() else 0,
            ) from exc
        except (OSError, ValueError) as exc:
            raise RemoteFetchError(str(exc)) from exc
        if not json_body:
            return payload
        try:
            value = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RemoteFetchError("response is not valid JSON") from exc
        if not isinstance(value, dict):
            raise RemoteFetchError("response JSON must be an object")
        return value

    def _health(self, name: str, connected: bool, now: int, error: str = "") -> None:
        self._source_health[name] = {
            "connected": connected,
            "updated_at": now,
            "error": str(error)[:240],
        }

    def _max_age_seconds(self) -> int:
        hours = max(1, min(168, int(self.config.get("max_age_hours", 24))))
        return hours * 3600

    def _fresh(self, published_at: int, now: int) -> bool:
        return published_at <= 0 or now - published_at <= self._max_age_seconds()

    def _event(self, **values: Any) -> Dict[str, Any]:
        event_id = str(values.get("event_id") or "")[:160]
        title = str(values.get("title") or "")[:160]
        event = {
            "event_id": event_id,
            "id": event_id,
            "kind": str(values.get("kind") or "ai_news")[:32],
            "severity": str(values.get("severity") or "inbox"),
            "title": title,
            "summary": str(values.get("summary") or "")[:240],
            "reason": str(values.get("reason") or "")[:240],
            "source": str(values.get("source") or "AI")[:64],
            "url": _canonical_url(values.get("url")),
            "published_at": max(0, int(values.get("published_at") or 0)),
            "received_at": max(0, int(values.get("received_at") or int(time.time()))),
            "status": str(values.get("status") or "unread"),
            "origin_id": str(values.get("origin_id") or event_id)[:160],
            "fingerprint": _title_fingerprint(title),
            "score": max(0, min(100, int(values.get("score") or 0))),
            "official": bool(values.get("official")),
            "sources": [str(values.get("source") or "AI")[:64]],
        }
        return event

    def _upsert_event(self, event: Dict[str, Any]) -> None:
        if not event.get("event_id") or not event.get("title"):
            return
        for current in self._events:
            if current.get("event_id") == event["event_id"]:
                status = current.get("status", "unread")
                sources = list(dict.fromkeys((current.get("sources") or []) + event.get("sources", [])))
                current.update(copy.deepcopy(event))
                current["status"] = status
                current["sources"] = sources[:8]
                return
        for current in reversed(self._events):
            same_url = bool(event.get("url")) and current.get("url") == event.get("url")
            same_title = current.get("fingerprint") == event.get("fingerprint")
            if not same_url and not same_title:
                continue
            published_delta = abs(
                int(current.get("published_at") or 0)
                - int(event.get("published_at") or 0)
            )
            if not same_url and published_delta > 24 * 3600:
                continue
            current["sources"] = list(
                dict.fromkeys((current.get("sources") or []) + event.get("sources", []))
            )[:8]
            if SEVERITY_ORDER.get(event["severity"], 0) > SEVERITY_ORDER.get(current.get("severity", "inbox"), 0):
                current["severity"] = event["severity"]
                current["reason"] = event["reason"]
                current["score"] = event["score"]
            if event.get("official") and not current.get("official"):
                current["official"] = True
                current["source"] = event["source"]
                current["url"] = event["url"]
            return
        self._events.append(copy.deepcopy(event))
        self._events = self._events[-self._max_queue() :]

    def _withdraw_aihot(self, origin_id: str) -> None:
        for event in self._events:
            if event.get("origin_id") == origin_id and event.get("kind") == "ai_news":
                event["status"] = "withdrawn"

    def _refresh_public_state(self, now: int) -> None:
        unread = [event for event in self._events if event.get("status") == "unread"]
        counts = {
            severity: sum(1 for event in unread if event.get("severity") == severity)
            for severity in SEVERITY_ORDER
        }
        screams = [event for event in unread if event.get("severity") == "scream"]
        screams.sort(key=lambda event: (int(event.get("published_at") or 0), int(event.get("received_at") or 0)))
        current = copy.deepcopy(screams[-1]) if screams else {}
        errors = [
            "%s: %s" % (name, value.get("error"))
            for name, value in self._source_health.items()
            if value.get("error")
        ]
        with self._lock:
            self._state = {
                "connected": any(value.get("connected") for value in self._source_health.values()),
                "active": bool(current),
                "unread_count": counts["scream"],
                "counts": counts,
                "alert": current,
                "events": copy.deepcopy(unread[-MAX_EXPOSED_EVENTS:]),
                "source_health": copy.deepcopy(self._source_health),
                "updated_at": now,
                "error": "; ".join(errors)[:480],
            }

    def _codex_config(self) -> Dict[str, Any]:
        value = self.config.get("codex_resets")
        return value if isinstance(value, dict) else {}

    def _aihot_config(self) -> Dict[str, Any]:
        value = self.config.get("aihot")
        return value if isinstance(value, dict) else {}

    def _official_sources(self) -> list[Dict[str, Any]]:
        values = self.config.get("official_sources", self.config.get("sources", []))
        if not isinstance(values, list):
            return []
        result = []
        for value in values:
            if not isinstance(value, dict):
                continue
            url = _canonical_url(value.get("url"))
            if not url:
                continue
            result.append(
                {
                    "name": str(value.get("name") or urlparse(url).netloc or "AI")[:48],
                    "url": url,
                }
            )
        return result

    def _poll_codex_resets(self, now: int) -> None:
        config = self._codex_config()
        if not config.get("enabled", False):
            return
        url = _canonical_url(config.get("status_url") or "https://codex-resets.com/api/v1/status")
        if not url:
            raise ValueError("codex_resets.status_url must use http or https")
        value = self._fetch(url, "codex_resets", json_body=True)
        if value is None:
            self._health("codex_resets", True, now)
            return
        data = value.get("data") if isinstance(value.get("data"), dict) else {}
        latest = data.get("latest_reset") if isinstance(data.get("latest_reset"), dict) else {}
        reset_id = str(latest.get("id") or "")
        if reset_id:
            if self._codex_last_reset_id and reset_id != self._codex_last_reset_id:
                published = _published_timestamp(latest.get("announced_at"))
                if self._fresh(published, now):
                    source = latest.get("source") if isinstance(latest.get("source"), dict) else {}
                    self._upsert_event(
                        self._event(
                            event_id="codex-reset:" + reset_id,
                            origin_id=reset_id,
                            kind="codex_reset",
                            severity="scream",
                            title="Codex 额度已重置",
                            summary=str(latest.get("text") or "额度重置公告已经确认"),
                            reason="检测到新的确认重置公告",
                            source="Codex Resets / @%s" % str(source.get("author") or "thsottiaux"),
                            url=source.get("url"),
                            published_at=published,
                            received_at=now,
                            score=100,
                        )
                    )
            self._codex_last_reset_id = reset_id

        watch = data.get("active_watch") if isinstance(data.get("active_watch"), dict) else {}
        observed = str(watch.get("observed_at") or "")
        watch_id = "%s:%s" % (str(watch.get("level") or ""), observed)
        if self._codex_watch_id and watch_id != self._codex_watch_id:
            for event in self._events:
                if (
                    event.get("kind") == "codex_reset_watch"
                    and event.get("origin_id") == self._codex_watch_id
                ):
                    event["status"] = "withdrawn"
        expires = _published_timestamp(watch.get("expires_at"))
        if watch_id != ":" and watch_id != self._codex_watch_id and (not expires or expires > now):
            level = str(watch.get("level") or "")
            source = watch.get("source") if isinstance(watch.get("source"), dict) else {}
            self._upsert_event(
                self._event(
                    event_id="codex-watch:" + hashlib.sha256(watch_id.encode()).hexdigest()[:16],
                    origin_id=watch_id,
                    kind="codex_reset_watch",
                    severity="alert" if level == "strong" else "inbox",
                    title="Codex 额度重置%s" % ("强预警" if level == "strong" else "观察"),
                    summary=str(watch.get("text") or "这是一项预测，不是确认公告"),
                    reason="Codex Resets AI 预测，不代表 OpenAI 已确认",
                    source="Codex Resets / @%s" % str(source.get("author") or "thsottiaux"),
                    url=source.get("url"),
                    published_at=_published_timestamp(observed),
                    received_at=now,
                    score=55 if level == "strong" else 25,
                )
            )
            self._codex_watch_id = watch_id
        self._health("codex_resets", True, now)

    def _bootstrap_aihot(self, now: int, config: Dict[str, Any]) -> None:
        snapshot_url = _canonical_url(
            config.get("snapshot_url") or "https://aihot.virxact.com/api/v1/selected/snapshot"
        )
        fields = str(config.get("fields") or "default")
        page = ""
        first_cursor = ""
        for index in range(20):
            query = {"fields": fields, "limit": 1000}
            if page:
                query["page"] = page
            value = self._fetch(snapshot_url + "?" + urlencode(query), "aihot_snapshot:%d" % index, json_body=True)
            if value is None:
                raise RemoteFetchError("AIHOT snapshot unexpectedly returned not modified")
            cursor = str(value.get("cursor") or "")
            if not first_cursor:
                first_cursor = cursor
            if not value.get("hasMore"):
                self._aihot_cursor = first_cursor
                self._health("aihot", True, now)
                return
            page = str(value.get("nextPage") or "")
            if not page:
                raise RemoteFetchError("AIHOT snapshot is missing nextPage")
        raise RemoteFetchError("AIHOT snapshot exceeded safe page limit")

    def _poll_aihot_hot_topics(self, now: int, config: Dict[str, Any]) -> None:
        hot_url = _canonical_url(
            config.get("hot_topics_url") or "https://aihot.virxact.com/api/v1/hot-topics"
        )
        value = self._fetch(hot_url, "aihot_hot_topics", json_body=True)
        if value is None:
            return
        topics = value.get("items") if isinstance(value.get("items"), list) else []
        self._hot_topics = {
            str(item.get("id")): copy.deepcopy(item)
            for item in topics
            if isinstance(item, dict) and item.get("id")
        }

    def _aihot_event(self, item: Dict[str, Any], now: int) -> Dict[str, Any]:
        item_id = str(item.get("id") or "")
        source = item.get("source") if isinstance(item.get("source"), dict) else {}
        links = item.get("links") if isinstance(item.get("links"), dict) else {}
        original_url = _canonical_url(links.get("original"))
        aihot_url = _canonical_url(links.get("aihot"))
        domains = _merged_terms(
            _terms(self.config, "official_domains", DEFAULT_OFFICIAL_DOMAINS),
            REQUIRED_PROVIDER_DOMAINS,
        )
        official_prefixes = _merged_terms(
            _terms(self.config, "official_url_prefixes", DEFAULT_OFFICIAL_URL_PREFIXES),
            DEFAULT_OFFICIAL_URL_PREFIXES,
        )
        hot = self._hot_topics.get(item_id) or {}
        raw = {
            "title": str(item.get("title") or ""),
            "summary": str(item.get("summary") or ""),
            "original_title": str(item.get("originalTitle") or ""),
            "source": str(source.get("name") or "AIHOT"),
            "official": (
                _host_is_official(original_url, domains)
                or _url_has_official_prefix(original_url, official_prefixes)
            ),
            "source_count": int(hot.get("sourceCount") or 0),
            "aggregator_score": item.get("score") or 0,
        }
        severity, score, reason = classify_ai_event(raw, self.config)
        return self._event(
            event_id="aihot:" + item_id,
            origin_id=item_id,
            kind="ai_news",
            severity=severity,
            title=raw["title"],
            summary=raw["summary"],
            reason=reason,
            source=raw["source"] + " · AIHOT",
            url=original_url or aihot_url,
            published_at=_published_timestamp(item.get("publishedAt") or item.get("discoveredAt")),
            received_at=now,
            score=score,
            official=raw["official"],
        )

    def _poll_aihot(self, now: int) -> None:
        config = self._aihot_config()
        if not config.get("enabled", False):
            return
        try:
            self._poll_aihot_hot_topics(now, config)
            self._health("aihot_hot_topics", True, now)
        except (OSError, ValueError) as exc:
            self._health("aihot_hot_topics", False, now, str(exc))
        if not self._aihot_cursor:
            self._bootstrap_aihot(now, config)
            return
        changes_url = _canonical_url(
            config.get("changes_url") or "https://aihot.virxact.com/api/v1/selected/changes"
        )
        for _index in range(20):
            query = urlencode({"cursor": self._aihot_cursor, "limit": 100})
            try:
                value = self._fetch(changes_url + "?" + query, "aihot_changes", json_body=True)
            except RemoteFetchError as exc:
                if exc.status == 409 and exc.code == "snapshot_required":
                    self._aihot_cursor = ""
                    self._bootstrap_aihot(now, config)
                    return
                raise
            if value is None:
                self._health("aihot", True, now)
                return
            changes = value.get("changes") if isinstance(value.get("changes"), list) else []
            for change in changes:
                if not isinstance(change, dict):
                    continue
                if change.get("op") == "remove":
                    self._withdraw_aihot(str(change.get("id") or ""))
                    continue
                item = change.get("item") if isinstance(change.get("item"), dict) else {}
                event = self._aihot_event(item, now)
                if event.get("title") and self._fresh(int(event.get("published_at") or 0), now):
                    self._upsert_event(event)
            cursor = str(value.get("cursor") or "")
            if not cursor:
                raise RemoteFetchError("AIHOT changes response is missing cursor")
            self._aihot_cursor = cursor
            if not value.get("hasMore"):
                self._health("aihot", True, now)
                return
        raise RemoteFetchError("AIHOT changes exceeded safe page limit")

    def _poll_official(self, now: int) -> None:
        for source in self._official_sources():
            source_key = "official:" + source["url"]
            if now < self._next_due.get(source_key, 0):
                continue
            try:
                payload = self._fetch(source["url"], source_key, json_body=False)
            except (OSError, ValueError, ET.ParseError) as exc:
                failures = min(6, self._failure_counts.get(source_key, 0) + 1)
                self._failure_counts[source_key] = failures
                backoff = min(3600, 60 * (2 ** (failures - 1)))
                retry_after = exc.retry_after if isinstance(exc, RemoteFetchError) else 0
                self._next_due[source_key] = now + max(backoff, retry_after)
                self._health(source["name"], False, now, str(exc))
                continue
            if payload is None:
                self._failure_counts[source_key] = 0
                self._health(source["name"], True, now)
                continue
            try:
                entries = parse_feed(payload, source["name"])
            except ET.ParseError as exc:
                failures = min(6, self._failure_counts.get(source_key, 0) + 1)
                self._failure_counts[source_key] = failures
                self._next_due[source_key] = now + min(3600, 60 * (2 ** (failures - 1)))
                self._health(source["name"], False, now, str(exc))
                continue
            self._failure_counts[source_key] = 0
            known = set(self._rss_seen)
            unseen = [entry for entry in entries if entry["id"] not in known]
            self._rss_seen.extend(entry["id"] for entry in unseen)
            self._rss_seen = list(dict.fromkeys(self._rss_seen))[-1000:]
            if source_key not in self._official_baselines:
                self._official_baselines.add(source_key)
                self._health(source["name"], True, now)
                continue
            for entry in unseen:
                raw = {
                    "title": entry["title"],
                    "summary": "",
                    "source": source["name"],
                    "official": True,
                    "source_count": 1,
                    "aggregator_score": 0,
                }
                severity, score, reason = classify_ai_event(raw, self.config)
                if not self._fresh(int(entry.get("published_at") or 0), now):
                    continue
                self._upsert_event(
                    self._event(
                        event_id="official:" + entry["id"],
                        origin_id=entry["id"],
                        kind="ai_news",
                        severity=severity,
                        title=entry["title"],
                        reason=reason,
                        source=source["name"],
                        url=entry["url"],
                        published_at=entry["published_at"],
                        received_at=now,
                        score=score,
                        official=True,
                    )
                )
            self._health(source["name"], True, now)

    def _due(self, key: str, now: int, refresh: int, force: bool) -> bool:
        if force or now >= self._next_due.get(key, 0):
            self._next_due[key] = now + max(15, refresh)
            return True
        return False

    def _run_source(self, key: str, now: int, refresh: int, force: bool, callback: Callable[[], None]) -> None:
        if not self._due(key, now, refresh, force):
            return
        try:
            callback()
            self._failure_counts[key] = 0
        except (OSError, ValueError, ET.ParseError, http.client.HTTPException) as exc:
            failures = min(6, self._failure_counts.get(key, 0) + 1)
            self._failure_counts[key] = failures
            retry_after = exc.retry_after if isinstance(exc, RemoteFetchError) else 0
            backoff = min(3600, max(15, refresh) * (2 ** (failures - 1)))
            self._next_due[key] = max(
                self._next_due.get(key, 0), now + max(backoff, retry_after)
            )
            self._health(key, False, now, str(exc))

    def poll_once(self, *, force: bool = True, now: Optional[int] = None) -> Dict[str, Any]:
        current = int(time.time()) if now is None else int(now)
        codex_config = self._codex_config()
        aihot_config = self._aihot_config()
        self._run_source(
            "codex_resets",
            current,
            int(codex_config.get("refresh_seconds", 60)),
            force,
            lambda: self._poll_codex_resets(current),
        )
        self._run_source(
            "aihot",
            current,
            int(aihot_config.get("refresh_seconds", 300)),
            force,
            lambda: self._poll_aihot(current),
        )
        self._run_source(
            "official_feeds",
            current,
            int(self.config.get("official_refresh_seconds", 300)),
            force,
            lambda: self._poll_official(current),
        )
        self._refresh_public_state(current)
        self._save()
        return self._publish()

    def acknowledge(self) -> Dict[str, Any]:
        with self._lock:
            current_id = str((self._state.get("alert") or {}).get("event_id") or "")
            for event in self._events:
                if event.get("event_id") == current_id:
                    event["status"] = "acknowledged"
                    break
        now = int(time.time())
        self._refresh_public_state(now)
        self._save()
        return self._publish()

    def open_current(self) -> Dict[str, Any]:
        with self._lock:
            url = str((self._state.get("alert") or {}).get("url") or "")
        if not url:
            raise ValueError("no AI hotspot URL is available")
        self._launcher(url)
        return self.acknowledge()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        poll_tick = max(15, min(60, int(self.config.get("refresh_seconds", 30))))
        self._publish()
        while not self._stop_event.is_set():
            self.poll_once(force=False)
            self._stop_event.wait(poll_tick)

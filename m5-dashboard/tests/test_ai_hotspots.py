from __future__ import annotations

import datetime as dt
import http.client
import json
import tempfile
import unittest
import urllib.error
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bridge.ai_hotspots import (
    AIHotspotMonitor,
    _url_has_official_prefix,
    classify_ai_event,
    headline_matches,
    parse_feed,
)


def feed(*titles: str) -> bytes:
    items = "".join(
        "<item><title>%s</title><link>https://example.com/%d</link>"
        "<guid>%d</guid><pubDate>Fri, 21 Aug 2026 12:%02d:00 +0800</pubDate></item>"
        % (title, index, index, index)
        for index, title in enumerate(titles)
    )
    return ("<rss><channel>%s</channel></rss>" % items).encode("utf-8")


class Response(BytesIO):
    def __init__(self, payload=b"", headers=None):
        super().__init__(payload)
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def json_response(value, headers=None):
    return Response(json.dumps(value).encode("utf-8"), headers)


def now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat()


class AIHotspotTests(unittest.TestCase):
    def test_incomplete_rss_response_isolated_for_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = AIHotspotMonitor(
                {
                    "state_path": str(Path(directory) / "state.json"),
                    "codex_resets": {"enabled": False},
                    "aihot": {"enabled": False},
                    "official_sources": [],
                },
                lambda _value: None,
            )
            now = int(dt.datetime.now().timestamp())

            def incomplete():
                raise http.client.IncompleteRead(b"partial", 100)

            monitor._run_source("official_feeds", now, 300, True, incomplete)

            self.assertEqual(monitor._failure_counts["official_feeds"], 1)
            self.assertFalse(monitor._source_health["official_feeds"]["connected"])
            self.assertGreater(monitor._next_due["official_feeds"], now)

    def test_feed_parser_and_keyword_filter(self):
        entries = parse_feed(feed("GPT-6 正式发布"), "OpenAI")
        self.assertEqual(entries[0]["title"], "GPT-6 正式发布")
        self.assertEqual(entries[0]["source"], "OpenAI")
        self.assertTrue(headline_matches(entries[0]["title"], ["GPT"]))
        self.assertFalse(headline_matches("普通设计文章", ["GPT"]))

    def test_deterministic_classification_keeps_editorial_posts_out_of_scream(self):
        official_release = {
            "title": "Claude Code 正式上线新的 Agent 能力",
            "source": "Claude Blog",
            "official": True,
            "source_count": 2,
            "aggregator_score": 82,
        }
        severity, score, reason = classify_ai_event(official_release, {})
        self.assertEqual(severity, "scream")
        self.assertGreaterEqual(score, 75)
        self.assertIn("官方原文", reason)

        teaching = {
            "title": "Anthropic 发布 AI 教学与学习方法",
            "source": "Claude Blog",
            "official": True,
            "source_count": 3,
            "aggregator_score": 90,
        }
        severity, _score, reason = classify_ai_event(teaching, {})
        self.assertEqual(severity, "inbox")
        self.assertIn("降级词", reason)

        third_party = {
            "title": "Claude Code 正式发布重大升级",
            "source": "AI News",
            "official": False,
            "source_count": 4,
            "aggregator_score": 85,
        }
        severity, _score, _reason = classify_ai_event(third_party, {})
        self.assertEqual(severity, "alert")

    def test_deepseek_and_kimi_multimodal_releases_are_permanent_scream_rules(self):
        old_private_config = {
            "interest_terms": ["Codex", "Claude"],
            "event_terms": ["正式发布", "released"],
        }
        deepseek = {
            "title": "DeepSeek-V4-Flash-Vision-Exp is now available",
            "source": "DeepSeek",
            "official": True,
            "source_count": 1,
        }
        severity, score, reason = classify_ai_event(deepseek, old_private_config)
        self.assertEqual(severity, "scream")
        self.assertGreaterEqual(score, 75)
        self.assertIn("deepseek", reason.casefold())
        self.assertIn("vision-exp", reason.casefold())

        kimi = {
            "title": "Kimi 新一代多模态模型正式上线",
            "source": "Moonshot AI",
            "official": True,
            "source_count": 1,
        }
        severity, score, reason = classify_ai_event(kimi, old_private_config)
        self.assertEqual(severity, "scream")
        self.assertGreaterEqual(score, 75)
        self.assertIn("kimi", reason.casefold())
        self.assertIn("多模态", reason)

    def test_only_exact_official_social_and_model_org_paths_are_trusted(self):
        prefixes = [
            "https://x.com/deepseek_ai/",
            "https://github.com/moonshotai/",
        ]
        self.assertTrue(
            _url_has_official_prefix("https://x.com/deepseek_ai/status/123?ref=home", prefixes)
        )
        self.assertTrue(
            _url_has_official_prefix("https://github.com/moonshotai/Kimi-K2", prefixes)
        )
        self.assertFalse(
            _url_has_official_prefix("https://x.com/random_user/status/123", prefixes)
        )
        self.assertFalse(
            _url_has_official_prefix("https://github.com/moonshotai-fake/model", prefixes)
        )

    def test_first_poll_baselines_then_new_match_alerts_and_acknowledges(self):
        with tempfile.TemporaryDirectory() as directory:
            payloads = [feed("旧闻"), feed("旧闻", "GPT-6 正式发布")]
            published = []
            opened = []

            def opener(_request, timeout):
                self.assertEqual(timeout, 2.0)
                return Response(payloads.pop(0))

            monitor = AIHotspotMonitor(
                {
                    "state_path": str(Path(directory) / "state.json"),
                    "timeout_seconds": 2,
                    "max_age_hours": 72,
                    "keywords": ["GPT"],
                    "sources": [{"name": "OpenAI", "url": "https://example.com/rss"}],
                },
                published.append,
                opener=opener,
                launcher=opened.append,
            )
            self.assertFalse(monitor.poll_once()["active"])
            alert = monitor.poll_once()
            self.assertTrue(alert["active"])
            self.assertEqual(alert["alert"]["title"], "GPT-6 正式发布")
            monitor.open_current()
            self.assertEqual(opened, ["https://example.com/1"])
            self.assertFalse(monitor.snapshot()["active"])
            self.assertTrue(published)

    def test_confirmed_codex_reset_baselines_then_always_screams(self):
        with tempfile.TemporaryDirectory() as directory:
            reset_ids = ["100", "101"]
            requests = []

            def opener(request, timeout):
                self.assertEqual(timeout, 2.0)
                requests.append(request)
                reset_id = reset_ids.pop(0)
                return json_response(
                    {
                        "data": {
                            "latest_reset": {
                                "id": reset_id,
                                "announced_at": now_iso(),
                                "text": "Codex usage limits have been reset.",
                                "source": {
                                    "type": "x_post",
                                    "author": "thsottiaux",
                                    "url": "https://x.com/thsottiaux/status/" + reset_id,
                                },
                            },
                            "active_watch": None,
                            "stats": {},
                        },
                        "meta": {"api_version": "v1", "generated_at": now_iso()},
                    },
                    {"ETag": '"reset-%s"' % reset_id},
                )

            monitor = AIHotspotMonitor(
                {
                    "state_path": str(Path(directory) / "state.json"),
                    "timeout_seconds": 2,
                    "codex_resets": {
                        "enabled": True,
                        "status_url": "https://codex-resets.test/api/v1/status",
                    },
                    "aihot": {"enabled": False},
                    "official_sources": [],
                },
                lambda _value: None,
                opener=opener,
            )
            self.assertFalse(monitor.poll_once()["active"])
            state = monitor.poll_once()
            self.assertTrue(state["active"])
            self.assertEqual(state["alert"]["severity"], "scream")
            self.assertEqual(state["alert"]["kind"], "codex_reset")
            self.assertEqual(state["alert"]["title"], "Codex 额度已重置")
            self.assertEqual(requests[1].get_header("If-none-match"), '"reset-100"')

    def test_codex_strong_watch_is_only_an_alert_and_is_withdrawn_when_cleared(self):
        with tempfile.TemporaryDirectory() as directory:
            watches = [
                {
                    "level": "strong",
                    "reset_chance_percent": 80,
                    "forecast_window": "next 24h",
                    "observed_at": now_iso(),
                    "expires_at": (
                        dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)
                    ).isoformat(),
                    "text": "A reset may happen soon.",
                    "source": {
                        "type": "x_post",
                        "author": "thsottiaux",
                        "url": "https://x.com/thsottiaux/status/watch",
                    },
                },
                None,
            ]

            def opener(_request, timeout):
                self.assertEqual(timeout, 2.0)
                return json_response(
                    {
                        "data": {
                            "latest_reset": {
                                "id": "100",
                                "announced_at": now_iso(),
                                "text": "Previous confirmed reset.",
                                "source": {
                                    "type": "x_post",
                                    "author": "thsottiaux",
                                    "url": "https://x.com/thsottiaux/status/100",
                                },
                            },
                            "active_watch": watches.pop(0),
                            "stats": {},
                        },
                        "meta": {"api_version": "v1", "generated_at": now_iso()},
                    }
                )

            monitor = AIHotspotMonitor(
                {
                    "state_path": str(Path(directory) / "state.json"),
                    "timeout_seconds": 2,
                    "codex_resets": {"enabled": True},
                    "aihot": {"enabled": False},
                    "official_sources": [],
                },
                lambda _value: None,
                opener=opener,
            )
            state = monitor.poll_once()
            self.assertFalse(state["active"])
            self.assertEqual(state["counts"]["alert"], 1)
            state = monitor.poll_once()
            self.assertFalse(state["active"])
            self.assertEqual(state["counts"]["alert"], 0)

    def test_aihot_snapshot_changes_and_remove_follow_the_public_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            changes_call = 0

            def opener(request, timeout):
                nonlocal changes_call
                self.assertEqual(timeout, 2.0)
                parsed = urlparse(request.full_url)
                if parsed.path.endswith("/hot-topics"):
                    return json_response(
                        {
                            "schemaVersion": 1,
                            "count": 1,
                            "items": [{"id": "news-1", "sourceCount": 3}],
                        }
                    )
                if parsed.path.endswith("/selected/snapshot"):
                    query = parse_qs(parsed.query)
                    self.assertEqual(query["fields"], ["default"])
                    return json_response(
                        {
                            "schemaVersion": 1,
                            "asOf": now_iso(),
                            "fields": "default",
                            "cursor": "cursor-1",
                            "count": 1,
                            "hasMore": False,
                            "nextPage": None,
                            "items": [{"id": "old"}],
                        }
                    )
                if parsed.path.endswith("/selected/changes"):
                    changes_call += 1
                    query = parse_qs(parsed.query)
                    self.assertEqual(query["cursor"], ["cursor-%d" % changes_call])
                    if changes_call == 1:
                        changes = [
                            {
                                "op": "upsert",
                                "changedAt": now_iso(),
                                "item": {
                                    "id": "news-1",
                                    "title": "Claude Code 正式上线新的 Agent 能力",
                                    "originalTitle": "Claude Code launches new agent capability",
                                    "summary": "Claude Code 获得重大升级。",
                                    "source": {"name": "Claude Blog"},
                                    "links": {
                                        "aihot": "https://aihot.virxact.com/items/news-1",
                                        "original": "https://claude.com/blog/news-1",
                                    },
                                    "publishedAt": now_iso(),
                                    "discoveredAt": now_iso(),
                                    "category": "ai-products",
                                    "score": 82,
                                    "selected": True,
                                },
                            }
                        ]
                    else:
                        changes = [{"op": "remove", "changedAt": now_iso(), "id": "news-1"}]
                    return json_response(
                        {
                            "schemaVersion": 1,
                            "fields": "default",
                            "cursor": "cursor-%d" % (changes_call + 1),
                            "count": 1,
                            "hasMore": False,
                            "changes": changes,
                        }
                    )
                self.fail("unexpected URL: %s" % request.full_url)

            monitor = AIHotspotMonitor(
                {
                    "state_path": str(Path(directory) / "state.json"),
                    "timeout_seconds": 2,
                    "codex_resets": {"enabled": False},
                    "aihot": {
                        "enabled": True,
                        "snapshot_url": "https://aihot.test/api/v1/selected/snapshot",
                        "changes_url": "https://aihot.test/api/v1/selected/changes",
                        "hot_topics_url": "https://aihot.test/api/v1/hot-topics",
                        "fields": "default",
                    },
                    "official_sources": [],
                },
                lambda _value: None,
                opener=opener,
            )
            self.assertFalse(monitor.poll_once()["active"])
            state = monitor.poll_once()
            self.assertTrue(state["active"])
            self.assertEqual(state["alert"]["event_id"], "aihot:news-1")
            self.assertEqual(state["alert"]["severity"], "scream")
            self.assertTrue(state["alert"]["official"])
            state = monitor.poll_once()
            self.assertFalse(state["active"])
            self.assertEqual(state["counts"]["scream"], 0)

    def test_aihot_alert_is_queued_without_triggering_legacy_device_scream(self):
        with tempfile.TemporaryDirectory() as directory:
            monitor = AIHotspotMonitor(
                {
                    "state_path": str(Path(directory) / "state.json"),
                    "codex_resets": {"enabled": False},
                    "aihot": {"enabled": False},
                    "official_sources": [],
                },
                lambda _value: None,
            )
            event = monitor._event(
                event_id="test-alert",
                title="Claude Code 发现值得关注的新能力",
                severity="alert",
                source="AIHOT",
            )
            monitor._upsert_event(event)
            monitor._refresh_public_state(int(dt.datetime.now().timestamp()))
            state = monitor.snapshot()
            self.assertFalse(state["active"])
            self.assertEqual(state["counts"]["alert"], 1)
            self.assertEqual(state["events"][0]["event_id"], "test-alert")

    def test_aihot_snapshot_required_rebuilds_the_cursor_without_alerting(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot_calls = 0

            def opener(request, timeout):
                nonlocal snapshot_calls
                self.assertEqual(timeout, 2.0)
                parsed = urlparse(request.full_url)
                if parsed.path.endswith("/hot-topics"):
                    return json_response({"schemaVersion": 1, "count": 0, "items": []})
                if parsed.path.endswith("/selected/changes"):
                    problem = BytesIO(
                        json.dumps(
                            {
                                "type": "about:blank",
                                "title": "Snapshot required",
                                "status": 409,
                                "code": "snapshot_required",
                                "detail": "rebuild the selected snapshot",
                                "requestId": "test-request",
                            }
                        ).encode("utf-8")
                    )
                    raise urllib.error.HTTPError(
                        request.full_url,
                        409,
                        "Conflict",
                        {},
                        problem,
                    )
                if parsed.path.endswith("/selected/snapshot"):
                    snapshot_calls += 1
                    return json_response(
                        {
                            "schemaVersion": 1,
                            "asOf": now_iso(),
                            "fields": "default",
                            "cursor": "fresh-cursor",
                            "count": 0,
                            "hasMore": False,
                            "nextPage": None,
                            "items": [],
                        }
                    )
                self.fail("unexpected URL: %s" % request.full_url)

            monitor = AIHotspotMonitor(
                {
                    "state_path": str(Path(directory) / "state.json"),
                    "timeout_seconds": 2,
                    "codex_resets": {"enabled": False},
                    "aihot": {
                        "enabled": True,
                        "snapshot_url": "https://aihot.test/api/v1/selected/snapshot",
                        "changes_url": "https://aihot.test/api/v1/selected/changes",
                        "hot_topics_url": "https://aihot.test/api/v1/hot-topics",
                    },
                    "official_sources": [],
                },
                lambda _value: None,
                opener=opener,
            )
            monitor._aihot_cursor = "stale-cursor"
            state = monitor.poll_once()
            self.assertFalse(state["active"])
            self.assertEqual(monitor._aihot_cursor, "fresh-cursor")
            self.assertEqual(snapshot_calls, 1)
            self.assertTrue(state["source_health"]["aihot"]["connected"])


if __name__ == "__main__":
    unittest.main()

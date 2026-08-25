"""Core collection orchestration."""

from __future__ import annotations

import asyncio
import datetime as _dt
import hashlib
import re
from typing import Dict, List, Optional

from .config import PUBLISHERS, PublisherConfig, USER_AGENT
from .fetchers import (
    AbstractHttpClient,
    CloudflareBrowserClient,
    generate_mock_candidates,
    parse_list_html,
)
from .models import EditorialArchive, generate_id
from .storage import JsonStorage

ArticleHashRe = re.compile(r"\s+")


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _fmt(iso_str: Optional[str]) -> str:
    if not iso_str:
        return "-"
    try:
        return _dt.datetime.fromisoformat(iso_str).strftime("%m/%d %H:%M")
    except ValueError:
        return iso_str


class CollectResult:
    def __init__(self, publisher: str, fetched: int, added: int, error: str = ""):
        self.publisher = publisher
        self.fetched = fetched
        self.added = added
        self.error = error

    @property
    def ok(self) -> bool:
        return not self.error


class EditorialCollector:
    def __init__(
        self,
        storage: JsonStorage | None = None,
        http_client: AbstractHttpClient | None = None,
        browser_client: CloudflareBrowserClient | None = None,
        use_mock: bool = False,
    ):
        from .fetchers import RequestsHttpClient, resolve_clients

        self.storage = storage or JsonStorage()
        if http_client is None or (browser_client is None):
            default_http, default_browser = resolve_clients()
            self.http_client = http_client or default_http
            self.browser_client = browser_client or default_browser
        else:
            self.http_client = http_client
            self.browser_client = browser_client
        self.use_mock = use_mock
        self.archives: List[EditorialArchive] = self.storage.load()
        self.alerts: List[Dict] = []

    # ------------------------------------------------------------------
    # alerts
    # ------------------------------------------------------------------
    def add_alert(self, kind: str, title: str, body: str) -> None:
        self.alerts.append(
            {"type": kind, "title": title, "body": body, "time": _now_iso()}
        )

    # ------------------------------------------------------------------
    # collection
    # ------------------------------------------------------------------
    def _build_item(
        self, cfg: PublisherConfig, title: str, url: str, publish_date: str
    ) -> EditorialArchive:
        item_id = generate_id(url, title, publish_date)
        return EditorialArchive(
            id=item_id,
            title=title,
            publisher=cfg.key,
            publisher_name=cfg.name,
            url=url,
            publish_date=publish_date,
            collected_at=_now_iso(),
            keywords=[cfg.key, "editorial"],
        )

    async def collect(self, publisher_key: str) -> CollectResult:
        cfg = PUBLISHERS.get(publisher_key)
        if cfg is None:
            raise KeyError(f"unknown publisher: {publisher_key}")

        candidates: List[Dict[str, str]] = []
        error = ""
        try:
            if self.use_mock:
                candidates = generate_mock_candidates(publisher_key)
            elif cfg.method == "direct":
                html = await self.http_client.fetch_text(cfg.list_url)
                candidates = parse_list_html(html, cfg, cfg.list_url)
            else:
                if self.browser_client is None:
                    error = (
                        "Cloudflare Browser Rendering 未設定のため取得できません"
                        "（CF_ACCOUNT_ID / CF_API_TOKEN を設定してください）"
                    )
                else:
                    selector = cfg.browser_selectors.get("list_selector")
                    html = await self.browser_client.fetch_content(cfg.list_url)
                    candidates = parse_list_html(
                        html, cfg, cfg.list_url, link_selector_override=selector
                    )
        except Exception as exc:  # noqa: BLE001 - surfaced to UI/CLI as alert text
            error = f"{type(exc).__name__}: {exc}"

        added = 0
        if not error:
            existing_ids = {a.id for a in self.archives}
            for cand in candidates:
                item = self._build_item(cfg, **cand)
                if item.id in existing_ids:
                    continue
                existing_ids.add(item.id)
                self.archives.insert(0, item)
                added += 1
            self.storage.save(self.archives)

        result = CollectResult(publisher_key, len(candidates), added, error)
        if error:
            self.add_alert("danger", f"{cfg.name} 収集エラー", error)
        elif added > 0:
            self.add_alert(
                "success", f"{cfg.name} 収集", f"{added} 件の新規社説を追加（候補 {len(candidates)} 件）"
            )
        else:
            self.add_alert("warn", f"{cfg.name} 収集", "新規アイテムはありませんでした")
        return result

    async def batch_collect(self, publisher_keys: Optional[List[str]] = None) -> List[CollectResult]:
        keys = publisher_keys or list(PUBLISHERS.keys())
        results: List[CollectResult] = []
        for key in keys:
            results.append(await self.collect(key))
        return results

    # ------------------------------------------------------------------
    # revisit / change detection
    # ------------------------------------------------------------------
    @staticmethod
    def _page_fingerprint(html: str) -> str:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = ArticleHashRe.sub(" ", soup.get_text(" ", strip=True))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]

    async def revisit(self, item_id: str) -> Optional[EditorialArchive]:
        archive = next((a for a in self.archives if a.id == item_id), None)
        if archive is None:
            return None
        cfg = PUBLISHERS.get(archive.publisher)
        html = ""
        error = ""
        try:
            if self.use_mock:
                import random

                dice = random.random()
                archive.status = "deleted" if dice < 0.1 else ("changed" if dice < 0.3 else "active")
            else:
                if cfg and cfg.method == "browser" and self.browser_client is not None:
                    html = await self.browser_client.fetch_text(archive.url)
                else:
                    import requests

                    response = await asyncio.to_thread(
                        requests.get,
                        archive.url,
                        headers={"User-Agent": USER_AGENT},
                        timeout=20,
                    )
                    if response.status_code in (404, 410):
                        archive.status = "deleted"
                    else:
                        response.raise_for_status()
                        if not response.encoding or response.encoding.lower() == "iso-8859-1":
                            response.encoding = response.apparent_encoding or "utf-8"
                        html = response.text
                if html:
                    fingerprint = self._page_fingerprint(html)
                    if archive.content_hash is None:
                        archive.content_hash = fingerprint
                        archive.status = "active"
                    elif fingerprint != archive.content_hash:
                        archive.content_hash = fingerprint
                        archive.status = "changed"
                        archive.changed = True
                    else:
                        archive.status = "active"
                        archive.changed = False
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"

        archive.last_revisit_at = _now_iso()
        if error:
            self.add_alert("danger", "再訪問エラー", f"#{archive.id} {archive.title[:30]}… {error}")
        elif archive.status == "deleted":
            self.add_alert("danger", "削除検出", f"#{archive.id} が 404/削除されました")
        elif archive.status == "changed":
            self.add_alert("warn", "変更検出", f"#{archive.id} の内容に変更があります")
        self.storage.save(self.archives)
        return archive

    async def revisit_stale(self, older_than_hours: int = 24) -> int:
        threshold = (_dt.datetime.now() - _dt.timedelta(hours=older_than_hours)).isoformat()
        targets = [
            a
            for a in self.archives
            if a.status != "deleted"
            and ((a.last_revisit_at or "") < threshold)
        ]
        count = 0
        for archive in targets[:50]:
            await self.revisit(archive.id)
            count += 1
        return count

    # ------------------------------------------------------------------
    # stats / views
    # ------------------------------------------------------------------
    def stats(self) -> Dict:
        by_publisher: Dict[str, int] = {}
        for a in self.archives:
            by_publisher[a.publisher] = by_publisher.get(a.publisher, 0) + 1
        return {
            "total": len(self.archives),
            "active": sum(1 for a in self.archives if a.status == "active"),
            "changed": sum(1 for a in self.archives if a.status == "changed"),
            "deleted": sum(1 for a in self.archives if a.status == "deleted"),
            "by_publisher": by_publisher,
        }

    def rows(self, publisher: Optional[str] = None, limit: int = 50) -> List[EditorialArchive]:
        data = [a for a in self.archives if publisher is None or a.publisher == publisher]
        return data[:limit]

    def print_dashboard(self) -> None:
        s = self.stats()
        line = "=" * 62
        print(line)
        print(" 社説コレクター ダッシュボード")
        print(line)
        print(f" 総アーカイブ数 : {s['total']}（active {s['active']} / changed {s['changed']} / deleted {s['deleted']}）")
        print("-" * 62)
        print(" 新聞社別件数:")
        for key, cnt in sorted(s["by_publisher"].items(), key=lambda x: -x[1]):
            name = PUBLISHERS.get(key).name if key in PUBLISHERS else key
            print(f"   {name:<10} {cnt:>4} 件")
        print(line)

    def print_table(self, publisher: Optional[str] = None, limit: int = 20) -> None:
        print(f"\n{'ID':<18} {'Publisher':<8} {'Date':<11} {'Status':<9} Title")
        print("-" * 96)
        for r in self.rows(publisher=publisher, limit=limit):
            print(
                f"{r.id:<18} {r.publisher:<8} {r.publish_date:<11} {r.status:<9} {r.title[:48]}"
            )

    def reset(self) -> None:
        self.archives = []
        self.alerts = []
        self.storage.save(self.archives)

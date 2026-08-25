"""HTTP fetching and HTML parsing layer.

Three transport modes share one interface:

- ``RequestsHttpClient``      direct HTTP access (CPython, static pages)
- ``CloudflareBrowserClient`` Cloudflare Browser Rendering REST API (JS-rendered pages)
- ``PyodideHttpClient``       browser fetch via pyodide.http.pyfetch (needs CORS proxy)

All public fetch helpers are async so the same core runs on CPython,
marimo and Pyodide without changes.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import random
import re
import time
from typing import Dict, List, Optional, Protocol
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .config import (
    POLITE_DELAY_SECONDS,
    PUBLISHERS,
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
    PublisherConfig,
    compile_href_pattern,
)


# ---------------------------------------------------------------------------
# transport clients
# ---------------------------------------------------------------------------
class AbstractHttpClient(Protocol):
    async def fetch_text(self, url: str) -> str: ...


class PoliteClock:
    """Serialises requests with a randomized minimum interval."""

    def __init__(self, delay_range=POLITE_DELAY_SECONDS):
        self.delay_range = delay_range
        self._last: float = 0.0

    async def wait(self) -> None:
        min_delay, max_delay = self.delay_range
        interval = random.uniform(min_delay, max_delay)
        elapsed = time.monotonic() - self._last
        if elapsed < interval:
            await asyncio.sleep(interval - elapsed)
        self._last = time.monotonic()


class RequestsHttpClient:
    def __init__(self, timeout: float = REQUEST_TIMEOUT_SECONDS):
        self.timeout = timeout
        self.clock = PoliteClock()

    async def fetch_text(self, url: str) -> str:
        import requests

        await self.clock.wait()
        response = await asyncio.to_thread(
            requests.get,
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=self.timeout,
        )
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding or "utf-8"
        return response.text


class CloudflareBrowserClient:
    """Cloudflare Browser Rendering REST API wrapper.

    Endpoints used:
      POST {base}/content   -> rendered HTML of the target page
      POST {base}/scrape    -> CSS-selector extraction results

    waitUntil accepts Puppeteer-style values ("load", "domcontentloaded",
    "networkidle0"); the Playwright-style "networkidle" is rejected (7001).
    """

    DEFAULT_WAIT_UNTIL = "domcontentloaded"
    FALLBACK_WAIT_UNTIL = "load"

    def __init__(
        self,
        account_id: str,
        api_token: str,
        timeout: float = 90.0,
        delay_range=(2.5, 4.0),
    ):
        self.base_url = (
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}/browser-rendering"
        )
        self.api_token = api_token
        self.timeout = timeout
        self.clock = PoliteClock(delay_range)

    @property
    def is_configured(self) -> bool:
        return bool(self.api_token)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    async def _post(self, endpoint: str, payload: dict) -> dict:
        import requests

        await self.clock.wait()
        response = await asyncio.to_thread(
            requests.post,
            endpoint,
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
        )
        try:
            return response.json()
        except ValueError:
            response.raise_for_status()
            return {"success": False, "errors": [{"message": "non-JSON response"}]}

    @staticmethod
    def _error_code(data: dict):
        errors = data.get("errors") or []
        return errors[0].get("code") if errors else None

    async def fetch_content(self, url: str, wait_until: Optional[str] = None) -> str:
        plan = (
            [wait_until]
            if wait_until
            else [self.DEFAULT_WAIT_UNTIL, self.FALLBACK_WAIT_UNTIL]
        )
        last_errors: str = "unknown error"
        for attempt in plan:
            data = await self._post(
                f"{self.base_url}/content",
                {"url": url, "gotoOptions": {"waitUntil": attempt}},
            )
            result = data.get("result")
            if isinstance(result, str) and result.strip():
                return result
            last_errors = str(data.get("errors"))
            if self._error_code(data) == 2001:
                break
        raise RuntimeError(f"browser-rendering /content failed: {last_errors}")

    async def scrape(self, url: str, selectors: List[str]) -> List[dict]:
        data = await self._post(
            f"{self.base_url}/scrape",
            {
                "url": url,
                "elements": [{"selector": s} for s in selectors],
                "gotoOptions": {"waitUntil": self.DEFAULT_WAIT_UNTIL},
            },
        )
        result = data.get("result")
        if isinstance(result, list):
            return result
        raise RuntimeError(f"browser-rendering /scrape failed: {data.get('errors')}")

    async def fetch_text(self, url: str) -> str:
        return await self.fetch_content(url)


class PyodideHttpClient:
    """Fetch through the browser runtime. Cross-origin targets must allow CORS,
    therefore a Worker proxy URL is prepended when provided."""

    def __init__(self, proxy_base: str = ""):
        self.proxy_base = proxy_base.rstrip("/") if proxy_base else ""

    async def fetch_text(self, url: str) -> str:
        from pyodide.http import pyfetch

        target = f"{self.proxy_base}/{url}" if self.proxy_base else url
        response = await pyfetch(target, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        return await response.string()


def resolve_clients(
    cf_account_id: str = "",
    cf_api_token: str = "",
) -> tuple[RequestsHttpClient, Optional[CloudflareBrowserClient]]:
    http_client = RequestsHttpClient()
    browser_client: Optional[CloudflareBrowserClient] = None
    if cf_account_id and cf_api_token:
        browser_client = CloudflareBrowserClient(cf_account_id, cf_api_token)
    return http_client, browser_client


# ---------------------------------------------------------------------------
# date extraction helpers
# ---------------------------------------------------------------------------
_URL_DATE_RE = re.compile(r"/(\d{4})(\d{2})(\d{2})[-_/]")
_ISO_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_JP_DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
_SLASH_DATE_RE = re.compile(r"(20\d{2})/(\d{1,2})/(\d{1,2})")

_WS_KEEPING_FULLWIDTH_RE = re.compile(r"[^\S\u3000]+")


def normalize_ws(text: str) -> str:
    """Collapse ASCII whitespace but preserve ideographic spaces (U+3000),
    which often separate title components inside Japanese headlines."""
    return _WS_KEEPING_FULLWIDTH_RE.sub(" ", text).strip()


def _is_recent_publish_date(date_str: str) -> bool:
    try:
        parsed = _dt.date.fromisoformat(date_str)
    except ValueError:
        return False
    age = (_dt.date.today() - parsed).days
    return 0 <= age <= MAX_PUBLISH_DATE_AGE_DAYS


def extract_publish_date(url: str, context_text: str = "") -> Optional[str]:
    match = _URL_DATE_RE.search(url)
    if match:
        y, m, d = match.groups()
        try:
            return _dt.date(int(y), int(m), int(d)).isoformat()
        except ValueError:
            pass
    for source in (context_text[:300], url):
        match = _ISO_DATE_RE.search(source)
        if match:
            return match.group(0)
    match = _JP_DATE_RE.search(context_text)
    if match:
        y, m, d = match.groups()
        try:
            return _dt.date(int(y), int(m), int(d)).isoformat()
        except ValueError:
            pass
    match = _SLASH_DATE_RE.search(context_text)
    if match:
        y, m, d = match.groups()
        try:
            return _dt.date(int(y), int(m), int(d)).isoformat()
        except ValueError:
            pass
    return None


# ---------------------------------------------------------------------------
# list page parsing (shared by direct HTTP and rendered HTML paths)
# ---------------------------------------------------------------------------
_PARENT_TAGS = ("article", "li", "section", "div")

MAX_ITEMS_PER_SOURCE = 30

MAX_PUBLISH_DATE_AGE_DAYS = 45


def _anchor_title_text(anchor) -> str:
    for tag in anchor.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        text = normalize_ws(tag.get_text(" ", strip=True))
        if text:
            return text
    for element in anchor.find_all(True, class_=True):
        classes = " ".join(element.get("class") or []).lower()
        if "title" in classes:
            text = normalize_ws(element.get_text(" ", strip=True))
            if text:
                return text
    return ""


def _anchor_context(anchor) -> str:
    texts = [_anchor_title_text(anchor), normalize_ws(anchor.get_text(" ", strip=True))]
    parent = anchor.find_parent(_PARENT_TAGS)
    if parent is not None:
        texts.append(normalize_ws(parent.get_text(" ", strip=True))[:400])
    return " ".join(part for part in texts if part)


def parse_list_html(
    html: str,
    cfg: PublisherConfig,
    fetched_url: str,
    link_selector_override: Optional[str] = None,
) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    selector = link_selector_override or cfg.link_selector
    anchors = soup.select(selector) if selector else soup.find_all("a", href=True)

    href_re = compile_href_pattern(cfg.href_pattern)
    seen: set[str] = set()
    items: List[Dict[str, str]] = []

    for anchor in anchors:
        href = anchor.get("href")
        if not href:
            continue
        absolute = urljoin(fetched_url, href)
        if href_re and not href_re.search(absolute):
            continue
        title = _anchor_title_text(anchor)
        if not title:
            title = normalize_ws(anchor.get_text(" ", strip=True))
        if cfg.title_cleanup == "ascii_space" and " " in title:
            title = title.split(" ", 1)[0]
        title = re.sub(r"\s*20\d{2}年\d{1,2}月\d{1,2}日\s*$", "", title)
        context = _anchor_context(anchor)
        if cfg.title_keywords:
            if not any(keyword in context for keyword in cfg.title_keywords):
                continue
        if not title and not href_re:
            continue
        if not title:
            tail = absolute.rstrip("/").split("/")[-1]
            title = re.sub(r"^[A-Z0-9]{8,}-?", "", tail) or tail
        key = absolute.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        publish_date = extract_publish_date(absolute, context)
        if not publish_date:
            parent = anchor.find_parent(_PARENT_TAGS)
            if parent is not None:
                publish_date = extract_publish_date(
                    absolute, normalize_ws(parent.get_text(" ", strip=True))
                )
        if not publish_date or not _is_recent_publish_date(publish_date):
            publish_date = _dt.date.today().isoformat()
        items.append(
            {
                "title": title,
                "url": absolute,
                "publish_date": publish_date,
            }
        )
        if len(items) >= MAX_ITEMS_PER_SOURCE:
            break
    return items


# ---------------------------------------------------------------------------
# mock data generator (demo mode, all publishers)
# ---------------------------------------------------------------------------
MOCK_TITLES: Dict[str, List[str]] = {
    "asahi": [
        "（社説）SNSと子ども 事業者任せにせずに",
        "（社説）首都直下地震 死者半減 目指すために",
        "（社説）国旗損壊罪 不要な立法 自由を侵す",
        "（社説）デジタル教科書 課題は多い 準備入念に",
        "（社説）米イラン覚書 粘り強く最終合意を",
    ],
    "mainichi": [
        "社説：海図なき世界 戦略の再構築を図らねば",
        "社説：世界の惨禍と終戦の日 歴史顧みぬ愚にあらがう",
        "社説：中国の対日圧力強化 不毛な対立終わらせねば",
        "社説：米国の分断と中間選挙 民主主義を守り抜かねば",
        "社説：軍拡時代と経済 いびつな連動を解きほぐせ",
    ],
    "yomiuri": [
        "憲法審査会 緊急事態条項は議論進んだが",
        "SNS是正勧告 誹謗中傷への対応策を怠るな",
        "千葉の豪雨被害 線状降水帯の脅威まざまざ",
        "終戦の日 平和の維持へ努力を重ねたい",
        "戦後80年 大国の「横暴」どう抑え込むか",
    ],
    "nikkei": [
        "［社説］企業は統治指針を自ら生かして成長を",
        "［社説］成田空港の土地収用はやむをえぬ",
        "［社説］拙速と対案不足で熟議逸した国会",
        "［社説］不当な関税いつまで続けるのか",
        "［社説］紅海の封鎖を憂う原油100ドル",
    ],
    "sankei": [
        "＜主張＞万博工事の不正 徹底究明でレガシー守れ",
        "＜主張＞ICC制裁 撤回し対話の道を",
        "＜主張＞特殊詐欺が悪化 偽広告「事前排除」の策を",
        "＜主張＞クロマグロ増枠 成果を確かな資源管理へ",
        "＜主張＞露朝の軍事協力 日本にも直結する脅威だ",
    ],
    "hokkaido": [
        "＜社説＞新学期の子ども 安心できる環境整えて",
        "＜社説＞残業時間見直し 働く人の健康守れるか",
        "＜社説＞死刑執行 存廃含め根本的議論を",
        "＜社説＞食料自給率向上 消費者とつなげる施策を",
        "＜社説＞豪雨災害 水害への備え再点検を",
    ],
    "tokyo": [
        "〈社説〉ICC所長制裁 米政権に撤回を求めよ",
        "〈社説〉クロマグロ交渉 自制あっての漁獲枠増",
        "〈社説〉情報教育の拡大 現場の疲弊招かぬよう",
        "〈社説〉「共育て」の推進 柔軟な働き方広げたい",
        "〈社説〉防災計画 地域の実情に合わせ見直せ",
    ],
    "kumanichi": [
        "ICC所長制裁 日本は米に撤回求めねば",
        "米価下落 市場安定へ対応急ぎたい",
        "井戸の被害 官民連携で復旧を急いで",
        "「2次避難」低調 事情踏まえ柔軟に対応を",
        "防衛白書 専守と対話を尊重したい",
    ],
}


def generate_mock_candidates(pub_key: str, limit: int = 5) -> List[Dict[str, str]]:
    cfg = PUBLISHERS[pub_key]
    titles = MOCK_TITLES.get(pub_key, [])
    today = _dt.date.today()
    items: List[Dict[str, str]] = []
    for i, title in enumerate(titles[:limit]):
        url = f"{cfg.list_url}#mock-{pub_key}-{i}"
        items.append(
            {
                "title": title,
                "url": url,
                "publish_date": (today - _dt.timedelta(days=i)).isoformat(),
            }
        )
    return items

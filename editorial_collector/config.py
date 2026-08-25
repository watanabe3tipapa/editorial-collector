"""Publisher configuration for the editorial collector."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class PublisherConfig:
    key: str
    name: str
    list_url: str
    method: str = "direct"
    link_selector: Optional[str] = None
    href_pattern: Optional[str] = None
    title_keywords: tuple[str, ...] = ()
    title_cleanup: Optional[str] = None
    browser_selectors: dict = field(default_factory=dict)
    note: str = ""


PUBLISHERS: dict[str, PublisherConfig] = {
    "yomiuri": PublisherConfig(
        key="yomiuri",
        name="読売新聞",
        list_url="https://www.yomiuri.co.jp/editorial/",
        method="direct",
        href_pattern=r"https://www\.yomiuri\.co\.jp/editorial/\d{8}-[A-Z0-9]+/?$",
        note="一覧は静的HTML。h3.title 内のリンク、URLに日付を含む。",
    ),
    "sankei": PublisherConfig(
        key="sankei",
        name="産経新聞",
        list_url="https://www.sankei.com/column/editorial/",
        method="direct",
        href_pattern=r"https://www\.sankei\.com/article/\d{8}-",
        note="「主張」として公開。/article/YYYYMMDD- 形式のリンクを抽出。",
    ),
    "hokkaido": PublisherConfig(
        key="hokkaido",
        name="北海道新聞",
        list_url="https://www.hokkaido-np.co.jp/tags/editorial/",
        method="direct",
        href_pattern=r"https://www\.hokkaido-np\.co\.jp/article/\d+/?$",
        title_keywords=("＜社説",),
        note="月曜日は社説配信なし。URLに日付が無いため周辺テキストから日付抽出。",
    ),
    "tokyo": PublisherConfig(
        key="tokyo",
        name="東京新聞",
        list_url="https://www.tokyo-np.co.jp/n/column/editorial",
        method="direct",
        title_keywords=("社説",),
        note="静的HTMLで取得可（〈社説〉タイトル＋/article/N リンクを実測）。",
    ),
    "kumanichi": PublisherConfig(
        key="kumanichi",
        name="熊本日日新聞",
        list_url="https://www.kumanichi.com/opinion/syasetsu",
        method="browser",
        browser_selectors={
            "list_selector": "main a[href*='/articles/'], main a[href*='/news/'], article h3 a",
            "article_title_selector": "h1",
            "article_body_selector": ".article-body, main",
            "date_selector": "time",
        },
        note="一覧はJS描画（静的HTMLに記事リンクなし確認済み）。会員限定記事はメタ情報のみ保存。",
    ),
    "asahi": PublisherConfig(
        key="asahi",
        name="朝日新聞",
        list_url="https://www.asahi.com/rensai/list.html?id=16",
        method="browser",
        href_pattern=r"asahi\.com/articles/[A-Z0-9]+\.html",
        title_keywords=("（社説）",),
        title_cleanup="ascii_space",
        browser_selectors={
            "article_title_selector": "h1",
            "article_body_selector": ".article-text",
            "date_selector": "time",
        },
        note="一覧はJS描画・クラス名は難読化（ul.ZMseR等）のため href パターンで抽出。"
             "タイトルと概要の境界は半角スペース、タイトル内部は全角スペース。",
    ),
    "mainichi": PublisherConfig(
        key="mainichi",
        name="毎日新聞",
        list_url="https://mainichi.jp/editorial/",
        method="browser",
        href_pattern=r"mainichi\.jp/articles/\d{8}/",
        browser_selectors={
            "list_selector": ".articlelist a",
            "article_title_selector": "h1",
            "article_body_selector": ".article-body, .nx-body-text",
            "date_selector": "time",
        },
        note="一覧はJS描画。レンダリング後は ul.articlelist > li > a（タイトルは .articlelist-title）。"
             "waitUntil は domcontentloaded（networkidle0/load は30秒タイムアウト実測）。",
    ),
    "nikkei": PublisherConfig(
        key="nikkei",
        name="日本経済新聞",
        list_url="https://www.nikkei.com/opinion/editorial/",
        method="browser",
        href_pattern=r"nikkei\.com/article/[A-Z0-9]+/",
        title_keywords=("［社説］",),
        browser_selectors={
            "list_selector": "article a",
            "article_title_selector": "h1",
            "article_body_selector": ".article_body",
            "date_selector": "time",
        },
        note="一覧はJS描画。レンダリング後は article 内の h2 リンク（［社説］プレフィックス）。"
             "クラス名は難読化のため href パターンで抽出。",
    ),
}

TITLE_PREFIXES = ("（社説）", "社説：", "＜主張＞", "＜社説＞", "〈社説〉", "［社説］")

POLITE_DELAY_SECONDS = (1.0, 1.5)

REQUEST_TIMEOUT_SECONDS = 20

USER_AGENT = (
    "editorial-collector/0.1.0 "
    "(research project; low-frequency crawling; contact via github.com/watanabe3tipapa)"
)


def compile_href_pattern(pattern: Optional[str]) -> Optional[re.Pattern]:
    if not pattern:
        return None
    return re.compile(pattern)

"""Word cloud generation from editorial titles.

Pure Python implementation (no third-party dependencies) so that the same
code runs under CPython, marimo and Pyodide (Web-UI).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

_KANJI_RUN = re.compile(r"[々〆一-龯]+")
_KATAKANA_RUN = re.compile(r"[ァ-ヴー・]+")
_LATIN_RUN = re.compile(r"[A-Za-z0-9][A-Za-z0-9'-]*")

STOPWORDS = frozenset(
    {
        "こと",
        "もの",
        "ため",
        "よう",
        "とき",
        "ときは",
        "ところ",
        "なか",
        "これ",
        "それ",
        "また",
        "まだ",
        "もう",
        "など",
        "ある",
        "あるい",
        "する",
        "した",
        "しない",
        "なる",
        "ない",
        "あるまい",
        "社説",
        "主張",
        "論説",
        "コラム",
        "新聞",
        "新聞社",
        "産経抄",
        "正論",
        "浪速風",
        "編集部",
        "から欄",
        "毎日",
        "読売",
        "朝日",
        "日経",
        "産経",
        "東京",
        "北海道",
        "熊本",
        "日本",
        "わが国",
        "今年",
        "昨年",
        "去年",
        "来年",
        "今回",
        "今回の",
        "今月",
        "先月",
        "今日",
        "明日",
        "昨日",
    }
)

MIN_LEN = {"kanji": 2, "katakana": 3, "latin": 2}
MAX_TOKEN_LEN = 12


def _normalize(text: str) -> str:
    return text.replace("　", " ").strip()


def tokenize(text: str) -> List[str]:
    text = _normalize(text)
    tokens: List[str] = []
    for pattern, kind in (
        (_KANJI_RUN, "kanji"),
        (_KATAKANA_RUN, "katakana"),
        (_LATIN_RUN, "latin"),
    ):
        for match in pattern.findall(text):
            token = match.strip("・")
            if len(token) < MIN_LEN[kind] or len(token) > MAX_TOKEN_LEN:
                continue
            if token in STOPWORDS:
                continue
            if re.fullmatch(r"[0-9]+|[０-９]+|20\d{2}", token):
                continue
            tokens.append(token)
    return tokens


def _record_title(record: object) -> Tuple[str, str]:
    if isinstance(record, dict):
        return str(record.get("title", "")), str(record.get("publisher", ""))
    return getattr(record, "title", ""), getattr(record, "publisher", "")


def word_frequencies(
    records: Iterable[object],
    publisher: Optional[str] = None,
) -> Counter:
    counter: Counter = Counter()
    for record in records:
        title, record_publisher = _record_title(record)
        if not title:
            continue
        if publisher not in (None, "", "all") and record_publisher != publisher:
            continue
        counter.update(tokenize(title))
    return counter


PALETTE = [
    "#1f3a93",
    "#2e86c1",
    "#117a65",
    "#b03a2e",
    "#884ea0",
    "#7d6608",
    "#34495e",
]


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_svg(
    frequencies: Counter,
    top_n: int = 60,
    width: int = 960,
    height: int = 440,
    seed: int = 42,
) -> str:
    del seed
    items: List[Tuple[str, int]] = list(frequencies.most_common(top_n))
    if not items:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}">'
            '<text x="50%" y="50%" text-anchor="middle" fill="#999">'
            "対象データがありません</text></svg>"
        )

    max_count = max(c for _, c in items)
    min_count = min(c for _, c in items)
    span = max(max_count - min_count, 1)

    def font_size(count: int) -> float:
        ratio = (count - min_count) / span
        return 13 + 39 * math.sqrt(ratio)

    def text_width(word: str, size: float) -> float:
        wide = sum(1 for ch in word if ord(ch) > 0x2E7F)
        narrow = len(word) - wide
        return size * (wide * 1.02 + narrow * 0.58)

    placed: List[Tuple[float, float, float, float]] = []
    parts: List[str] = []

    def collides(x: float, y: float, w: float, h: float) -> bool:
        pad = 2.5
        for px, py, pw, ph in placed:
            if x < px + pw + pad and px < x + w + pad and y < py + ph + pad and py < y + h + pad:
                return True
        return False

    center_x, center_y = width / 2, height / 2
    angle_step = 0.35
    for order, (word, count) in enumerate(items):
        size = font_size(count)
        est_w = text_width(word, size)
        est_h = size * 1.15
        color = PALETTE[order % len(PALETTE)]
        opacity = 0.55 + 0.45 * ((count - min_count) / span)
        position = None
        for step in range(1, 2600):
            radius = 1.4 * step
            theta = step * angle_step
            cx = center_x + radius * math.cos(theta)
            cy = center_y + radius * math.sin(theta) * (height / width)
            x, y = cx - est_w / 2, cy - est_h / 2
            if x < 6 or y < 6 or x + est_w > width - 6 or y + est_h > height - 6:
                continue
            if not collides(x, y, est_w, est_h):
                position = (cx, cy, x, y)
                break
        if position is None:
            continue
        cx, cy, x, y = position
        placed.append((x, y, est_w, est_h))
        parts.append(
            f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" '
            f'font-family="\'Hiragino Kaku Gothic ProN\',\'Yu Gothic\',sans-serif" '
            f'font-size="{size:.1f}" font-weight="700" fill="{color}" '
            f'fill-opacity="{opacity:.2f}">{_escape_xml(word)}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="word cloud">'
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>'
        + "".join(parts)
        + "</svg>"
    )


def render_from_records(
    records: Sequence[dict],
    publisher: Optional[str] = None,
    top_n: int = 60,
    width: int = 960,
    height: int = 440,
) -> Dict[str, object]:
    freqs = word_frequencies(records, publisher=publisher)
    svg = render_svg(freqs, top_n=top_n, width=width, height=height)
    top_words = [{"word": w, "count": c} for w, c in freqs.most_common(30)]
    return {
        "svg": svg,
        "top_words": top_words,
        "token_count": sum(freqs.values()),
        "unique_count": len(freqs),
    }

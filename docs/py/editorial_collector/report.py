"""Standalone HTML report export."""

from __future__ import annotations

import html
import datetime as _dt
from pathlib import Path
from typing import List, Optional

from .config import PUBLISHERS
from .models import EditorialArchive

_STATUS_COLORS = {
    "active": "#2f9e44",
    "changed": "#e8590c",
    "deleted": "#c92a2a",
}


def _escape(text: Optional[str]) -> str:
    return html.escape(str(text or ""), quote=True)


def export_html(
    archives: List[EditorialArchive],
    out_path: str = "data/editorial_report.html",
) -> Path:
    s_total = len(archives)
    by_publisher: dict[str, int] = {}
    for a in archives:
        by_publisher[a.publisher] = by_publisher.get(a.publisher, 0) + 1

    stat_chips = "".join(
        f'<span class="chip"><b>{_escape(PUBLISHERS[k].name if k in PUBLISHERS else k)}</b> {v}</span>'
        for k, v in sorted(by_publisher.items(), key=lambda x: -x[1])
    )

    rows = []
    for a in archives[:500]:
        color = _STATUS_COLORS.get(a.status, "#495057")
        rows.append(
            "<tr>"
            f"<td>{_escape(a.publish_date)}</td>"
            f"<td>{_escape(a.publisher_name)}</td>"
            f"<td><span class='badge' style='color:{color}'>{_escape(a.status.upper())}</span></td>"
            f"<td><a href='{_escape(a.url)}' target='_blank' rel='noopener noreferrer'>{_escape(a.title)}</a></td>"
            "</tr>"
        )
    rows_html = "\n".join(rows)

    document = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>社説コレクター レポート</title>
<style>
  body {{ font-family: "Helvetica Neue", Arial, "Hiragino Kaku Gothic ProN", "Noto Sans JP", sans-serif;
         margin: 40px auto; max-width: 1080px; background: #f8f9fa; color: #212529; }}
  h1 {{ font-size: 1.5rem; }}
  .meta {{ color: #868e96; font-size: .85rem; }}
  .chips {{ margin: 16px 0 24px; display: flex; flex-wrap: wrap; gap: 8px; }}
  .chip {{ background: #fff; border: 1px solid #dee2e6; border-radius: 999px;
          padding: 4px 12px; font-size: .82rem; }}
  table {{ border-collapse: collapse; width: 100%; background: #fff; font-size: .88rem; }}
  th, td {{ border: 1px solid #dee2e6; padding: 8px 10px; text-align: left; vertical-align: top; }}
  th {{ background: #e9ecef; white-space: nowrap; }}
  tr:nth-child(even) td {{ background: #fbfbfc; }}
  a {{ color: #1864ab; text-decoration: none; word-break: break-all; }}
  a:hover {{ text-decoration: underline; }}
  .badge {{ font-weight: bold; font-size: .78rem; letter-spacing: .04em; }}
</style>
</head>
<body>
<h1>社説コレクター レポート</h1>
<p class="meta">生成日時: {_dt.datetime.now().isoformat(timespec="seconds")} ／ 総件数: {s_total}（表示は最新500件）</p>
<div class="chips">{stat_chips}</div>
<table>
  <thead><tr><th>掲載日</th><th>新聞社</th><th>状態</th><th>タイトル</th></tr></thead>
  <tbody>
{rows_html}
  </tbody>
</table>
</body>
</html>
"""

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")
    return path

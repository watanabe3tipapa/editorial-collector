"""Command line interface for editorial-collector."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

from .collector import EditorialCollector
from .config import PUBLISHERS
from .fetchers import CloudflareBrowserClient, resolve_clients
from .report import export_html
from .storage import JsonStorage


def _load_credentials() -> tuple[str, str]:
    import os

    load_dotenv()
    return os.environ.get("CF_ACCOUNT_ID", ""), os.environ.get("CF_API_TOKEN", "")


def build_collector(args: argparse.Namespace) -> EditorialCollector:
    account_id, api_token = _load_credentials()
    http_client, browser_client = resolve_clients(account_id, api_token)
    return EditorialCollector(
        storage=JsonStorage(args.db),
        http_client=http_client,
        browser_client=browser_client,
        use_mock=args.mock,
    )


def cmd_pubs(_args: argparse.Namespace) -> int:
    print(f"{'KEY':<12} {'NAME':<10} {'METHOD':<8} LIST_URL")
    print("-" * 90)
    for cfg in PUBLISHERS.values():
        print(f"{cfg.key:<12} {cfg.name:<10} {cfg.method:<8} {cfg.list_url}")
        if cfg.note:
            print(f"{'':<32} note: {cfg.note}")
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    collector = build_collector(args)
    keys: List[str] = list(PUBLISHERS.keys()) if args.all else [args.pub]
    results = asyncio.run(collector.batch_collect(keys))
    failed = 0
    for r in results:
        name = PUBLISHERS[r.publisher].name
        if r.ok:
            print(f"[ok]      {name:<8} 候補 {r.fetched:>3} 件 / 新規 {r.added} 件")
        else:
            failed += 1
            print(f"[error]   {name:<8} {r.error}")
    collector.print_dashboard()
    return 1 if failed else 0


def cmd_revisit(args: argparse.Namespace) -> int:
    collector = build_collector(args)

    async def run() -> int:
        if args.id:
            archive = await collector.revisit(args.id)
            if archive is None:
                print(f"not found: {args.id}")
                return 1
            print(f"#{archive.id} status={archive.status} {archive.title[:40]}")
            return 0
        count = await collector.revisit_stale(older_than_hours=args.stale_hours)
        print(f"revisited {count} items")
        return 0

    return asyncio.run(run())


def cmd_stats(args: argparse.Namespace) -> int:
    collector = build_collector(args)
    collector.print_dashboard()
    collector.print_table(publisher=args.pub, limit=args.limit)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    collector = build_collector(args)
    path = export_html(collector.archives, out_path=args.out)
    print(f"saved: {path}")
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    if not args.yes:
        print("use --yes to confirm reset")
        return 1
    collector = build_collector(args)
    collector.reset()
    print("all archives cleared")
    return 0


def cmd_wordcloud(args: argparse.Namespace) -> int:
    import xml.etree.ElementTree as ET

    from editorial_collector.wordcloud import render_from_records

    collector = build_collector(args)
    records = [a.to_dict() for a in collector.archives]
    result = render_from_records(records, publisher=args.pub, top_n=args.top)
    ET.fromstring(result["svg"])
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result["svg"], encoding="utf-8")
    scope = "全体" if args.pub in (None, "", "all") else PUBLISHERS[args.pub].name
    print(f"[ok] {scope}: tokens={result['token_count']} unique={result['unique_count']}")
    print("top words:", ", ".join(w["word"] for w in result["top_words"][:20]))
    print(f"saved: {out_path}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="editorial-collector",
        description="日本の主要新聞の社説を無料公開範囲で収集するツール",
    )
    parser.add_argument("--db", default="data/editorial_archives.json", help="JSON DB path")
    parser.add_argument("--mock", action="store_true", help="demo mode (no network)")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("pubs", help="show publisher configuration").set_defaults(func=cmd_pubs)

    p_collect = sub.add_parser("collect", help="collect editorials")
    target = p_collect.add_mutually_exclusive_group(required=True)
    target.add_argument("--pub", choices=list(PUBLISHERS.keys()), help="single publisher")
    target.add_argument("--all", action="store_true", help="all publishers")
    p_collect.set_defaults(func=cmd_collect)

    p_revisit = sub.add_parser("revisit", help="revisit archives and detect changes")
    p_revisit.add_argument("--id", help="archive id to revisit")
    p_revisit.add_argument("--stale-hours", type=int, default=24, help="threshold hours (default 24)")
    p_revisit.set_defaults(func=cmd_revisit)

    p_stats = sub.add_parser("stats", help="dashboard and table view")
    p_stats.add_argument("--pub", choices=list(PUBLISHERS.keys()))
    p_stats.add_argument("--limit", type=int, default=20)
    p_stats.set_defaults(func=cmd_stats)

    p_report = sub.add_parser("report", help="export HTML report")
    p_report.add_argument("--out", default="data/editorial_report.html")
    p_report.set_defaults(func=cmd_report)

    p_reset = sub.add_parser("reset", help="clear all archives")
    p_reset.add_argument("--yes", action="store_true")
    p_reset.set_defaults(func=cmd_reset)

    pub_choices = list(PUBLISHERS.keys()) + ["all"]
    p_wc = sub.add_parser("wordcloud", help="generate SVG word cloud from titles")
    p_wc.add_argument("--pub", choices=pub_choices, default="all")
    p_wc.add_argument("--top", type=int, default=60)
    p_wc.add_argument("--out", default="data/wordcloud.svg")
    p_wc.set_defaults(func=cmd_wordcloud)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

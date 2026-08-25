import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        # 社説コレクター
        日本の主要新聞の社説を **無料公開範囲** で収集・アーカイブします。

        | 取得方式 | 対象 |
        |---|---|
        | 直接HTTP | 読売 / 産経 / 北海道 / 東京 |
        | Browser Rendering（要CFキー） | 朝日 / 毎日 / 日経 / 熊本日日 |

        API キー未設定時は **デモモード** で動作確認できます。
        ロードマップ: 収集社説からの Word Cloud 生成（次フェーズ）
        """
    )
    return


@app.cell
def _():
    import os
    from pathlib import Path

    import marimo as mo
    from dotenv import load_dotenv

    load_dotenv()

    BASE_DIR = Path(__file__).resolve().parent
    DB_PATH = str(BASE_DIR / "data" / "editorial_archives.json")
    REPORT_PATH = str(BASE_DIR / "data" / "editorial_report.html")

    CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "")
    CF_API_TOKEN = os.environ.get("CF_API_TOKEN", "")
    BROWSER_READY = bool(CF_ACCOUNT_ID and CF_API_TOKEN)

    def build_collector(use_mock: bool = False):
        from editorial_collector.collector import EditorialCollector
        from editorial_collector.fetchers import RequestsHttpClient, resolve_clients
        from editorial_collector.storage import JsonStorage

        http_client = RequestsHttpClient()
        browser_client = (
            resolve_clients(CF_ACCOUNT_ID, CF_API_TOKEN)[1] if BROWSER_READY else None
        )
        return EditorialCollector(
            storage=JsonStorage(DB_PATH),
            http_client=http_client,
            browser_client=browser_client,
            use_mock=use_mock,
        )

    def publisher_names():
        from editorial_collector import PUBLISHERS

        return {key: cfg.name for key, cfg in PUBLISHERS.items()}

    get_tick, set_tick = mo.state(0)
    get_preview_html, set_preview_html = mo.state("")

    build_collector()
    return (
        BROWSER_READY,
        BASE_DIR,
        DB_PATH,
        REPORT_PATH,
        build_collector,
        get_preview_html,
        get_tick,
        mo,
        publisher_names,
        set_preview_html,
        set_tick,
    )


@app.cell(hide_code=True)
def _(BROWSER_READY, mo):
    if BROWSER_READY:
        _status_note = mo.callout(
            "Cloudflare Browser Rendering: 設定済み", kind="neutral"
        )
    else:
        _status_note = mo.callout(
            "Browser Rendering 未設定: `.env` に CF_ACCOUNT_ID / CF_API_TOKEN を設定すると"
            "朝日・毎日・日経・熊本日日の実データ取得が有効になります",
            kind="warn",
        )
    _status_note
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""## 収集""")
    return


@app.cell
def _(mo, publisher_names):
    _names = publisher_names()
    collect_pub_select = mo.ui.dropdown(
        options=_names, value="yomiuri", label="新聞社（単一収集）"
    )
    collect_one_btn = mo.ui.run_button(label="選択した新聞社を収集")
    collect_batch_btn = mo.ui.run_button(label="直接HTTP対応社を一括収集")
    collect_mock_btn = mo.ui.run_button(label="デモデータ生成（全社）")
    collect_controls = mo.vstack(
        [
            mo.hstack([collect_pub_select], justify="start"),
            mo.hstack(
                [collect_one_btn, collect_batch_btn, collect_mock_btn],
                justify="start",
                gap=1,
            ),
        ]
    )
    collect_controls
    return (
        collect_batch_btn,
        collect_mock_btn,
        collect_one_btn,
        collect_pub_select,
    )


@app.cell
async def _(
    _direct_keys,
    build_collector,
    collect_batch_btn,
    collect_mock_btn,
    collect_one_btn,
    collect_pub_select,
    mo,
    publisher_names,
    set_tick,
):
    if collect_one_btn.value:
        op_collector = build_collector()
        op_result = await op_collector.collect(collect_pub_select.value)
        _name = publisher_names().get(op_result.publisher, op_result.publisher)
        collect_output = mo.md(
            f"**{_name}**: 候補 {op_result.fetched} 件 / 新規 {op_result.added} 件"
            + (f"\n\n> ⚠️ {op_result.error}" if op_result.error else "")
        )
        op_alerts = op_collector.alerts
    elif collect_batch_btn.value:
        op_collector = build_collector()
        op_results = await op_collector.batch_collect(
            [k for k, c in _direct_keys().items() if c == "direct"]
        )
        _names = publisher_names()
        _lines = [
            f"- {_names.get(r.publisher, r.publisher)}: 候補 {r.fetched} / 新規 {r.added}"
            + (f" ⚠️ {r.error}" if r.error else "")
            for r in op_results
        ]
        collect_output = mo.md("**一括収集結果**\n\n" + "\n".join(_lines))
        op_alerts = op_collector.alerts
    elif collect_mock_btn.value:
        op_collector = build_collector(use_mock=True)
        op_results = await op_collector.batch_collect()
        _total = sum(r.added for r in op_results)
        collect_output = mo.md(f"**デモデータ生成完了**: {_total} 件を追加")
        op_alerts = []
    else:
        collect_output = mo.md("*ボタンで操作してください*")
        op_alerts = []

    if collect_one_btn.value or collect_batch_btn.value or collect_mock_btn.value:
        for _alert in list(op_alerts)[-6:]:
            _icon = {"success": "✅", "warn": "⚠️", "danger": "❌"}.get(_alert["type"], "·")
            collect_output = mo.vstack(
                [collect_output, mo.md(f"{_icon} **{_alert['title']}**: {_alert['body']}")]
            )
        set_tick(lambda v: v + 1)
    collect_output
    return


@app.cell
def _():
    def _direct_keys():
        from editorial_collector.config import PUBLISHERS

        return {k: cfg.method for k, cfg in PUBLISHERS.items()}

    return (_direct_keys,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""## ダッシュボード""")
    return


@app.cell
def _(build_collector, get_tick, mo, publisher_names):
    get_tick()
    dash_collector = build_collector()
    dash_stats = dash_collector.stats()
    dash_stat_row = mo.hstack(
        [
            mo.stat(label="総アーカイブ数", value=dash_stats["total"], caption="件"),
            mo.stat(label="active", value=dash_stats["active"]),
            mo.stat(label="changed", value=dash_stats["changed"]),
            mo.stat(label="deleted", value=dash_stats["deleted"]),
        ],
        justify="start",
        gap=2,
    )
    _names = publisher_names()
    _table_md = "| 新聞社 | 件数 |\n|---|---:|\n"
    for _key, _cnt in sorted(dash_stats["by_publisher"].items(), key=lambda x: -x[1]):
        _table_md += f"| {_names.get(_key, _key)} | {_cnt} |\n"
    mo.vstack([dash_stat_row, mo.md(_table_md)])
    return


@app.cell
def _(build_collector, get_tick, mo):
    get_tick()
    table_collector = build_collector()
    table_rows_data = [
        {
            "掲載日": arc.publish_date,
            "新聞社": arc.publisher_name,
            "状態": arc.status,
            "タイトル": arc.title,
            "URL": arc.url,
        }
        for arc in table_collector.rows(limit=300)
    ]
    archive_table = mo.ui.table(data=table_rows_data, page_size=15)
    archive_table
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""## Word Cloud""")
    return


@app.cell
def _(mo, publisher_names):
    _names = {"all": "全体（全社）"}
    _names.update(publisher_names())
    wc_pub_select = mo.ui.dropdown(options=_names, value="all", label="対象")
    wc_top_number = mo.ui.number(start=20, stop=150, value=60, step=10, label="最大語数")
    wc_run_btn = mo.ui.run_button(label="Word Cloud 生成")
    wc_controls = mo.hstack(
        [wc_pub_select, wc_top_number, wc_run_btn], justify="start", gap=1
    )
    wc_controls
    return (wc_pub_select, wc_run_btn, wc_top_number)


@app.cell
def _(build_collector, get_tick, mo, wc_pub_select, wc_run_btn, wc_top_number):
    get_tick()
    if wc_run_btn.value:
        import xml.etree.ElementTree as ET

        from editorial_collector.wordcloud import render_from_records

        wc_records = [a.to_dict() for a in build_collector().archives]
        wc_result = render_from_records(
            wc_records,
            publisher=wc_pub_select.value,
            top_n=int(wc_top_number.value),
        )
        ET.fromstring(wc_result["svg"])
        wc_rows = "| # | 語 | 出現数 |\n|---|---|---:|\n"
        for _i, _w in enumerate(wc_result["top_words"][:15]):
            wc_rows += f"| {_i + 1} | {_w['word']} | {_w['count']} |\n"
        mo.vstack(
            [
                mo.md(
                    f"トークン {wc_result['token_count']} / ユニーク {wc_result['unique_count']}"
                ),
                mo.Html(wc_result["svg"]),
                mo.md("**出現数上位**\n\n" + wc_rows),
            ]
        )
    else:
        mo.md("*ボタンで生成してください*")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""## 再訪問・変更検知""")
    return


@app.cell
def _(mo):
    revisit_hours_number = mo.ui.number(
        start=1, stop=720, value=24, step=1, label="再訪問対象（N時間以上前に収集/再訪問）"
    )
    revisit_run_btn = mo.ui.run_button(label="古い記事を再訪問して変更検知")
    revisit_controls = mo.hstack(
        [revisit_hours_number, revisit_run_btn], justify="start", gap=1
    )
    revisit_controls
    return (revisit_hours_number, revisit_run_btn)


@app.cell
async def _(
    build_collector,
    mo,
    revisit_hours_number,
    revisit_run_btn,
    set_tick,
):
    if revisit_run_btn.value:
        revisit_collector = build_collector()
        revisit_count = await revisit_collector.revisit_stale(
            older_than_hours=int(revisit_hours_number.value)
        )
        revisit_changed = sum(1 for a in revisit_collector.archives if a.status == "changed")
        revisit_deleted = sum(1 for a in revisit_collector.archives if a.status == "deleted")
        set_tick(lambda v: v + 1)
        mo.md(
            f"**再訪問 {revisit_count} 件** ／ 変更 {revisit_changed} 件・削除 {revisit_deleted} 件"
        )
    else:
        mo.md("*未実行*")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""## レポート出力・リセット""")
    return


@app.cell
def _(mo):
    report_export_btn = mo.ui.run_button(label="HTMLレポート出力")
    data_reset_btn = mo.ui.run_button(label="全アーカイブ削除")
    reset_confirm_checkbox = mo.ui.checkbox(label="削除を実行する場合はチェック（保護）")
    maintenance_controls = mo.hstack(
        [report_export_btn, data_reset_btn, reset_confirm_checkbox],
        justify="start",
        gap=1,
    )
    maintenance_controls
    return (data_reset_btn, report_export_btn, reset_confirm_checkbox)


@app.cell
async def _(
    DB_PATH,
    REPORT_PATH,
    build_collector,
    data_reset_btn,
    get_tick,
    mo,
    report_export_btn,
    reset_confirm_checkbox,
    set_tick,
):
    if report_export_btn.value:
        report_collector = build_collector()
        from editorial_collector.report import export_html

        rp_path = export_html(report_collector.archives, out_path=REPORT_PATH)
        mo.md(f"レポートを出力しました: `{rp_path}`")
    elif data_reset_btn.value:
        if reset_confirm_checkbox.value:
            build_collector().reset()
            set_tick(lambda v: v + 1)
            mo.md("**すべてのアーカイブを削除しました**")
        else:
            mo.callout("確認チェックが未選択のため実行しませんでした", kind="warn")
    else:
        get_tick()
        mo.md("*未実行*")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ## セレクタチューナー
        一覧ページの HTML を取得して CSS セレクタを試験できます。
        Browser Rendering 対応社のプレビューには Cloudflare キーが必要です。
        """
    )
    return


@app.cell
def _(mo, publisher_names):
    tuner_target_select = mo.ui.dropdown(
        options=publisher_names(), value="yomiuri", label="対象", full_width=True
    )
    tuner_preview_btn = mo.ui.run_button(label="① HTML プレビュー取得")
    tuner_selector_input = mo.ui.text(
        value="", label="② CSS セレクタ（空欄なら設定値を使用）", full_width=True
    )
    tuner_test_btn = mo.ui.run_button(label="③ 抽出テスト")
    tuner_controls_box = mo.vstack(
        [
            tuner_target_select,
            mo.hstack([tuner_preview_btn], justify="start"),
            tuner_selector_input,
            mo.hstack([tuner_test_btn], justify="start"),
        ]
    )
    tuner_controls_box
    return (
        tuner_preview_btn,
        tuner_selector_input,
        tuner_target_select,
        tuner_test_btn,
    )


@app.cell
async def _(
    BROWSER_READY,
    build_collector,
    mo,
    set_preview_html,
    tuner_preview_btn,
    tuner_target_select,
):
    if tuner_preview_btn.value:
        from editorial_collector import PUBLISHERS as TP_PUBS

        tp_cfg = TP_PUBS[tuner_target_select.value]
        try:
            tp_collector = build_collector()
            if tp_cfg.method == "browser":
                if not BROWSER_READY or tp_collector.browser_client is None:
                    raise RuntimeError("Browser Rendering 未設定のため取得できません")
                tp_html_text = await tp_collector.browser_client.fetch_content(tp_cfg.list_url)
            else:
                tp_html_text = await tp_collector.http_client.fetch_text(tp_cfg.list_url)
            set_preview_html(tp_html_text)
            mo.md(f"`{tp_cfg.list_url}` を取得しました（{len(tp_html_text):,} 文字）")
        except Exception as tp_exc:  # noqa: BLE001
            mo.callout(f"取得失敗: {tp_exc}", kind="danger")
    else:
        mo.md("*① を実行してください*")
    return


@app.cell
def _(
    get_preview_html,
    mo,
    tuner_selector_input,
    tuner_target_select,
    tuner_test_btn,
):
    if tuner_test_btn.value:
        from editorial_collector import PUBLISHERS as TT_PUBS
        from editorial_collector.fetchers import parse_list_html

        tt_cfg = TT_PUBS[tuner_target_select.value]
        tt_html = get_preview_html()
        if not tt_html:
            mo.callout("先に ① HTML プレビュー取得を実行してください", kind="warn")
        else:
            tt_override = tuner_selector_input.value.strip() or None
            tt_items = parse_list_html(
                tt_html, tt_cfg, tt_cfg.list_url, link_selector_override=tt_override
            )
            if tt_items:
                _md = "| # | タイトル | 日付 | URL |\n|---|---|---|---|\n"
                for _i, _it in enumerate(tt_items[:15]):
                    _md += (
                        f"| {_i + 1} | {_it['title'][:40]} "
                        f"| {_it['publish_date']} | {_it['url'][:60]} |\n"
                    )
                mo.vstack([mo.md(f"**抽出 {len(tt_items)} 件**（先頭15件表示）"), mo.md(_md)])
            else:
                mo.callout("0 件でした。セレクタを見直してください。", kind="warn")
    else:
        mo.md("*③ を実行してください*")
    return


if __name__ == "__main__":
    app.run()

# editorial-collector

**新聞社の社説を、無料公開分だけ自動で集める。**

研究・比較・定点観測にそのまま使える収集基盤です。朝日・毎日・読売・日経・産経・北海道・東京・熊本日日の社説一覧（タイトル・掲載日・URL）を収集し、JSON アーカイブ・HTML レポート・Word Cloud を生成します。CLI・marimo UI・ブラウザ Web-UI（Pyodide）の3つの形態で同じコアを共有します。

[![Version](https://img.shields.io/badge/version-v0.1.1-blue.svg)](https://github.com/watanabe3tipapa/editorial-collector/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![deploy-pages](https://github.com/watanabe3tipapa/editorial-collector/actions/workflows/deploy-pages.yml/badge.svg)](https://github.com/watanabe3tipapa/editorial-collector/actions/workflows/deploy-pages.yml)

**ライブデモ**: <https://watanabe3tipapa.github.io/editorial-collector/>

---

## できること

- **社説を自動収集** — 朝日・毎日・読売・日経・産経など主要8社の社説一覧と無料公開部分を取得
- **JSON / CSV で保存** — タイトル・掲載日・URL・変更検知の状態を構造化データとして保存
- **Word Cloud で可視化** — 収集したタイトルからキーワードを抽出し、SVG ワードクラウドを生成
- **定期実行に対応** — GitHub Actions で毎朝自動収集。Worker・CLI・marimo からも実行可能

## こんな人向け

- 論調の変化を継続的に追いたい人
- 複数新聞社の社説を比較したい人
- 研究・分析用にデータをためたい人
- 毎朝のコピペ作業を自動化したい人

## 使い方

### Step 1 — デモで動作を確認

[ライブデモ](https://watanabe3tipapa.github.io/editorial-collector/) で「デモデータ生成」を押すだけ。全8社分のサンプル社説が投入され、ダッシュボードとエクスポートを試せます。

```bash
# ローカルでデモモードを試す（通信なし）
git clone https://github.com/watanabe3tipapa/editorial-collector
cd editorial-collector && uv sync
uv run editorial-collector --mock collect --pub yomiuri
uv run editorial-collector report && open data/editorial_report.html
```

### Step 2 — 実データを取得する場合

静的HTMLページ（読売 / 産経 / 北海道 / 東京）は追加設定なしで取得可能です。

```bash
uv run editorial-collector collect --all
uv run editorial-collector stats
```

JS描画対応社（朝日 / 毎日 / 日経 / 熊本日日）を取得する場合は `.env` を作成:

```bash
cp .env.example .env   # CF_ACCOUNT_ID / CF_API_TOKEN を記入（.env は gitignore 済み）
```

### Step 3 — 定期収集をセットアップ

GitHub Actions で毎朝自動収集。詳細は [GitHub Actions](#github-actions) を参照。

### Step 4 — 結果を活用

```bash
# HTML レポート出力
uv run editorial-collector report

# Word Cloud 生成（SVG）
uv run editorial-collector wordcloud && open data/wordcloud.svg
uv run editorial-collector wordcloud --pub asahi --top 80

# JSON / CSV エクスポート
uv run editorial-collector collect --all
```

## 出力例

収集データは1ファイルの JSON 配列（既定 `data/editorial_archives.json`）で、各要素は次のフィールドを持ちます。

| フィールド | 内容 |
|---|---|
| `title` | 社説タイトル |
| `publish_date` | 掲載日（ISO 8601） |
| `source` / `publisher` | 新聞社キー（`asahi` `mainichi` `yomiuri` `nikkei` `sankei` `hokkaido` `tokyo` `kumanichi`） |
| `url` | 記事URL |
| `status` | `active` / `changed` / `deleted`（再訪問時の変更検知結果） |
| `keywords` | 抽出キーワード |
| `content_hash` | 記事本文ハッシュ（再訪問時に比較） |
| `collected_at` / `last_revisit_at` | 初回収集・最終再訪問時刻（UTC ISO 8601） |

## 特長

- **無料公開分のみ取得** — ペイウォール内の全文は取得せず、公開されている一覧情報と無料部分だけを対象
- **軽量で導入しやすい** — 重いインフラは不要。CLI 一つ、または Web-UI から始められる
- **複数の実行方法に対応** — Cloudflare Worker・CLI・marimo・GitHub Actions から実行可能
- **継続運用しやすい** — 変更検知機能で、掲載日の変化や記事の追加・削除を検出

## 注意点

- 取得対象は各サイトの**無料公開部分のみ**です
- サイト側の仕様変更でセレクタ調整が必要な場合があります
- 利用時は各サイトの利用条件に従ってください
- 低頻度での利用を推奨します

---

## CLI リファレンス

```bash
uv run editorial-collector <コマンド>
```

| コマンド | 内容 |
|---|---|
| `pubs` | 対応新聞社と取得方式（直接HTTP / Browser Rendering）の一覧表示 |
| `collect --pub yomiuri` | 選択した1社の社説一覧を収集して JSON に保存 |
| `collect --all` | 全社を収集（APIキー未設定社は自動スキップ） |
| `stats [--pub KEY]` | 件数ダッシュボードと記事テーブルを表示 |
| `revisit` | 保存済み記事を再訪問して変更検知（`active` / `changed` / `deleted`） |
| `report` | スタンドアロン HTML レポートを出力 |
| `wordcloud [--pub KEY] [--top N]` | タイトルから SVG ワードクラウドを生成 |
| `reset --yes` | アーカイブを全削除 |

共通オプション: `--db PATH`（保存先、既定 `data/editorial_archives.json`）／`--mock`（通信なしデモモード）

### marimo UI

```bash
uv run marimo run notebook.py
```

ボタン操作で収集・ダッシュボード・変更検知・Word Cloud・セレクタチューナーが利用できます。

### Web-UI（ブラウザ）

[GitHub Pages](https://watanabe3tipapa.github.io/editorial-collector/) を開き **「Python 環境を読み込む」** → 収集・閲覧が可能。
実データの取得には Worker プロキシ URLが必要（ページ内チュートリアル STEP 2）。
プロキシなしでも「公開アーカイブを読み込む」で定期収集データの閲覧のみ可能です。

## 収集対象と取得方式

| 取得方式 | 対象 | 備考 |
|---|---|---|
| 直接HTTP（静的HTML） | 読売 / 産経 / 北海道 / 東京 | 追加設定なしで動作 |
| Cloudflare Browser Rendering | 朝日 / 毎日 / 日経 / 熊本日日 | JS描画ページ。APIキーが必要（CLI/marimo版） |

## GitHub Actions

| ワークフロー | トリガー | 内容 |
|---|---|---|
| `deploy-pages.yml` | `main` への push（docs/ やパッケージ変更時）／手動 | `tools/sync_docs.sh` でパッケージを同期し `docs/` を Pages へデプロイ |
| `scheduled-collect.yml` | 毎日 09:20 JST（cron）／手動 | 全社を収集し、レポート・Word Cloud・アーカイブ JSON を `docs/generated/` に生成してコミット（→ Pages 自動再デプロイ） |

セットアップ:

1. リポジトリ Settings → Pages → **Source: GitHub Actions** を選択
2. JS描画対応社を定期収集する場合は Settings → Secrets and variables → Actions に `CF_ACCOUNT_ID` / `CF_API_TOKEN` を登録（未登録でも直接HTTP対応社は収集継続）
3. `Actions` タブの `scheduled-collect` を手動実行して初回データを生成できる

## トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| Browser Rendering で `9109` / `10000 Authentication error` | トークンに **Account → Browser Rendering → Edit** 権限がない。権限を追加するか再作成する |
| `2001 Rate limit exceeded` | API のレート制限。クライアントは 2.5–4 秒間隔で呼び出すため通常は出ない。連続実行後は数分待つ |
| `.env` 設定済みなのに朝日等がスキップされる | `collect --all` は失敗社をスキップして続行する。単独で `collect --pub asahi` を実行してエラー内容を確認 |
| Web-UI で「Worker プロキシ URL が未設定」 | ブラウザ CORS のため直接取得不可。チュートリアル STEP 2 の Worker をデプロイするか、デモモードを使う |
| Pages の「定期収集データ」が 404 | `scheduled-collect` がまだ一度も実行されていない。Actions タブから手動実行する |
| cron 収集が止まった | GitHub は 60 日間アクティブのない scheduled workflow を自動停止する。手動実行または push で再開 |

## 収集ポリシー

- 無料公開範囲のみを対象とし、有料記事の取得は行わない
- robots.txt と各社利用規約を尊重し、低頻度（1日1回程度）で運用する
- User-Agent でプロジェクト名を明示する
- 記事の削除・変更検知はアーカイブ目的であり、再配布を目的としない

## リポジトリ構成

| パス | 内容 |
|---|---|
| `editorial_collector/` | コアパッケージ（config / models / storage / fetchers / collector / report / wordcloud / cli） |
| `notebook.py` | marimo UI |
| `docs/index.html` | GitHub Pages LP + Pyodide Web-UI |
| `tools/sync_docs.sh` | パッケージソース → `docs/py/` 同期スクリプト |
| `data/` | 収集データ（gitignore・生成物） |
| `DEV-MEMO.md` | 開発メモ・実装記録 |

## セキュリティ

- 認証情報は `.env` に置き、**gitignore 済み**。設計資料 `PLAN/` も同様に非公開扱いとする
- CI では認証情報を GitHub Secrets 経由でのみ参照する（リポジトリやログに書かない）
- API トークンは権限を最小限（Browser Rendering のみ）に絞り、漏洩疑いがある場合はローテーションする

## ロードマップ

- shasetsu.jp シードによる網羅性チェック
- Word Cloud の辞書ベース分かち書き（SudachiPy 等・CPython 版のみ）

## コントリビューション

Issue / Pull Request を歓迎します。セレクタの不具合報告（サイト構造変更）は特に助かります。

## ライセンス

MIT License — 詳細は [LICENSE](LICENSE) を参照してください。

## 開発・保守状態

個人プロジェクトとして保守中。開発経緯や技術的な判断は [DEV-MEMO.md](DEV-MEMO.md) に記録しています。

# editorial-collector

**日本の主要新聞の社説を、無料で見える範囲だけ、静かに集める。**

editorial-collector は、朝日・毎日・読売・日経・産経・北海道・東京・熊本日日新聞の社説一覧（タイトル・掲載日・URL）を収集し、JSON アーカイブと HTML レポート、Word Cloud を生成するツールです。CLI・marimo UI・ブラウザ Web-UI（Pyodide）の3つの形態で同じコアを共有します。

[![Version](https://img.shields.io/badge/version-v0.1.0-blue.svg)](https://github.com/watanabe3tipapa/editorial-collector/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![deploy-pages](https://github.com/watanabe3tipapa/editorial-collector/actions/workflows/deploy-pages.yml/badge.svg)](https://github.com/watanabe3tipapa/editorial-collector/actions/workflows/deploy-pages.yml)

**ライブデモ**: <https://watanabe3tipapa.github.io/editorial-collector/>

---

## 概要

- 収集対象は **無料公開範囲のみ**（一覧ページのタイトル・URL・日付）。ペイウォール内の全文取得は行いません
- 静的HTMLは直接HTTPで取得し、JS描画ページ（朝日 / 毎日 / 日経 / 熊本日日）は Cloudflare Browser Rendering REST API を使用
- 再訪問による変更検知（`active` / `changed` / `deleted`）と SHA256 コンテンツハッシュ管理
- 1日1回程度の低頻度運用を前提としたポリライト設計（ランダム待機・単発リクエスト）

## コンセプト (なぜ「コレクター」か)

社説は新聞社の「その時々の主張」であり、時間とともに削除・改変される生きた文書です。本ツールはそれを**低頻度・低負荷・無料範囲**という礼儀を守りながら記録し、後日の分析（トレンド可視化など）に耐える形で蓄積することを目的としています。

## 主な特徴

- 3つの実行形態: CLI バッチ / marimo ノートブック GUI / GitHub Pages の Pyodide Web-UI
- 取得方式の自動切替: 静的ページは直接 HTTP、JS 描画ページは Browser Rendering（要 API キー）
- デモモード: ネットワーク通信なしで全機能の動作確認が可能
- Word Cloud: 辞書不要の簡易トークナイザで SVG を生成（Pyodide でも同一コードが動作）
- セレクタチューナー: 一覧ページの HTML プレビューを見ながら CSS セレクタを実験
- アトミックな JSON 永続化とスタンドアロン HTML レポート出力

## 前提条件

| ツール | 必要バージョン | 確認コマンド |
|---|---:|---|
| Python | >= 3.11 | `python3 --version` |
| uv | 最新推奨 | `uv --version` |
| Cloudflare アカウント | 任意（JS描画対応社のみ） | — |

macOS では `brew install uv` で導入できます。

## 開始手順

```bash
git clone https://github.com/watanabe3tipapa/editorial-collector
cd editorial-collector
uv sync
```

```bash
# デモモードで動作確認（通信なし）
uv run editorial-collector --mock collect --pub yomiuri
uv run editorial-collector report && open data/editorial_report.html
```

```bash
# 実データ収集（APIキー不要社: 読売 / 産経 / 北海道 / 東京）
uv run editorial-collector collect --all
uv run editorial-collector stats

# Word Cloud 生成（SVG）
uv run editorial-collector wordcloud && open data/wordcloud.svg
uv run editorial-collector wordcloud --pub asahi --top 80
```

JS描画対応社（朝日 / 毎日 / 日経 / 熊本日日）を取得する場合は `.env` を作成:

```bash
cp .env.example .env   # CF_ACCOUNT_ID / CF_API_TOKEN を記入（.env は gitignore 済み）
```

## 使い方

### CLI

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
実データの取得には Worker プロキシ URL が必要（ページ内チュートリアル STEP 2）。
プロキシなしでも「公開アーカイブを読み込む」で定期収集データの閲覧のみ可能です。

## データ形式

収集データは1ファイルの JSON 配列（既定 `data/editorial_archives.json`）で、各要素は次のフィールドを持ちます。

| フィールド | 型 | 内容 |
|---|---|---|
| `id` | string | URL＋タイトル＋掲載日の SHA256 ハッシュ（主キー） |
| `publisher` | string | 社キー（`asahi` `mainichi` `yomiuri` `nikkei` `sankei` `hokkaido` `tokyo` `kumanichi`） |
| `publisher_name` | string | 表示名（例: 朝日新聞） |
| `title` / `url` | string | 社説タイトル・記事URL |
| `publish_date` | string | 掲載日（ISO 8601・不明時は収集日） |
| `status` | string | `active` / `changed` / `deleted`（再訪問時の変更検知結果） |
| `source_type` | string | 取得方式（`http` / `browser` / `media` 等） |
| `content_hash` | string \| null | 記事本文ハッシュ（再訪問時に比較） |
| `collected_at` / `last_revisit_at` | string | 初回収集・最終再訪問時刻（UTC ISO 8601） |
| `summary` / `changed` / `keywords` | | 概要・変更フラグ・分類タグ |

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

## リポジトリ構成（主なファイル・ディレクトリ)

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

## 収集ポリシー

- 無料公開範囲のみを対象とし、有料記事の取得は行わない
- robots.txt と各社利用規約を尊重し、低頻度（1日1回程度）で運用する
- User-Agent でプロジェクト名を明示する
- 記事の削除・変更検知はアーカイブ目的であり、再配布を目的としない

## ロードマップ

- shasetsu.jp シードによる網羅性チェック
- Word Cloud の辞書ベース分かち書き（SudachiPy 等・CPython 版のみ）

## コントリビューション

Issue / Pull Request を歓迎します。セレクタの不具合報告（サイト構造変更）は特に助かります。

## ライセンス

MIT License — 詳細は [LICENSE](LICENSE) を参照してください。

## 開発・保守状態

個人プロジェクトとして保守中。開発経緯や技術的な判断は [DEV-MEMO.md](DEV-MEMO.md) に記録しています。

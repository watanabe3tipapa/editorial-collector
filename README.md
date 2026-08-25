# editorial-collector

**日本の主要新聞の社説を、無料で見える範囲だけ、静かに集める。**

editorial-collector は、朝日・毎日・読売・日経・産経・北海道・東京・熊本日日新聞の社説一覧（タイトル・掲載日・URL）を収集し、JSON アーカイブと HTML レポートを生成するツールです。CLI・marimo UI・ブラウザ Web-UI（Pyodide）の3つの形態で同じコアを共有します。

[![Version](https://img.shields.io/badge/version-v0.1.0-blue.svg)](https://github.com/watanabe3tipapa/editorial-collector/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

---

## 概要

- 収集対象は **無料公開範囲のみ**（一覧ページのタイトル・URL・日付）。ペイウォール内の全文取得は行いません
- 静的HTMLは直接HTTPで取得し、JS描画ページは Cloudflare Browser Rendering REST API にフォールバック
- 再訪問による変更検知（`active` / `changed` / `deleted`）と SHA256 コンテンツハッシュ管理
- 1日1回程度の低頻度運用を前提としたポリライト設計（ランダム待機・単発リクエスト）

## コンセプト (なぜ「コレクター」か)

社説は新聞社の「その時々の主張」であり、時間とともに削除・改変される生きた文書です。本ツールはそれを**低頻度・低負荷・無料範囲**という礼儀を守りながら記録し、後日の分析（トレンド可視化など）に耐える形で蓄積することを目的としています。

## 主な特徴

- 3つの実行形態: CLI バッチ / marimo ノートブック GUI / GitHub Pages の Pyodide Web-UI
- 取得方式の自動切替: 静的ページは直接 HTTP、JS 描画ページは Browser Rendering（要 API キー）
- デモモード: ネットワーク通信なしで全機能の動作確認が可能
- セレクタチューナー: 一覧ページの HTML プレビューを見ながら CSS セレクタを実験
- アトミックな JSON 永続化とスタンドアロン HTML レポート出力

## 前提条件

| ツール | 必要バージョン | 確認コマンド |
|---|---:|---|
| Python | >= 3.11 | `python3 --version` |
| uv | 最新推奨 | `uv --version` |
| Cloudflare アカウント | 任意（JS描画対応社のみ） | — |

macOS では `brew install uv` で導入できます。

## 開始手順（確認できる事実のみ）

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
# 実データ収集（直接HTTP対応社: 読売 / 産経 / 北海道 / 東京）
uv run editorial-collector collect --all
uv run editorial-collector stats

# Word Cloud 生成（SVG）
uv run editorial-collector wordcloud && open data/wordcloud.svg
uv run editorial-collector wordcloud --pub asahi --top 80
```

```bash
# marimo UI を起動
uv run marimo run notebook.py
```

JS描画対応社（朝日 / 毎日 / 日経 / 熊本日日）を取得する場合は `.env` を作成:

```bash
cp .env.example .env   # CF_ACCOUNT_ID / CF_API_TOKEN を記入（.env は gitignore 済み）
```

Web-UI は GitHub Pages（またはローカルで `docs/index.html` をサーブ）から利用できます。詳細はページ内チュートリアル参照。

## GitHub Actions

| ワークフロー | トリガー | 内容 |
|---|---|---|
| `deploy-pages.yml` | `main` への push（docs/ やパッケージ変更時）／手動 | `tools/sync_docs.sh` でパッケージを同期し `docs/` を Pages へデプロイ |
| `scheduled-collect.yml` | 毎日 09:20 JST（cron）／手動 | 全社を収集し、レポート・Word Cloud・アーカイブ JSON を `docs/generated/` に生成してコミット（→ Pages 自動再デプロイ） |

セットアップ:

1. リポジトリ Settings → Pages → **Source: GitHub Actions** を選択
2. Browser Rendering 対応社（朝日 / 毎日 / 日経 / 熊本日日）を定期収集する場合は Settings → Secrets and variables → Actions に `CF_ACCOUNT_ID` / `CF_API_TOKEN` を登録（未登録でも直接HTTP対応社は収集継続）
3. `Actions` タブの `scheduled-collect` を手動実行して初回データを生成できる

## リポジトリ構成（主なファイル・ディレクトリ)

| パス | 内容 |
|---|---|
| `editorial_collector/` | コアパッケージ（config / models / storage / fetchers / collector / report / wordcloud / cli） |
| `notebook.py` | marimo UI |
| `docs/index.html` | GitHub Pages LP + Pyodide Web-UI |
| `tools/sync_docs.sh` | パッケージソース → `docs/py/` 同期スクリプト |
| `data/` | 収集データ（gitignore・生成物） |
| `PLAN/` | 設計資料・プロトタイプ |
| `DEV-MEMO.md` | 開発メモ・実装記録 |

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

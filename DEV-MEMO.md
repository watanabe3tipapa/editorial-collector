# DEV-MEMO

開発メモ・実装記録（日付順で追記していく）

---

## 2026-08-25 — 初回実装 v0.1.0

### 実装スコープ

- コアパッケージ `editorial_collector/`（CPython / Pyodide 両対応設計）
- CLI（`uv run editorial-collector ...`）
- marimo UI（`notebook.py`）
- GitHub Pages LP + Pyodide Web-UI（`docs/index.html`）
- 設計資料は `PLAN/` に現状維持

### ファイル構成

```
editorial-collector/
├── PLAN/                        # 設計資料（AI回答の原型・プロトタイプ群）
├── docs/
│   ├── index.html               # GitHub Pages LP（チュートリアル + Pyodide Web-UI）
│   └── py/editorial_collector/  # tools/sync_docs.sh がパッケージソースを同期
├── editorial_collector/
│   ├── config.py                # 8社設定（URL・セレクタ・取得方式 direct|browser）
│   ├── models.py                # EditorialArchive dataclass + ID生成
│   ├── storage.py               # JSON永続化（アトミック書き込み）
│   ├── fetchers.py              # HTTP層: RequestsHttpClient / CloudflareBrowserClient /
│   │                            #        PyodideHttpClient + 一覧パーサ + モック生成
│   ├── collector.py             # collect / batch_collect / revisit(変更検知) / stats
│   ├── report.py                # スタンドアロンHTMLレポート
│   └── cli.py                   # argparse サブコマンド
├── notebook.py                  # marimo UI
├── tools/sync_docs.sh           # パッケージ→docs/py 同期
├── pyproject.toml               # uv 管理（marimo, requests, beautifulsoup4, python-dotenv）
└── .env.example                 # CF認証情報テンプレート（.env は gitignore 済み）
```

### 重要な設計判断

1. **「kitesurf」は実在しない**
   PLAN資料中の kitesurf（Cloudflare の軽量ブラウザ、`?browser=` パラメータ等）は
   AI 回答による誤りと判明。本実装では実在する **Cloudflare Browser Rendering REST API**
   （`POST /accounts/{id}/browser-rendering/{content,scrape}`）に準拠した。
   レスポンス形式は仕様確認前のため防御的にパース（`result` が文字列なら HTML、配列なら抽出結果）。

2. **取得方式の2段構え**（事前 curl 検証に基づく）

   | 社 | 方式 | 根拠 |
   |---|---|---|
   | 読売 | direct | 静的HTMLに `h3.title > a`、URLに日付 |
   | 産経 | direct | `/article/YYYYMMDD-` リンク静的配置 |
   | 北海道 | direct | `＜社説` タイトル＋ `/article/N` |
   | 東京 | direct | `〈社説〉` タイトル＋ `/article/N?rct=editorial`（検証で発見） |
   | 熊本日日 | browser | 静的HTMLに記事リンク無しを確認 → JS描画と判定 |
   | 朝日 | browser | 一覧は plasma（JS）で描画 |
   | 毎日 | browser | RSS(maisho.xml) 403・一覧JS描画 |
   | 日経 | browser | bot対策想定 |

3. **async取得レイヤ**: 全フェッチを `async def` 化。
   CPython は `requests` を `asyncio.to_thread` でラップ、Pyodide は JS fetch ブリッジ。
   `requests` は関数内遅延インポート（Pyodide で import エラーにならないため）。

4. **marimo 変数規約対応**: セル間での定義名重複禁止・参照名は全てセル引数に列挙。
   セル内ローカル変数は接頭辞で衝突回避（op_/dash_/table_/rv_/rp_/tp_/tt_ 等）。

5. **変更検知**: 収集時は本文を取りに行かず（低頻度ポリシー）、
   `revisit` 時のみ記事ページへアクセスし get_text の SHA256 で差分判定。
   初回 revisit は基線ハッシュ登録のみ（changed 扱いにしない）。

6. **Web版の制約**: ブラウザからの直接 fetch は CORS で拒否されるため、
   Worker プロキシ URL を設定欄に入れてもらう方式。
   Browser Rendering 対応社は Web 版非対応（CLI/marimo 版で取得）と明記。

### セキュリティ

- `.env`（CF_ACCOUNT_ID / CF_API_TOKEN）は gitignore 済み。コードは `os.environ` 経由のみ。
- marimo UI 側は環境変数読み込み専用（UI入力欄は設けない＝ノートブックファイルに残らない）。

### 検証結果（2026-08-25 時点）

- [x] `uv run editorial-collector --mock collect/stats/table/report` 全動作
- [x] 実データ収集: 読売26 / 東京24 / 産経15 / 北海道13 件（計78件）→ `data/editorial_archives.json`
- [x] `revisit --stale-hours 0` 50件再訪問・基線ハッシュ登録（全 active 維持）
- [x] HTMLレポート生成 `data/editorial_report.html`
- [x] marimo: `import notebook` OK ＋ `--headless` サーバ起動 HTTP 200
- [x] `tools/sync_docs.sh` 9モジュール同期
- [ ] CF Browser Rendering（朝日・毎日・日経・熊本日日）— **APIキー取得後に検証予定**
- [ ] docs/index.html のブラウザ実機確認（Pyodide CDN バージョン v0.27.7 指定・失敗時 v0.26.4 へフォールバック実装済み）

### 既知の課題

- 日経は bot 対策が強く、Browser Rendering でも取れない可能性 → 要実験
- 毎日は RSS 再挑戦余地あり（UA/経路変更時）
- 熊本日日の browser セレクタは推定値 → セレクタチューナーで要確定
- Pyodide 版の Pyodide バージョン固定値は適宜更新が必要

### ロードマップ（次フェーズ以降）

1. **Word Cloud 生成**（ユーザー要望済み）
   - 各社社説タイトルから名詞抽出（簡易形態素 or n-gram）→ wordcloud2.js / matplotlib で可視化
   - データ足場: `keywords` フィールド・`summary` 保持済み。marimo UI と Web-UI 双方にタブ追加想定
2. shasetsu.jp をシードとした網羅性チェック（PLAN資料案）
3. GitHub Actions での定期収集（cron）+ Pages 自動デプロイ
4. D1/R2 等クラウド保存オプション

---

## 2026-08-25（追記2） — Cloudflare 認証情報セットアップと全8社実データ取得

### 経緯

1. 1個目のトークン（`cfut_…`）: verify は成功するが Browser Rendering 権限なし
   （`/accounts/{id}` → 9109、`/browser-rendering/*` → 10000 Authentication error）
2. 2個目のトークン（`cfat_…`）: `Invalid API Token`(1000) で完全無効
3. 1個目に **Account → Browser Rendering → Edit** 権限を追加 → 全機能動作

### Browser Rendering REST API 実測ノウハウ

| 項目 | 実測結果 |
|---|---|
| `waitUntil: "networkidle"` | ❌ 7001 Invalid input（Playwright式は不可。Puppeteer式のみ有効） |
| `waitUntil: "networkidle0"` / `"load"` on 毎日 | ❌ 6002 ナビゲーション30秒タイムアウト |
| `waitUntil: "domcontentloaded"` | ✅ 毎日・朝日・日経・熊本日日すべて成功 |
| レート制限 | 連続呼び出しで 2001 Rate limit exceeded → クライアント側を 2.5–4 秒間隔に設定 |

→ `CloudflareBrowserClient` を修正: デフォルト `domcontentloaded`、失敗時 `load` へフォールバック、
HTTP ステータスに関わらずレスポンス JSON の errors コードで判定。

### 各社レンダリング後DOMの実構造（セレクタ確定値）

| 社 | 実構造 | 対応 |
|---|---|---|
| 朝日 | `ul.ZMseR > li > a > div.r2y4W`。**クラス名が難読化**され不安定 | hrefパターン `asahi.com/articles/[A-Z0-9]+.html` ＋ keywords `（社説）`。タイトル/概要の境界は半角スペース → `title_cleanup="ascii_space"` |
| 毎日 | `section.mb-64 > ul.articlelist > li > a`、タイトルは `.articlelist-title` | `.articlelist a` ＋ hrefパターン。アンカー全文は日時・文字数・概要混在のため title 要素を優先 |
| 日経 | `article.headlineCard_… > div.textArea_… > h2.title_… > a`、`［社説］` | hrefパターン `nikkei.com/article/[A-Z0-9]+/` ＋ keywords。bot対策は domcontentloaded なら回避可 |
| 熊本日日 | アンカー全文末尾に「2026年08月16日」形式の日付が混入 | タイトル末尾の JP 日付を generic 正規化で除去 |

### パーサ改善（fetchers.py）

1. `normalize_ws()`: ASCII 空白のみ畳み **全角スペース(U+3000)を保持**
   （`str.split()` は U+3000 も潰すため、全角スペース区切りの見出しが崩壊していた）
2. `_anchor_title_text()`: h1–h6 → class名に title を含む要素 → アンカー全文、の優先順
3. 日付抽出の堅牢化:
   - URL パターン → 直近コンテキスト → 親要素全文 の順
   - `MAX_PUBLISH_DATE_AGE_DAYS = 45` の sanity フィルタ追加
     （朝日の社説本文中に言及される「1989年6月4日」等の歴史的日付誤爆を排除）
4. 熊本日日用にタイトル末尾の JP 日付を除去する generic 正規化

### 最終データ品質（2026-08-25）

全8社 合計 **139件**。日付レンジは全社正常（min は各社リストの最古記事で妥当）:

```
asahi      n=10   mainichi  n=20   yomiuri  n=26   nikkei    n=20
sankei     n=16   hokkaido  n=13   tokyo    n=24   kumanichi n=10
```

### セキュリティ運用

- `.env` パーミッション 600・gitignore済み
- チャットに貼付されたトークンは検証完了後の **ローテーション推奨**

### 未消化・次ステップ

- [ ] Word Cloud 生成（ユーザー要望・次フェーズ）
- [ ] docs/index.html のブラウザ実機確認
- [ ] GitHub Actions 定期収集 + Pages デプロイ
- [ ] marimo UI の実機クリック操作確認（headless 起動までは確認済み）

---

## 2026-08-25（追記3） — Word Cloud 実装と用語修正

### Word Cloud（次フェーズ → 完了）

**設計方針**: 外部依存ゼロ（辞書・MeCab・wordcloud ライブラリ不使用）で
CPython / marimo / Pyodide の3環境同一コード動作。

`editorial_collector/wordcloud.py`:

| 関数 | 役割 |
|---|---|
| `tokenize()` | タイトルを漢字連続 / カタカナ連続 / 英数の run で分割。ひらがなのみのトークンは除去、STOPWORDS（社説・新聞名・産経抄等のコラム名）フィルタ |
| `word_frequencies()` | records（dict or dataclass両対応）から出現カウント。publisher フィルタ可 |
| `render_svg()` | アルキメデス螺旋配置＋矩形衝突判定。フォントサイズは sqrt スケール（13–52px）、CJK 1.02em / 半角0.58em の幅推定 |
| `render_from_records()` | 上記ラッパ。svg + top_words + 統計を返す（Web-UI はここだけ呼ぶ） |

実測（139件のタイトル）: 全体 tokens=453 unique=384。上位語は ICC / 対策 / クロマグロ / 終戦 等、
週のトピックを妥当に反映。

既知の限界:
- 分かち書きされない言語のため「残業指導見直」（見直し）のような語幹切り出しアーティファクトが出る
- タイトル内に空白なしで連結した複合語（熊本日日「北方領土初訪問」等）は1語として扱われる
→ 辞書ベース化（SudachiPy 等）は CPython 版のみ将来拡張候補

### UI 統合

- **CLI**: `wordcloud` サブコマンド（--pub / --top / --out）。XML validity 検証付き
- **marimo**: 「Word Cloud」セクション（対象ドロップダウン＋最大語数＋生成ボタン、SVG 表示＋上位15語表）
- **Web-UI**: 同セクションを index.html に追加。レコード JSON を Pyodide へ渡して `render_from_records()` を実行、返された SVG を innerHTML 描画（JS 側レイアウトコード不要）

### 用語修正

ユーザー指摘により「出版社」→「新聞社」に全体修正
（docs/index.html ×3、notebook.py ×4、report.py ×1、collector.py ×1、docs/py 再同期）

### 実機確認

- `python3 -m http.server 8765`（docs/）で全リソース 200
- inline JS を `node --check` で構文検証 OK
- Pyodide CDN (v0.27.7) 到達性 200
- ブラウザで `http://127.0.0.1:8765/` を開いて動作確認を依頼済み

---

## 2026-08-25（追記4） — GitHub Actions（Pages デプロイ・定期収集）

### ワークフロー構成

| ファイル | トリガー | 処理 |
|---|---|---|
| `.github/workflows/deploy-pages.yml` | push to main（docs/・パッケージ変更時）/ manual | sync_docs → upload-pages-artifact → deploy-pages。concurrency group `pages` |
| `.github/workflows/scheduled-collect.yml` | cron `20 0 * * *`（09:20 JST）/ manual | collect --all → `docs/generated/` にレポート+Word Cloud+アーカイブJSON生成 → bot コミット＆push（→ deploy-pages が連鎖起動） |

### 設計メモ

- 収集失敗してもジョブは継続（`|| echo "::warning::…"`）。既存データでレポート生成を優先
- `docs/generated/` はローカルでは gitignore、CI では `git add -A` で強制追加
  （ローカルの手元生成物とリポジトリ状態を分離するため）
- コミットは `github-actions[bot]` 名義。変更ゼロ時はコミットしない（無限ループ防止というより履歴衛生）
- cron は JST 朝1回＝収集ポリシー「低頻度（1日1回）」を順守
- Secrets: `CF_ACCOUNT_ID` / `CF_API_TOKEN`（未登録なら直接HTTP社のみ収集され warning 継続）

### index.html 追加

- 「定期収集データ」カード: レポート/SVG へのリンク＋`btnLoadRemote`（`./generated/editorial_archives.json`
  を fetch して localStorage 経由で UI テーブルへ流し込み。404 時はログに理由表示）
- `a.btn` / `a.btn.neutral` スタイル追加

### ローカル検証済み

- YAML パース OK（triggers/jobs 確認）、inline JS を node --check OK
- CI と同じ生成コマンドを手元実行 → `http://127.0.0.1:8765/generated/` 配下3ファイルとも 200・139件

### 未検証（git init 後）

- 実際の Actions 実行（Pages Source 設定と secrets 登録が前提）

---

## 2026-08-25（追記5） — LP デザイン: マイルド Neo Brutalism

docs/index.html の CSS を全面リテーマ（マークアップ・JSは無変更）。

- クリーム背景 `#faf5ea`、白カードに **2px 墨線 + 4px オフセットハードシャドウ**（角丸12pxで「キツさ」を緩和）
- アクセントはパステル寄せ: バター `#ffd43b` / スカイ `#a5d8ff` / ミント `#b2f2bb` / コーラル / ラベンダー
- ヒーロー: 黄色＋ドットパターン、h1 は白カード化。h2 はミントのハイライトボックス
- ボタン/リンク: 押下で translate＋シャドウ消失のタクタイル挙動、`:focus-visible` 対応
- chips は nth-child で3色循環。テーブルは墨線+黄ヘッダ+偶数行クリーム
- wordcloud SVG の背景を #ffffff に変更してカードに馴染ませ、再生成済み
- 気に入らない場合は git diff docs/index.html で元デザインへ戻せる（本コミット前のため現状 diff で確認）

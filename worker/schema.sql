-- D1 スキーマ: editorial-collector
-- 収集結果を保存するテーブル

CREATE TABLE IF NOT EXISTS editorials (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  url TEXT NOT NULL,
  publish_date TEXT,
  publisher TEXT NOT NULL,
  publisher_name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  content_hash TEXT,
  collected_at TEXT NOT NULL,
  last_revisit_at TEXT,
  keywords TEXT DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_editorials_publisher ON editorials(publisher);
CREATE INDEX IF NOT EXISTS idx_editorials_publish_date ON editorials(publish_date);
CREATE INDEX IF NOT EXISTS idx_editorials_status ON editorials(status);

-- 実行ログ
CREATE TABLE IF NOT EXISTS collect_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_at TEXT NOT NULL,
  publisher TEXT NOT NULL,
  fetched INTEGER DEFAULT 0,
  added INTEGER DEFAULT 0,
  error TEXT
);

CREATE INDEX IF NOT EXISTS idx_collect_logs_run_at ON collect_logs(run_at);

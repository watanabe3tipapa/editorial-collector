/**
 * D1 CRUD — 収集データの保存・読み込み
 */

export interface EditorialRecord {
  id: string;
  title: string;
  url: string;
  publishDate: string | null;
  publisher: string;
  publisherName: string;
  status: string;
  contentHash: string | null;
  collectedAt: string;
  lastRevisitAt: string | null;
  keywords: string;
}

export interface CollectLog {
  runAt: string;
  publisher: string;
  fetched: number;
  added: number;
  error: string | null;
}

// --- 既存IDロード (重複チェック用) ---

export async function loadExistingIds(db: D1Database): Promise<Set<string>> {
  const { results } = await db
    .prepare("SELECT id FROM editorials")
    .all<{ id: string }>();
  return new Set(results.map((r) => r.id));
}

// --- バルク INSERT ---

export async function insertEditorials(
  db: D1Database,
  records: EditorialRecord[]
): Promise<number> {
  if (records.length === 0) return 0;

  const stmt = db.prepare(
    `INSERT OR IGNORE INTO editorials
     (id, title, url, publish_date, publisher, publisher_name, status, content_hash, collected_at, last_revisit_at, keywords)
     VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11)`
  );

  const batches = records.map((r) =>
    stmt.bind(
      r.id,
      r.title,
      r.url,
      r.publishDate,
      r.publisher,
      r.publisherName,
      r.status,
      r.contentHash,
      r.collectedAt,
      r.lastRevisitAt,
      r.keywords
    )
  );

  // D1 は一度に最大100件ずつ
  let added = 0;
  for (let i = 0; i < batches.length; i += 100) {
    const batch = batches.slice(i, i + 100);
    const result = await db.batch(batch);
    for (const r of result) {
      if (r.meta?.changes) added += r.meta.changes;
    }
  }
  return added;
}

// --- 実行ログ ---

export async function logCollectRun(
  db: D1Database,
  log: CollectLog
): Promise<void> {
  await db
    .prepare(
      `INSERT INTO collect_logs (run_at, publisher, fetched, added, error)
       VALUES (?1, ?2, ?3, ?4, ?5)`
    )
    .bind(log.runAt, log.publisher, log.fetched, log.added, log.error)
    .run();
}

// --- API 用: 全件取得 ---

export async function getAllEditorials(
  db: D1Database,
  limit: number = 500
): Promise<EditorialRecord[]> {
  const { results } = await db
    .prepare(
      "SELECT * FROM editorials ORDER BY publish_date DESC, collected_at DESC LIMIT ?1"
    )
    .bind(limit)
    .all<EditorialRecord>();
  return results;
}

// --- API 用: 出版社別件数 ---

export async function getStatsByPublisher(
  db: D1Database
): Promise<Record<string, number>> {
  const { results } = await db
    .prepare(
      "SELECT publisher, COUNT(*) as cnt FROM editorials GROUP BY publisher"
    )
    .all<{ publisher: string; cnt: number }>();

  const stats: Record<string, number> = {};
  for (const r of results) {
    stats[r.publisher] = r.cnt;
  }
  return stats;
}

// --- API 用: 最新の実行ログ ---

export async function getRecentLogs(
  db: D1Database,
  limit: number = 10
): Promise<CollectLog[]> {
  const { results } = await db
    .prepare("SELECT * FROM collect_logs ORDER BY run_at DESC LIMIT ?1")
    .bind(limit)
    .all<CollectLog>();
  return results;
}

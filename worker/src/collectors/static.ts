/**
 * 静的HTML対応社の収集 — fetch() + parser.ts
 * 対象: 読売 / 産経 / 北海道 / 東京
 */

import { PUBLISHERS, USER_AGENT, POLITE_DELAY_MS } from "../config";
import { parseListHtml, generateId } from "../parser";
import { insertEditorials, logCollectRun, type EditorialRecord } from "../storage";
import { todayISO } from "../utils";

export async function collectStaticPublisher(
  db: D1Database,
  publisherKey: string
): Promise<{ fetched: number; added: number; error: string | null }> {
  const cfg = PUBLISHERS[publisherKey];
  if (!cfg || cfg.method !== "direct") {
    return { fetched: 0, added: 0, error: `unknown or non-static publisher: ${publisherKey}` };
  }

  const runAt = todayISO() + "T" + new Date().toISOString().slice(11);
  let fetched = 0;
  let added = 0;
  let error: string | null = null;

  try {
    // ポリット待機
    await sleep(POLITE_DELAY_MS.min, POLITE_DELAY_MS.max);

    const resp = await fetch(cfg.listUrl, {
      headers: { "User-Agent": USER_AGENT },
      cf: { cacheTtl: 0 },
    });

    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }

    const html = await resp.text();
    const candidates = parseListHtml(html, cfg, cfg.listUrl);
    fetched = candidates.length;

    // 既存IDを取得
    const existingIds = await db
      .prepare("SELECT id FROM editorials")
      .all<{ id: string }>();
    const seen = new Set(existingIds.results.map((r) => r.id));

    // 新規アイテムを作成
    const now = new Date().toISOString();
    const newRecords: EditorialRecord[] = [];

    for (const cand of candidates) {
      const id = await generateId(cand.url, cand.title, cand.publishDate || todayISO());
      if (seen.has(id)) continue;
      seen.add(id);

      newRecords.push({
        id,
        title: cand.title,
        url: cand.url,
        publishDate: cand.publishDate,
        publisher: cfg.key,
        publisherName: cfg.name,
        status: "active",
        contentHash: null,
        collectedAt: now,
        lastRevisitAt: null,
        keywords: JSON.stringify([cfg.key, "editorial"]),
      });
    }

    added = await insertEditorials(db, newRecords);
  } catch (e: any) {
    error = `${e.constructor?.name || "Error"}: ${e.message}`;
  }

  await logCollectRun(db, { runAt, publisher: cfg.key, fetched, added, error });
  return { fetched, added, error };
}

function sleep(minMs: number, maxMs: number): Promise<void> {
  const delay = minMs + Math.random() * (maxMs - minMs);
  return new Promise((resolve) => setTimeout(resolve, delay));
}

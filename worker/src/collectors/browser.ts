/**
 * Browser Rendering対応社の収集
 * 対象: 朝日 / 毎日 / 日経 / 熊本日日
 *
 * 注意: Browser Rendering API は有料サービス。
 * フリープランでは1日500リクエストまで無料。
 * 4社 × 1日 = 約4リクエストで十分収まる。
 *
 * wrangler.toml に [browser] binding を追加して有効化する。
 * binding がない場合はスキップしてエラーを記録する。
 */

import { PUBLISHERS, USER_AGENT, POLITE_DELAY_MS } from "../config";
import { parseListHtml, generateId } from "../parser";
import { insertEditorials, logCollectRun, type EditorialRecord } from "../storage";
import { todayISO } from "../utils";

interface BrowserBinding {
  fetch(url: string, options?: RequestInit): Promise<Response>;
}

export async function collectBrowserPublisher(
  db: D1Database,
  publisherKey: string,
  browser?: BrowserBinding
): Promise<{ fetched: number; added: number; error: string | null }> {
  const cfg = PUBLISHERS[publisherKey];
  if (!cfg || cfg.method !== "browser") {
    return { fetched: 0, added: 0, error: `unknown or non-browser publisher: ${publisherKey}` };
  }

  if (!browser) {
    const error = "Browser Rendering binding が未設定です (wrangler.toml の [browser] を確認)";
    await logCollectRun(db, {
      runAt: new Date().toISOString(),
      publisher: cfg.key,
      fetched: 0,
      added: 0,
      error,
    });
    return { fetched: 0, added: 0, error };
  }

  const runAt = todayISO() + "T" + new Date().toISOString().slice(11);
  let fetched = 0;
  let added = 0;
  let error: string | null = null;

  try {
    // ポリット待機
    await sleep(POLITE_DELAY_MS.min, POLITE_DELAY_MS.max);

    // Browser Rendering API でページを取得
    const resp = await browser.fetch(
      `https://api.cloudflare.com/client/v4/accounts/browser-rendering/content`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          url: cfg.listUrl,
          gotoOptions: { waitUntil: "domcontentloaded" },
        }),
      }
    );

    if (!resp.ok) {
      throw new Error(`Browser Rendering HTTP ${resp.status}`);
    }

    const data = await resp.json<any>();
    const html = data?.result;
    if (typeof html !== "string" || !html.trim()) {
      throw new Error(`Browser Rendering: empty result — ${JSON.stringify(data.errors)}`);
    }

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

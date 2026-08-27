/**
 * editorial-collector Worker
 *
 * エントリポイント: Cron トリガー / HTTP リクエスト
 *
 * Cron 時の処理:
 *   1. D1 から既存IDをロード
 *   2. 全8社を巡回 (静的: fetch, JS描画: Browser Rendering)
 *   3. 新規アイテムを D1 に INSERT
 *   4. 実行ログを記録
 *
 * HTTP 時の処理:
 *   GET /             → 収集データ一覧 (JSON)
 *   GET /stats        → 出版社別件数
 *   GET /logs         → 最新の実行ログ
 *   GET /health       → ヘルスチェック
 */

import {
  PUBLISHERS,
  STATIC_PUBLISHERS,
  BROWSER_PUBLISHERS,
} from "./config";
import { collectStaticPublisher } from "./collectors/static";
import { collectBrowserPublisher } from "./collectors/browser";
import {
  getAllEditorials,
  getStatsByPublisher,
  getRecentLogs,
} from "./storage";
import { nowISO } from "./utils";

interface Env {
  DB: D1Database;
  USER_AGENT?: string;
  // BROWSER?: BrowserBinding;  // [browser] binding を有効化した場合
}

export default {
  // --- Cron トリガー ---
  async scheduled(
    event: ScheduledEvent,
    env: Env,
    ctx: ExecutionContext
  ): Promise<void> {
    console.log(`[Cron] fired at ${nowISO()}`);

    const results: { publisher: string; fetched: number; added: number; error: string | null }[] = [];

    // 静的HTML対応社を処理
    for (const cfg of STATIC_PUBLISHERS) {
      console.log(`[collect] ${cfg.key} (direct) ...`);
      const r = await collectStaticPublisher(env.DB, cfg.key);
      results.push({ publisher: cfg.key, ...r });
      console.log(`[collect] ${cfg.key}: fetched=${r.fetched} added=${r.added} error=${r.error}`);
    }

    // Browser Rendering対応社を処理
    // env.BROWSER binding が設定されている場合のみ実行
    const browser = (env as any).BROWSER;
    for (const cfg of BROWSER_PUBLISHERS) {
      console.log(`[collect] ${cfg.key} (browser) ...`);
      const r = await collectBrowserPublisher(env.DB, cfg.key, browser);
      results.push({ publisher: cfg.key, ...r });
      console.log(`[collect] ${cfg.key}: fetched=${r.fetched} added=${r.added} error=${r.error}`);
    }

    // サマリ
    const totalAdded = results.reduce((s, r) => s + r.added, 0);
    const errors = results.filter((r) => r.error);
    console.log(
      `[Cron] done. total_added=${totalAdded} errors=${errors.length}/${results.length}`
    );
  },

  // --- HTTP リクエスト ---
  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext
  ): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;

    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    if (path === "/health") {
      return jsonResponse({ status: "ok", time: nowISO() }, corsHeaders);
    }

    if (path === "/") {
      const limit = parseInt(url.searchParams.get("limit") || "500", 10);
      const records = await getAllEditorials(env.DB, limit);
      return jsonResponse({ count: records.length, records }, corsHeaders);
    }

    if (path === "/stats") {
      const stats = await getStatsByPublisher(env.DB);
      const total = Object.values(stats).reduce((s, n) => s + n, 0);
      return jsonResponse({ total, byPublisher: stats }, corsHeaders);
    }

    if (path === "/logs") {
      const logs = await getRecentLogs(env.DB);
      return jsonResponse({ logs }, corsHeaders);
    }

    return jsonResponse({ error: "not found" }, corsHeaders, 404);
  },
};

function jsonResponse(
  data: unknown,
  headers: Record<string, string> = {},
  status: number = 200
): Response {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      ...headers,
    },
  });
}

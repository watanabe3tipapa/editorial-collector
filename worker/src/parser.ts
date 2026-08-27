/**
 * HTML パース — 社説一覧ページからリンクとタイトルを抽出
 *
 * Cloudflare Workers では DOMParser が使えないため、
 * 正規表現ベース + 軽量な HTML タグ解析で処理する。
 */

import {
  MAX_ITEMS_PER_SOURCE,
  MAX_PUBLISH_DATE_AGE_DAYS,
  type PublisherConfig,
} from "./config";

export interface ParsedItem {
  title: string;
  url: string;
  publishDate: string | null;
}

// --- 日付抽出 ---

const URL_DATE_RE = /\/(\d{4})(\d{2})(\d{2})[-_/]/;
const ISO_DATE_RE = /(\d{4})-(\d{2})-(\d{2})/;
const JP_DATE_RE = /(\d{4})年(\d{1,2})月(\d{1,2})日/;
const SLASH_DATE_RE = /(20\d{2})\/(\d{1,2})\/(\d{1,2})/;

function extractPublishDate(
  url: string,
  contextText: string = ""
): string | null {
  // URL から日付を抽出
  const urlMatch = URL_DATE_RE.exec(url);
  if (urlMatch) {
    const [_, y, m, d] = urlMatch;
    const date = `${y}-${m}-${d}`;
    if (isValidDate(date)) return date;
  }

  // コンテキストテキストから ISO 形式
  const isoMatch = ISO_DATE_RE.exec(contextText.slice(0, 300));
  if (isoMatch) return isoMatch[0];

  // コンテキストテキストから日本語日付
  const jpMatch = JP_DATE_RE.exec(contextText);
  if (jpMatch) {
    const [_, y, m, d] = jpMatch;
    const date = `${y}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`;
    if (isValidDate(date)) return date;
  }

  // スラッシュ区切り
  const slashMatch = SLASH_DATE_RE.exec(contextText);
  if (slashMatch) {
    const [_, y, m, d] = slashMatch;
    const date = `${y}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`;
    if (isValidDate(date)) return date;
  }

  return null;
}

function isValidDate(dateStr: string): boolean {
  try {
    const d = new Date(dateStr + "T00:00:00Z");
    const now = new Date();
    const ageDays = (now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24);
    return ageDays >= 0 && ageDays <= MAX_PUBLISH_DATE_AGE_DAYS;
  } catch {
    return false;
  }
}

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

// --- タイトル正規化 ---

const WS_KEEPING_FULLWIDTH_RE = /[^\S\u3000]+/g;

function normalizeWs(text: string): string {
  return text.replace(WS_KEEPING_FULLWIDTH_RE, " ").trim();
}

const TITLE_SUFFIX_DATE_RE = /\s*20\d{2}年\d{1,2}月\d{1,2}日\s*$/;

function cleanTitle(title: string, cleanup?: "ascii_space"): string {
  let t = normalizeWs(title);
  if (cleanup === "ascii_space" && t.includes(" ")) {
    t = t.split(" ", 1)[0];
  }
  t = t.replace(TITLE_SUFFIX_DATE_RE, "");
  return t;
}

// --- メインパーサー ---

/**
 * HTML文字列から社説候補を抽出する
 *
 * 方式: <a> タグをregexで走査し、href パターンとタイトル条件でフィルタ
 */
export function parseListHtml(
  html: string,
  cfg: PublisherConfig,
  fetchedUrl: string
): ParsedItem[] {
  const items: ParsedItem[] = [];
  const seen = new Set<string>();

  // <a ... href="..." ... >...</a> を抽出
  const anchorRe = /<a\b([^>]*)>([\s\S]*?)<\/a>/gi;
  let match: RegExpExecArray | null;

  while ((match = anchorRe.exec(html)) !== null) {
    if (items.length >= MAX_ITEMS_PER_SOURCE) break;

    const attrs = match[1];
    const innerHtml = match[2];

    // href を抽出
    const hrefMatch = /href\s*=\s*["']([^"']+)["']/i.exec(attrs);
    if (!hrefMatch) continue;
    const href = hrefMatch[1];

    // 絶対URLに変換
    const absolute = resolveUrl(fetchedUrl, href);

    // href パターンチェック
    if (cfg.hrefPattern && !cfg.hrefPattern.test(absolute)) continue;

    // タイトルを抽出 (タグを除去してテキストだけ取得)
    let title = stripTags(innerHtml);
    title = cleanTitle(title, cfg.titleCleanup);

    // タイトルキーワードチェック
    if (cfg.titleKeywords && cfg.titleKeywords.length > 0) {
      const context = normalizeWs(stripTags(innerHtml));
      const hasKeyword = cfg.titleKeywords.some((kw) => context.includes(kw));
      if (!hasKeyword) continue;
    }

    if (!title && !cfg.hrefPattern) continue;

    // タイトルが空ならURL末尾から生成
    if (!title) {
      const tail = absolute.replace(/\/+$/, "").split("/").pop() || "";
      title = tail.replace(/^[A-Z0-9]{8,}-?/, "") || tail;
    }

    // 重複排除
    const key = absolute.replace(/\/+$/, "");
    if (seen.has(key)) continue;
    seen.add(key);

    // 日付
    const context = normalizeWs(stripTags(innerHtml));
    let publishDate = extractPublishDate(absolute, context);
    if (!publishDate) publishDate = todayISO();

    items.push({ title, url: absolute, publishDate });
  }

  return items;
}

// --- ユーティリティ ---

function stripTags(html: string): string {
  return html.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

function resolveUrl(base: string, href: string): string {
  if (href.startsWith("http://") || href.startsWith("https://")) return href;
  try {
    return new URL(href, base).href;
  } catch {
    return href;
  }
}

// --- ID 生成 (Python 側と同一ロジック) ---

export async function generateId(
  url: string,
  title: string,
  publishDate: string
): Promise<string> {
  const data = `${url}\n${title}\n${publishDate}`;
  const encoder = new TextEncoder();
  const hashBuffer = await crypto.subtle.digest("SHA-256", encoder.encode(data));
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
}

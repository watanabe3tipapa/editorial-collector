/**
 * Publisher configuration — Python config.py と同期する
 */

export interface PublisherConfig {
  key: string;
  name: string;
  listUrl: string;
  method: "direct" | "browser";
  hrefPattern?: RegExp;
  titleKeywords?: string[];
  titleCleanup?: "ascii_space";
  note?: string;
}

export const PUBLISHERS: Record<string, PublisherConfig> = {
  yomiuri: {
    key: "yomiuri",
    name: "読売新聞",
    listUrl: "https://www.yomiuri.co.jp/editorial/",
    method: "direct",
    hrefPattern: /https:\/\/www\.yomiuri\.co\.jp\/editorial\/\d{8}-[A-Z0-9]+\/?$/,
  },
  sankei: {
    key: "sankei",
    name: "産経新聞",
    listUrl: "https://www.sankei.com/column/editorial/",
    method: "direct",
    hrefPattern: /https:\/\/www\.sankei\.com\/article\/\d{8}-/,
  },
  hokkaido: {
    key: "hokkaido",
    name: "北海道新聞",
    listUrl: "https://www.hokkaido-np.co.jp/tags/editorial/",
    method: "direct",
    hrefPattern: /https:\/\/www\.hokkaido-np\.co\.jp\/article\/\d+\/?$/,
    titleKeywords: ["＜社説"],
  },
  tokyo: {
    key: "tokyo",
    name: "東京新聞",
    listUrl: "https://www.tokyo-np.co.jp/n/column/editorial",
    method: "direct",
    titleKeywords: ["社説"],
  },
  asahi: {
    key: "asahi",
    name: "朝日新聞",
    listUrl: "https://www.asahi.com/rensai/list.html?id=16",
    method: "browser",
    hrefPattern: /asahi\.com\/articles\/[A-Z0-9]+\.html/,
    titleKeywords: ["（社説）"],
    titleCleanup: "ascii_space",
  },
  mainichi: {
    key: "mainichi",
    name: "毎日新聞",
    listUrl: "https://mainichi.jp/editorial/",
    method: "browser",
    hrefPattern: /mainichi\.jp\/articles\/\d{8}\//,
  },
  nikkei: {
    key: "nikkei",
    name: "日本経済新聞",
    listUrl: "https://www.nikkei.com/opinion/editorial/",
    method: "browser",
    hrefPattern: /nikkei\.com\/article\/[A-Z0-9]+\//,
    titleKeywords: ["［社説］"],
  },
  kumanichi: {
    key: "kumanichi",
    name: "熊本日日新聞",
    listUrl: "https://www.kumanichi.com/opinion/syasetsu",
    method: "browser",
  },
};

/** 静的HTML対応社 (直接fetch可) */
export const STATIC_PUBLISHERS = Object.values(PUBLISHERS).filter(
  (p) => p.method === "direct"
);

/** Browser Rendering対応社 */
export const BROWSER_PUBLISHERS = Object.values(PUBLISHERS).filter(
  (p) => p.method === "browser"
);

export const USER_AGENT =
  "editorial-collector/0.1.2 (research project; low-frequency crawling; contact via github.com/watanabe3tipapa)";

export const MAX_ITEMS_PER_SOURCE = 30;

export const MAX_PUBLISH_DATE_AGE_DAYS = 45;

/** リクエスト間の待機時間 (ms) */
export const POLITE_DELAY_MS = { min: 2000, max: 4000 };

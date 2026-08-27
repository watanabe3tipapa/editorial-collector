/**
 * ユーティリティ関数
 */

export function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

export function nowISO(): string {
  return new Date().toISOString();
}

/** UTC → JST 変換 */
export function toJST(utcDate: Date): string {
  const jst = new Date(utcDate.getTime() + 9 * 60 * 60 * 1000);
  return jst.toISOString().replace("T", " ").slice(0, 19);
}

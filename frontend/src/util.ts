// 展示格式化工具。

export function fmtNum(v: unknown, digits = 2): string {
  if (v === null || v === undefined || v === "") return "-";
  const n = Number(v);
  if (Number.isNaN(n)) return "-";
  return n.toFixed(digits);
}

/** 万元市值 → 亿元展示。 */
export function fmtYi(v: unknown): string {
  if (v === null || v === undefined) return "-";
  const n = Number(v);
  if (Number.isNaN(n)) return "-";
  return (n / 10000).toFixed(2) + "亿";
}

/** 涨跌幅上色类名。 */
export function pctClass(v: unknown): string {
  const n = Number(v);
  if (Number.isNaN(n) || n === 0) return "";
  return n > 0 ? "up" : "down";
}

export function fmtPct(v: unknown): string {
  if (v === null || v === undefined) return "-";
  const n = Number(v);
  if (Number.isNaN(n)) return "-";
  return (n > 0 ? "+" : "") + n.toFixed(2) + "%";
}

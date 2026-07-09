// 后端返回结构的 TS 类型（与 FastAPI 响应对齐）。

export interface UserItem {
  id: string;
  name: string;
}

export interface Overview {
  total: number;
  user_count: number;
  first: string;
  last: string;
  active_days: number;
  monthly: { ym: string; n: number }[];
  daily: { date: string; n: number }[];
  latest: PostItem[];
}

export interface PostItem {
  id: string;
  user_name: string;
  date: string;
  created_at: number;
  title: string;
  text: string;
  url: string;
  like_count: number;
  retweet_count: number;
  reply_count: number;
  fav_count: number;
}

export interface PostsPage {
  total: number;
  items: PostItem[];
  page: number;
  size: number;
}

export interface SummaryResp {
  found: boolean;
  html: string;
  raw?: string;
}

export interface StockRow {
  code: string;
  name: string;
  close?: number;
  change_pct?: number;
  volume?: number;
  amount?: number;
  turnover_rate?: number;
  pe_ttm?: number;
  pb?: number;
  total_mv?: number;
  circ_mv?: number;
  eps?: number;
  roe?: number;
  net_profit_yoy?: number;
  revenue_yoy?: number;
  gross_margin?: number;
  report_date?: string;
  added_at?: number;
  [k: string]: unknown;
}

export interface ScreenResp {
  trade_date: string | null;
  items: StockRow[];
  error: string;
}

export interface SectorItem {
  board_code: string;
  name: string;
  kind: string;
  abbr?: string;
}

export interface FieldMeta {
  field: string;
  label: string;
}

export interface Condition {
  field: string;
  op: string;
  value: number;
}

export interface KlineBar {
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  dif: number;
  dea: number;
  macd: number;
  k: number;
  d: number;
  j: number;
  strict_ok: boolean;
  loose_ok: boolean;
  golden_ok: boolean;
  mid_reverse_ok: boolean;
  stop_loss_ok: boolean;
}

export interface KlineView {
  code: string;
  name: string;
  bars: KlineBar[];
  error: string;
}

export interface Fundamentals {
  code: string;
  name: string;
  quote: { pe_ttm?: number; pb?: number; total_mv?: number; circ_mv?: number };
  finance: Record<string, unknown> | null;
  sectors: { sector: string; board_code: string; kind: string }[];
  mentions: PostItem[];
  error: string;
}

export interface NewsItem {
  date: string;
  time: string;
  title: string;
  url: string;
}

export interface GroupItem {
  id: number;
  name: string;
  created_at: number;
  member_count: number;
}

export interface JobStatus {
  running: boolean;
  log: string[];
  error: string;
  source?: string;
  started_at: string;
  finished_at: string;
}

export interface ScheduleCfg {
  enabled: boolean;
  start: string;
  end: string;
  interval: number;
}

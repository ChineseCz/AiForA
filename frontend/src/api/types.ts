// 后端返回结构的 TS 类型（与 FastAPI 响应对齐）。

export interface UserItem {
  id: string;
  name: string;
}

export interface BullishHeatItem {
  name: string;
  code: string;
  close: number | null;
  change_pct: number | null;
  bullish_count: number;
  bullish_users: string[];
}

export interface BullishHeatBoard {
  sector: string;
  kind: "industry" | "concept";
  bullish_stock_count: number;
  bullish_stocks: { name: string; code: string }[];
  bullish_user_count: number;
  bullish_users: string[];
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
  bullish_heat: BullishHeatItem[];
  bullish_heat_boards: BullishHeatBoard[];
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
  images?: string[];
  brief?: string | null;
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
  sectors?: string[];
  concepts?: string[];
  bullish_sectors?: string[];
  bullish_concepts?: string[];
  bullish_users?: string[];
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

export interface SectorRankItem {
  sector: string;
  board_code: string;
  kind: string;
  member_count: number;
  up_count: number;
  down_count: number;
  avg_change_pct: number | null;
  mv_weighted_change_pct: number | null;
}

export interface SectorRankResp {
  trade_date: string | null;
  items: SectorRankItem[];
  error: string;
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

export interface StockAiAnalysisResp {
  content: string;
  html: string;
  generated: boolean;
  error: string;
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
  volume_breakout_ok: boolean;
  boll_breakout_ok: boolean;
  rsi_bounce_ok: boolean;
  rsi_overbought_ok: boolean;
  break_ma_ok: boolean;
  high_vol_drop_ok: boolean;
}

export interface KlineView {
  code: string;
  name: string;
  period?: "day" | "week" | "month";
  bars: KlineBar[];
  error: string;
}

export interface Quote {
  code: string;
  name: string;
  open: number;
  pre_close: number;
  close: number;
  high: number;
  low: number;
  volume: number | null;
  trade_date: string;
  time: string;
  error?: string;
}

export interface IntradayBar {
  time: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number;
  amount: number;
}

export interface IntradayView {
  code: string;
  name: string;
  date: string;
  pre_close: number | null;
  bars: IntradayBar[];
  error: string;
}

export interface BondDetail {
  code: string;
  name: string | null;
  close: number | null;
  change_pct: number | null;
  volume: number | null;
  amount: number | null;
  high: number | null;
  low: number | null;
  stock_code: string | null;
  stock_name: string | null;
  convert_price: number | null;
  conversion_value: number | null;
  premium_rate: number | null;
  maturity_date: string | null;
  rating: string | null;
  redeem_status: string | null;
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

export interface GroupMember {
  code: string;
  name: string;
  added_at: number;
  close?: number;
  change_pct?: number;
  volume?: number;
}

export interface TradeRecord {
  id: number;
  code: string;
  stock_name: string;
  direction: "buy" | "sell";
  price: number;
  quantity: number;
  trade_date: string;
  note: string;
  created_at: number;
}

export interface TradeNote {
  id: number;
  note_date: string;  // YYYY-MM-DD
  content: string;
  updated_at: number;
  is_favorite: boolean;
}

export interface TradeStats {
  total_sell_trades: number;
  wins: number;
  losses: number;
  total_stocks: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number | null;
  total_realized_pnl: number;
}

export interface JobStatus {
  running: boolean;
  log: string[];
  error: string;
  source?: string;
  started_at: string;
  finished_at: string;
}

export interface WatchlistOverview {
  total: number;
  up: number;
  down: number;
  flat: number;
  avg_change: number | null;
  trade_date: string | null;
  signals: { code: string; name: string; label: string }[];
  gainers: { code: string; name: string; change_pct: number }[];
  losers: { code: string; name: string; change_pct: number }[];
}

export interface RecentJob {
  id: number;
  kind: string;
  status: string;
  source?: string;
  started_at?: number;
  finished_at?: number;
  error?: string;
  duration_seconds?: number | null;
  log?: string;
}

export interface DataHealth {
  stock_date: string | null;
  stock_count: number;
  bond_date: string | null;
  bond_count: number;
  backfill_failures: number;
  stock_sync_status: string | null;
  stock_sync_started_at: number | null;
  stock_sync_finished_at: number | null;
  stock_sync_duration_seconds: number | null;
  stock_sync_summary: string;
  stock_sync_error: string | null;
}

export interface BackfillFailure {
  asset_type: "stock" | "bond" | string;
  code: string;
  last_job_id: number | null;
  error: string | null;
  updated_at: number;
}

export interface NotificationSettings {
  signal_enabled: boolean;
  email_enabled: boolean;
  wechat_enabled: boolean;
}

export interface ScheduleCfg {
  enabled: boolean;
  start: string;
  end: string;
  interval: number;
  stock_auto_sync_enabled: boolean;
  stock_sync_interval: number;
  weekly_summary_enabled: boolean;
}

export interface AuthSettingsCfg {
  require_login_enabled: boolean;
}

export interface AuthConfigResp {
  require_login: boolean;
  visitor_mode: boolean;
}

export interface VisitorLoginResp {
  access_token: string;
  phone?: string;
  email?: string;
  admin_token?: string;
}

export interface ResetCaptchaResp {
  challenge_id: string;
  image: string;
  error: string;
}

export interface WechatQrcodeResp {
  scene_key: string;
  qr_url: string;
}

export interface WechatPollResp {
  status: "pending" | "scanned";
  access_token?: string;
}

export interface VisitorMeResp {
  login_type: "phone" | "wechat" | "email";
  phone: string | null;
  email?: string | null;
  nickname: string | null;
  created_at: number;
}

// 选股页筛选条件 + 结果的模块级单例：路由到 /stock/:code 再返回时 Screener 组件会重新 mount，
// 单靠 useState 保存不住；这个模块只要页面没整个刷新就一直存在，充当一个轻量的"记忆"。
import type { Condition, StockRow } from "@/api/types";

export type CapFilter = "all" | "small" | "mid" | "large";

export interface ScreenerState {
  strategies: string[];
  strategyParams: Record<string, Record<string, number | boolean>>;
  conds: Condition[];
  nameQuery: string;
  capFilter: CapFilter;
  mentionOn: boolean;
  mentionDays: number;
  mentionUsers: string[];
  mentionBullishOnly: boolean;
  sectorOn: boolean;
  sectorMode: string;
  sectorNames: string[];
  rows: StockRow[];
  tradeDate: string | null;
}

export const screenerState: ScreenerState = {
  strategies: [],
  strategyParams: {},
  conds: [],
  nameQuery: "",
  capFilter: "all",
  mentionOn: false,
  mentionDays: 7,
  mentionUsers: [],
  mentionBullishOnly: false,
  sectorOn: false,
  sectorMode: "manual",
  sectorNames: [],
  rows: [],
  tradeDate: null,
};

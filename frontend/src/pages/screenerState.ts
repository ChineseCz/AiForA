// 选股页筛选条件 + 结果的模块级单例：路由到 /stock/:code 再返回时 Screener 组件会重新 mount，
// 单靠 useState 保存不住；这个模块只要页面没整个刷新就一直存在，充当一个轻量的"记忆"。
import type { Condition, StockRow } from "@/api/types";

export interface ScreenerState {
  strategies: string[];
  conds: Condition[];
  nameQuery: string;
  mentionOn: boolean;
  mentionDays: number;
  mentionUser: string;
  mentionBullishOnly: boolean;
  sectorOn: boolean;
  sectorMode: string;
  sectorNames: string[];
  rows: StockRow[];
  tradeDate: string | null;
}

export const screenerState: ScreenerState = {
  strategies: [],
  conds: [],
  nameQuery: "",
  mentionOn: false,
  mentionDays: 7,
  mentionUser: "",
  mentionBullishOnly: false,
  sectorOn: false,
  sectorMode: "manual",
  sectorNames: [],
  rows: [],
  tradeDate: null,
};

// 全站统一的手机端断点：768px（antd 的 md），替代过去 App.tsx 用 lg、Posts.tsx 用 md 各自为政的写法。
import { Grid } from "antd";

const { useBreakpoint } = Grid;

export function useIsMobile(): boolean {
  const screens = useBreakpoint();
  return !screens.md;
}

// 让当前页面告诉菲比"用户现在在看什么"：各页面用 usePageContext(text) 注册一段简短摘要，
// FeibiWidget 发问时把它当成上下文一起带给后端。模块级单例——不用 Context/Provider 那套，
// 菲比本身也是脱离 React 树挂在 body 上的（见 live2d.ts），保持同一种"跨页面共享"的方式。
import { useEffect } from "react";

let current = "";

export function setPageContext(text: string) {
  current = text;
}

export function getPageContext(): string {
  return current;
}

/** 页面组件里调用：挂载时设置，卸载时清空，内容变化（比如加载完数据）时更新。 */
export function usePageContext(text: string) {
  useEffect(() => {
    setPageContext(text);
    return () => setPageContext("");
  }, [text]);
}

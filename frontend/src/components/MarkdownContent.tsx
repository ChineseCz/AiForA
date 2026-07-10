// 渲染后端返回的 markdown-to-html：给每个表格套一层横向滚动容器（避免手机端单元格被挤成竖排文字）；
// 移动端再按表头文字（而不是列序号）把“代码”列摘掉——旧总结是4列(名称/代码/方向/理由)，
// 新总结已经是3列，按文字匹配才能两种都兼容。
import { Grid } from "antd";
import { useEffect, useRef, type CSSProperties } from "react";

const { useBreakpoint } = Grid;

function enhanceTables(root: HTMLElement, dropCodeColumn: boolean) {
  root.querySelectorAll("table").forEach((table) => {
    if (dropCodeColumn) {
      const headerRow = table.querySelector("tr");
      const headerCells = headerRow ? Array.from(headerRow.children) : [];
      const codeIdx = headerCells.findIndex((c) => c.textContent?.trim() === "代码");
      if (codeIdx >= 0) {
        table.querySelectorAll("tr").forEach((row) => {
          row.children[codeIdx]?.remove();
        });
      }
    }
    if (table.parentElement?.classList.contains("table-scroll")) return;
    const wrapper = document.createElement("div");
    wrapper.className = "table-scroll";
    table.parentElement?.insertBefore(wrapper, table);
    wrapper.appendChild(table);
  });
}

export default function MarkdownContent({ html, className, style }: {
  html: string; className?: string; style?: CSSProperties;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const screens = useBreakpoint();
  const isMobile = !screens.md;

  useEffect(() => {
    if (ref.current) enhanceTables(ref.current, isMobile);
  }, [html, isMobile]);

  return (
    <div ref={ref} className={className} style={style} dangerouslySetInnerHTML={{ __html: html }} />
  );
}

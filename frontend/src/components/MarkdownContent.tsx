// 渲染后端返回的 markdown-to-html：给每个表格套一层横向滚动容器（避免手机端单元格被挤成竖排文字）；
// 移动端再按表头文字（而不是列序号）把“代码”列摘掉——旧总结是4列(名称/代码/方向/理由)，
// 新总结已经是3列，按文字匹配才能两种都兼容。
import { Grid } from "antd";
import { useEffect, useRef, type CSSProperties } from "react";

const { useBreakpoint } = Grid;

// "方向"列的取值是模型自由生成的短语（看多/买入/加仓 vs 看空/卖出/减仓等），没有固定枚举，
// 用关键词兜底判断多空而不是精确匹配，未命中的（如"中性"/"观察"）保持默认颜色不上色。
const BULL_RE = /看多|买入|加仓|增持|多头/;
const BEAR_RE = /看空|卖出|减仓|清仓|空头/;

function colorizeDirectionColumn(table: HTMLTableElement) {
  const headerRow = table.querySelector("tr");
  const headerCells = headerRow ? Array.from(headerRow.children) : [];
  const dirIdx = headerCells.findIndex((c) => c.textContent?.trim().startsWith("方向"));
  if (dirIdx < 0) return;
  table.querySelectorAll("tr").forEach((row, i) => {
    if (i === 0) return;
    const cell = row.children[dirIdx];
    if (!cell) return;
    const text = cell.textContent ?? "";
    if (BULL_RE.test(text)) cell.classList.add("dir-bull");
    else if (BEAR_RE.test(text)) cell.classList.add("dir-bear");
  });
}

// "提到的标的"表格里"名称"固定是第一列（新旧两种表头格式都如此），标的名称本身也要标蓝，
// 跟正文里提及的标的名称保持一致的视觉提示。
function colorizeNameColumn(table: HTMLTableElement) {
  table.querySelectorAll("tr").forEach((row, i) => {
    if (i === 0) return;
    row.children[0]?.classList.add("ticker-name");
  });
}

// 手机端窄屏放不下"名称/方向/作者理由"这种长文本列，横向滚动表格要来回拖才能看全一行，
// 体验很差 —— 干脆把每一行拆成一张竖排卡片（首列当标题，其余列变成"表头：内容"两行），
// 不需要横向滚动就能看全一条。桌面端保留原始表格+横向滚动。
function tableToCardList(table: HTMLTableElement, isTickerTable: boolean): HTMLElement {
  const headerRow = table.querySelector("tr");
  const headers = headerRow ? Array.from(headerRow.children).map((c) => c.textContent?.trim() ?? "") : [];
  const bodyRows = Array.from(table.querySelectorAll("tr")).slice(1);
  const list = document.createElement("div");
  list.className = "md-table-cards";
  bodyRows.forEach((row) => {
    const cells = Array.from(row.children);
    if (!cells.length) return;
    const card = document.createElement("div");
    card.className = "md-table-card";
    const title = document.createElement("div");
    title.className = isTickerTable ? "md-table-card-title ticker-name" : "md-table-card-title";
    title.innerHTML = cells[0].innerHTML;
    card.appendChild(title);
    for (let i = 1; i < cells.length; i++) {
      const label = headers[i] ?? "";
      const cellText = cells[i].textContent ?? "";
      const rowEl = document.createElement("div");
      rowEl.className = "md-table-card-row";
      const labelEl = document.createElement("span");
      labelEl.className = "md-table-card-label";
      labelEl.textContent = label;
      const valueEl = document.createElement("span");
      valueEl.className = "md-table-card-value";
      if (label === "方向") {
        if (BULL_RE.test(cellText)) valueEl.classList.add("dir-bull");
        else if (BEAR_RE.test(cellText)) valueEl.classList.add("dir-bear");
      }
      valueEl.innerHTML = cells[i].innerHTML;
      rowEl.appendChild(labelEl);
      rowEl.appendChild(valueEl);
      card.appendChild(rowEl);
    }
    list.appendChild(card);
  });
  return list;
}

// "提到的标的"表格在周/月总结里常常有几十行，无论桌面表格还是手机卡片都太长——
// 超过阈值的行/卡片先隐藏，插入一个"展开全部 N 条 / 收起"按钮，纯 DOM 事件切换，不需要 React 状态。
const COLLAPSE_THRESHOLD = 8;

function hasDirectionColumn(table: HTMLTableElement): boolean {
  const headerRow = table.querySelector("tr");
  const headerCells = headerRow ? Array.from(headerRow.children) : [];
  return headerCells.some((c) => c.textContent?.trim().startsWith("方向"));
}

function addCollapseToggle(anchor: HTMLElement, items: HTMLElement[], total: number) {
  if (items.length <= COLLAPSE_THRESHOLD) return;
  const extra = items.slice(COLLAPSE_THRESHOLD);
  extra.forEach((el) => el.classList.add("md-row-hidden"));
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "md-collapse-toggle";
  btn.textContent = `展开全部 ${total} 条`;
  let expanded = false;
  btn.addEventListener("click", () => {
    expanded = !expanded;
    extra.forEach((el) => el.classList.toggle("md-row-hidden", !expanded));
    btn.textContent = expanded ? "收起" : `展开全部 ${total} 条`;
  });
  anchor.insertAdjacentElement("afterend", btn);
}

// 桌面端"提到的标的"默认还原成旧版纯表格样式，额外提供一个按钮切换到卡片视图——
// 两种视图都提前搭好（各自套自己的折叠/展开），切换只是显隐两个容器，不重新构建 DOM。
function buildViewToggle(tableView: HTMLElement, cardView: HTMLElement): HTMLElement {
  const bar = document.createElement("div");
  bar.className = "md-view-toggle";
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "md-view-toggle-btn";
  let showingCard = false;
  const sync = () => {
    tableView.classList.toggle("md-view-hidden", showingCard);
    cardView.classList.toggle("md-view-hidden", !showingCard);
    btn.textContent = showingCard ? "切换为表格视图" : "切换为卡片视图";
  };
  btn.addEventListener("click", () => {
    showingCard = !showingCard;
    sync();
  });
  sync();
  bar.appendChild(btn);
  return bar;
}

function enhanceTables(root: HTMLElement, isMobile: boolean) {
  root.querySelectorAll("table").forEach((table) => {
    const isTickerTable = hasDirectionColumn(table as HTMLTableElement);
    if (isMobile) {
      const headerRow = table.querySelector("tr");
      const headerCells = headerRow ? Array.from(headerRow.children) : [];
      const codeIdx = headerCells.findIndex((c) => c.textContent?.trim() === "代码");
      if (codeIdx >= 0) {
        table.querySelectorAll("tr").forEach((row) => {
          row.children[codeIdx]?.remove();
        });
      }
      const cardList = tableToCardList(table as HTMLTableElement, isTickerTable);
      table.parentElement?.replaceChild(cardList, table);
      if (isTickerTable) {
        const cards = Array.from(cardList.children) as HTMLElement[];
        addCollapseToggle(cardList, cards, cards.length);
      }
      return;
    }
    colorizeDirectionColumn(table as HTMLTableElement);
    if (isTickerTable) colorizeNameColumn(table as HTMLTableElement);
    if (table.parentElement?.classList.contains("table-scroll") || table.closest(".md-view-toggle-group")) return;
    const wrapper = document.createElement("div");
    wrapper.className = "table-scroll";
    table.parentElement?.insertBefore(wrapper, table);
    wrapper.appendChild(table);
    if (isTickerTable) {
      const bodyRows = Array.from(table.querySelectorAll("tr")).slice(1) as HTMLElement[];
      addCollapseToggle(wrapper, bodyRows, bodyRows.length);

      // 标的表格额外提供卡片视图：另建一份卡片列表，默认隐藏，配一个切换按钮显隐两者。
      const cardList = tableToCardList(table as HTMLTableElement, true);
      const cards = Array.from(cardList.children) as HTMLElement[];
      addCollapseToggle(cardList, cards, cards.length);
      cardList.classList.add("md-view-hidden");

      const group = document.createElement("div");
      group.className = "md-view-toggle-group";
      wrapper.parentElement?.insertBefore(group, wrapper);
      group.appendChild(wrapper);
      group.appendChild(cardList);
      group.insertBefore(buildViewToggle(wrapper, cardList), wrapper);
    }
  });
}

export default function MarkdownContent({ html, className, style }: {
  html: string; className?: string; style?: CSSProperties;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const screens = useBreakpoint();
  const isMobile = !screens.md;

  useEffect(() => {
    if (!ref.current) return;
    // enhanceTables 会直接摘掉/替换原始 <table>，是破坏性操作；isMobile 的初值来自 antd
    // useBreakpoint，首次渲染前必定是 {}（视为手机端），随后才修正为真实值触发二次渲染——
    // 若不重置，第二次运行时表格已被第一次替换掉，找不到东西可处理。每次先用原始 html
    // 重置 DOM，保证 enhanceTables 总是处理干净的原始表格。
    ref.current.innerHTML = html;
    enhanceTables(ref.current, isMobile);
  }, [html, isMobile]);

  return (
    <div ref={ref} className={className} style={style} dangerouslySetInnerHTML={{ __html: html }} />
  );
}

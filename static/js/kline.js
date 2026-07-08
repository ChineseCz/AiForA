(function () {
  const code = window.STOCK_CODE;
  const titleEl = document.getElementById("klineTitle");
  const subEl = document.getElementById("klineSub");
  const chartEl = document.getElementById("klineChart");

  const COLOR_UP = "#f6465d";
  const COLOR_DOWN = "#0ecb81";
  const AXIS_LABEL = "#8695ab";
  const SPLIT_LINE = "#1f2a3a";

  function fmt(v, digits) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    return Number(v).toFixed(digits === undefined ? 2 : digits);
  }
  function fmtVol(v) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    return Number(v).toLocaleString("zh-CN") + " 手";
  }
  function fmtBool(v) {
    return v ? "是" : "否";
  }
  function fmtNum0(v) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    return Number(v).toLocaleString("zh-CN", { maximumFractionDigits: 0 });
  }
  function escHtml(s) {
    return (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  async function load() {
    subEl.textContent = "加载中…";
    let data;
    try {
      data = await fetch(`/api/stock/kline?code=${encodeURIComponent(code)}`).then((r) => r.json());
    } catch (e) {
      subEl.textContent = "加载失败：" + e;
      return;
    }
    if (data.error) {
      subEl.textContent = data.error;
      return;
    }
    titleEl.textContent = `${data.name || code} (${code})`;
    if (!data.bars || !data.bars.length) {
      subEl.textContent = "历史数据不足（需要至少23个交易日），请先在选股页运行「历史K线回补」";
      return;
    }
    const strictDays = data.bars.filter((b) => b.strict_ok).length;
    const looseDays = data.bars.filter((b) => b.loose_ok).length;
    const goldenDays = data.bars.filter((b) => b.golden_ok).length;
    const midReverseDays = data.bars.filter((b) => b.mid_reverse_ok).length;
    const stopLossDays = data.bars.filter((b) => b.stop_loss_ok).length;
    subEl.textContent =
      `共 ${data.bars.length} 个交易日 · 严格买点 ${strictDays} 天 · 宽松买点 ${looseDays} 天 · 金叉买点 ${goldenDays} 天 · ` +
      `中期反转 ${midReverseDays} 天 · 短期止损 ${stopLossDays} 天`;
    render(data.bars);
  }

  function render(bars) {
    const dates = bars.map((b) => b.trade_date);
    const kdata = bars.map((b) => [b.open, b.close, b.low, b.high]);

    const chart = echarts.init(chartEl, null, { renderer: "canvas" });

    const grids = [
      { top: "3%", height: "25%" },
      { top: "31%", height: "9%" },
      { top: "44%", height: "11%" },
      { top: "58%", height: "11%" },
      { top: "72%", height: "7%" },
      { top: "82%", height: "7%" },
    ];
    grids.forEach((g) => {
      g.left = "3%";
      g.right = "3%";
    });

    const boolGrids = [4, 5];
    const names = ["K线", "成交量", "MACD", "KDJ", "买点信号", "卖点信号"];
    const xAxes = grids.map((g, i) => ({
      type: "category",
      data: dates,
      gridIndex: i,
      boundaryGap: false,
      axisLine: { lineStyle: { color: SPLIT_LINE } },
      axisLabel: { color: AXIS_LABEL, show: i === grids.length - 1 },
      axisTick: { show: false },
      splitLine: { show: false },
      axisPointer: { label: { show: i === grids.length - 1 } },
    }));
    const yAxes = grids.map((g, i) => ({
      gridIndex: i,
      scale: !boolGrids.includes(i),
      min: boolGrids.includes(i) ? -0.2 : null,
      max: boolGrids.includes(i) ? 1.2 : null,
      interval: boolGrids.includes(i) ? 1 : null,
      name: names[i],
      nameLocation: "end",
      nameGap: 4,
      nameTextStyle: { color: AXIS_LABEL, fontSize: 12, align: "left" },
      axisLine: { show: false },
      axisLabel: { color: AXIS_LABEL, show: !boolGrids.includes(i) },
      splitLine: { lineStyle: { color: SPLIT_LINE } },
    }));

    function maSeries(field, label, color) {
      return {
        name: label, type: "line", xAxisIndex: 0, yAxisIndex: 0,
        data: bars.map((b) => b[field]), showSymbol: false,
        lineStyle: { width: 1, color }, z: 2,
      };
    }
    function stepSeries(field, label, color, axisIndex) {
      return {
        name: label, type: "line", step: "end", xAxisIndex: axisIndex, yAxisIndex: axisIndex,
        data: bars.map((b) => (b[field] ? 1 : 0)), showSymbol: false,
        lineStyle: { width: 1.5, color }, areaStyle: { opacity: 0.12, color },
      };
    }
    function signalScatter(field, label, color, lane, above) {
      const data = [];
      bars.forEach((b) => {
        if (!b[field]) return;
        const base = above ? b.high : b.low;
        const factor = above ? 1 + 0.012 * (lane + 1) : 1 - 0.012 * (lane + 1);
        data.push([b.trade_date, base * factor]);
      });
      return {
        name: label, type: "scatter", xAxisIndex: 0, yAxisIndex: 0,
        data, symbol: "triangle", symbolSize: 9,
        symbolRotate: above ? 180 : 0,
        itemStyle: { color }, z: 3,
      };
    }

    const option = {
      backgroundColor: "transparent",
      textStyle: { color: "#e6edf6" },
      animation: false,
      axisPointer: { link: [{ xAxisIndex: "all" }] },
      legend: {
        top: 0, left: "center",
        data: ["K线", "MA5", "MA10", "MA20", "严格买点", "宽松买点", "金叉买点", "中期反转", "短期止损"],
        textStyle: { color: AXIS_LABEL, fontSize: 11 },
      },
      grid: grids,
      xAxis: xAxes,
      yAxis: yAxes,
      dataZoom: [
        { type: "inside", xAxisIndex: [0, 1, 2, 3, 4, 5], start: 60, end: 100 },
        { type: "slider", xAxisIndex: [0, 1, 2, 3, 4, 5], bottom: 4, height: 14, start: 60, end: 100 },
      ],
      tooltip: {
        trigger: "axis", axisPointer: { type: "cross" },
        showContent: false,
      },
      series: [
        {
          name: "K线", type: "candlestick", xAxisIndex: 0, yAxisIndex: 0, data: kdata,
          itemStyle: { color: COLOR_UP, color0: COLOR_DOWN, borderColor: COLOR_UP, borderColor0: COLOR_DOWN },
        },
        maSeries("ma5", "MA5", "#f0b90b"),
        maSeries("ma10", "MA10", "#60a5fa"),
        maSeries("ma20", "MA20", "#c792ea"),
        signalScatter("strict_ok", "严格买点", "#f6465d", 0, false),
        signalScatter("loose_ok", "宽松买点", "#3b82f6", 1, false),
        signalScatter("golden_ok", "金叉买点", "#22d3ee", 2, false),
        signalScatter("mid_reverse_ok", "中期反转", "#ff6b35", 0, true),
        signalScatter("stop_loss_ok", "短期止损", "#8b5cf6", 1, true),
        {
          name: "成交量", type: "bar", xAxisIndex: 1, yAxisIndex: 1,
          data: bars.map((b) => ({
            value: b.volume || 0,
            itemStyle: { color: b.close >= b.open ? COLOR_UP : COLOR_DOWN },
          })),
        },
        { name: "DIF", type: "line", xAxisIndex: 2, yAxisIndex: 2, data: bars.map((b) => b.dif), showSymbol: false, lineStyle: { width: 1, color: "#60a5fa" } },
        { name: "DEA", type: "line", xAxisIndex: 2, yAxisIndex: 2, data: bars.map((b) => b.dea), showSymbol: false, lineStyle: { width: 1, color: "#f0b90b" } },
        {
          name: "MACD", type: "bar", xAxisIndex: 2, yAxisIndex: 2,
          data: bars.map((b) => b.macd),
          itemStyle: { color: (p) => (p.value >= 0 ? COLOR_UP : COLOR_DOWN) },
        },
        { name: "K", type: "line", xAxisIndex: 3, yAxisIndex: 3, data: bars.map((b) => b.k), showSymbol: false, lineStyle: { width: 1, color: "#60a5fa" } },
        { name: "D", type: "line", xAxisIndex: 3, yAxisIndex: 3, data: bars.map((b) => b.d), showSymbol: false, lineStyle: { width: 1, color: "#f0b90b" } },
        { name: "J", type: "line", xAxisIndex: 3, yAxisIndex: 3, data: bars.map((b) => b.j), showSymbol: false, lineStyle: { width: 1, color: "#c792ea" } },
        stepSeries("strict_ok", "严格买点", "#f6465d", 4),
        stepSeries("loose_ok", "宽松买点", "#3b82f6", 4),
        stepSeries("golden_ok", "金叉买点", "#22d3ee", 4),
        stepSeries("mid_reverse_ok", "中期反转", "#ff6b35", 5),
        stepSeries("stop_loss_ok", "短期止损", "#8b5cf6", 5),
      ],
    };

    chart.setOption(option);

    const els = {
      date: document.getElementById("bDate"), open: document.getElementById("bOpen"),
      close: document.getElementById("bClose"), pct: document.getElementById("bPct"),
      high: document.getElementById("bHigh"), low: document.getElementById("bLow"),
      vol: document.getElementById("bVol"), ma5: document.getElementById("bMa5"),
      ma10: document.getElementById("bMa10"), ma20: document.getElementById("bMa20"),
      ovVol: document.getElementById("ovVol"), ovMacd: document.getElementById("ovMacd"),
      ovKdj: document.getElementById("ovKdj"), ovSignal: document.getElementById("ovSignal"),
      ovSell: document.getElementById("ovSell"),
    };

    function updatePanels(idx) {
      const b = bars[idx];
      if (!b) return;
      const prevClose = idx > 0 ? bars[idx - 1].close : null;
      const pct = prevClose ? (b.close / prevClose - 1) * 100 : null;
      els.date.textContent = b.trade_date;
      els.open.textContent = fmt(b.open);
      els.close.textContent = fmt(b.close);
      els.pct.textContent = pct === null ? "—" : `${pct >= 0 ? "+" : ""}${fmt(pct)}%`;
      els.pct.className = pct > 0 ? "up" : pct < 0 ? "down" : "";
      els.high.textContent = fmt(b.high);
      els.low.textContent = fmt(b.low);
      els.vol.textContent = fmtVol(b.volume);
      els.ma5.textContent = fmt(b.ma5);
      els.ma10.textContent = fmt(b.ma10);
      els.ma20.textContent = fmt(b.ma20);

      els.ovVol.textContent = `成交量 ${fmtVol(b.volume)}`;
      els.ovMacd.textContent = `DIF ${fmt(b.dif)}  DEA ${fmt(b.dea)}  MACD ${fmt(b.macd)}`;
      els.ovKdj.textContent = `K ${fmt(b.k)}  D ${fmt(b.d)}  J ${fmt(b.j)}`;
      els.ovSignal.textContent = `严格买点 ${fmtBool(b.strict_ok)}  宽松买点 ${fmtBool(b.loose_ok)}  金叉买点 ${fmtBool(b.golden_ok)}`;
      els.ovSell.textContent = `中期反转 ${fmtBool(b.mid_reverse_ok)}  短期止损 ${fmtBool(b.stop_loss_ok)}`;
    }

    chart.on("updateAxisPointer", (event) => {
      const axisInfo = event.axesInfo && event.axesInfo[0];
      if (axisInfo) updatePanels(axisInfo.value);
    });
    updatePanels(bars.length - 1);

    window.addEventListener("resize", () => chart.resize());
  }

  load();
  loadFundamentals();
  loadStockNews();

  async function loadFundamentals() {
    const statusEl = document.getElementById("fundaStatus");
    let data;
    try {
      data = await fetch(`/api/stock/fundamentals?code=${encodeURIComponent(code)}`).then((r) => r.json());
    } catch (e) {
      statusEl.textContent = "加载失败：" + e;
      return;
    }
    if (data.error) {
      statusEl.textContent = data.error;
      return;
    }
    statusEl.textContent = "";
    renderFinance(data.finance, data.quote);
    renderSectors(data.sectors);
    renderMentions(data.mentions);
  }

  function renderFinance(fin, quote) {
    const box = document.getElementById("fundaFinance");
    quote = quote || {};
    const items = [
      ["市盈率(动态)", fmt(quote.pe_ttm)],
      ["市净率", fmt(quote.pb)],
      ["总市值(万元)", fmtNum0(quote.total_mv)],
      ["流通市值(万元)", fmtNum0(quote.circ_mv)],
    ];
    if (fin) {
      items.push(
        ["报告期", fin.report_date || "—"],
        ["EPS", fmt(fin.eps)],
        ["ROE(%)", fmt(fin.roe)],
        ["净利润同比(%)", fmt(fin.net_profit_yoy)],
        ["营收同比(%)", fmt(fin.revenue_yoy)],
        ["毛利率(%)", fmt(fin.gross_margin)],
      );
    }
    let html = items
      .map(([label, value]) => `<div class="funda-item"><span class="fi-label">${label}</span><span class="fi-value">${value}</span></div>`)
      .join("");
    if (!fin) {
      html += `<div class="funda-empty">暂无财务数据，请先在选股页运行「财务指标同步」</div>`;
    }
    box.innerHTML = html;
  }

  function renderSectors(sectors) {
    const box = document.getElementById("fundaSectors");
    if (!sectors || !sectors.length) {
      box.innerHTML = `<div class="funda-empty">暂无板块数据，请先在选股页运行「板块成分股全量同步」</div>`;
      return;
    }
    box.innerHTML = sectors
      .map((s) => `<span class="funda-tag ${s.kind === "concept" ? "concept" : ""}">${escHtml(s.sector)}</span>`)
      .join("");
  }

  function renderMentions(mentions) {
    const box = document.getElementById("fundaMentions");
    if (!mentions || !mentions.length) {
      box.innerHTML = `<p class="muted funda-empty">近期没有被跟踪的大V提及。</p>`;
      return;
    }
    box.innerHTML = mentions
      .map((p) => {
        const text = p.text || "";
        const trimmed = text.length > 200 ? text.slice(0, 200) + "…" : text;
        return `<div class="post">
          <div class="post-top">
            <span class="post-date">${escHtml(p.date)} · ${escHtml(p.user_name || "")}</span>
            <a class="post-link" href="${escHtml(p.url)}" target="_blank" rel="noopener">原帖 ↗</a>
          </div>
          ${p.title ? `<div class="post-title">${escHtml(p.title)}</div>` : ""}
          <div class="post-text open">${escHtml(trimmed)}</div>
        </div>`;
      })
      .join("");
  }

  async function loadStockNews() {
    const box = document.getElementById("fundaNews");
    let data;
    try {
      data = await fetch(`/api/stock/news?code=${encodeURIComponent(code)}`).then((r) => r.json());
    } catch (e) {
      box.innerHTML = `<p class="muted funda-empty">新闻加载失败：${escHtml(String(e))}</p>`;
      return;
    }
    if (data.error) {
      box.innerHTML = `<p class="muted funda-empty">${escHtml(data.error)}</p>`;
      return;
    }
    renderNews(data.items);
  }

  function renderNews(items) {
    const box = document.getElementById("fundaNews");
    if (!items || !items.length) {
      box.innerHTML = `<p class="muted funda-empty">近期没有相关新闻。</p>`;
      return;
    }
    box.innerHTML = items
      .map(
        (n) => `<div class="post">
          <div class="post-top">
            <span class="post-date">${escHtml(n.date)} ${escHtml(n.time)}</span>
            <a class="post-link" href="${escHtml(n.url)}" target="_blank" rel="noopener">查看 ↗</a>
          </div>
          <div class="post-title">${escHtml(n.title)}</div>
        </div>`
      )
      .join("");
  }
})();

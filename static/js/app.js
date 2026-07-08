/* 雪球大V看板 —— 前端逻辑 */
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);
const api = (u) => fetch(u).then((r) => r.json());
const esc = (s) => (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const state = {
  user: "",
  view: "dashboard",
  postsPage: 1,
  sumType: "daily",
  sumKey: "",
  charts: {},
  screenerSub: "filter",
  groups: [],
  activeGroupId: null,
  sectorCatalog: [],
};

const VIEW_META = {
  dashboard: ["看板", "市场观点全景"],
  posts: ["帖子流", "浏览与检索原始帖子"],
  summary: ["AI 总结", "日 / 周 / 月 / 年 / 精华归纳"],
  screener: ["选股", "A股条件筛选（收盘后行情，仅供参考）"],
};

const DEFAULT_MOBILE_USER = "冰冰小美";

/* ---------- 初始化 ---------- */
async function init() {
  const users = await api("/api/users");
  const sel = $("#userSelect");
  sel.innerHTML =
    `<option value="">全部大V</option>` +
    users.map((u) => `<option value="${u.id}">${esc(u.name)}</option>`).join("");

  const isMobile = window.matchMedia("(max-width: 760px)").matches;
  if (isMobile) {
    const target = users.find((u) => u.name === DEFAULT_MOBILE_USER);
    if (target) {
      sel.value = target.id;
      state.user = target.id;
    }
  }

  sel.addEventListener("change", () => {
    state.user = sel.value;
    reloadCurrent();
  });

  $$(".nav-item").forEach((el) =>
    el.addEventListener("click", () => { switchView(el.dataset.view); closeSidebar(); })
  );
  $("#refreshBtn").addEventListener("click", reloadCurrent);

  // 移动端侧边栏抽屉
  $("#menuToggle").addEventListener("click", () => document.body.classList.toggle("sidebar-open"));
  $("#sidebarOverlay").addEventListener("click", closeSidebar);

  // 帖子流
  $("#pSearch").addEventListener("click", () => { state.postsPage = 1; loadPosts(); });
  $("#pQuery").addEventListener("keydown", (e) => { if (e.key === "Enter") { state.postsPage = 1; loadPosts(); } });
  $("#prevPage").addEventListener("click", () => { if (state.postsPage > 1) { state.postsPage--; loadPosts(); } });
  $("#nextPage").addEventListener("click", () => { state.postsPage++; loadPosts(); });

  // 总结
  $$("#periodTabs .tab").forEach((t) =>
    t.addEventListener("click", () => {
      $$("#periodTabs .tab").forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      state.sumType = t.dataset.type;
      loadSummaryKeys();
    })
  );
  $("#sumGenBtn").addEventListener("click", startSummarize);
  $("#askBtn").addEventListener("click", askAboutSummary);

  window.addEventListener("resize", () => Object.values(state.charts).forEach((c) => c && c.resize()));

  // 采集按钮 + 自动采集设置
  $("#crawlBtn").addEventListener("click", startCrawl);
  const sched = await api("/api/schedule");
  $("#schedEnabled").checked = sched.enabled;
  $("#schedStart").value = sched.start;
  $("#schedInterval").value = sched.interval;
  $("#schedEnd").value = sched.end;
  ["schedEnabled", "schedStart", "schedInterval", "schedEnd"].forEach((id) =>
    $("#" + id).addEventListener("change", saveSchedule)
  );
  pollCrawl(); // 若已有采集在跑，接上进度

  // 选股
  $("#stockSyncBtn").addEventListener("click", startStockSync);
  $("#stockBackfillBtn").addEventListener("click", startStockBackfill);
  $("#stockFinanceSyncBtn").addEventListener("click", startStockFinanceSync);
  $("#sectorSyncBtn").addEventListener("click", startSectorSync);
  $("#sectorMembersSyncBtn").addEventListener("click", startSectorMembersSync);
  $("#sectorMode").addEventListener("change", updateSectorModeUI);
  $("#sectorSearch").addEventListener("input", renderSectorOptions);
  $("#presetRunBtn").addEventListener("click", runPreset);
  $("#condAddBtn").addEventListener("click", addCondRow);
  $("#screenBtn").addEventListener("click", runScreen);
  $$("#screenerTabs .stab").forEach((t) =>
    t.addEventListener("click", () => switchScreenerSub(t.dataset.sub))
  );
  $("#screenSelectAll").addEventListener("change", (e) => {
    $$("#screenResult .rowChk").forEach((c) => { c.checked = e.target.checked; });
  });
  $("#screenAddToGroupBtn").addEventListener("click", addSelectedToGroup);
  $("#groupCreateBtn").addEventListener("click", createGroup);
  $("#groupNameInput").addEventListener("keydown", (e) => { if (e.key === "Enter") createGroup(); });

  switchView(isMobile ? "summary" : "dashboard");
}

/* ---------- 采集 ---------- */
let crawlTimer = null;

async function startCrawl() {
  const summarize = $("#crawlSummarize").checked;
  const r = await fetch("/api/crawl", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ summarize }),
  }).then((x) => x.json());
  if (!r.started && r.running) {
    // 已在运行，直接接上
  }
  pollCrawl();
}

function renderCrawlStatus(s) {
  const box = $("#crawlStatus");
  const btn = $("#crawlBtn");
  const last = s.log && s.log.length ? s.log[s.log.length - 1] : "";
  if (s.running) {
    btn.disabled = true;
    btn.textContent = "采集中…";
    box.innerHTML =
      `<div class="cs-run"><span class="spinner"></span>${s.source || ""}采集中…</div>` +
      `<div class="cs-line">${esc(last)}</div>`;
  } else {
    btn.disabled = false;
    btn.textContent = "▶ 立即采集";
    if (s.finished_at) {
      const cls = s.error ? "cs-err" : "cs-ok";
      const tip = s.error ? `出错：${esc(s.error)}` : esc(last || "完成");
      box.innerHTML = `<div class="${cls}">${tip}</div><div class="cs-line">${s.finished_at}</div>`;
    } else {
      box.innerHTML = "";
    }
  }
}

async function pollCrawl() {
  const s = await api("/api/crawl/status");
  renderCrawlStatus(s);
  if (crawlTimer) { clearInterval(crawlTimer); crawlTimer = null; }
  if (s.running) {
    crawlTimer = setInterval(async () => {
      const st = await api("/api/crawl/status");
      renderCrawlStatus(st);
      if (!st.running) {
        clearInterval(crawlTimer); crawlTimer = null;
        reloadCurrent(); // 采集完刷新当前视图
        refreshUsers();
      }
    }, 2000);
  }
}

async function saveSchedule() {
  await fetch("/api/schedule", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      enabled: $("#schedEnabled").checked,
      start: $("#schedStart").value,
      end: $("#schedEnd").value,
      interval: parseInt($("#schedInterval").value) || 30,
    }),
  });
}

async function refreshUsers() {
  const users = await api("/api/users");
  const sel = $("#userSelect");
  const cur = sel.value;
  sel.innerHTML =
    `<option value="">全部大V</option>` +
    users.map((u) => `<option value="${u.id}">${esc(u.name)}</option>`).join("");
  sel.value = cur;
}

function closeSidebar() {
  document.body.classList.remove("sidebar-open");
}

function wrapTables(root) {
  root.querySelectorAll("table").forEach((t) => {
    if (t.parentElement.classList.contains("table-scroll")) return;
    const wrap = document.createElement("div");
    wrap.className = "table-scroll";
    t.replaceWith(wrap);
    wrap.appendChild(t);
  });
}

function switchView(view) {
  state.view = view;
  $$(".nav-item").forEach((el) => el.classList.toggle("active", el.dataset.view === view));
  $$(".view").forEach((v) => v.classList.add("hidden"));
  $(`#view-${view}`).classList.remove("hidden");
  const [title, sub] = VIEW_META[view];
  $("#viewTitle").textContent = title;
  $("#viewSub").textContent = sub;
  reloadCurrent();
}

function reloadCurrent() {
  if (state.view === "dashboard") loadDashboard();
  else if (state.view === "posts") loadPosts();
  else if (state.view === "screener") loadScreener();
  else loadSummaryKeys();
}

/* ---------- 看板 ---------- */
async function loadDashboard() {
  const d = await api(`/api/overview?user=${state.user}`);
  $("#spanBadge").textContent = d.first === "-" ? "暂无数据" : `${d.first} ~ ${d.last}`;

  const cards = [
    { label: "帖子总数", value: d.total.toLocaleString(), foot: "已入库", accent: true },
    { label: "活跃天数", value: d.active_days, foot: "有发帖的天数" },
    { label: "跟踪大V", value: d.user_count, foot: "已抓取" },
    { label: "最近更新", value: d.last === "-" ? "—" : d.last, foot: "最新帖子日期" },
  ];
  $("#statCards").innerHTML = cards
    .map(
      (c) => `<div class="card ${c.accent ? "accent" : ""}">
        <div class="c-label">${c.label}</div>
        <div class="c-value">${c.value}</div>
        <div class="c-foot">${c.foot}</div></div>`
    )
    .join("");

  renderHeatmap(d.daily);
  renderMonthly(d.monthly);
  $("#latestList").innerHTML = d.latest.length
    ? d.latest.map(postCard).join("")
    : `<p class="muted center">暂无帖子，先在命令行运行 <code>python main.py crawl</code></p>`;
  bindPostToggles();
}

function chart(id) {
  if (!state.charts[id]) state.charts[id] = echarts.init($(`#${id}`), null, { renderer: "canvas" });
  return state.charts[id];
}

function renderHeatmap(daily) {
  if (typeof echarts === "undefined") return;
  const map = Object.fromEntries(daily.map((x) => [x.date, x.n]));
  const dates = daily.map((x) => x.date);
  const year = dates.length ? dates[dates.length - 1].slice(0, 4) : String(new Date().getFullYear());
  const max = Math.max(1, ...daily.map((x) => x.n));
  const data = daily.filter((x) => x.date.startsWith(year)).map((x) => [x.date, x.n]);
  chart("heatmap").setOption({
    tooltip: { formatter: (p) => `${p.value[0]}<br/>发帖 ${p.value[1]} 条` },
    visualMap: { min: 0, max, calculable: false, orient: "horizontal", left: "center", bottom: 0,
      inRange: { color: ["#16233a", "#1e4b8f", "#3b82f6", "#8fc0ff"] }, textStyle: { color: "#8695ab" }, itemHeight: 90 },
    calendar: { top: 20, left: 30, right: 10, cellSize: ["auto", 14], range: year,
      itemStyle: { color: "#0e1420", borderColor: "#0a0e17", borderWidth: 2 },
      splitLine: { show: false }, yearLabel: { show: false },
      dayLabel: { color: "#5f6d82", nameMap: "cn" }, monthLabel: { color: "#8695ab", nameMap: "cn" } },
    series: { type: "heatmap", coordinateSystem: "calendar", data },
  }, true);
}

function renderMonthly(monthly) {
  if (typeof echarts === "undefined") return;
  chart("monthlyChart").setOption({
    grid: { top: 20, left: 40, right: 16, bottom: 30 },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: monthly.map((m) => m.ym), axisLabel: { color: "#8695ab" }, axisLine: { lineStyle: { color: "#1f2a3a" } } },
    yAxis: { type: "value", axisLabel: { color: "#8695ab" }, splitLine: { lineStyle: { color: "#141d2c" } } },
    series: [{ type: "bar", data: monthly.map((m) => m.n), barMaxWidth: 34,
      itemStyle: { borderRadius: [4, 4, 0, 0], color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: "#60a5fa" }, { offset: 1, color: "#1d4ed8" }]) } }],
  }, true);
}

/* ---------- 帖子卡片 ---------- */
function postCard(p) {
  const text = esc(p.text || "");
  const long = text.length > 260;
  return `<div class="post">
    <div class="post-top">
      <span class="post-date">${p.date}</span>
      <a class="post-link" href="${p.url}" target="_blank" rel="noopener">原帖 ↗</a>
    </div>
    ${p.title ? `<div class="post-title">${esc(p.title)}</div>` : ""}
    <div class="post-text ${long ? "" : "open"}">${text}</div>
    ${long ? `<span class="post-more">展开全文 ▾</span>` : ""}
    <div class="post-meta">
      <span><b>${p.like_count}</b> 赞</span>
      <span><b>${p.retweet_count}</b> 转</span>
      <span><b>${p.reply_count}</b> 评</span>
      <span><b>${p.fav_count}</b> 收</span>
    </div>
  </div>`;
}

function bindPostToggles() {
  $$(".post-more").forEach((el) =>
    el.addEventListener("click", () => {
      const t = el.previousElementSibling;
      const open = t.classList.toggle("open");
      el.textContent = open ? "收起 ▴" : "展开全文 ▾";
    })
  );
}

/* ---------- 帖子流 ---------- */
async function loadPosts() {
  const q = encodeURIComponent($("#pQuery").value.trim());
  const s = $("#pStart").value, e = $("#pEnd").value;
  const d = await api(`/api/posts?user=${state.user}&page=${state.postsPage}&size=20&q=${q}&start=${s}&end=${e}`);
  $("#postsList").innerHTML = d.items.length
    ? d.items.map(postCard).join("")
    : `<p class="muted center">没有匹配的帖子。</p>`;
  bindPostToggles();
  const pages = Math.max(1, Math.ceil(d.total / d.size));
  $("#pageInfo").textContent = `第 ${d.page} / ${pages} 页 · 共 ${d.total} 条`;
  $("#prevPage").disabled = d.page <= 1;
  $("#nextPage").disabled = d.page >= pages;
}

/* ---------- AI 总结 ---------- */
async function loadSummaryKeys() {
  state.currentSummaryKey = null;
  $("#askInput").value = "";
  $("#askStatus").textContent = "";
  $("#askAnswer").innerHTML = "";
  if (!state.user) {
    $("#keyList").innerHTML = `<p class="muted">请先在左侧选择一个具体大V。</p>`;
    $("#summaryBody").innerHTML = `<p class="muted center">总结按大V存储，请在侧边栏选择一位。</p>`;
    return;
  }
  const keys = await api(`/api/summary_keys?user=${state.user}&type=${state.sumType}`);
  if (!keys.length) {
    $("#keyList").innerHTML = `<p class="muted">该维度暂无总结。</p>`;
    $("#summaryBody").innerHTML = `<p class="muted center">还没有生成，命令行运行：<br><code>python main.py summary ${state.sumType === "highlights" ? "" : state.sumType}</code></p>`;
    return;
  }
  $("#keyList").innerHTML = keys
    .map((k) => `<div class="key-item" data-key="${k}">${k}</div>`)
    .join("");
  $$(".key-item").forEach((el) =>
    el.addEventListener("click", () => {
      $$(".key-item").forEach((x) => x.classList.remove("active"));
      el.classList.add("active");
      loadSummary(el.dataset.key);
    })
  );
  $(".key-item").click();
}

async function loadSummary(key) {
  state.currentSummaryKey = key;
  $("#askInput").value = "";
  $("#askStatus").textContent = "";
  $("#askAnswer").innerHTML = "";
  const d = await api(`/api/summary?user=${state.user}&type=${state.sumType}&key=${encodeURIComponent(key)}`);
  $("#summaryBody").innerHTML = d.found ? d.html : `<p class="muted center">未找到该总结。</p>`;
  wrapTables($("#summaryBody"));
}

async function askAboutSummary() {
  const question = $("#askInput").value.trim();
  if (!question) return;
  if (!state.currentSummaryKey) {
    $("#askStatus").textContent = "请先在左侧选择一份总结";
    return;
  }
  $("#askStatus").textContent = "思考中…";
  $("#askBtn").disabled = true;
  try {
    const r = await fetch("/api/summary/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user: state.user,
        type: state.sumType,
        key: state.currentSummaryKey,
        question,
      }),
    }).then((x) => x.json());
    if (r.error) {
      $("#askStatus").textContent = r.error;
    } else {
      $("#askStatus").textContent = "";
      $("#askAnswer").innerHTML = r.html;
    }
  } finally {
    $("#askBtn").disabled = false;
  }
}

/* ---------- 生成总结 ---------- */
let summTimer = null;

async function startSummarize() {
  if (!state.user) {
    setSumStatus("请先在左侧选择一个具体大V", "err");
    return;
  }
  const body = {
    type: state.sumType,
    start: $("#sumStart").value,
    end: $("#sumEnd").value,
    user: state.user,
    regen: $("#sumRegen").checked,
  };
  const r = await fetch("/api/summarize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((x) => x.json());
  if (r.error) { setSumStatus(r.error, "err"); return; }
  pollSummarize();
}

function setSumStatus(text, cls) {
  const el = $("#sumStatus");
  el.className = "sum-status " + (cls || "");
  el.innerHTML = cls === "run" ? `<span class="spinner"></span> ${esc(text)}` : esc(text);
}

async function pollSummarize() {
  const btn = $("#sumGenBtn");
  const tick = async () => {
    const s = await api("/api/summarize/status");
    const last = s.log && s.log.length ? s.log[s.log.length - 1] : "";
    if (s.running) {
      btn.disabled = true;
      setSumStatus(last || "生成中…", "run");
    } else {
      btn.disabled = false;
      if (summTimer) { clearInterval(summTimer); summTimer = null; }
      if (s.error) setSumStatus("出错：" + s.error, "err");
      else setSumStatus(last || "完成", "ok");
      loadSummaryKeys(); // 刷新日期列表，显示新生成的
    }
  };
  await tick();
  if (!summTimer) summTimer = setInterval(tick, 2000);
}

/* ---------- 选股 ---------- */
let screenerFields = [];
let stockSyncTimer = null;

async function loadScreener() {
  if (!screenerFields.length) {
    screenerFields = await api("/api/screen/fields");
    if (!$("#condList").children.length) addCondRow();
  }
  pollStockSync();
  pollStockBackfill();
  pollStockFinanceSync();
  pollSectorSync();
  pollSectorMembersSync();
  loadSectorCatalog();
  loadGroups();
}

async function loadSectorCatalog() {
  state.sectorCatalog = await api("/api/screen/sectors");
  renderSectorOptions();
}

function renderSectorOptions() {
  const sel = $("#sectorSelect");
  const kept = new Set(Array.from(sel.selectedOptions).map((o) => o.value));
  const q = $("#sectorSearch").value.trim();
  const qUpper = q.toUpperCase();
  const kindLabel = { industry: "行业", concept: "概念" };
  const list = q
    ? state.sectorCatalog.filter((s) => s.name.includes(q) || (s.abbr || "").includes(qUpper))
    : state.sectorCatalog;
  sel.innerHTML = list
    .map((s) => `<option value="${esc(s.name)}"${kept.has(s.name) ? " selected" : ""}>[${kindLabel[s.kind] || s.kind}] ${esc(s.name)}</option>`)
    .join("");
}

function updateSectorModeUI() {
  const bullish = $("#sectorMode").value === "bullish";
  $("#sectorSelect").classList.toggle("hidden", bullish);
  $$(".sector-bullish-days").forEach((el) => el.classList.toggle("hidden", !bullish));
}

function switchScreenerSub(sub) {
  state.screenerSub = sub;
  $$("#screenerTabs .stab").forEach((el) => el.classList.toggle("active", el.dataset.sub === sub));
  $("#screener-sub-filter").classList.toggle("hidden", sub !== "filter");
  $("#screener-sub-groups").classList.toggle("hidden", sub !== "groups");
}

function fieldOptionsHtml() {
  return screenerFields.map((f) => `<option value="${f.field}">${esc(f.label)}</option>`).join("");
}

function addCondRow() {
  const row = document.createElement("div");
  row.className = "cond-row";
  row.innerHTML = `
    <select class="cond-field inp">${fieldOptionsHtml()}</select>
    <select class="cond-op inp">
      <option value=">">&gt;</option>
      <option value=">=">&gt;=</option>
      <option value="<">&lt;</option>
      <option value="<=">&lt;=</option>
      <option value="==">=</option>
      <option value="!=">&ne;</option>
    </select>
    <input type="number" class="cond-value inp" step="any" placeholder="数值">
    <button class="btn-ghost cond-del" title="删除">✕</button>`;
  row.querySelector(".cond-del").addEventListener("click", () => row.remove());
  $("#condList").appendChild(row);
}

function collectConditions() {
  return Array.from($$("#condList .cond-row"))
    .map((row) => ({
      field: row.querySelector(".cond-field").value,
      op: row.querySelector(".cond-op").value,
      value: row.querySelector(".cond-value").value,
    }))
    .filter((c) => c.value !== "");
}

function fmtNum(v) {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  return Number.isFinite(n) ? n.toFixed(2) : "—";
}

function renderScreenTable(items) {
  if (!items.length) return `<p class="muted center">没有符合条件的股票。</p>`;
  const showFinance = items.some((it) => it.roe !== undefined);
  const rows = items
    .map((it) => {
      const chg = Number(it.change_pct);
      const chgCls = chg > 0 ? "up" : chg < 0 ? "down" : "";
      const financeCells = showFinance
        ? `<td class="num">${fmtNum(it.eps)}</td>
           <td class="num">${fmtNum(it.roe)}%</td>
           <td class="num">${fmtNum(it.net_profit_yoy)}%</td>
           <td class="num">${fmtNum(it.revenue_yoy)}%</td>
           <td class="num">${fmtNum(it.gross_margin)}%</td>`
        : "";
      return `<tr>
        <td class="chk-cell"><input type="checkbox" class="rowChk" data-code="${esc(it.code)}" data-name="${esc(it.name)}"></td>
        <td>${esc(it.code)}</td>
        <td><a href="/stock/${esc(it.code)}" target="_blank" rel="noopener">${esc(it.name)}</a></td>
        <td class="num">${fmtNum(it.close)}</td>
        <td class="num ${chgCls}">${fmtNum(it.change_pct)}%</td>
        <td class="num">${fmtNum(it.pe_ttm)}</td>
        <td class="num">${fmtNum(it.pb)}</td>
        <td class="num">${fmtNum(it.turnover_rate)}%</td>
        ${financeCells}
      </tr>`;
    })
    .join("");
  const financeHead = showFinance
    ? `<th>EPS</th><th>ROE</th><th>净利润同比</th><th>营收同比</th><th>毛利率</th>`
    : "";
  return `<div class="table-scroll"><table class="stock-table">
    <thead><tr><th></th><th>代码</th><th>名称</th><th>最新价</th><th>涨跌幅</th><th>市盈率</th><th>市净率</th><th>换手率</th>${financeHead}</tr></thead>
    <tbody>${rows}</tbody>
  </table></div>`;
}

async function runScreen() {
  const body = {
    strategies: Array.from($$(".presetChk:checked")).map((el) => el.value),
    conditions: collectConditions(),
    name_query: $("#nameQuery").value.trim(),
    mentioned: {
      enabled: $("#mentionEnabled").checked,
      days: parseInt($("#mentionDays").value) || 7,
      user_id: state.user,
    },
    sector: {
      enabled: $("#sectorEnabled").checked,
      mode: $("#sectorMode").value,
      names: Array.from($("#sectorSelect").selectedOptions).map((o) => o.value),
      days: parseInt($("#sectorDays").value) || 7,
      user_id: state.user,
    },
    limit: 200,
  };
  $("#screenStatus").textContent = "查询中…";
  const r = await fetch("/api/screen", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((x) => x.json());
  if (r.error) {
    $("#screenStatus").textContent = "出错：" + r.error;
    $("#screenResult").innerHTML = "";
    $("#screenCount").textContent = "";
    return;
  }
  $("#screenStatus").textContent = "";
  $("#stockTradeDate").textContent = r.trade_date || "—";
  $("#screenCount").textContent = `共 ${r.items.length} 条`;
  $("#screenResult").innerHTML = renderScreenTable(r.items);
  $("#screenSelectAll").checked = false;
  $("#screenAddStatus").textContent = "";
}

async function startStockSync() {
  await fetch("/api/stock/sync", { method: "POST" }).then((x) => x.json());
  pollStockSync();
}

function renderStockSyncStatus(s) {
  const box = $("#stockSyncStatus");
  const btn = $("#stockSyncBtn");
  const last = s.log && s.log.length ? s.log[s.log.length - 1] : "";
  if (s.running) {
    btn.disabled = true;
    box.innerHTML = `<span class="spinner"></span><span title="${esc(last)}">同步中…</span>`;
  } else {
    btn.disabled = false;
    if (s.finished_at) {
      const cls = s.error ? "cs-err" : "cs-ok";
      const tip = s.error ? `出错：${s.error}` : (last || "完成");
      box.innerHTML = `<span class="${cls}" title="${esc(tip)}">${esc(tip)}</span>`;
    } else {
      box.innerHTML = "";
    }
  }
}

async function pollStockSync() {
  const s = await api("/api/stock/sync/status");
  renderStockSyncStatus(s);
  if (stockSyncTimer) { clearInterval(stockSyncTimer); stockSyncTimer = null; }
  if (s.running) {
    stockSyncTimer = setInterval(async () => {
      const st = await api("/api/stock/sync/status");
      renderStockSyncStatus(st);
      if (!st.running) {
        clearInterval(stockSyncTimer); stockSyncTimer = null;
      }
    }, 2000);
  }
}

let stockBackfillTimer = null;

async function startStockBackfill() {
  await fetch("/api/stock/backfill", { method: "POST" }).then((x) => x.json());
  pollStockBackfill();
}

function renderStockBackfillStatus(s) {
  const box = $("#stockBackfillStatus");
  const btn = $("#stockBackfillBtn");
  const last = s.log && s.log.length ? s.log[s.log.length - 1] : "";
  if (s.running) {
    btn.disabled = true;
    box.innerHTML = `<span class="spinner"></span><span title="${esc(last)}">回补中…</span>`;
  } else {
    btn.disabled = false;
    if (s.finished_at) {
      const cls = s.error ? "cs-err" : "cs-ok";
      const tip = s.error ? `出错：${s.error}` : (last || "完成");
      box.innerHTML = `<span class="${cls}" title="${esc(tip)}">${esc(tip)}</span>`;
    } else {
      box.innerHTML = "";
    }
  }
}

async function pollStockBackfill() {
  const s = await api("/api/stock/backfill/status");
  renderStockBackfillStatus(s);
  if (stockBackfillTimer) { clearInterval(stockBackfillTimer); stockBackfillTimer = null; }
  if (s.running) {
    stockBackfillTimer = setInterval(async () => {
      const st = await api("/api/stock/backfill/status");
      renderStockBackfillStatus(st);
      if (!st.running) {
        clearInterval(stockBackfillTimer); stockBackfillTimer = null;
      }
    }, 2000);
  }
}

let stockFinanceSyncTimer = null;

async function startStockFinanceSync() {
  await fetch("/api/stock/finance_sync", { method: "POST" }).then((x) => x.json());
  pollStockFinanceSync();
}

function renderStockFinanceSyncStatus(s) {
  const box = $("#stockFinanceSyncStatus");
  const btn = $("#stockFinanceSyncBtn");
  const last = s.log && s.log.length ? s.log[s.log.length - 1] : "";
  if (s.running) {
    btn.disabled = true;
    box.innerHTML = `<span class="spinner"></span><span title="${esc(last)}">同步中…</span>`;
  } else {
    btn.disabled = false;
    if (s.finished_at) {
      const cls = s.error ? "cs-err" : "cs-ok";
      const tip = s.error ? `出错：${s.error}` : (last || "完成");
      box.innerHTML = `<span class="${cls}" title="${esc(tip)}">${esc(tip)}</span>`;
    } else {
      box.innerHTML = "";
    }
  }
}

async function pollStockFinanceSync() {
  const s = await api("/api/stock/finance_sync/status");
  renderStockFinanceSyncStatus(s);
  if (stockFinanceSyncTimer) { clearInterval(stockFinanceSyncTimer); stockFinanceSyncTimer = null; }
  if (s.running) {
    stockFinanceSyncTimer = setInterval(async () => {
      const st = await api("/api/stock/finance_sync/status");
      renderStockFinanceSyncStatus(st);
      if (!st.running) {
        clearInterval(stockFinanceSyncTimer); stockFinanceSyncTimer = null;
      }
    }, 2000);
  }
}

let sectorSyncTimer = null;

async function startSectorSync() {
  await fetch("/api/stock/sync-sectors", { method: "POST" }).then((x) => x.json());
  pollSectorSync();
}

function renderSectorSyncStatus(s) {
  const box = $("#sectorSyncStatus");
  const btn = $("#sectorSyncBtn");
  const last = s.log && s.log.length ? s.log[s.log.length - 1] : "";
  if (s.running) {
    btn.disabled = true;
    box.innerHTML = `<span class="spinner"></span><span title="${esc(last)}">同步中…</span>`;
  } else {
    btn.disabled = false;
    if (s.finished_at) {
      const cls = s.error ? "cs-err" : "cs-ok";
      const tip = s.error ? `出错：${s.error}` : (last || "完成");
      box.innerHTML = `<span class="${cls}" title="${esc(tip)}">${esc(tip)}</span>`;
    } else {
      box.innerHTML = "";
    }
  }
}

async function pollSectorSync() {
  const s = await api("/api/stock/sync-sectors/status");
  renderSectorSyncStatus(s);
  if (sectorSyncTimer) { clearInterval(sectorSyncTimer); sectorSyncTimer = null; }
  if (s.running) {
    sectorSyncTimer = setInterval(async () => {
      const st = await api("/api/stock/sync-sectors/status");
      renderSectorSyncStatus(st);
      if (!st.running) {
        clearInterval(sectorSyncTimer); sectorSyncTimer = null;
        loadSectorCatalog();
      }
    }, 2000);
  }
}

let sectorMembersSyncTimer = null;

async function startSectorMembersSync() {
  await fetch("/api/stock/sync-sector-members", { method: "POST" }).then((x) => x.json());
  pollSectorMembersSync();
}

function renderSectorMembersSyncStatus(s) {
  const box = $("#sectorMembersSyncStatus");
  const btn = $("#sectorMembersSyncBtn");
  const last = s.log && s.log.length ? s.log[s.log.length - 1] : "";
  if (s.running) {
    btn.disabled = true;
    box.innerHTML = `<span class="spinner"></span><span title="${esc(last)}">同步中…</span>`;
  } else {
    btn.disabled = false;
    if (s.finished_at) {
      const cls = s.error ? "cs-err" : "cs-ok";
      const tip = s.error ? `出错：${s.error}` : (last || "完成");
      box.innerHTML = `<span class="${cls}" title="${esc(tip)}">${esc(tip)}</span>`;
    } else {
      box.innerHTML = "";
    }
  }
}

async function pollSectorMembersSync() {
  const s = await api("/api/stock/sync-sector-members/status");
  renderSectorMembersSyncStatus(s);
  if (sectorMembersSyncTimer) { clearInterval(sectorMembersSyncTimer); sectorMembersSyncTimer = null; }
  if (s.running) {
    sectorMembersSyncTimer = setInterval(async () => {
      const st = await api("/api/stock/sync-sector-members/status");
      renderSectorMembersSyncStatus(st);
      if (!st.running) {
        clearInterval(sectorMembersSyncTimer); sectorMembersSyncTimer = null;
      }
    }, 2000);
  }
}

async function runPreset() {
  const strategies = Array.from($$(".presetChk:checked")).map((el) => el.value);
  if (!strategies.length) {
    $("#presetStatus").textContent = "请至少选择一个策略";
    return;
  }
  $("#presetStatus").textContent = "查询中…";
  const r = await fetch("/api/screen/preset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ strategies, limit: 200 }),
  }).then((x) => x.json());
  if (r.error) {
    $("#presetStatus").textContent = "出错：" + r.error;
    $("#screenResult").innerHTML = "";
    $("#screenCount").textContent = "";
    return;
  }
  $("#presetStatus").textContent = "";
  $("#stockTradeDate").textContent = r.trade_date || "—";
  $("#screenCount").textContent = `共 ${r.items.length} 条`;
  $("#screenResult").innerHTML = renderScreenTable(r.items);
  $("#screenSelectAll").checked = false;
  $("#screenAddStatus").textContent = "";
}

/* ---------- 股票分组 ---------- */
async function loadGroups() {
  const r = await api("/api/groups");
  state.groups = r.groups || [];
  renderGroupSelect();
  renderGroupList();
  if (state.activeGroupId && !state.groups.some((g) => g.id === state.activeGroupId)) {
    state.activeGroupId = null;
    $("#groupMembersTitle").textContent = "分组成员";
    $("#groupMembersCount").textContent = "";
    $("#groupMembersResult").innerHTML = `<p class="muted center">请先在上方选择一个分组。</p>`;
  }
}

function renderGroupSelect() {
  const sel = $("#screenGroupSelect");
  const cur = sel.value;
  sel.innerHTML =
    `<option value="">选择分组…</option>` +
    state.groups.map((g) => `<option value="${g.id}">${esc(g.name)}（${g.member_count}）</option>`).join("");
  sel.value = cur;
}

function renderGroupList() {
  const box = $("#groupList");
  if (!state.groups.length) {
    box.innerHTML = `<p class="muted center">还没有分组，先在上方新建一个。</p>`;
    return;
  }
  box.innerHTML = state.groups
    .map(
      (g) => `<div class="group-item ${g.id === state.activeGroupId ? "active" : ""}" data-id="${g.id}">
        <span class="g-name">${esc(g.name)}</span>
        <span class="g-count">${g.member_count} 只</span>
        <button class="g-del" title="删除分组" data-id="${g.id}">✕</button>
      </div>`
    )
    .join("");
  $$("#groupList .group-item").forEach((el) =>
    el.addEventListener("click", (e) => {
      if (e.target.closest(".g-del")) return;
      selectGroup(Number(el.dataset.id));
    })
  );
  $$("#groupList .g-del").forEach((el) =>
    el.addEventListener("click", (e) => { e.stopPropagation(); deleteGroupHandler(Number(el.dataset.id)); })
  );
}

async function selectGroup(id) {
  state.activeGroupId = id;
  renderGroupList();
  const g = state.groups.find((x) => x.id === id);
  $("#groupMembersTitle").textContent = g ? `分组成员 · ${g.name}` : "分组成员";
  $("#groupMembersResult").innerHTML = `<p class="muted center">加载中…</p>`;
  await loadGroupMembers(id);
}

async function loadGroupMembers(id) {
  const r = await api(`/api/groups/${id}/members`);
  const items = r.items || [];
  $("#groupMembersCount").textContent = `共 ${items.length} 只`;
  $("#groupMembersResult").innerHTML = renderGroupMembersTable(items, id);
  $$(`#groupMembersResult .member-del`).forEach((el) =>
    el.addEventListener("click", () => removeMemberHandler(id, el.dataset.code))
  );
}

function renderGroupMembersTable(items, groupId) {
  if (!items.length) return `<p class="muted center">该分组还没有股票，去「筛选」勾选后加入。</p>`;
  const rows = items
    .map((it) => {
      const chg = Number(it.change_pct);
      const chgCls = chg > 0 ? "up" : chg < 0 ? "down" : "";
      return `<tr>
        <td>${esc(it.code)}</td>
        <td><a href="/stock/${esc(it.code)}" target="_blank" rel="noopener">${esc(it.name)}</a></td>
        <td class="num">${fmtNum(it.close)}</td>
        <td class="num ${chgCls}">${fmtNum(it.change_pct)}%</td>
        <td class="num">${fmtNum(it.pe_ttm)}</td>
        <td><button class="member-del" data-code="${esc(it.code)}">移除</button></td>
      </tr>`;
    })
    .join("");
  return `<div class="table-scroll"><table class="stock-table">
    <thead><tr><th>代码</th><th>名称</th><th>最新价</th><th>涨跌幅</th><th>市盈率</th><th></th></tr></thead>
    <tbody>${rows}</tbody>
  </table></div>`;
}

async function createGroup() {
  const input = $("#groupNameInput");
  const name = input.value.trim();
  if (!name) { $("#groupCreateStatus").textContent = "请输入分组名称"; return; }
  const r = await fetch("/api/groups", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  }).then((x) => x.json());
  if (r.error) { $("#groupCreateStatus").textContent = "出错：" + r.error; return; }
  input.value = "";
  $("#groupCreateStatus").textContent = "";
  await loadGroups();
}

async function deleteGroupHandler(id) {
  if (!confirm("确定删除该分组？分组内的股票记录也会一并删除。")) return;
  await fetch(`/api/groups/${id}`, { method: "DELETE" });
  if (state.activeGroupId === id) state.activeGroupId = null;
  await loadGroups();
}

async function removeMemberHandler(groupId, code) {
  await fetch(`/api/groups/${groupId}/members/${encodeURIComponent(code)}`, { method: "DELETE" });
  await loadGroupMembers(groupId);
  await loadGroups();
}

async function addSelectedToGroup() {
  const groupId = $("#screenGroupSelect").value;
  const status = $("#screenAddStatus");
  if (!groupId) { status.textContent = "请先选择一个分组"; return; }
  const stocks = Array.from($$("#screenResult .rowChk:checked")).map((c) => ({
    code: c.dataset.code, name: c.dataset.name,
  }));
  if (!stocks.length) { status.textContent = "请先勾选要加入的股票"; return; }
  const r = await fetch(`/api/groups/${groupId}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ stocks }),
  }).then((x) => x.json());
  if (r.error) { status.textContent = "出错：" + r.error; return; }
  status.textContent = `已加入 ${stocks.length} 只`;
  loadGroups();
}

init();

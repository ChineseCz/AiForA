import { useEffect, useMemo, useState } from "react";
import { CheckCircleFilled, CheckCircleOutlined, ClockCircleOutlined, LinkOutlined, ReadOutlined } from "@ant-design/icons";
import { Button, Card, Col, Progress, Row, Segmented, Space, Tag, Typography } from "antd";
import { useThemeMode } from "../theme";

const { Paragraph, Text, Title } = Typography;
type Lesson = { id: string; title: string; minutes: number; content: string[]; points: string[]; chart?: "candle" | "volume" | "breakout" };
type Course = { id: string; level: "入门基础" | "进阶方法"; title: string; description: string; lessons: Lesson[] };

const COURSES: Course[] = [
  {
    id: "trading-basics", level: "入门基础", title: "看懂交易与K线", description: "从一笔交易如何成交开始，读懂价格、成交量和常见K线形态。", lessons: [
      { id: "trade-flow", title: "一笔交易怎样完成", minutes: 6, content: ["股票交易是买卖双方通过交易所撮合的过程。你提交委托后，只有价格和数量与对手盘匹配，才会成交；挂单不等于成交。", "限价委托限定你愿意接受的价格，成交速度不确定；市价类委托优先追求成交，实际成交价可能偏离看到的最新价。A股还涉及交易时段、涨跌幅限制、T+1等规则，具体品种和板块规则可能不同。"], points: ["下单前核对代码、方向、数量和价格。", "查看成交回报与费用，不把委托当作成交。", "先熟悉所在市场和券商的规则，再进行真实交易。"] },
      { id: "candle-parts", title: "K线的四个价格", minutes: 8, chart: "candle", content: ["每根K线记录一个周期内的开盘价、收盘价、最高价和最低价。实体连接开盘与收盘，影线延伸到最高和最低。图中红色表示收涨、绿色表示收跌，这是A股常见配色；海外软件也可能相反。", "日K代表一个交易日，周K代表一周。相同形状放在不同周期、不同位置，意义也不同。K线只描述已发生的价格，不会单独告诉你下一步一定怎么走。"], points: ["先读周期，再读开收盘和高低点。", "实体较长代表该周期收盘方向上的价格移动较大。", "影线说明价格曾到达那里，但未能在该处收盘。"] },
      { id: "volume", title: "成交量在说什么", minutes: 7, chart: "volume", content: ["成交量表示一段时间内实际成交的数量，成交额则是成交金额。它们反映交易活跃程度，不等同于买方人数或资金净流入。每笔成交同时有买方和卖方。", "价格上涨同时放量，说明参与度提高；但放量也可能出现在分歧加剧或高位换手时。缩量回落也不自动代表卖压消失，要结合趋势、位置和后续价格验证。"], points: ["比较相同周期、相邻时段的量能更有意义。", "量价关系是线索，不是买卖指令。", "留意成交额和流动性，避免只看涨跌幅。"] },
      { id: "common-patterns", title: "常见K线形态与误区", minutes: 9, chart: "candle", content: ["长下影可能表示低位出现承接，也可能只是波动很大；长上影可能反映高位抛压，也可能发生在趋势中的正常震荡。单根K线的形状没有固定胜率。", "形态要放在前后走势中观察：此前是上涨还是下跌，附近是否有明显支撑阻力，成交量如何，下一根是否确认。不要看到某个名字就直接套用买卖结论。"], points: ["先描述图上事实，再提出可能解释。", "等待后续走势验证，不因单根K线追涨杀跌。", "用多个例子复盘同类形态，记录失败样本。"] },
      { id: "risk-first", title: "仓位、止损与交易计划", minutes: 8, content: ["交易前先写下为什么买、什么情况说明判断失效、最多能承受多少损失。仓位应根据可承受亏损和止损距离来定，而不是因为“看起来便宜”就加大投入。", "跳空、停牌、流动性不足和涨跌幅限制都可能让实际退出价格与预想不同。止损是风险管理计划，不是保证成交或保证损失上限。"], points: ["只用能承受损失的资金，避免借钱交易。", "单笔风险和总仓位都要设边界。", "计划失效时重新评估，不用加仓掩盖错误。"] },
    ]
  },
  {
    id: "short-term-method", level: "进阶方法", title: "超短线观察与复盘", description: "参考市场公开的超短线交易框架，学习情绪、题材、龙头与纪律，不构成任何账号观点复述。", lessons: [
      { id: "market-mood", title: "先判断市场环境", minutes: 9, content: ["超短线交易周期短，市场整体情绪会影响个股表现。可以观察上涨与下跌家数、涨停和跌停数量、连板高度、炸板情况，以及指数和成交额的变化。", "这些数据是环境描述，不是预测。情绪指标快速变化，单一数字容易误导；在退潮或分歧放大时，降低出手频率和仓位也是一种选择。"], points: ["用多项指标交叉观察，不用一个指标代替判断。", "区分情绪回暖、加速、分歧和退潮等不同阶段。", "市场环境不清楚时，允许空仓观察。"] },
      { id: "theme-leader", title: "题材、梯队与核心标的", minutes: 10, content: ["题材是市场围绕某类事件或产业形成的交易叙事。观察时要核实催化信息来源，了解板块内有多少标的响应、持续性如何，以及领涨标的是否仍有资金关注。", "所谓龙头或核心标的，是对一段行情的事后归纳，不是稳定标签。高辨识度也意味着拥挤和波动风险，不能把市场称呼当作买入理由。"], points: ["把事实、市场表现和个人推断分开记录。", "观察板块内强弱梯队与持续性。", "不因热门标签忽略估值、公告和流动性风险。"] },
      { id: "entry-exit", title: "买点、卖点与盈亏比", minutes: 10, chart: "breakout", content: ["交易计划应定义触发条件、失效条件和退出方式。突破前高、回踩承接等说法需要明确到可复盘的价格和量能条件；否则容易在事后把任何走势解释成信号。", "预期收益与可能亏损的比值可以帮助筛选交易，但并不代表胜率。超短线的滑点、隔夜跳空和无法成交会改变盈亏结构。"], points: ["进场条件要能被另一位读者按图核对。", "先算错了会亏多少，再看潜在空间。", "信号失效就按计划退出，不把短线被套自动改成长线。"] },
      { id: "breakout-review", title: "复盘与样本统计", minutes: 12, content: ["复盘时保留当时可见的信息和决策理由，标注市场环境、题材位置、触发条件、仓位、退出理由及执行偏差。把成功和失败样本都留下，避免只挑漂亮案例。", "评估一套方法，需要足够样本并考虑交易成本、滑点和不可成交情形。少量案例的收益不能证明方法有效，更不能保证未来结果。"], points: ["记录计划内交易与计划外交易。", "统计胜率、平均盈亏、最大回撤和交易成本。", "按市场阶段拆分样本，检查方法何时失效。"] },
      { id: "discipline", title: "仓位纪律与连续亏损", minutes: 8, content: ["连续亏损会放大情绪和决策偏差。事先设置每日或每周的风险上限，触及后停止交易并复盘，通常比急于回本更有利于保持判断质量。", "超短线频繁交易会累积佣金、税费和滑点，也更容易受到情绪影响。模拟交易和小规模验证可以帮助熟悉流程，但模拟成交未必代表真实市场执行。"], points: ["明确单日亏损上限和暂停条件。", "连续亏损后先检查规则和状态，不加倍下注。", "把不交易作为计划的一部分。"] },
    ]
  },
];

const EXTERNAL_RESOURCES = [
  { title: "上交所投资者教育", category: "A股规则", description: "了解股票交易规则、市场制度与投资者保护。", url: "https://edu.sse.com.cn/" },
  { title: "深交所投教服务", category: "A股规则", description: "学习深市交易制度、风险提示和基础知识。", url: "https://investor.szse.cn/" },
  { title: "中国投资者网", category: "投资基础", description: "证监会投资者保护局主办，提供投资知识与风险教育。", url: "https://www.investor.org.cn/" },
  { title: "Investor.gov: Introduction to Investing", category: "投资基础", description: "美国证券交易委员会的投资入门资料，适合理解风险、收益与分散投资。", url: "https://www.investor.gov/introduction-investing" },
  { title: "FINRA: Investing Basics", category: "投资基础", description: "面向个人投资者的基础指南，涵盖账户、产品和常见风险。", url: "https://www.finra.org/investors/investing/investing-basics" },
  { title: "CME Group Education", category: "图表与技术分析", description: "提供市场、图表和技术分析课程；衍生品内容风险较高，按需选读。", url: "https://www.cmegroup.com/education.html" },
];

const STORAGE_KEY = "investing-learning-progress-v2";
function readProgress(): Record<string, string[]> {
  try { const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"); return Object.fromEntries(Object.entries(parsed).map(([key, value]) => [key, Array.isArray(value) ? value.filter((x) => typeof x === "string") : []])); }
  catch { return {}; }
}

function CandleIllustration({ variant }: { variant: "candle" | "volume" | "breakout" }) {
  const bars = variant === "breakout"
    ? [{ x: 42, o: 78, c: 66, h: 57, l: 86 }, { x: 92, o: 70, c: 75, h: 60, l: 84 }, { x: 142, o: 75, c: 56, h: 48, l: 82 }, { x: 192, o: 58, c: 62, h: 49, l: 70 }, { x: 242, o: 61, c: 35, h: 26, l: 69 }, { x: 292, o: 37, c: 23, h: 16, l: 45 }]
    : [{ x: 42, o: 65, c: 48, h: 35, l: 77 }, { x: 92, o: 52, c: 59, h: 40, l: 70 }, { x: 142, o: 61, c: 37, h: 27, l: 72 }, { x: 192, o: 42, c: 53, h: 31, l: 67 }, { x: 242, o: 48, c: 30, h: 20, l: 62 }, { x: 292, o: 33, c: 45, h: 24, l: 56 }];
  return <div className="learning-chart" role="img" aria-label="K线示意图：展示每根K线的开盘、收盘、最高和最低价">
    <svg viewBox="0 0 340 142" aria-hidden="true">
      {[20, 50, 80, 110].map((y) => <line key={y} x1="24" x2="326" y1={y} y2={y} className="chart-grid" />)}
      {variant === "breakout" && <line x1="25" x2="326" y1="60" y2="60" className="chart-level" />}
      {bars.map((bar, index) => { const up = bar.c < bar.o; const top = Math.min(bar.o, bar.c); const height = Math.max(5, Math.abs(bar.o - bar.c)); return <g key={bar.x}>
        <line x1={bar.x} x2={bar.x} y1={bar.h} y2={bar.l} className={up ? "chart-up" : "chart-down"} strokeWidth="2" />
        <rect x={bar.x - 10} y={top} width="20" height={height} className={up ? "chart-up" : "chart-down"} rx="1" />
        {variant === "volume" && <rect x={bar.x - 8} y={125 - [24, 38, 30, 46, 62, 37][index]} width="16" height={[24, 38, 30, 46, 62, 37][index]} className={up ? "chart-volume-up" : "chart-volume-down"} rx="1" />}
      </g>; })}
      {variant === "breakout" && <text x="268" y="55" className="chart-label">前高区域</text>}
      {variant === "volume" && <text x="26" y="139" className="chart-label">成交量柱</text>}
    </svg>
    <div className="learning-chart-caption"><span><i className="chart-legend-up" />收涨</span><span><i className="chart-legend-down" />收跌</span><span>示意数据，仅用于识图</span></div>
  </div>;
}

export default function LearningCenter() {
  const { mode } = useThemeMode();
  const [level, setLevel] = useState<Course["level"]>("入门基础");
  const [progress, setProgress] = useState(readProgress);
  const course = useMemo(() => COURSES.find((item) => item.level === level)!, [level]);
  const [lessonId, setLessonId] = useState(course.lessons[0].id);
  const lesson = course.lessons.find((item) => item.id === lessonId) ?? course.lessons[0];
  const completed = progress[course.id] ?? [];
  const done = completed.includes(lesson.id);
  const completionCount = course.lessons.filter((item) => completed.includes(item.id)).length;
  const isDark = mode === "dark";
  useEffect(() => { setLessonId(course.lessons[0].id); }, [course]);
  useEffect(() => { localStorage.setItem(STORAGE_KEY, JSON.stringify(progress)); }, [progress]);
  const toggleCompleted = () => setProgress((current) => { const items = new Set(current[course.id] ?? []); if (items.has(lesson.id)) items.delete(lesson.id); else items.add(lesson.id); return { ...current, [course.id]: [...items] }; });

  return <div className="learning-page">
    <div className="learning-heading"><div><Text type="secondary">投资学习</Text><Title level={2} style={{ margin: "4px 0" }}>从读懂K线到制定交易计划</Title><Paragraph type="secondary" style={{ maxWidth: 720, marginBottom: 0 }}>循序学习交易规则、K线语言、风险控制与超短线复盘。内容用于投资者教育，不构成个股推荐或投资建议。</Paragraph></div>
      <Segmented value={level} options={["入门基础", "进阶方法"]} onChange={(value) => setLevel(value as Course["level"])} />
    </div>
    <div className="learning-overview"><div className="learning-course-title"><div className="learning-course-icon"><ReadOutlined /></div><div><Text type="secondary">{course.level} · {course.lessons.length} 个章节</Text><Title level={4} style={{ margin: "2px 0" }}>{course.title}</Title><Text type="secondary">{course.description}</Text></div></div><div className="learning-progress"><div><Text strong>学习进度</Text><Text type="secondary">{completionCount}/{course.lessons.length} 章</Text></div><Progress percent={Math.round(completionCount / course.lessons.length * 100)} showInfo={false} strokeColor="#2f8f6b" /></div></div>
    <Row gutter={[16, 16]} align="top"><Col xs={24} md={8} lg={7}><div className="learning-lesson-list" aria-label="章节列表">{course.lessons.map((item, index) => { const selected = item.id === lesson.id; const finished = completed.includes(item.id); return <button key={item.id} type="button" className={`learning-lesson-item${selected ? " active" : ""}`} onClick={() => setLessonId(item.id)}><span className="learning-lesson-number">{finished ? <CheckCircleFilled /> : String(index + 1).padStart(2, "0")}</span><span className="learning-lesson-copy"><strong>{item.title}</strong><small><ClockCircleOutlined /> {item.minutes} 分钟</small></span>{selected && <span className="learning-current-mark" />}</button>; })}</div></Col>
      <Col xs={24} md={16} lg={17}><Card className="learning-article" bordered={!isDark}><div className="learning-article-meta"><Tag color={level === "入门基础" ? "green" : "blue"}>{level}</Tag><Text type="secondary">约 {lesson.minutes} 分钟</Text></div><Title level={3}>{lesson.title}</Title>{lesson.content.map((paragraph) => <Paragraph key={paragraph}>{paragraph}</Paragraph>)}{lesson.chart && <CandleIllustration variant={lesson.chart} />}<div className="learning-keypoints"><Text strong>本章要点</Text><ul>{lesson.points.map((point) => <li key={point}>{point}</li>)}</ul></div><div className="learning-article-footer"><Text type="secondary">学习进度保存在当前浏览器</Text><Button type={done ? "default" : "primary"} icon={done ? <CheckCircleFilled /> : <CheckCircleOutlined />} onClick={toggleCompleted}>{done ? "已完成" : "标记完成"}</Button></div></Card></Col>
    </Row>
    <section className="learning-resources" aria-labelledby="learning-resources-title">
      <div className="learning-resources-heading"><div><Title level={4} id="learning-resources-title">精选外部学习资料</Title><Text type="secondary">优先选择交易所、监管机构和成熟教育平台</Text></div></div>
      <div className="learning-resource-grid">{EXTERNAL_RESOURCES.map((resource) => <a className="learning-resource" key={resource.title} href={resource.url} target="_blank" rel="noopener noreferrer">
        <span className="learning-resource-top"><Tag>{resource.category}</Tag><LinkOutlined aria-hidden="true" /></span>
        <strong>{resource.title}</strong><span className="learning-resource-description">{resource.description}</span>
      </a>)}</div>
      <Text className="learning-resource-note" type="secondary">外部网站由其运营方维护，内容与规则可能更新。海外资料涉及的市场制度不一定适用于A股。</Text>
    </section>
    <div className="learning-disclaimer"><Space align="start"><Text type="secondary">超短线交易波动大、交易频率高，可能造成快速亏损。示意图不代表真实行情，任何策略都需要独立验证并承担相应风险。</Text></Space></div>
  </div>;
}

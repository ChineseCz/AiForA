import { useEffect, useMemo, useState } from "react";
import { CheckCircleFilled, CheckCircleOutlined, ClockCircleOutlined, ReadOutlined } from "@ant-design/icons";
import { Button, Card, Col, Progress, Row, Segmented, Space, Tag, Typography } from "antd";
import { useThemeMode } from "../theme";

const { Paragraph, Text, Title } = Typography;

type Lesson = { id: string; title: string; minutes: number; content: string[]; points: string[] };
type Course = { id: string; level: "入门基础" | "进阶方法"; title: string; description: string; lessons: Lesson[] };

const COURSES: Course[] = [
  {
    id: "first-principles", level: "入门基础", title: "建立投资常识", description: "先理解市场、风险和自己的资金，再开始研究具体标的。", lessons: [
      { id: "market-basics", title: "股票市场如何运作", minutes: 8, content: ["股票代表对一家公司的部分所有权。买入股票后，你持有的是公司的权益，价格则由交易中的供需和对未来的预期共同决定。", "A 股交易通过证券交易所撮合。委托价、成交量、涨跌停限制、停复牌和交易时间都会影响订单能否成交。行情软件展示的价格不等于你一定能按该价格买到或卖出。"], points: ["价格反映交易双方当下的预期，不是公司价值的精确刻度。", "下单后要区分委托、部分成交和全部成交。", "涨跌停限制价格范围，但不保证有对手盘成交。"] },
      { id: "risk-and-return", title: "收益与风险是一体两面", minutes: 10, content: ["投资收益来自价格变化、分红等因素，但结果不确定。收益预期越高，通常需要承担更大的波动、亏损或流动性风险。", "最大回撤描述资产从阶段高点下跌到后续低点的幅度。它能帮助你理解策略在不利阶段可能经历什么，而不只是关注最终收益。"], points: ["历史收益不是未来收益的承诺。", "先想清楚最多能承受多大损失，再决定投入金额。", "不要用借款、生活费或应急资金承担高波动风险。"] },
      { id: "account-and-orders", title: "账户、委托与交易费用", minutes: 8, content: ["开始交易前，了解证券账户、资金账户、交易时间和委托类型。限价委托会指定价格，市价类委托通常更强调尽快成交，但实际规则取决于市场和券商。", "交易成本会持续影响长期结果。除佣金外，还要了解印花税、过户费及券商最低收费规则。具体费率以你的券商交割单为准。"], points: ["下单前再次核对代码、方向、数量和价格。", "成交后查看交割单，确认实际费用。", "不要把软件里的模拟成交当成真实成交体验。"] },
      { id: "company-research", title: "认识一家公司", minutes: 12, content: ["研究公司时，先弄清楚它卖什么、客户是谁、收入如何形成、主要成本是什么，以及竞争优势能否持续。再阅读定期报告、公告和行业资料。", "财务数据需要放在业务背景中理解。收入增长不代表利润和现金流一定改善；利润增长也不代表应收账款、负债和资本开支没有风险。"], points: ["从公司公告和定期报告等原始资料开始。", "对比收入、利润、经营现金流和负债变化。", "把事实、推测和个人判断分开记录。"] },
    ],
  },
  {
    id: "research-practice", level: "进阶方法", title: "形成可验证的方法", description: "把研究、估值、组合和复盘连成一套可以检查的流程。", lessons: [
      { id: "valuation", title: "估值与预期差", minutes: 12, content: ["估值不是给公司贴一个永远正确的数字，而是在一组假设下估算未来现金流或盈利对应的价格区间。不同商业模式、周期和资本结构适合的估值方法也不同。", "市场价格会随预期变化。研究时要问：当前价格隐含了什么增长和利润假设？哪些关键事实可能让预期上修或下修？"], points: ["估值结果依赖假设，应该做情景分析。", "便宜不等于低风险，贵也不等于一定下跌。", "把安全边际和判断失效条件写清楚。"] },
      { id: "portfolio-risk", title: "仓位与组合风险", minutes: 10, content: ["单只股票的判断可能出错，组合管理关心多个风险如何叠加。持仓数量、行业集中度、相关性和流动性都会影响组合在压力时期的表现。", "仓位大小应与风险承受能力和策略波动匹配。分散可以降低部分个股风险，但不能消除系统性下跌，也不能替代对资产本身的研究。"], points: ["提前设定单笔和整体风险边界。", "检查组合是否集中在相同公司、行业或宏观因素。", "为极端行情和流动性下降留出空间。"] },
      { id: "backtest-basics", title: "正确理解策略回测", minutes: 14, content: ["回测是在历史数据上按明确规则模拟交易。它可以帮助发现规则是否自洽、风险集中在哪些时期，但不能证明策略未来有效。", "回测容易受到未来数据泄漏、幸存者偏差、复权数据修订、手续费、滑点、涨跌停无法成交和参数过拟合影响。样本外验证和不同市场阶段测试可以帮助发现脆弱结论。"], points: ["只使用当时可获得的数据生成信号。", "把手续费、滑点和无法成交纳入模拟。", "同时观察收益、回撤、交易次数和样本外表现。"] },
      { id: "research-journal", title: "建立研究与复盘记录", minutes: 9, content: ["每次决策都记录当时依据、关键假设、计划持有周期、风险边界和失效条件。之后按计划检查事实是否变化，而不是只看价格涨跌给自己找理由。", "复盘关注流程质量：有没有按规则执行、有没有忽略新信息、策略在哪种环境下失效。单笔盈亏不能单独证明决策正确或错误。"], points: ["决策前记录假设，决策后记录执行。", "区分运气、方法和纪律。", "定期检查策略是否仍适用于当前市场和个人情况。"] },
    ],
  },
];

const STORAGE_KEY = "investing-learning-progress-v1";

function readProgress(): Record<string, string[]> {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    return Object.fromEntries(Object.entries(parsed).map(([key, value]) => [key, Array.isArray(value) ? value.filter((x) => typeof x === "string") : []]));
  } catch { return {}; }
}

export default function LearningCenter() {
  const { mode } = useThemeMode();
  const [level, setLevel] = useState<"入门基础" | "进阶方法">("入门基础");
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

  const toggleCompleted = () => setProgress((current) => {
    const items = new Set(current[course.id] ?? []);
    if (items.has(lesson.id)) items.delete(lesson.id); else items.add(lesson.id);
    return { ...current, [course.id]: [...items] };
  });

  return (
    <div className="learning-page">
      <div className="learning-heading">
        <div>
          <Text type="secondary">投资学习</Text>
          <Title level={2} style={{ margin: "4px 0" }}>从基础知识到研究方法</Title>
          <Paragraph type="secondary" style={{ maxWidth: 680, marginBottom: 0 }}>
            按自己的节奏学习市场规则、公司研究、组合风险和策略验证。内容用于投资者教育，不构成个股推荐或投资建议。
          </Paragraph>
        </div>
        <Segmented value={level} options={["入门基础", "进阶方法"]} onChange={(value) => setLevel(value as typeof level)} />
      </div>

      <div className="learning-overview">
        <div className="learning-course-title">
          <div className="learning-course-icon"><ReadOutlined /></div>
          <div>
            <Text type="secondary">{course.level} · {course.lessons.length} 个章节</Text>
            <Title level={4} style={{ margin: "2px 0" }}>{course.title}</Title>
            <Text type="secondary">{course.description}</Text>
          </div>
        </div>
        <div className="learning-progress">
          <div><Text strong>学习进度</Text><Text type="secondary">{completionCount}/{course.lessons.length} 章</Text></div>
          <Progress percent={Math.round(completionCount / course.lessons.length * 100)} showInfo={false} strokeColor="#2f8f6b" />
        </div>
      </div>

      <Row gutter={[16, 16]} align="top">
        <Col xs={24} md={8} lg={7}>
          <div className="learning-lesson-list" aria-label="章节列表">
            {course.lessons.map((item, index) => {
              const selected = item.id === lesson.id;
              const finished = completed.includes(item.id);
              return <button key={item.id} type="button" className={`learning-lesson-item${selected ? " active" : ""}`} onClick={() => setLessonId(item.id)}>
                <span className="learning-lesson-number">{finished ? <CheckCircleFilled /> : String(index + 1).padStart(2, "0")}</span>
                <span className="learning-lesson-copy"><strong>{item.title}</strong><small><ClockCircleOutlined /> {item.minutes} 分钟</small></span>
                {selected && <span className="learning-current-mark" />}
              </button>;
            })}
          </div>
        </Col>
        <Col xs={24} md={16} lg={17}>
          <Card className="learning-article" bordered={!isDark}>
            <div className="learning-article-meta"><Tag color={level === "入门基础" ? "green" : "blue"}>{level}</Tag><Text type="secondary">约 {lesson.minutes} 分钟</Text></div>
            <Title level={3}>{lesson.title}</Title>
            {lesson.content.map((paragraph) => <Paragraph key={paragraph}>{paragraph}</Paragraph>)}
            <div className="learning-keypoints">
              <Text strong>学习要点</Text>
              <ul>{lesson.points.map((point) => <li key={point}>{point}</li>)}</ul>
            </div>
            <div className="learning-article-footer">
              <Text type="secondary">学习记录保存在当前浏览器</Text>
              <Button type={done ? "default" : "primary"} icon={done ? <CheckCircleFilled /> : <CheckCircleOutlined />} onClick={toggleCompleted}>
                {done ? "已完成" : "标记完成"}
              </Button>
            </div>
          </Card>
        </Col>
      </Row>
      <div className="learning-disclaimer"><Space align="start"><Text type="secondary">学习内容帮助建立分析框架，不保证投资收益。作出投资决定前，请结合自身情况独立判断并承担相应风险。</Text></Space></div>
    </div>
  );
}

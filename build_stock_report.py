from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak

OUT = Path('reports/stock_investing_2026')
FIG = OUT / 'figures'
FIG.mkdir(parents=True, exist_ok=True)
FONT_PATH = 'C:/Windows/Fonts/simhei.ttf'
pdfmetrics.registerFont(TTFont('SimHei', FONT_PATH))

def font(size):
    return ImageFont.truetype(FONT_PATH, size)

def bar_chart(path, title, labels, vals, suffix, note):
    W,H=1500,820
    im=Image.new('RGB',(W,H),'white'); d=ImageDraw.Draw(im)
    d.text((55,30), title, font=font(36), fill='#172033')
    left,right,top,bottom=120,100,140,650
    maxv=max(vals)*1.25
    slot=(W-left-right)//len(vals)
    palette=['#94A3B8','#C99A2E','#7C9CCB','#74A88B','#D17D5A']
    for i,(lab,val) in enumerate(zip(labels,vals)):
        bw=int(slot*.52); x=left+i*slot+(slot-bw)//2
        y=bottom-int((bottom-top)*val/maxv)
        d.rectangle((x,y,x+bw,bottom),fill=palette[i%len(palette)])
        d.text((x+bw//2-30,y-42),f'{val}{suffix}',font=font(27),fill='#172033')
        d.text((x+bw//2-70,bottom+20),lab,font=font(24),fill='#334155')
    d.line((left,top,left,bottom),fill='#94A3B8',width=2); d.line((left,bottom,W-right,bottom),fill='#94A3B8',width=2)
    d.text((55,735),note,font=font(19),fill='#64748B')
    im.save(path)

def allocation_chart(path):
    W,H=1500,820
    im=Image.new('RGB',(W,H),'white'); d=ImageDraw.Draw(im)
    d.text((55,30),'10万元存款：保守起步的资金分层示例',font=font(36),fill='#172033')
    items=[('应急现金/货币基金','40%',40,'#78909C'),('低风险固收','30%',30,'#8BA6B5'),('宽基指数/长期权益','20%',20,'#C99A2E'),('个股学习账户','5%',5,'#D17D5A'),('黄金/其他分散','5%',5,'#D8B65A')]
    x0,y0=100,210; barw=1250; cur=x0
    for name,pct,val,col in items:
        w=int(barw*val/100); d.rectangle((cur,y0,cur+w,y0+100),fill=col)
        if w>100: d.text((cur+12,y0+34),pct,font=font(25),fill='white')
        cur+=w
    y=390
    for name,pct,val,col in items:
        d.rectangle((110,y+5,140,y+35),fill=col); d.text((160,y),f'{name}：{pct}（约{val*1000:,}元）',font=font(25),fill='#334155'); y+=62
    d.text((55,745),'前提：10万元是当前主要存款，尚未单独建立应急金；应按个人房租、负债和家庭支持责任调整。',font=font(19),fill='#64748B')
    im.save(path)

def matrix_chart(path):
    W,H=1500,880
    im=Image.new('RGB',(W,H),'white'); d=ImageDraw.Draw(im)
    d.text((55,30),'市场选择：不是“哪个一定赚钱”，而是优势与风险匹配',font=font(34),fill='#172033')
    headers=['市场','对你的直接优势','主要风险/成本','当前建议']
    xs=[70,270,720,1130]; widths=[180,420,390,300]
    y=140
    for x,h in zip(xs,headers): d.text((x,y),h,font=font(25),fill='#9A6B16')
    rows=[('A股','项目数据、国家队、板块、财务、选股策略可直接使用','T+1、波动与题材噪音、基本面质量差异','优先作为学习主场'),('美股','优质公司多、ETF生态成熟、长期复利工具丰富','跨境合规/税务、汇率、时差、估值与单股风险','先用合规基金/ETF学习'),('港股','中国公司国际定价、部分公司估值可能较低','流动性分化、汇率、公司治理和波动','研究型补充，不宜盲目抄底')]
    y=210
    for i,row in enumerate(rows):
        bg=['#F5F7FA','#FFF8E5','#F3F8F5'][i]
        d.rounded_rectangle((55,y-20,1445,y+130),16,fill=bg,outline='#CBD5E1',width=2)
        for x,text in zip(xs,row):
            d.text((x,y),text,font=font(23),fill='#334155')
        y+=190
    d.text((55,790),'结论：对你最重要的不是市场标签，而是能否形成可验证、可复盘、合规执行的投资系统。',font=font(19),fill='#64748B')
    im.save(path)

bar_chart(FIG/'market_learning_curve.png','三类市场：对个人投资者的相对学习难度（示意）',['A股','港股','美股'],[2,3,4],'级','不是收益预测；按规则、信息、汇率/税务和执行复杂度综合示意。')
allocation_chart(FIG/'allocation_100k.png')
matrix_chart(FIG/'market_matrix.png')

styles=getSampleStyleSheet()
normal=ParagraphStyle('CN',parent=styles['BodyText'],fontName='SimHei',fontSize=9.2,leading=15,spaceAfter=5)
h1=ParagraphStyle('H1CN',parent=styles['Heading1'],fontName='SimHei',fontSize=16,textColor=colors.HexColor('#9A6B16'),spaceBefore=12,spaceAfter=7)
h2=ParagraphStyle('H2CN',parent=styles['Heading2'],fontName='SimHei',fontSize=12,textColor=colors.HexColor('#B07D1E'),spaceBefore=8,spaceAfter=5)
title=ParagraphStyle('TCN',parent=styles['Title'],fontName='SimHei',fontSize=22,leading=30,alignment=TA_CENTER,textColor=colors.HexColor('#1F2937'))
sub=ParagraphStyle('SUB',parent=normal,alignment=TA_CENTER,fontSize=11)
small=ParagraphStyle('SMALL',parent=normal,fontSize=7.5,textColor=colors.HexColor('#64748B'))

def P(text, style=normal): return Paragraph(text.replace('&','&amp;'), style)
def table(data, widths):
    t=Table([[P(str(c)) for c in r] for r in data], colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#F3E6C2')),('TEXTCOLOR',(0,0),(-1,0),colors.HexColor('#6B4B10')),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#CBD5E1')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    return t

story=[P('股票市场选择、学习路径与个人资金配置研究报告',title),Spacer(1,5),P('A股 / 美股 / 港股比较｜项目价值评估｜10万元存款起步方案',sub),P('报告日期：2026年9月7日｜面向刚毕业上班族｜公开资料研究，不构成个性化投资建议',ParagraphStyle('D',parent=small,alignment=TA_CENTER)),Spacer(1,10),RLImage(str(FIG/'market_matrix.png'),width=175*mm,height=102*mm)]
story += [P('一、执行摘要',h1),P('<b>我的主判断：</b>如果你的主要生活和收入在中国内地，且目前刚毕业、存款约10万元，我不建议把问题定义为“炒A股、炒美股还是炒港股”。更好的定义是：先建立长期投资系统，再用很小的资金验证自己的方法。就你的现有项目而言，<b>A股是最有直接研究优势的主场</b>；美股和港股可作为后续扩展，但不应仅因为“海外市场更成熟”就直接重仓。'),P('资金层面，若10万元是你的主要存款，建议先把应急金与投资金分开。示例是：4万元应急现金、3万元低风险固收、2万元宽基指数/长期权益、5000元个股学习账户、5000元黄金或其他分散资产。这个方案优先保证不因失业、搬家、疾病或家庭支出被迫卖出。'),P('学习层面，前12个月的目标不应是赚多少钱，而应是：懂规则、会读财报、能写投资假设、能控制仓位、能记录交易、能判断自己的方法是否有效。')]
story += [P('二、A股、美股、港股如何选择',h1),RLImage(str(FIG/'market_learning_curve.png'),width=175*mm,height=96*mm),table([['市场','适合什么人','你的直接优势','主要注意事项'],['A股','熟悉中国经济、政策和行业，能跟踪国内公司的人','项目已接入A股行情、财务、板块、K线、国家队持仓、雪球观点和选股策略','T+1；题材波动大；需警惕追热点、内幕消息和小盘股流动性'],['美股','有长期全球资产配置需求，能处理汇率、税务、跨境合规和时差的人','可学习宽基ETF、优秀公司和股东回报体系','跨境资金路径、税务、汇率、估值、单股集中风险；不要直接照搬A股指标'],['港股','希望研究中国公司国际定价、熟悉港股交易规则的人','可把A股产业研究迁移到部分中国公司','流动性和估值分化大；汇率、公司治理、市场情绪风险明显']], [26*mm,42*mm,55*mm,52*mm]),P('推荐顺序：<b>先A股学习与验证，后用合规、低成本的全球/海外指数工具扩展，再考虑港美个股。</b>这不是判断A股未来一定跑赢，而是基于你的信息、工具、语言、数据和执行优势。')]
story += [P('三、你当前项目对于炒股的意义',h1),P('项目的真正价值不是“给出明天买什么”，而是帮助你把投资流程结构化。当前代码和产品能力包括：'),P('• 数据层：A股行情快照、历史K线、前复权处理、财务、板块、国家队持仓、雪球大V帖子与总结。'),P('• 分析层：MA、MACD、KDJ、RSI、布林、成交量、均线突破等指标；基本面筛选；板块与个股关联；大V提及与看多判断。'),P('• 选股层：ma_cross、ma_cross2、golden_cross、fund_ok等预设策略，并有预计算指标快路径。'),P('• 研究层：可以把“观点—数据—候选股票—结果”连成可复盘链路，减少只凭感觉看盘。'),P('<b>边界非常重要：</b>技术指标是条件描述，不是因果证明；历史回测可能受到幸存者偏差、数据修订、滑点、手续费、涨跌停无法成交和样本外失效影响；雪球观点反映的是信息和情绪，不是可靠的买卖信号；国家队持仓披露有滞后，也不代表未来继续持有。'),table([['项目能做什么','项目不能保证什么'],['提高信息整理和筛选效率','不能预测明天涨跌'],['把策略条件标准化、可复盘','不能证明策略未来有效'],['补充财务、技术、板块和舆情视角','不能替代公司研究和风险管理'],['形成候选池和研究优先级','不能自动完成适当性、合规和个人决策']], [83*mm,83*mm])]
story += [P('四、10万元存款的资金分配',h1),RLImage(str(FIG/'allocation_100k.png'),width=175*mm,height=96*mm),P('以下方案的前提是：10万元是你目前主要存款，工作刚开始，未来收入仍需建立，且没有明确说明已拥有独立应急金。若你有高息负债，应先还债；若10万元只是闲置资金、另有充足现金储备，可适度提高投资比例。'),table([['资金用途','金额示例','目的与纪律'],['应急现金/货币基金','40,000元','覆盖失业、房租、医疗和突发支出；不要用于追涨'],['低风险固收','30,000元','降低组合波动；了解产品非保本、久期和信用风险'],['宽基指数/长期权益','20,000元','以分散为主，分批投入；持有期限至少3—5年'],['个股学习账户','5,000元','只用于验证方法；单只股票不宜过度集中，不融资'],['黄金/其他分散','5,000元','作为组合分散，不因短期新闻满仓'],], [42*mm,27*mm,98*mm]),P('<b>个股学习账户的原则：</b>把5000元视为学费上限，而不是收益目标。若连续出现违规交易、冲动加仓、无法执行止损或记账中断，应暂停实盘，回到模拟和复盘。')]
story += [P('五、炒股应该学习什么',h1),P('1. 先学市场机制：交易时间、T+1/T+2、涨跌幅、停牌、最小交易单位、订单类型、结算、佣金、印花税、汇率和税务。A股、港股、美股规则不能混用。'),P('2. 再学财务报表：利润表看盈利质量，资产负债表看杠杆和现金，现金流量表看利润是否能变成现金。重点理解收入确认、应收账款、存货、商誉、资本开支、自由现金流、ROE、毛利率和净利率。'),P('3. 学估值而不是只看低PE：PE、PB、EV/EBITDA、DCF、股息率各有适用范围；低估值可能是周期高点、竞争恶化或治理风险，不能机械抄指标。'),P('4. 学行业和公司：行业空间、竞争格局、商业模式、护城河、管理层、资本配置、客户集中度、供应链和监管风险。'),P('5. 学组合管理：仓位、相关性、最大回撤、再平衡、现金比例、单股上限和退出条件。'),P('6. 学行为金融：追涨杀跌、损失厌恶、过度自信、确认偏误、FOMO、赌徒谬误。很多人不是输在不会分析，而是输在无法执行纪律。'),P('7. 学验证方法：区分样本内和样本外，保留交易成本与滑点，避免未来函数和数据窥探；策略必须有基准、足够样本和明确失效条件。')]
story += [P('六、12个月学习路线',h1),table([['阶段','重点任务','可交付成果'],['第1—2个月','交易规则、基金/ETF、财报三表、基本术语','写一页自己的投资纪律；完成10家公司财报速读'],['第3—4个月','行业研究、估值、公司公告和年报','完成3份公司研究卡片，不交易或极小额验证'],['第5—6个月','使用项目做数据筛选，学习回测偏差','把一个策略写成规则，规定买入、持有、退出和失效'],['第7—9个月','小额实盘、交易日志、组合风险','每笔记录假设、仓位、结果、错误和情绪'],['第10—12个月','复盘策略与个人适配度','判断自己更适合指数、基本面、量化筛选或不适合主动交易']], [25*mm,69*mm,73*mm])]
story += [P('七、渠道推荐',h1),P('优先使用一手或准一手资料：'),P('• 中国证监会投资者教育、中国投资者网；上海证券交易所、深圳证券交易所、北京证券交易所投教与规则页面。'),P('• 上市公司年报、半年报、季报、公告和交易所问询回复；不要只看财经自媒体的二次解读。'),P('• 美国市场：SEC Investor.gov、公司10-K/10-Q/8-K、FINRA投资者教育。SEC特别强调费用会长期侵蚀组合，FINRA明确提示日内交易可能极其危险，不应使用生活费、应急金或借款。'),P('• 港股：香港交易所、香港证监会、投委会“钱家有道”投资者教育。'),P('• 数据工具：你的项目用于A股候选池和复盘；财报与估值需回到公告和原始数据；海外市场先用官方披露和正规指数资料。'),P('<b>不建议作为主要学习渠道：</b>短视频荐股、付费群、只展示收益截图的课程、没有完整交易记录的“老师”、承诺稳定高收益的策略。')]
story += [P('八、跨境投资与合规提醒',h1),P('如果你是中国内地居民，直接通过境外券商投资美股、港股涉及账户、资金来源、外汇、税务、反洗钱和券商展业等问题，不能因为账户能开就推断路径一定合规。港股通、QDII等既有渠道与直接境外开户不是一回事。实际操作前应以国家外汇管理部门、证监会、交易所、券商和税务专业人士的最新规则为准，不要借用他人购汇额度、虚假申报用途或使用来路不明的跨境平台。')]
story += [P('九、风险红线',h1),P('• 不借钱、不融资、不用信用卡套现炒股；不把房租、学费、应急金投入高波动资产。'),P('• 不把单只股票当作信仰；不因亏损加倍摊平。'),P('• 不把项目筛出的候选股直接当成买入清单；必须经过公司研究、估值、仓位和退出条件。'),P('• 不以短期收益评价长期系统；至少记录一个完整市场周期。'),P('• 不交易自己无法解释商业模式、财务质量和风险来源的公司。')]
story += [P('十、最终建议',h1),P('<b>对市场：</b>优先A股作为学习和研究主场，原因不是A股一定优于美股或港股，而是你的项目、数据、语言和观察对象都对A股形成直接优势。海外市场适合未来做全球分散，但先从合规、低成本、分散化工具开始。'),P('<b>对资金：</b>如果10万元是主要存款，先保留约4万元应急金；投资部分以宽基、低成本和分批投入为核心；个股只用约5000元做学习验证，不融资。'),P('<b>对项目：</b>把它定位为“研究操作系统”：发现候选、补充信息、统一规则、追踪结果、复盘偏差。下一步最有价值的升级不是增加更多指标，而是加入可验证回测、基准对比、交易成本/滑点、样本外测试、组合回撤和策略失效监控。'),P('<b>一句话：</b>你现在最应该投资的不是某个市场，而是自己的投资能力和可重复的决策流程；先活下来、能复盘，再谈扩大本金。'),P('参考资料：',h1),P('中国证监会投资者教育：https://www.csrc.gov.cn/csrc/c100211/common_list.shtml<br/>上海证券交易所投资者教育：https://edu.sse.com.cn/<br/>SEC Investor.gov：https://www.investor.gov/<br/>FINRA Day Trading Risk Disclosure：https://www.finra.org/rules-guidance/rulebooks/finra-rules/2270<br/>香港交易所市场监管：https://www.hkex.com.hk/Global/Exchange/FAQ/Getting-Started/Regulation-of-the-Hong-Kong-Market?sc_lang=zh-HK<br/>香港投委会：https://www.ifec.org.hk/web/tc/index.page<br/><br/>注：规则和跨境监管可能更新，交易前应核对最新官方文件。',small)]

pdf=SimpleDocTemplate(str(OUT/'股票市场选择与学习路径研究报告.pdf'),pagesize=A4,rightMargin=15*mm,leftMargin=15*mm,topMargin=14*mm,bottomMargin=14*mm,title='股票市场选择与学习路径研究报告',author='Research Report')
pdf.build(story)
print('created', OUT/'股票市场选择与学习路径研究报告.pdf')
for p in sorted(FIG.glob('*.png')): print(p, p.stat().st_size)

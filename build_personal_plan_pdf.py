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

BASE=Path('reports/personal_financial_plan_2026')
FIG=BASE/'figures'; FIG.mkdir(exist_ok=True)
FONT='C:/Windows/Fonts/simhei.ttf'; pdfmetrics.registerFont(TTFont('SimHei',FONT))
def ft(n): return ImageFont.truetype(FONT,n)

def line_chart(path):
    W,H=1500,820; im=Image.new('RGB',(W,H),'white'); d=ImageDraw.Draw(im)
    d.text((50,25),'基准情景：流动资金变化预测（不含投资收益、奖金和公积金）',font=ft(34),fill='#172033')
    labels=['现在','2027年1月','2027年2月','2027年6月','2027年12月','2028年6月']
    vals=[120000,147400,157380,197300,257180,317060]
    left,top,bottom,right=140,150,650,100; maxv=340000
    pts=[]
    for i,v in enumerate(vals):
        x=left+i*(W-left-right)//(len(vals)-1); y=bottom-int((bottom-top)*v/maxv); pts.append((x,y))
    for yv in [0,100000,200000,300000]:
        y=bottom-int((bottom-top)*yv/maxv); d.line((left,y,W-right,y),fill='#E2E8F0',width=2); d.text((35,y-12),f'{yv//10000}万',font=ft(22),fill='#64748B')
    d.line((left,top,left,bottom),fill='#94A3B8',width=2); d.line((left,bottom,W-right,bottom),fill='#94A3B8',width=2)
    d.line(pts,fill='#C99A2E',width=7)
    for (x,y),lab,v in zip(pts,labels,vals):
        d.ellipse((x-10,y-10,x+10,y+10),fill='#C99A2E'); d.text((x-45,y-45),f'{v//10000:.1f}万',font=ft(22),fill='#172033'); d.text((x-55,bottom+20),lab,font=ft(21),fill='#334155')
    d.text((50,735),'说明：按当前至2027年1月每月结余5,480元，转正后每月结余9,980元估算。',font=ft(19),fill='#64748B')
    im.save(path)

def surplus_chart(path):
    W,H=1500,760; im=Image.new('RGB',(W,H),'white'); d=ImageDraw.Draw(im)
    d.text((50,25),'收入与月度现金结余',font=ft(36),fill='#172033')
    items=[('当前收入',9500,'#94A3B8'),('转正后收入',14000,'#C99A2E'),('当前结余',5480,'#74A88B'),('转正后结余',9980,'#D17D5A')]
    left,bottom,top,right=140,590,140,120; maxv=15000; slot=(W-left-right)//len(items)
    for i,(lab,v,col) in enumerate(items):
        bw=int(slot*.55); x=left+i*slot+(slot-bw)//2; y=bottom-int((bottom-top)*v/maxv); d.rectangle((x,y,x+bw,bottom),fill=col); d.text((x+bw//2-55,y-40),f'{v:,}',font=ft(25),fill='#172033'); d.text((x+bw//2-75,bottom+20),lab,font=ft(22),fill='#334155')
    d.line((left,top,left,bottom),fill='#94A3B8',width=2); d.line((left,bottom,W-right,bottom),fill='#94A3B8',width=2); d.text((50,690),'每月总现金流出=个人预算2,520元+给家里1,500元=4,020元。',font=ft(19),fill='#64748B'); im.save(path)
line_chart(FIG/'cashflow_forecast.png'); surplus_chart(FIG/'monthly_surplus.png')

S=getSampleStyleSheet(); normal=ParagraphStyle('CN',parent=S['BodyText'],fontName='SimHei',fontSize=9.1,leading=14.5,spaceAfter=4); h1=ParagraphStyle('H1',parent=S['Heading1'],fontName='SimHei',fontSize=15,textColor=colors.HexColor('#9A6B16'),spaceBefore=11,spaceAfter=6); h2=ParagraphStyle('H2',parent=S['Heading2'],fontName='SimHei',fontSize=11.5,textColor=colors.HexColor('#B07D1E'),spaceBefore=7,spaceAfter=4); title=ParagraphStyle('T',parent=S['Title'],fontName='SimHei',fontSize=21,leading=28,alignment=TA_CENTER,textColor=colors.HexColor('#1F2937')); sub=ParagraphStyle('SUB',parent=normal,alignment=TA_CENTER,fontSize=10.5); small=ParagraphStyle('SM',parent=normal,fontSize=7.3,textColor=colors.HexColor('#64748B'))
def P(t,st=normal): return Paragraph(t.replace('&','&amp;'),st)
def make_table(data,widths):
    t=Table([[P(str(c)) for c in row] for row in data],colWidths=widths,repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#F3E6C2')),('TEXTCOLOR',(0,0),(-1,0),colors.HexColor('#6B4B10')),('GRID',(0,0),(-1,-1),.3,colors.HexColor('#CBD5E1')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)])); return t

story=[P('个人资金与投资修复计划',title),Spacer(1,4),P('收入现金流｜生活预算｜资金变化预测｜股票风险控制',sub),P('版本V1.0｜制定日期：2026年9月7日｜个人规划文件，不构成投资建议',small),Spacer(1,8),P('<b>计划目标：</b>不是通过一次交易赚回过去亏损，而是通过控制风险、提高储蓄率、逐步建立投资系统，恢复净资产并避免再次发生不可逆的大亏损。',normal),RLImage(str(FIG/'monthly_surplus.png'),width=176*mm,height=89*mm)]
story += [P('一、已知情况',h1),make_table([['项目','当前/预计情况'],['当前流动存款','约120,000元'],['过去股票亏损','约140,000元；过去曾有约240,000元'],['当前月到手','约9,500元'],['当前每月给家里','1,500元'],['2027年2月转正后','月到手约14,000元；公积金双边约5,600元'],['2028年年中','全年税后总包预计约250,000元，不含公积金；具体奖金以实际为准']], [48*mm,128*mm]),P('本计划将过去亏损视为沉没成本，不把它当作必须通过短期交易追回的债务。恢复净资产可以依靠未来储蓄、收入增长和长期投资共同完成。')]
story += [P('二、月度生活预算',h1),P('计算假设：将“房租1750元，加水电可能2000元”按房租+水电合计约2000元/月计算；工作日按每月22天估算。若实际含义是房租1750元、另加水电2000元，则需要重新测算。'),make_table([['支出项目','月预算'],['房租+水电','2,000元'],['工作日食堂','5元×22天=110元'],['游泳','80元'],['话费及其他杂费','50元'],['米诺地尔等药费','80元'],['娱乐开支','200元'],['个人基本生活支出','2,520元'],['给家里','1,500元'],['每月总现金流出','4,020元']], [110*mm,66*mm]),P('上述预算较为节制，尚未单独计入交通、服装、回家、社交聚餐、保险、培训、搬家、设备、体检和较大额医疗支出。建议每月另设500—1,000元不可预见支出准备金，不把理论结余全部视为可投资资金。')]
story += [P('三、每月结余预测',h1),make_table([['阶段','月收入','月总支出','月可结余'],['当前至2027年1月底','9,500元','4,020元','5,480元'],['2027年2月转正后','14,000元','4,020元','9,980元']], [48*mm,40*mm,40*mm,48*mm]),P('如果实际生活支出比预算高500—1,000元，结余会相应减少。每月底应以真实账单更新本表。')]
story += [P('四、资金变化预测：基准情景',h1),P('假设2026年9月至2027年1月底按5个月，2027年2月至2028年6月底按17个月计算；只计算工资结余，不计算股票涨跌、利息、年终奖和公积金。'),RLImage(str(FIG/'cashflow_forecast.png'),width=176*mm,height=96*mm),make_table([['时间点','累计流动资金预测'],['当前，2026年9月','120,000元'],['2027年1月底','147,400元'],['2027年2月底','157,380元'],['2027年6月底','197,300元'],['2027年12月底','257,180元'],['2028年6月底，不含奖金','317,060元']], [70*mm,106*mm]),P('<b>关键判断：</b>你不需要让当前12万元在股市中翻倍，才能回到过去24万元的资产水平。只要稳定工作、控制支出、不发生重大投资损失，工资结余本身就可能在2028年前后帮助你恢复甚至超过过去资产水平。')]
story += [P('五、年终奖情景',h1),P('如果“2028年年中全年税后总包25万元”指2027年度税后总收入，且转正后月到手按14,000元计算，则隐含奖金约为：250,000−14,000×12=82,000元。'),make_table([['情景','2028年年中流动资产预测'],['不含奖金','约317,060元'],['加入约82,000元奖金','约399,060元'],['保守生活支出情景，不含奖金','约306,060元'],['保守生活支出情景，含奖金','约388,060元']], [84*mm,92*mm]),P('奖金可能受入职月份、绩效、公司政策、税务和发放口径影响，不应提前消费或提前计入投资计划。公积金属于长期净资产，但不等同于随时可用现金，因此本预测未计入。')]
story += [P('六、当前12万元分层方案',h1),make_table([['用途','建议金额','纪律'],['应急金','50,000元','应对失业、搬家、医疗和家庭突发支出，不用于炒股'],['核心长期投资','40,000元','宽基或分散化权益，分6—12个月投入'],['主动选股账户','10,000元','验证项目和个人策略，不融资、不报复性加仓'],['现金/未来大额支出','20,000元','等待机会，覆盖回家、培训、设备和搬家等'],['合计','120,000元','—']], [42*mm,30*mm,104*mm]),P('随着转正和收入稳定，应急金可逐步提高到6万—8万元。若存在高息负债，偿债优先级高于投资。')]
story += [P('七、每月结余自动分配',h1),P('<b>当前至2027年1月底，结余约5,480元：</b>每月3,000元进入核心长期投资，1,980元进入现金/未来支出准备，主动交易最多500元且不强制交易。主动账户达到1万—1.5万元后暂停补充。'),P('<b>2027年2月转正后，结余约9,980元：</b>每月6,500元进入核心长期投资，2,480元进入现金/未来支出准备，主动交易最多1,000元。转正后先观察实际工资、社保、公积金和生活成本三个月，再决定是否调整。')]
story += [P('八、股票账户纪律',h1),P('1. 2026年至2027年上半年，主动选股账户上限1万—1.5万元。'),P('2. 单只股票不超过主动账户20%—25%，单个行业不超过主动账户40%。'),P('3. 不融资、不借钱、不用信用卡套现，不使用应急金交易。'),P('4. 每笔交易写清买入逻辑、预期周期、退出条件和最大可承受损失。'),P('5. 如果一只股票今天没有持仓，我是否仍愿意用现在的价格买入？若不愿意，不能仅因“已经亏了很多”继续持有。'),P('6. 项目筛选结果只能进入候选池，必须经过公司研究、估值、仓位和退出条件检查。')]
story += [P('九、项目使用方式',h1),P('项目适合用于A股行情、K线、前复权、MA/MACD/KDJ/RSI、财务、板块、国家队持仓、雪球观点和策略筛选的统一研究与复盘。它的定位应是“研究操作系统”，不是自动赚钱或自动荐股系统。'),P('下一步优先升级方向：加入基准指数比较、手续费和滑点、涨跌停无法成交、样本外测试、最大回撤、连续亏损次数、信号后的跟踪数据库和策略失效监控。')]
story += [P('十、阶段目标',h1),make_table([['阶段','目标'],['2026年9月—2027年1月','停止报复性交易；完成持仓复盘；应急金达到5万元；主动账户控制在1万—1.5万元'],['2027年2月—2027年12月','转正后观察真实现金流；核心投资分批进行；主动策略积累6—12个月记录'],['2028年上半年','奖金到账后重新评估住房、家庭、职业和应急需求；不提前消费或提前重仓']], [54*mm,122*mm])]
story += [P('十一、最终原则',h1),P('• 过去亏损是沉没成本，不能决定今天是否继续持有。'),P('• 当前12万元的首要任务是保护本金，而不是承担翻倍任务。'),P('• 真正的回本来源是未来收入、储蓄、公积金和长期投资共同作用。'),P('• 先验证主动策略，再扩大本金；没有验证就不加仓。'),P('• 任何需要借钱、融资、集中押注才能实现的回本计划，都不是稳健计划。'),P('<b>最终目标：不是尽快回到过去的24万元，而是建立一个不会因为一次错误再次跌破财务安全线的系统。</b>')]
story += [P('十二、执行复盘模板',h1),make_table([['每月底记录','填写内容'],['本月实际收入',''],['本月实际生活支出','与预算2,520元比较'],['本月给家里金额','默认1,500元'],['本月新增储蓄','收入−全部现金流出'],['股票账户收益/回撤','不只看收益，记录最大回撤'],['是否违反纪律','融资、追涨、补亏损、冲动交易等'],['下月调整','只调整预算和流程，不因短期涨跌改变长期目标']], [60*mm,116*mm]),P('注：本计划是基于你提供的信息制作的估算文件。实际执行时，每月底更新一次；如果房租、水电、交通、家庭支持、收入或奖金口径发生变化，应重新计算。',small)]

out=BASE/'个人资金与投资修复计划.pdf'
pdf=SimpleDocTemplate(str(out),pagesize=A4,rightMargin=15*mm,leftMargin=15*mm,topMargin=14*mm,bottomMargin=14*mm,title='个人资金与投资修复计划',author='Research Report')
pdf.build(story)
print(out, out.stat().st_size)

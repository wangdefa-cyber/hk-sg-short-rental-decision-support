const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, PageBreak,
  ImageRun, Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  TableLayoutType, TableOfContents, Footer, PageNumber, LevelFormat,
  VerticalAlign, PageOrientation, SectionType
} = require('docx');

const ROOT = 'C:/Users/Auraro/Desktop/Data Mining';
const REPORT_DIR = path.join(ROOT, 'report');
const CHART = path.join(ROOT, 'outputs', 'charts');
const TREND_CHART = path.join(CHART, 'trends');
const OUT = path.join(REPORT_DIR, '数据挖掘课程中期报告_香港新加坡短租分析_最终版.docx');
const BODY_FONT = { ascii: 'Times New Roman', eastAsia: '宋体', hAnsi: 'Times New Roman' };
const HEAD_FONT = { ascii: 'Arial', eastAsia: '黑体', hAnsi: 'Arial' };
const NAVY = '17365D';
const MUTED = '666666';

const readJson = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), 'utf8'));
const citySummary = readJson('outputs/tables/descriptive_summary.json').city_summary;
const kmeans = readJson('outputs/tables/kmeans_summary.json');
const priceModels = readJson('outputs/tables/price_model_summary.json');
const hosts = readJson('outputs/tables/host_competition_summary.json');
const spatial = readJson('outputs/tables/spatial_summary.json');
const network = readJson('outputs/tables/network_summary.json');
const supply = readJson('outputs/tables/supply_demand_summary.json');
const trends = readJson('outputs/tables/google_trends_summary.json');
const quality = readJson('outputs/tables/warehouse_quality.json');
const audit = readJson('outputs/tables/data_audit.json');
const textSummary = readJson('outputs/tables/text_analysis_summary.json');
const figureManifest = readJson('outputs/charts/trends/figure_manifest.json');

function parseCsv(file) {
  const text = fs.readFileSync(path.join(ROOT, file), 'utf8').replace(/^\uFEFF/, '');
  const rows = [];
  let row = [], field = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"') {
      if (quoted && text[i + 1] === '"') { field += '"'; i++; }
      else quoted = !quoted;
    } else if (ch === ',' && !quoted) { row.push(field); field = ''; }
    else if ((ch === '\n' || ch === '\r') && !quoted) {
      if (ch === '\r' && text[i + 1] === '\n') i++;
      if (field.length || row.length) { row.push(field); rows.push(row); row = []; field = ''; }
    } else field += ch;
  }
  if (field.length || row.length) { row.push(field); rows.push(row); }
  const headers = rows.shift();
  return rows.map(r => Object.fromEntries(headers.map((h, i) => [h, r[i] ?? ''])));
}
const travelCorr = parseCsv('outputs/tables/google_trends_review_correlation.csv')
  .filter(r => r.series_mode === 'month_over_month_change' && Number(r.lag_months) === 2);
const topQueries = parseCsv('outputs/tables/google_trends_top_queries.csv');
const trendMetrics = parseCsv('outputs/tables/google_trends_series_metrics.csv');

const hkAudit = audit.cities['hong-kong'].files;
const sgAudit = audit.cities['singapore'].files;
const hkQuality = quality.listing_quality['hong-kong'];
const sgQuality = quality.listing_quality['singapore'];
const hkReview = quality.review_deduplication['hong-kong'];
const sgReview = quality.review_deduplication['singapore'];
const hkPriceMissingRate = hkQuality.price_missing / hkQuality.rows * 100;
const sgPriceMissingRate = sgQuality.price_missing / sgQuality.rows * 100;
const hk = citySummary.find(x => x.city_key === 'hong-kong');
const sg = citySummary.find(x => x.city_key === 'singapore');
const hkModel = priceModels.models.find(x => x.city_key === 'hong-kong');
const sgModel = priceModels.models.find(x => x.city_key === 'singapore');
const hkMetric = trendMetrics.find(x => x.city_key === 'hong-kong' && x.keyword_group === 'tourism');
const sgMetric = trendMetrics.find(x => x.city_key === 'singapore' && x.keyword_group === 'tourism');
const trendMetric = (city, group) => trendMetrics.find(x => x.city_key === city && x.keyword_group === group);
const monthNames = ['', '1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];

function imageDimensions(file) {
  const data = fs.readFileSync(file);
  return { width: data.readUInt32BE(16), height: data.readUInt32BE(20) };
}

function pngRun(file, width, alt) {
  const dims = imageDimensions(file);
  const height = Math.round(width * dims.height / dims.width);
  return new ImageRun({
    data: fs.readFileSync(file),
    type: 'png',
    transformation: { width, height },
    altText: alt ? { name: alt.slice(0, 60), description: alt } : undefined,
  });
}

function h(text, level) {
  return new Paragraph({
    heading: level === 1 ? HeadingLevel.HEADING_1 : level === 2 ? HeadingLevel.HEADING_2 : HeadingLevel.HEADING_3,
    children: [new TextRun({ text })],
  });
}

function body(text) {
  return new Paragraph({
    spacing: { line: 360, after: 100 },
    indent: { firstLine: 420 },
    children: [new TextRun({ text, size: 21, font: BODY_FONT })],
  });
}

function bullet(text) {
  return new Paragraph({
    numbering: { reference: 'project-bullets', level: 0 },
    spacing: { line: 330, after: 60 },
    children: [new TextRun({ text, size: 21, font: BODY_FONT })],
  });
}

function caption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 160 },
    keepNext: false,
    children: [new TextRun({ text, italics: true, size: 17, color: MUTED, font: BODY_FONT })],
  });
}

function figure(file, cap, alt, width = 560) {
  if (!fs.existsSync(file)) return [body(`[图表待生成：${path.basename(file)}]`)];
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      keepNext: true,
      children: [pngRun(file, width, alt)],
    }),
    caption(cap),
  ];
}

function cell(text, opts = {}) {
  const width = opts.width || 1800;
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    verticalAlign: VerticalAlign.CENTER,
    shading: opts.header ? { fill: NAVY, type: ShadingType.CLEAR, color: 'auto' } : opts.shade ? { fill: 'F2F5F8', type: ShadingType.CLEAR, color: 'auto' } : undefined,
    children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 0, line: 260 },
      children: [new TextRun({ text: String(text ?? ''), bold: !!opts.header, color: opts.header ? 'FFFFFF' : '000000', size: opts.header ? 18 : 18, font: BODY_FONT })],
    })],
  });
}

function table(headers, rows, cap, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  return [
    new Table({
      width: { size: total, type: WidthType.DXA },
      columnWidths: widths,
      layout: TableLayoutType.FIXED,
      rows: [
        new TableRow({
          tableHeader: true,
          cantSplit: true,
          children: headers.map((x, i) => cell(x, { header: true, width: widths[i] })),
        }),
        ...rows.map((r, ri) => new TableRow({
          cantSplit: true,
          children: r.map((x, i) => cell(x, { width: widths[i], shade: ri % 2 === 1 })),
        })),
      ],
    }),
    caption(cap),
  ];
}

const coverChildren = [];
const children = [];

// Cover: follows the original course template's first-page structure.
function coverLine(text, size = 24, font = BODY_FONT, after = 0) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after, line: 300 },
    children: [new TextRun({ text, size, font })],
  });
}
function blankLine(size = 21, after = 0) {
  return new Paragraph({ spacing: { after, line: 260 }, children: [new TextRun({ text: '', size })] });
}
const members = [
  ['信息管理与信息系统', '2024116236', '程国庆'],
  ['信息管理与信息系统', '2024116231', '李俊涵'],
  ['信息管理与信息系统', '2024116255', '陈尚嘉'],
  ['信息管理与信息系统', '2024116206', '丁文艳'],
  ['信息管理与信息系统', '2024116254', '李迪雯'],
];
coverChildren.push(
  blankLine(), blankLine(), blankLine(),
  coverLine('2026~2027学年第1学期', 24),
  coverLine('数据挖掘', 24, { ascii: 'Times New Roman', eastAsia: '华文楷体', hAnsi: 'Times New Roman' }),
  coverLine('中期报告', 24, { ascii: 'Times New Roman', eastAsia: '华文楷体', hAnsi: 'Times New Roman' }),
  blankLine(26), blankLine(26),
  coverLine('城市短租平台供需匹配与经营决策支持系统', 22, HEAD_FONT),
  coverLine('——基于中国香港与新加坡的多维分析', 20, HEAD_FONT),
  blankLine(), blankLine(), blankLine(), blankLine(), blankLine(), blankLine(),
  ...members.map(([major, sid, name]) => coverLine(`${major}    ${sid}    ${name}`, 16, HEAD_FONT, 80)),
  blankLine(16), blankLine(16),
  coverLine('2026年10月', 16),
  blankLine()
);

// Abstract
children.push(h('摘  要', 1));
children.push(body(
  `本研究以中国香港和新加坡短租市场为研究对象，基于 Inside Airbnb 公开房源快照与 Google Trends 分别导出的月度搜索兴趣数据构建跨城市分析数据集。` +
  `香港快照包含 ${Number(hk.listing_count).toLocaleString()} 套房源、${Number(hk.host_count).toLocaleString()} 位房东；新加坡快照包含 ${Number(sg.listing_count).toLocaleString()} 套房源、${Number(sg.host_count).toLocaleString()} 位房东。` +
  `研究完成房源清洗、维度建模、描述统计、空间分析、K-Means 经营类型、随机森林房价模型、房东集中度、评论文本分析、社区供需匹配和交互式决策支持系统。香港随机森林测试集 R²(log)=${hkModel.metrics.random_forest.r2_log.toFixed(3)}，新加坡为 ${sgModel.metrics.random_forest.r2_log.toFixed(3)}。` +
  `Google Trends 共解析 7 条月度序列、427 条观测，时间范围为 ${trends.date_min} 至 ${trends.date_max}，无缺失值。由于各文件独立归一化，研究使用每条序列的 z-score 和月度变化进行跨序列比较，不将不同文件的原始 0–100 指数视为可直接比较的绝对搜索量。`
));
children.push(new Paragraph({ spacing: { after: 200 }, children: [
  new TextRun({ text: '关键词：', bold: true, size: 21, font: BODY_FONT }),
  new TextRun({ text: '短租市场；香港；新加坡；供需匹配；Google Trends；K-Means；随机森林；空间分析；决策支持', size: 21, font: BODY_FONT })
]}));
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(h('目  录', 1));
children.push(new TableOfContents('目录', { hyperlink: true, headingStyleRange: '1-3', beginDirty: true }));
children.push(new Paragraph({ children: [new PageBreak()] }));

// 1
children.push(h('1  需求分析', 1));
children.push(h('1.1  环境假设', 2));
children.push(h('1.1.1  企业概况或业务背景', 3));
children.push(body('本项目假设研究对象为一家在国际城市运营短租业务的平台区域团队，连接房东、住客、物业服务和清洁/配送合作方。平台通过房源发布、搜索匹配、预订、支付、入住服务、评价和复购形成经营闭环。企业、组织架构与决策角色均为课程研究中的业务环境假设，不代表任何真实企业内部组织。'));
children.push(body('中国香港和新加坡均为高密度国际城市，具有旅游、商务出行和跨境访客需求，同时其短租供给受住房、旅游和监管环境影响。选择两城进行同口径结构比较，有助于识别不同市场规模与房东结构下的经营差异。'));
children.push(h('1.1.2  组织架构', 3));
children.push(body('虚拟区域运营团队由区域管理层统筹，下设市场研究、供给运营、收益与定价、房东运营、客户体验和数据分析六类职能。组织架构决定系统的用户角色、看板指标和决策流程。'));
children.push(...figure(path.join(CHART, '00_org_structure.png'), '图 1-1  虚拟短租平台区域运营组织架构（研究假设）', '短租平台区域运营组织架构图，区域管理层下设计六个职能团队。'));
children.push(h('1.1.3  主要业务', 3));
children.push(body('主要业务从房东入驻和房源上架开始，经过定价与库存管理、搜索与预订、入住服务、评价反馈，再回到经营决策。需求侧活动和供给侧管理通过评论、可订状态和经营指标形成反馈闭环。'));
children.push(...figure(path.join(CHART, '00_business_flow.png'), '图 1-2  短租平台主要业务流程图', '短租平台从房东入驻到评价反馈和经营决策的业务流程图。'));
children.push(h('1.2  DSS 需求', 2));
children.push(h('1.2.1  管理重点与难点', 3));
[
  '供给结构复杂：房源数量、房型、社区密度和房东类型共同决定竞争结构，仅比较房源总数会误判市场机会。',
  '价格缺乏可比性：香港使用 HKD、新加坡使用 SGD；同城内还要区分房型、容量、最低入住天数和异常挂牌。',
  '需求难以直接观测：平台不公开真实订单和入住率，只能使用评论活跃度和 Google Trends 搜索兴趣作为需求代理。',
  '口碑需要定位：应从评论文本识别位置、卫生、入住、服务和噪音等主题，而不能只看总评分。',
  '社区层面存在供需错配：高需求低供给可能是机会，也可能是数据不足或监管约束；高供给低需求意味着价格和经营压力。'
].forEach(x => children.push(bullet(x)));
children.push(h('1.2.2  所需的决策支持功能', 3));
[
  '城市和社区经营总览：房源、房东、价格、评分和评论活动。',
  '供给结构与竞争分析：房型、房东规模、HHI、Gini 和 Lorenz 曲线。',
  '需求关注分析：评论月度趋势与 Google Trends 的导入、标准化、季节性和相关性分析。',
  '挖掘实验室：K-Means、随机森林、DBSCAN 和特征重要性。',
  '社区供需匹配：供给指数 S、需求代理指数 D、匹配指数 M 和四象限。',
  '经营决策中心：输入城市、社区、房型、容量和定位，输出可解释价格区间、竞争程度、风险和策略。'
].forEach(x => children.push(bullet(x)));
children.push(new Paragraph({ children: [new PageBreak()] }));

// 2
children.push(h('2  数据获取与处理', 1));
children.push(h('2.1  数据来源与获取方式', 2));
children.push(body('Inside Airbnb 提供城市级公开房源快照，包含房源、日历、评论和社区边界。香港快照日期为 2026-09-20，新加坡为 2026-09-23。原始文件下载日期、下载链接、文件大小和 SHA256 哈希记录在 data_manifest.json 中。数据授权为 CC BY 4.0。'));
children.push(body(`Google Trends 使用人工导出的 8 个真实 CSV 文件。其中 7 个为单个关键词的月度时间序列，1 个为全球 Airbnb 相关搜索词 Top 50。月度序列时间为 ${trends.date_min} 至 ${trends.date_max}，共 61 个月；7 条序列均无缺失值。由于每个文件独立归一化，原始指数不进行跨文件绝对水平比较。`));
children.push(...table(
  ['城市', '快照日期', '房源', '日历记录', '评论', '社区边界'],
  [['香港','2026-09-20',Number(hk.listing_count).toLocaleString(),Number(hkAudit['calendar.csv.gz'].row_count).toLocaleString(),Number(hkAudit['reviews.csv.gz'].row_count).toLocaleString(),Number(hkAudit['neighbourhoods.geojson'].feature_count).toLocaleString()],['新加坡','2026-09-23',Number(sg.listing_count).toLocaleString(),Number(sgAudit['calendar.csv.gz'].row_count).toLocaleString(),Number(sgAudit['reviews.csv.gz'].row_count).toLocaleString(),Number(sgAudit['neighbourhoods.geojson'].feature_count).toLocaleString()]],
  '表 2-1  原始数据规模', [1100,1300,1000,1300,1000,1000]
));
children.push(h('2.2  数据表结构与数据示例', 2));
children.push(body('房源表为一套房源一行，日历表为一个房源一天一行，评论表为一条评论一行；Google Trends 表为一条序列一个月一行。核心字段和用途见表 2-2。'));
children.push(...table(
  ['数据表', '核心字段', '用途'],
  [['listings','listing_id, host_id, room_type, price, availability_365, review_scores_rating','房源、价格、房东和口碑'],['calendar','listing_id, date, available, minimum_nights','可订率、季节性和日历结构'],['reviews','listing_id, id, date, comments','月度评论活动和文本分析'],['Google Trends','source_file, date, keyword, interest_index','城市级搜索关注度'],['GeoJSON','neighbourhood, geometry','空间分析和地图']],
  '表 2-2  核心数据表与字段', [1700,4300,2300]
));
children.push(h('2.3  数据预处理说明', 2));
children.push(h('2.3.1  数据清洗', 3));
children.push(body(`价格字段去除货币符号和千分位后转数值。香港识别 ${Number(hkQuality.price_missing).toLocaleString()} 条价格缺失（${hkPriceMissingRate.toFixed(1)}%）和 ${Number(hkQuality.price_outliers).toLocaleString()} 条异常值；新加坡识别 ${Number(sgQuality.price_missing).toLocaleString()} 条价格缺失（${sgPriceMissingRate.toFixed(1)}%）和 ${Number(sgQuality.price_outliers).toLocaleString()} 条异常值。异常值保留记录并标记，不直接删除。评论按 city_key + review_id 去重，香港删除 ${Number(hkReview.duplicate_review_id_rows).toLocaleString()} 条重复评论，新加坡删除 ${Number(sgReview.duplicate_review_id_rows).toLocaleString()} 条。`));
children.push(h('2.3.2  数据集成', 3));
children.push(body('以 city_key + listing_id 建立跨城市唯一房源键，以 city_key + host_id 建立房东键。日历和评论通过 listing_key 关联房源维度，两地未匹配记录均为 0。大事实表使用 Parquet，维度和汇总表使用 SQLite。'));
children.push(h('2.3.3  数据选取', 3));
children.push(body('描述统计保留价格缺失，价格模型只使用清洗后有效价格；空间分析只排除经纬度缺失或越界记录。评论只作为需求活动代理，不把评论数量解释为订单量或入住人数。'));
children.push(h('2.3.4  数据转换', 3));
[
  '价格拆分为 price_local、price_clean 和 price_outlier。',
  '从 bathrooms_text 解析卫浴数量、共享或独立属性。',
  '根据房东房源数量划分单房源、小型多房源和专业多房源房东。',
  '为 Google Trends 每条独立序列生成 z-score、相对首月指数和月度变化率。',
  'estimated_occupancy_l365d 按估计入住晚数处理，仅保留 0–365 晚；occupancy_estimate_rate = 晚数 / 365。'
].forEach(x => children.push(bullet(x)));
children.push(h('2.4  集成后的数据统计分析—Python', 2));
children.push(body(`香港房源数量为 ${Number(hk.listing_count).toLocaleString()} 套，约为新加坡 ${Number(sg.listing_count).toLocaleString()} 套的 ${(hk.listing_count/sg.listing_count).toFixed(2)} 倍。香港和新加坡独立房间占比分别为 ${(hk.private_room_share*100).toFixed(1)}% 和 ${(sg.private_room_share*100).toFixed(1)}%，两城均以房间型产品为主。`));
children.push(...table(
  ['指标','香港','新加坡'],
  [['房源数量',Number(hk.listing_count).toLocaleString(),Number(sg.listing_count).toLocaleString()],['房东数量',Number(hk.host_count).toLocaleString(),Number(sg.host_count).toLocaleString()],['整套房源占比',(hk.entire_home_share*100).toFixed(2)+'%',(sg.entire_home_share*100).toFixed(2)+'%'],['独立房间占比',(hk.private_room_share*100).toFixed(2)+'%',(sg.private_room_share*100).toFixed(2)+'%'],['价格中位数',hk.price_median_local.toFixed(2)+' HKD',sg.price_median_local.toFixed(2)+' SGD'],['平均评分',hk.review_score_mean.toFixed(3),sg.review_score_mean.toFixed(3)],['专业房东占比',(hk.professional_host_share*100).toFixed(2)+'%',(sg.professional_host_share*100).toFixed(2)+'%']],
  '表 2-3  两城核心描述统计', [2500,2100,2100]
));
children.push(...figure(path.join(CHART,'01_city_listing_count.png'),'图 2-1  香港与新加坡房源总量对比','柱状图比较香港与新加坡房源总量。'));
children.push(...figure(path.join(CHART,'02_room_type_share.png'),'图 2-2  两地房型结构占比','堆叠柱状图展示香港和新加坡的房型结构占比。'));
children.push(...figure(path.join(CHART,'03_price_distribution.png'),'图 2-3  清洗后房源价格分布','箱线图展示香港和新加坡的清洗后价格分布，单位为各自本币。'));
children.push(h('2.5  集成后的数据统计分析—Excel 或其他工具', 2));
children.push(body('分析结果已整理为 Excel 多维分析工作簿，包含说明、香港房源、新加坡房源、城市对比、社区统计、房型统计、月度评论、房东经营、房东集中度、供需匹配、KMeans 画像、趋势状态和字段说明等工作表。表头冻结并设置筛选，可直接建立透视表。'));
children.push(...table(
  ['Excel 工作表','主要分析维度'],
  [['香港房源 / 新加坡房源','城市 × 社区 × 房型 × 价格 × 评分 × 经营类型'],['城市对比 / 房型统计','城市 × 房型 × 供给占比 × 价格'],['社区统计 / 供需匹配','社区 × 密度 × 供给指数 × 需求代理 × 匹配指数'],['月度评论 / 趋势状态','年月 × 评论活动 × Google Trends 导入状态'],['房东经营 / 房东集中度','房东类型 × 房源数 × HHI × Gini']],
  '表 2-4  Excel 多维分析结构', [3000,4700]
));
children.push(new Paragraph({ children: [new PageBreak()] }));

// 3
children.push(h('3  数据多维分析与可视化', 1));
children.push(h('3.1  XX 数据多维分析—Excel', 2));
children.push(h('3.1.1  数据源设置', 3));
children.push(body('Excel 工作簿的数据源来自清洗后的 Parquet/CSV 导出，不使用手工录入的统计值。每个工作表采用一行一条记录的结构，便于使用 Excel 表格和数据透视表。'));
children.push(h('3.1.2  建立多维数据集', 3));
children.push(body('多维数据集以城市、社区、房型、月份和房东类型为主要维度，以房源数量、价格、评分、评论活动、可订率和供需指数为度量。跨城市绝对价格不作直接比较。'));
children.push(h('3.1.3  维度设计', 3));
children.push(body('城市维度用于两城对比；社区维度用于区域内供给和价格差异；房型维度区分整套、独立房间、合住和酒店房间；月份维度用于评论活动；房东类型用于识别单房源、小型多房源和专业多房源房东。'));
children.push(h('3.1.4  多维数据浏览分析', 3));
children.push(body('用户可以按城市、社区、房型筛选，并观察价格中位数、评分、评论数量和可订率变化。Excel 自动筛选与冻结表头保证可以快速钻取。'));
children.push(h('3.1.5  数据钻取', 3));
children.push(body('钻取路径为“城市 → 社区 → 房型 → 房源”，同时在社区层与供需匹配表关联。报告中的判断必须配合样本量和缺失率阅读。'));
children.push(h('3.2  XX 数据多维分析—Power BI/帆软', 2));
children.push(body('Power BI-ready CSV 和模型关系说明已整理，包含 dim_city、dim_listing、dim_neighbourhood、dim_date、fact_listing_snapshot、fact_calendar_monthly、fact_review_monthly、fact_google_trends、supply_demand_district 等文件。本轮提供 CSV 数据模型与 DAX 说明；具体关系和 DAX 见 outputs/powerbi/PowerBI模型说明.md。'));
children.push(h('3.3  XX 数据—网络分析—Gephi', 2));
children.push(...table(
  ['网络指标','数值'],
  [['节点数',Number(network.nodes).toLocaleString()],['边数',Number(network.edges).toLocaleString()],['连通分量',network.connected_components],['最大连通分量节点',Number(network.largest_component_nodes).toLocaleString()],['网络密度',Number(network.density).toFixed(6)]],
  '表 3-1  多房源房东网络指标', [3000,2200]
));
children.push(body('网络只保留多房源房东及其真实房源关系，生成房东、房源和社区节点。所有边来自真实 host_id、listing_id 和社区字段，没有生成虚构关系。'));
children.push(h('3.4  XX 数据分析展示—ECharts', 2));
children.push(body('项目生成可离线打开的 ECharts 看板，包含城市房源量、房型结构、价格箱线图、社区密度、社区价格热力图、月度评论、房东结构、Google Trends 标准化趋势、全球相关搜索词、价格与评分散点、K-Means 聚类、供需四象限和城市雷达图。'));
children.push(...figure(path.join(CHART,'11a_echarts_top.png'),'图 3-1  ECharts 看板：城市、房型、价格与供给结构','ECharts 看板上半部分，展示城市房源量、房型结构、价格和社区密度。',560));
children.push(...figure(path.join(CHART,'11c_echarts_trends.png'),'图 3-2  ECharts 看板：Google Trends 与相关搜索词','ECharts 看板中 Google Trends 标准化趋势和全球 Airbnb 相关搜索词。',560));
children.push(...figure(path.join(CHART,'11d_echarts_bottom.png'),'图 3-3  ECharts 看板：聚类与供需四象限','ECharts 看板下半部分，展示价格散点、K-Means 聚类和供需四象限。',560));
children.push(h('3.5  XX 文本数据—词云图', 2));
children.push(body('评论文本先去除 HTML 标签、统一空白并移除英文停用词，再使用 CountVectorizer 和 TF-IDF 提取高频词。词云只展示真实评论文本，评论数量不解释为订单量。'));
children.push(...figure(path.join(CHART,'10_hong-kong_review_wordcloud.png'),'图 3-4  香港 Airbnb 评论词云','香港 Airbnb 评论高频词云，主要包含地点、清洁、房东、房间和交通等词。'));
children.push(...figure(path.join(CHART,'10_singapore_review_wordcloud.png'),'图 3-5  新加坡 Airbnb 评论词云','新加坡 Airbnb 评论高频词云，主要包含地点、清洁、住宿、MRT 和房东等词。'));
for (const item of textSummary.summary) children.push(body(`${item.city_name}高频词包括：${item.top_terms.slice(0,8).join('、')}。这些词反映位置、清洁、房东服务、房间和交通等体验主题，但不能替代结构化满意度量表。`));

children.push(h('3.6  XX 数据—XX 工具', 2));
children.push(body('自选工具部分包括 Google Trends 需求关注分析、空间分析、K-Means、随机森林、DBSCAN、HHI/Gini、社区供需匹配和 Streamlit 决策支持系统。'));

children.push(h('3.6.1  Google Trends 搜索关注度分析', 3));
children.push(body(`Google Trends 共解析 7 条时间序列和 1 个相关搜索词文件，覆盖 ${trends.date_min} 至 ${trends.date_max}。每条城市序列包含 61 个月，缺失值为 0。由于每个文件由 Google Trends 独立归一化，研究不比较原始 0–100 绝对水平，而使用每条序列的 z-score、首尾三个月均值、线性斜率和月度变化进行解释。`));
children.push(...table(
  ['城市/主题','首3月均值','末3月均值','首尾变化','斜率/月','季节峰值'],
  [
    ['香港-旅游',Number(trendMetric('hong-kong','tourism').first3_mean).toFixed(1),Number(trendMetric('hong-kong','tourism').last3_mean).toFixed(1),(Number(trendMetric('hong-kong','tourism').change_first3_to_last3_pct)).toFixed(1)+'%',Number(trendMetric('hong-kong','tourism').slope_per_month).toFixed(2),monthNames[trendMetric('hong-kong','tourism').seasonal_peak_month]],
    ['香港-住宿',Number(trendMetric('hong-kong','accommodation').first3_mean).toFixed(1),Number(trendMetric('hong-kong','accommodation').last3_mean).toFixed(1),(Number(trendMetric('hong-kong','accommodation').change_first3_to_last3_pct)).toFixed(1)+'%',Number(trendMetric('hong-kong','accommodation').slope_per_month).toFixed(2),monthNames[trendMetric('hong-kong','accommodation').seasonal_peak_month]],
    ['香港-Airbnb',Number(trendMetric('hong-kong','airbnb').first3_mean).toFixed(1),Number(trendMetric('hong-kong','airbnb').last3_mean).toFixed(1),(Number(trendMetric('hong-kong','airbnb').change_first3_to_last3_pct)).toFixed(1)+'%',Number(trendMetric('hong-kong','airbnb').slope_per_month).toFixed(2),monthNames[trendMetric('hong-kong','airbnb').seasonal_peak_month]],
    ['新加坡-旅游',Number(trendMetric('singapore','tourism').first3_mean).toFixed(1),Number(trendMetric('singapore','tourism').last3_mean).toFixed(1),(Number(trendMetric('singapore','tourism').change_first3_to_last3_pct)).toFixed(1)+'%',Number(trendMetric('singapore','tourism').slope_per_month).toFixed(2),monthNames[trendMetric('singapore','tourism').seasonal_peak_month]],
    ['新加坡-住宿',Number(trendMetric('singapore','accommodation').first3_mean).toFixed(1),Number(trendMetric('singapore','accommodation').last3_mean).toFixed(1),(Number(trendMetric('singapore','accommodation').change_first3_to_last3_pct)).toFixed(1)+'%',Number(trendMetric('singapore','accommodation').slope_per_month).toFixed(2),monthNames[trendMetric('singapore','accommodation').seasonal_peak_month]],
    ['新加坡-Airbnb',Number(trendMetric('singapore','airbnb').first3_mean).toFixed(1),Number(trendMetric('singapore','airbnb').last3_mean).toFixed(1),(Number(trendMetric('singapore','airbnb').change_first3_to_last3_pct)).toFixed(1)+'%',Number(trendMetric('singapore','airbnb').slope_per_month).toFixed(2),monthNames[trendMetric('singapore','airbnb').seasonal_peak_month]],
  ],
  '表 3-2  Google Trends 独立序列趋势摘要',
  [1500,1000,1000,1000,1000,1100]
));
children.push(body(`香港的旅游、住宿和 Airbnb 搜索兴趣在各自序列口径下均呈上升；新加坡住宿和 Airbnb 也上升，但新加坡旅游序列的首尾三个月均值下降，线性斜率仍为正，说明单看首尾月份容易受短期波动影响。完整年份的季节峰值显示：香港旅游为 ${monthNames[trendMetric('hong-kong','tourism').seasonal_peak_month]}，住宿为 ${monthNames[trendMetric('hong-kong','accommodation').seasonal_peak_month]}，Airbnb 为 ${monthNames[trendMetric('hong-kong','airbnb').seasonal_peak_month]}；新加坡旅游为 ${monthNames[trendMetric('singapore','tourism').seasonal_peak_month]}，住宿为 ${monthNames[trendMetric('singapore','accommodation').seasonal_peak_month]}，Airbnb 为 ${monthNames[trendMetric('singapore','airbnb').seasonal_peak_month]}。`));
children.push(...figure(path.join(TREND_CHART,'15_trends_standardized_lines.png'),'图 3-6  香港与新加坡 Google Trends 标准化趋势',figureManifest.figures[0].long_description,560));
children.push(...figure(path.join(TREND_CHART,'16_trends_seasonality.png'),'图 3-7  完整年份的月度季节性',figureManifest.figures[1].long_description,560));

const crossTourism = trends.cross_city.find(x => x.keyword_group === 'tourism' && x.series_mode === 'month_over_month_change');
const crossAcc = trends.cross_city.find(x => x.keyword_group === 'accommodation' && x.series_mode === 'month_over_month_change');
const crossAirbnb = trends.cross_city.find(x => x.keyword_group === 'airbnb' && x.series_mode === 'month_over_month_change');
children.push(body(`标准化月度变化相关显示，两城旅游序列的 Pearson r=${crossTourism.pearson_r_standardized.toFixed(3)}，住宿 r=${crossAcc.pearson_r_standardized.toFixed(3)}，Airbnb r=${crossAirbnb.pearson_r_standardized.toFixed(3)}。这说明两城搜索关注度的月度变化具有较强同向性，但该结果不意味着香港和新加坡的原始搜索规模相同，也不能解释为因果关系。`));
children.push(body(`与评论活动的相关分析使用一阶月度变化，以避免共同趋势造成虚假高相关。滞后 2 个月时，香港旅游 r=${Number(travelCorr.find(x=>x.city_key==='hong-kong'&&x.keyword_group==='tourism').pearson_r).toFixed(3)}，新加坡旅游 r=${Number(travelCorr.find(x=>x.city_key==='singapore'&&x.keyword_group==='tourism').pearson_r).toFixed(3)}；住宿与 Airbnb 的变化相关整体较弱至中等。该分析未进行多重比较校正，不能据此建立因果或预测订单关系。`));
children.push(...figure(path.join(TREND_CHART,'17_trends_review_correlation.png'),'图 3-8  Google Trends 月度变化与评论活动相关',figureManifest.figures[2].long_description,560));
const topFive = topQueries.sort((a,b)=>Number(b.search_interest)-Number(a.search_interest)).slice(0,5).map(x=>x.query).join('、');
children.push(body(`全球 Airbnb 相关搜索词前五为：${topFive}。相关搜索词反映用户对住宿比价、品牌认知和替代平台的查询兴趣，可作为平台品牌运营和内容建设的辅助信息，但它们不是香港或新加坡本地搜索量。`));
children.push(...figure(path.join(TREND_CHART,'18_airbnb_top_queries.png'),'图 3-9  全球 Airbnb 相关搜索词 Top 15',figureManifest.figures[3].long_description,560));

children.push(h('3.6.2  K-Means 经营类型', 3));
children.push(body(`K-Means 特征包括 log 价格、log 评论数、评分、log 最低入住天数、可订天数、log 房东房源数、容量、log 卧室数和整套房源标记。${kmeans.details.map(x=>`${x.city_key === 'hong-kong' ? '香港' : '新加坡'}选择 k=${x.best_k}，Silhouette=${x.best_silhouette.toFixed(3)}`).join('；')}。经营类型标签在查看真实画像后解释，不预先强制指定。`));
children.push(...figure(path.join(CHART,'05_hong-kong_kmeans_clusters.png'),'图 3-10  香港房源经营类型聚类','香港房源的 K-Means 经营类型散点图，价格使用对数轴，评论数使用对称对数轴。'));
children.push(...figure(path.join(CHART,'05_singapore_kmeans_clusters.png'),'图 3-11  新加坡房源经营类型聚类','新加坡房源的 K-Means 经营类型散点图，价格使用对数轴，评论数使用对称对数轴。'));

children.push(h('3.6.3  房价影响因素与预测模型', 3));
children.push(body('房价模型使用 log1p(price_clean) 作为目标，分别对两个城市训练线性回归和随机森林，避免 HKD 与 SGD 直接混合。随机森林在两个城市均取得更高测试集 R² 和更低误差。'));
children.push(...table(
  ['城市/模型','R²(log)','MAE(log)','RMSE(log)','R²(价格)'],
  [['香港-线性',hkModel.metrics.linear_regression.r2_log.toFixed(3),hkModel.metrics.linear_regression.mae_log.toFixed(3),hkModel.metrics.linear_regression.rmse_log.toFixed(3),hkModel.metrics.linear_regression.r2_price.toFixed(3)],['香港-随机森林',hkModel.metrics.random_forest.r2_log.toFixed(3),hkModel.metrics.random_forest.mae_log.toFixed(3),hkModel.metrics.random_forest.rmse_log.toFixed(3),hkModel.metrics.random_forest.r2_price.toFixed(3)],['新加坡-线性',sgModel.metrics.linear_regression.r2_log.toFixed(3),sgModel.metrics.linear_regression.mae_log.toFixed(3),sgModel.metrics.linear_regression.rmse_log.toFixed(3),sgModel.metrics.linear_regression.r2_price.toFixed(3)],['新加坡-随机森林',sgModel.metrics.random_forest.r2_log.toFixed(3),sgModel.metrics.random_forest.mae_log.toFixed(3),sgModel.metrics.random_forest.rmse_log.toFixed(3),sgModel.metrics.random_forest.r2_price.toFixed(3)]],
  '表 3-3  房价模型测试集结果', [2200,1200,1200,1300,1300]
));
children.push(...figure(path.join(CHART,'07_hong-kong_price_feature_importance.png'),'图 3-12  香港房价模型特征重要性','香港随机森林模型中前十五个特征的变量重要性条形图。'));
children.push(...figure(path.join(CHART,'07_singapore_price_feature_importance.png'),'图 3-13  新加坡房价模型特征重要性','新加坡随机森林模型中前十五个特征的变量重要性条形图。'));
children.push(body('容量、房型、最低入住天数、房东房源数量、卧室数、可订天数和评论活动对挂牌价格有较强贡献。该结果反映平台公开价格的结构关联，不能解释为成交价或因果效应。'));

children.push(h('3.6.4  空间分析与房东集中度', 3));
children.push(body(`DBSCAN 使用 0.5 km 邻域和最少 20 个样本，在香港识别 ${spatial.clusters['hong-kong']} 个空间簇、${spatial.noise['hong-kong']} 个噪声点；新加坡识别 ${spatial.clusters.singapore} 个空间簇、${spatial.noise.singapore} 个噪声点。房东集中度方面，香港 Gini=${hosts.city_summary[0].gini.toFixed(3)}，新加坡 Gini=${hosts.city_summary[1].gini.toFixed(3)}；HHI 分别为 ${hosts.city_summary[0].hhi.toFixed(2)} 和 ${hosts.city_summary[1].hhi.toFixed(2)}。`));
children.push(...figure(path.join(CHART,'04_hong-kong_district_price_map.png'),'图 3-14  香港各区房源价格中位数','香港十八区房源价格中位数地图，颜色越深表示本币价格中位数越高。'));
children.push(...figure(path.join(CHART,'04_singapore_district_price_map.png'),'图 3-15  新加坡各区房源价格中位数','新加坡规划区房源价格中位数地图，灰色区域表示没有可分析房源。'));
children.push(...figure(path.join(CHART,'08_host_lorenz_curve.png'),'图 3-16  房东房源占有量 Lorenz 曲线','香港和新加坡房东房源占有量的 Lorenz 曲线及完全均等线。'));

children.push(h('3.6.5  社区供需匹配', 3));
children.push(body('供给侧综合房源密度、房源数量、可订率、房东竞争程度和价格可负担性；需求侧使用最近 12 个月每房源评论数、评论总量和评论增长率。所有指标在城市内转为百分位指数，M=D/(S+ε) 仅作为研究性相对指标。'));
children.push(...figure(path.join(CHART,'09_hong-kong_supply_demand.png'),'图 3-17  香港社区供需四象限','香港各社区供给指数与需求代理指数的四象限散点图，气泡大小表示房源数量。'));
children.push(...figure(path.join(CHART,'09_singapore_supply_demand.png'),'图 3-18  新加坡社区供需四象限','新加坡各社区供给指数与需求代理指数的四象限散点图，气泡大小表示房源数量。'));
children.push(body('潜在机会区必须结合社区房源样本量、监管条件和真实入住需求进一步核查。供需指数不能解释为投资收益率，也不能将城市级 Google Trends 指数分配到社区。'));

children.push(h('3.6.6  Streamlit 决策支持系统', 3));
children.push(body('系统使用 Streamlit 开发，包含项目总览、数据管理中心、市场供给分析、需求关注分析、数据挖掘实验室、供需匹配分析、经营决策中心和研究报告中心八个页面。筛选器实际影响图表，Google Trends 文件状态在系统中可见。'));
children.push(...figure(path.join(CHART,'12_streamlit_dashboard.png'),'图 3-19  系统项目总览页面','深色商业风格的项目总览页面，展示房源总量、房东、评论和平均评分以及城市对比图。',560));
children.push(...figure(path.join(CHART,'13_streamlit_supply.png'),'图 3-20  市场供给分析页面','市场供给分析页面的城市、社区、房型和价格筛选器及动态图表。',560));
children.push(...figure(path.join(CHART,'19_streamlit_demand.png'),'图 3-21  需求关注分析页面','需求关注分析页面展示真实 Google Trends 标准化趋势、季节性、月度变化相关和全球相关搜索词。',560));
children.push(...figure(path.join(CHART,'14_streamlit_decision_result.png'),'图 3-22  经营决策中心结果','经营决策中心根据同类房源和供需指标生成的可解释价格区间和经营建议。',560));

children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(h('4  总结与展望', 1));
children.push(body('本项目完成了从真实公开数据获取、清洗、维度建模、描述统计、空间分析、聚类、回归、网络分析、Google Trends 需求代理分析到交互式决策支持系统的完整流程。两城均以房间型短租供给为主，但价格、房东结构和社区供需格局存在差异；随机森林优于线性回归；供需四象限可帮助识别潜在机会和供给压力区域。Google Trends 月度变化与评论活动存在弱至中等相关，且两城关注度变化具有较强同向性。'));
children.push(body('研究仍存在限制：Inside Airbnb 价格是挂牌价格而不是成交价格；评论量不是订单量；可订状态不是入住率；Google Trends 文件独立归一化，不能比较原始绝对水平；月度导出仍可能存在平台抽样误差；部分社区样本量较小；相关分析未进行多重比较校正。后续可补充官方旅游和人口数据、比较多个季度快照，并开展时间序列外部验证。'));

children.push(h('参考文献', 1));
[
  'Inside Airbnb. Get the Data. https://insideairbnb.com/get-the-data/，访问日期：2026-11-07。',
  'Inside Airbnb. Data Policies and Attribution. https://insideairbnb.com/data-policies/。',
  'Google Trends. https://trends.google.com/trends/，数据导出日期：2026-11-08。',
  'Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M. (2026). Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents. arXiv:2609.00065. https://doi.org/10.48550/arXiv.2609.00065',
  'scikit-learn developers. scikit-learn: Machine Learning in Python.',
  'NetworkX developers. NetworkX Documentation.'
].forEach(ref => children.push(new Paragraph({ indent: { left: 360, hanging: 360 }, spacing: { after: 100, line: 300 }, children: [new TextRun({ text: ref, size: 20, font: BODY_FONT })] })));

children.push(h('附录：项目交付文件', 1));
children.push(...table(
  ['类别','路径'],
  [['原始数据','data/raw/hong-kong/2026-09-20、data/raw/singapore/2026-09-23'],['Google Trends','data/external/google_trends/'],['清洗数据','data/processed/*.parquet、data/processed/analytics.sqlite'],['数据清单','data_manifest.json、data/processed/warehouse_manifest.json'],['分析结果','outputs/tables/'],['图表','outputs/charts/、outputs/charts/trends/'],['Excel','outputs/excel/香港新加坡短租多维分析.xlsx'],['Power BI','outputs/powerbi/'],['Gephi','outputs/gephi/'],['ECharts','outputs/charts/echarts/dashboard.html'],['系统','app.py、pages/、src/'],['文档','docs/、README.md']],
  '表 A-1  项目交付物目录', [1600,5800]
));

const doc = new Document({
  creator: 'Data Mining Project',
  title: '城市短租平台供需匹配与经营决策支持系统——基于中国香港与新加坡的多维分析',
  description: '数据挖掘课程中期报告',
  styles: {
    default: {
      document: {
        run: { font: BODY_FONT, size: 21, color: '000000' },
        paragraph: { spacing: { line: 360, after: 80 }, indent: { firstLine: 420 } },
      },
    },
    paragraphStyles: [
      { id: 'Normal', name: 'Normal', run: { font: BODY_FONT, size: 21 }, paragraph: { spacing: { line: 360, after: 80 } } },
      { id: 'Heading1', name: 'Heading 1', next: 'Normal', run: { font: BODY_FONT, size: 44, bold: true, color: '000000' }, paragraph: { alignment: AlignmentType.JUSTIFIED, outlineLevel: 0, keepNext: true, keepLines: true, spacing: { before: 340, after: 330, line: 578, lineRule: 'auto' } } },
      { id: 'Heading2', name: 'Heading 2', next: 'Normal', run: { font: HEAD_FONT, size: 32, bold: true, color: '000000' }, paragraph: { alignment: AlignmentType.JUSTIFIED, outlineLevel: 1, keepNext: true, keepLines: true, spacing: { before: 260, after: 260, line: 416, lineRule: 'auto' } } },
      { id: 'Heading3', name: 'Heading 3', next: 'Normal', run: { font: BODY_FONT, size: 32, bold: true, color: '000000' }, paragraph: { alignment: AlignmentType.JUSTIFIED, outlineLevel: 2, keepNext: true, keepLines: true, spacing: { before: 260, after: 260, line: 416, lineRule: 'auto' } } },
    ],
  },
  numbering: {
    config: [{
      reference: 'project-bullets',
      levels: [{
        level: 0,
        format: LevelFormat.BULLET,
        text: '\u2022',
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 }, spacing: { line: 330, after: 60 } } },
      }],
    }],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1417, right: 1587, bottom: 1417, left: 1701 },
        },
      },
      children: coverChildren,
    },
    {
      properties: {
        type: SectionType.NEXT_PAGE,
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1417, right: 1587, bottom: 1417, left: 1701 },
        },
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, font: BODY_FONT })] })],
        }),
      },
      children,
    },
  ],
});

if (fs.existsSync(OUT) && process.env.REPORT_FORCE !== '1') {
  console.log(`Report already exists; preserving manual edits: ${OUT}`);
  console.log('Set REPORT_FORCE=1 to overwrite.');
  process.exit(0);
}
Packer.toBuffer(doc).then(buf => {
  fs.mkdirSync(REPORT_DIR, { recursive: true });
  fs.writeFileSync(OUT, buf);
  console.log(OUT);
});

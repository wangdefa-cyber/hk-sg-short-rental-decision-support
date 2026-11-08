"""Generate a standalone ECharts dashboard with embedded real analysis results."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import CHARTS_DIR, PROCESSED_DIR, TABLES_DIR

ECHARTS_DIR = CHARTS_DIR / "echarts"
CITY_NAMES = {"hong-kong": "香港", "singapore": "新加坡"}
COLORS = ["#59c3c3", "#f39c6b", "#8e7dbe", "#f7d060", "#ef6f6c"]


def _box_stats(values: pd.Series) -> list[float]:
    values = pd.to_numeric(values, errors="coerce").dropna().to_numpy()
    if values.size == 0:
        return [0, 0, 0, 0, 0]
    q1, median, q3 = np.quantile(values, [0.25, 0.5, 0.75])
    iqr = q3 - q1
    low = values[values >= q1 - 1.5 * iqr]
    high = values[values <= q3 + 1.5 * iqr]
    return [float(low.min() if low.size else values.min()), float(q1), float(median), float(q3), float(high.max() if high.size else values.max())]


def _prepare_data() -> dict:
    city = pd.read_parquet(PROCESSED_DIR / "dim_city.parquet")
    room = pd.read_csv(TABLES_DIR / "room_type_summary.csv")
    district = pd.read_csv(TABLES_DIR / "district_spatial_summary.csv")
    host = pd.read_csv(TABLES_DIR / "host_type_summary.csv")
    fact = pd.read_parquet(PROCESSED_DIR / "fact_listing_snapshot.parquet")
    dim = pd.read_parquet(PROCESSED_DIR / "dim_listing.parquet")
    listings = dim.merge(fact, on=["listing_key", "city_key", "snapshot_date"], how="inner")
    clusters = pd.read_parquet(PROCESSED_DIR / "fact_listing_clusters.parquet")
    supply = pd.read_csv(TABLES_DIR / "supply_demand_district.csv")
    reviews = pd.read_csv(TABLES_DIR / "review_monthly_by_city.csv")

    rental_price = listings[["city_key", "room_type_cn", "price_clean", "review_scores_rating", "number_of_reviews"]].dropna(subset=["price_clean"]).copy()
    rental_price["city_name"] = rental_price["city_key"].map(CITY_NAMES)
    boxes = []
    box_labels = []
    for city_key in CITY_NAMES:
        for room_type in ["整套房源", "独立房间", "合住房间", "酒店房间"]:
            values = rental_price[(rental_price["city_key"] == city_key) & (rental_price["room_type_cn"] == room_type)]["price_clean"]
            if len(values) >= 10:
                box_labels.append(f"{CITY_NAMES[city_key]}-{room_type}")
                boxes.append(_box_stats(values))

    top_district = district.sort_values(["city_key", "median_price_local"], ascending=[True, False]).groupby("city_key").head(10)
    heat_categories = sorted(top_district["neighbourhood"].unique().tolist())
    heat_data = []
    for y, city_key in enumerate(CITY_NAMES):
        subset = top_district[top_district["city_key"] == city_key]
        for _, row in subset.iterrows():
            heat_data.append([heat_categories.index(row["neighbourhood"]), y, round(float(row["median_price_local"]), 2)])

    scatter_sample = rental_price.sample(min(len(rental_price), 5000), random_state=42)
    scatter = [
        [round(float(row.price_clean), 2), round(float(row.review_scores_rating), 3), CITY_NAMES[row.city_key], row.room_type_cn]
        for row in scatter_sample.itertuples()
        if pd.notna(row.review_scores_rating)
    ]
    cluster_points = clusters.dropna(subset=["price_clean", "review_scores_rating"]).copy()
    cluster_points = cluster_points.sample(min(len(cluster_points), 5000), random_state=42)
    cluster_series = []
    for operating_type, group in cluster_points.groupby("operating_type"):
        cluster_series.append(
            {
                "name": operating_type,
                "data": [
                    [round(float(r.price_clean), 2), round(float(r.number_of_reviews or 0), 2), CITY_NAMES[r.city_key]]
                    for r in group.itertuples()
                ],
            }
        )

    supply_series = []
    for strategy, group in supply.groupby("market_strategy"):
        supply_series.append(
            {
                "name": strategy,
                "data": [
                    [round(float(r.supply_index), 4), round(float(r.demand_index), 4), r.neighbourhood, CITY_NAMES[r.city_key], int(r.listing_count)]
                    for r in group.itertuples()
                ],
            }
        )

    review_series = []
    for city_key, group in reviews.groupby("city_key"):
        group = group.sort_values("year_month")
        review_series.append({"name": CITY_NAMES[city_key], "data": [[r.year_month, int(r.review_count)] for r in group.itertuples()]})

    trends_monthly = pd.read_csv(TABLES_DIR / "google_trends_monthly.csv")
    top_queries = pd.read_csv(TABLES_DIR / "google_trends_top_queries.csv")
    trends_series = []
    if not trends_monthly.empty:
        for (city_key, group, keyword), part in trends_monthly.groupby(["city_key", "keyword_group", "keyword"]):
            part = part.sort_values("year_month")
            trends_series.append(
                {
                    "city_key": city_key,
                    "city_name": CITY_NAMES.get(city_key, "全球"),
                    "keyword_group": group,
                    "keyword": keyword,
                    "data": [[r.year_month, round(float(r.z_score), 4)] for r in part.itertuples()],
                }
            )
    top_queries_records = []
    if not top_queries.empty:
        top_queries_records = top_queries.sort_values("search_interest", ascending=False).head(12)[
            ["query", "search_interest", "increase_percent"]
        ].to_dict("records")

    host_pivot = host.pivot(index="host_type", columns="city_name", values="listing_count").fillna(0)
    city_data = city.set_index("city_key")
    radar_max = [
        float(city_data["listing_count"].max()),
        float(city_data["host_count"].max()),
        1.0,
        5.0,
        float(city_data["professional_host_share"].max()),
    ]
    radar_values = [
        [
            float(city_data.loc[key, "listing_count"]),
            float(city_data.loc[key, "host_count"]),
            float(city_data.loc[key, "entire_home_share"]),
            float(city_data.loc[key, "review_score_mean"]),
            float(city_data.loc[key, "professional_host_share"]),
        ]
        for key in CITY_NAMES
    ]

    return {
        "source": "Inside Airbnb 2026-09 快照；Google Trends 2021-11 至 2026-11 月度导出",
        "city_names": list(CITY_NAMES.values()),
        "city_counts": city[["city_name", "listing_count", "host_count", "price_median_local", "review_score_mean"]].to_dict("records"),
        "room": room[["city_name", "room_type_cn", "listing_count", "room_type_share"]].to_dict("records"),
        "box_labels": box_labels,
        "boxes": boxes,
        "district": district[["city_name", "neighbourhood", "listing_density_per_km2", "median_price_local", "listing_count"]].to_dict("records"),
        "heat_categories": heat_categories,
        "heat_data": heat_data,
        "monthly_reviews": review_series,
        "host": host_pivot.reset_index().to_dict("records"),
        "scatter": scatter,
        "cluster_series": cluster_series,
        "supply_series": supply_series,
        "radar_indicators": [
            {"name": "房源数量", "max": radar_max[0]},
            {"name": "房东数量", "max": radar_max[1]},
            {"name": "整套房源占比", "max": 1},
            {"name": "平均评分", "max": 5},
            {"name": "专业房东占比", "max": 1},
        ],
        "radar_values": [{"name": name, "value": values} for name, values in zip(CITY_NAMES.values(), radar_values)],
        "trends_status": json.loads((TABLES_DIR / "google_trends_status.json").read_text(encoding="utf-8")),
        "trends_series": trends_series,
        "top_queries": top_queries_records,
    }


def run() -> Path:
    ECHARTS_DIR.mkdir(parents=True, exist_ok=True)
    data = _prepare_data()
    data_json = json.dumps(data, ensure_ascii=False)
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>香港与新加坡短租市场分析</title>
<style>
  :root {{ --bg:#0d1726; --panel:#142439; --panel2:#192d45; --text:#e7f0f7; --muted:#8fa9bd; --accent:#59c3c3; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text); font-family:"Microsoft YaHei","Segoe UI",sans-serif; }}
  header {{ padding:30px 38px 18px; background:linear-gradient(120deg,#10233b,#142439 55%,#1e3d53); border-bottom:1px solid #29445f; }}
  h1 {{ margin:0 0 8px; font-size:28px; letter-spacing:1px; }}
  .sub {{ color:var(--muted); font-size:14px; }}
  .grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; padding:22px 28px 40px; }}
  .card {{ background:var(--panel); border:1px solid #28435d; border-radius:12px; overflow:hidden; box-shadow:0 8px 22px rgba(0,0,0,.18); }}
  .card.full {{ grid-column:1 / -1; }}
  .card h2 {{ font-size:16px; margin:0; padding:15px 18px 3px; }}
  .note {{ color:var(--muted); font-size:12px; padding:3px 18px 10px; }}
  .chart {{ width:100%; height:360px; }}
  .chart.tall {{ height:480px; }}
  .status {{ margin:0 18px 20px; padding:14px; border:1px dashed #4c6b84; color:#b9cfe0; background:#101f31; border-radius:8px; line-height:1.7; }}
  @media (max-width:1100px) {{ .grid {{ grid-template-columns:1fr; }} .card.full {{ grid-column:auto; }} }}
</style>
<script src="echarts.min.js"></script>
</head>
<body>
<header>
  <h1>香港与新加坡短租市场分析</h1>
  <div class="sub">城市短租平台供需匹配与经营决策支持系统 · Inside Airbnb 2026-09 快照 · Google Trends 2021-11 至 2026-11</div>
</header>
<div class="grid">
  <section class="card"><h2>房源总量对比</h2><div class="note">单位：套；来源：Inside Airbnb</div><div id="cityBar" class="chart"></div></section>
  <section class="card"><h2>房型结构</h2><div class="note">单位：占比；来源：Inside Airbnb</div><div id="roomPie" class="chart"></div></section>
  <section class="card"><h2>清洗后价格分布</h2><div class="note">单位：本币/晚；香港 HKD、新加坡 SGD；箱线图隐藏须外异常值</div><div id="priceBox" class="chart tall"></div></section>
  <section class="card"><h2>社区房源密度</h2><div class="note">单位：套/平方公里；来源：Inside Airbnb + 社区边界</div><div id="densityBar" class="chart tall"></div></section>
  <section class="card full"><h2>社区价格热力图</h2><div class="note">单位：本币/晚；每个城市展示价格中位数最高的 10 个社区</div><div id="priceHeat" class="chart"></div></section>
  <section class="card"><h2>月度评论活跃度</h2><div class="note">单位：条/月；评论量是需求活动代理，不是订单量</div><div id="reviewLine" class="chart"></div></section>
  <section class="card"><h2>房东经营规模结构</h2><div class="note">单位：套；按房源数量划分房东类型</div><div id="hostBar" class="chart"></div></section>
  <section class="card"><h2>旅游搜索兴趣</h2><div class="note">香港 vs 新加坡；各文件独立归一化后使用 z-score；蓝实线圆点为香港，橙虚线方点为新加坡</div><div id="trendsTourism" class="chart"></div></section>
  <section class="card"><h2>住宿搜索兴趣</h2><div class="note">香港 hotel 与新加坡 hotel；仅比较标准化趋势，不比较原始绝对高度</div><div id="trendsHotel" class="chart"></div></section>
  <section class="card"><h2>Airbnb 搜索兴趣</h2><div class="note">香港、新加坡与全球 Airbnb；各序列独立 0–100 导出</div><div id="trendsAirbnb" class="chart"></div></section>
  <section class="card"><h2>全球 Airbnb 相关搜索词</h2><div class="note">按搜索兴趣排序 Top 12；搜索兴趣不是搜索次数</div><div id="topQueries" class="chart"></div></section>
  <section class="card"><h2>价格与评分关系</h2><div class="note">单位：本币/晚与评分；仅展示真实有效价格样本</div><div id="priceScatter" class="chart"></div></section>
  <section class="card"><h2>K-Means 经营类型</h2><div class="note">单位：本币/晚与评论数；颜色为数据驱动聚类标签</div><div id="clusterScatter" class="chart"></div></section>
  <section class="card full"><h2>社区供需匹配四象限</h2><div class="note">S、D 为城市内百分位指数；M=D/(S+ε)，仅为研究性相对指标；气泡大小表示房源数量</div><div id="supplyScatter" class="chart tall"></div></section>
  <section class="card full"><h2>城市综合对比</h2><div class="note">雷达图用于结构对比；价格没有跨币种直接比较，因此不放入雷达图</div><div id="cityRadar" class="chart"></div></section>
</div>
<script>
const DATA = {data_json};
const theme = {{ aria:{{enabled:true}}, textStyle: {{ color:'#dceaf4', fontFamily:'Microsoft YaHei' }}, title:{{textStyle:{{color:'#e7f0f7'}}}}, legend:{{textStyle:{{color:'#b9cfe0'}}}}, tooltip:{{backgroundColor:'#0f2032',borderColor:'#3e5c75',textStyle:{{color:'#e7f0f7'}}}} }};
const charts = [];
function init(id, option) {{ const chart=echarts.init(document.getElementById(id)); chart.setOption(Object.assign({{}},theme,option)); charts.push(chart); return chart; }}
init('cityBar', {{tooltip:{{trigger:'axis'}},grid:{{left:60,right:24,top:30,bottom:45}},xAxis:{{type:'category',data:DATA.city_counts.map(x=>x.city_name)}},yAxis:{{type:'value',name:'套'}},series:[{{type:'bar',data:DATA.city_counts.map(x=>x.listing_count),itemStyle:{{color:(p)=>['#59c3c3','#f39c6b'][p.dataIndex],borderRadius:[5,5,0,0]}},label:{{show:true,position:'top'}}}}]}});
const roomCities=DATA.city_names;
const roomTypes=[...new Set(DATA.room.map(x=>x.room_type_cn))];
init('roomPie', {{tooltip:{{trigger:'item'}},legend:{{bottom:0}},series:roomCities.map((city,i)=>({{name:city,type:'pie',radius:[i*22+25,i*22+40],center:[25+i*50+'%','44%'],data:roomTypes.map(t=>{{const r=DATA.room.find(x=>x.city_name===city&&x.room_type_cn===t);return {{name:t,value:r?r.listing_count:0}}}}),label:{{show:false}}}}))}});
init('priceBox', {{tooltip:{{trigger:'item'}},grid:{{left:65,right:24,top:30,bottom:120}},xAxis:{{type:'category',data:DATA.box_labels,axisLabel:{{rotate:35}}}},yAxis:{{type:'value',name:'本币/晚'}},series:[{{type:'boxplot',data:DATA.boxes,itemStyle:{{color:'#59c3c3'}}}}]}});
const densityTop=DATA.district.slice().sort((a,b)=>b.listing_density_per_km2-a.listing_density_per_km2).slice(0,20).reverse();
init('densityBar', {{tooltip:{{trigger:'axis'}},grid:{{left:110,right:28,top:20,bottom:40}},xAxis:{{type:'value',name:'套/km²'}},yAxis:{{type:'category',data:densityTop.map(x=>x.city_name+'-'+x.neighbourhood)}},series:[{{type:'bar',data:densityTop.map(x=>x.listing_density_per_km2),itemStyle:{{color:'#f39c6b'}}}}]}});
init('priceHeat', {{tooltip:{{formatter:p=>DATA.heat_categories[p.value[0]]+'<br>'+DATA.city_names[p.value[1]]+'：'+p.value[2]}},grid:{{left:70,right:25,top:25,bottom:110}},xAxis:{{type:'category',data:DATA.heat_categories,axisLabel:{{rotate:45,fontSize:10}}}},yAxis:{{type:'category',data:DATA.city_names}},visualMap:{{min:0,max:Math.max(...DATA.heat_data.map(x=>x[2])),calculable:true,orient:'horizontal',left:'center',bottom:5,textStyle:{{color:'#b9cfe0'}}}},series:[{{type:'heatmap',data:DATA.heat_data,label:{{show:false}}}}]}});
init('reviewLine', {{tooltip:{{trigger:'axis'}},legend:{{top:0}},grid:{{left:60,right:24,top:40,bottom:45}},xAxis:{{type:'time'}},yAxis:{{type:'value',name:'条/月'}},series:DATA.monthly_reviews.map(s=>({{name:s.name,type:'line',showSymbol:false,smooth:true,data:s.data}}))}});
init('hostBar', {{tooltip:{{trigger:'axis'}},legend:{{top:0}},grid:{{left:60,right:24,top:40,bottom:55}},xAxis:{{type:'category',data:DATA.host.map(x=>x.host_type)}},yAxis:{{type:'value',name:'套'}},series:DATA.city_names.map(c=>({{name:c,type:'bar',data:DATA.host.map(x=>x[c]||0)}}))}});
init('priceScatter', {{tooltip:{{formatter:p=>p.value[2]+' / '+p.value[3]+'<br>价格 '+p.value[0]+'，评分 '+p.value[1]}},grid:{{left:65,right:24,top:30,bottom:45}},xAxis:{{type:'log',name:'本币/晚'}},yAxis:{{type:'value',name:'评分',min:1,max:5}},series:[{{type:'scatter',symbolSize:5,data:DATA.scatter,itemStyle:{{opacity:.42}}}}]}});
init('clusterScatter', {{tooltip:{{formatter:p=>p.seriesName+'<br>'+p.value[2]+'<br>价格 '+p.value[0]+'，评论 '+p.value[1]}},legend:{{type:'scroll',top:0}},grid:{{left:65,right:24,top:45,bottom:45}},xAxis:{{type:'log',name:'本币/晚'}},yAxis:{{type:'log',name:'评论数（log 轴）',min:1}},series:DATA.cluster_series.map(s=>({{name:s.name,type:'scatter',symbolSize:5,data:s.data,itemStyle:{{opacity:.5}}}}))}});
init('supplyScatter', {{tooltip:{{formatter:p=>p.value[3]+' / '+p.value[2]+'<br>S='+p.value[0]+'，D='+p.value[1]+'<br>房源 '+p.value[4]+' 套'}},legend:{{type:'scroll',top:0}},grid:{{left:60,right:25,top:45,bottom:45}},xAxis:{{type:'value',name:'供给指数 S',min:0,max:1}},yAxis:{{type:'value',name:'需求代理指数 D',min:0,max:1}},series:DATA.supply_series.map(s=>({{name:s.name,type:'scatter',symbolSize:v=>Math.max(8,Math.min(45,Math.sqrt(v[4])*1.8)),data:s.data,itemStyle:{{opacity:.7}}}}))}});
init('cityRadar', {{tooltip:{{}},legend:{{bottom:0}},radar:{{indicator:DATA.radar_indicators,splitArea:{{areaStyle:{{color:['rgba(89,195,195,.03)','rgba(89,195,195,.07)']}}}},axisName:{{color:'#b9cfe0'}}}},series:[{{type:'radar',data:DATA.radar_values,areaStyle:{{opacity:.12}}}}]}});
function trendsOption(group) {{
  const part=DATA.trends_series.filter(x=>x.keyword_group===group);
  const cities=[...new Set(part.map(x=>x.city_key))];
  const styles={{'hong-kong':{{color:'#0072B2',lineStyle:'solid',symbol:'circle'}},'singapore':{{color:'#D55E00',lineStyle:'dashed',symbol:'square'}},'global':{{color:'#009E73',lineStyle:'dotted',symbol:'diamond'}}}};
  return {{tooltip:{{trigger:'axis'}},legend:{{top:0}},grid:{{left:55,right:20,top:38,bottom:40}},xAxis:{{type:'time'}},yAxis:{{type:'value',name:'z-score',min:-3.2,max:3.6}},series:part.map(s=>({{name:s.city_name,type:'line',showSymbol:true,symbolSize:5,data:s.data,lineStyle:{{width:2,type:styles[s.city_key].lineStyle}},itemStyle:{{color:styles[s.city_key].color}},symbol:styles[s.city_key].symbol}}))}};
}}
init('trendsTourism', trendsOption('tourism'));
init('trendsHotel', trendsOption('accommodation'));
init('trendsAirbnb', trendsOption('airbnb'));
const tq=DATA.top_queries.slice().reverse();
init('topQueries', {{tooltip:{{trigger:'axis'}},grid:{{left:95,right:25,top:20,bottom:40}},xAxis:{{type:'value',name:'搜索兴趣（0–100）'}},yAxis:{{type:'category',data:tq.map(x=>x.query)}},series:[{{type:'bar',data:tq.map(x=>x.search_interest),itemStyle:{{color:'#0072B2'}},label:{{show:true,position:'right'}}}}]}});
window.addEventListener('resize',()=>charts.forEach(c=>c.resize()));
</script>
</body>
</html>'''
    path = ECHARTS_DIR / "dashboard.html"
    path.write_text(html, encoding="utf-8")
    return path


if __name__ == "__main__":
    print(run())

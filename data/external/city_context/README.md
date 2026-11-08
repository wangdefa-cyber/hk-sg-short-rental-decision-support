# 城市背景数据

建议后续补充以下真实公开数据，用于跨城市比较和解释：

- 城市人口
- 土地面积
- 访客或旅客到访量
- 酒店入住率或旅游统计
- 短租监管背景
- 货币和汇率口径

数据文件建议命名为 `city_context.csv`，每个城市至少包含：

```text
city_key,population,land_area_km2,visitor_arrivals,hotel_occupancy_rate,currency_code,source_url,source_date
```

在城市背景数据未提供前，系统不得编造人口、面积或旅游统计数字。

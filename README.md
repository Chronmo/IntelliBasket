# 客群智篮

> 基于 Hive 数仓、动态 RFM 分层与分群购物篮挖掘的零售精准营销决策系统

## 项目定位

本项目以 UCI Online Retail II 两年真实零售交易数据为基础，构建从原始交易入湖、Hive 分层治理、客户价值分层、分群关联规则挖掘到 Web 营销决策展示的完整大数据应用。

项目不是只输出一份 RFM 表或一组 Apriori 规则，而是回答三个连续的业务问题：

1. 哪些客户最有价值、最需要保持或挽留？
2. 不同价值客群分别偏好哪些商品组合？
3. 面向指定客群和主推商品，应采用什么组合营销策略？

## 当前阶段

- [x] 第一阶段：项目背景、数据可行性、功能边界与技术栈总结
- [ ] 第二阶段：数据仓库、算法、后端与前端编码
- [ ] 第三阶段：测试总结、项目文档、答辩 PPT 与演示材料

第一阶段正式文档：

- [项目背景与技术栈总结](docs/01_项目背景与技术栈总结.md)
- [编码规范与接口标准](docs/02_编码规范与接口标准.md)

## 数据源

- 数据集：UCI Online Retail II
- 原始文件：`E:\bigdata\online+retail+ii\online_retail_II.xlsx`
- 官方页面：https://archive.ics.uci.edu/dataset/502/online+retail+ii
- DOI：https://doi.org/10.24432/C5CG6D
- 许可：CC BY 4.0

## 规划技术链路

```text
Excel/CSV → HDFS → Hive ODS/DWD/DWS/ADS
                         ↓
                Python RFM + FP-Growth
                         ↓
                       MySQL
                         ↓
                 FastAPI → Vue/ECharts
```

## 项目目录

```text
retail_customer_basket_intelligence/
├── README.md
├── docs/
│   └── 01_项目背景与技术栈总结.md
└── scripts/
    └── profile_source.py
```

第二阶段将继续补充 `data`、`sql`、`backend`、`frontend`、`tests` 与 `outputs` 等目录。

# API 与服务层验证记录

## 1. 本节点目标

把 Hive 与 Python 分析输出稳定加载到 MySQL，并通过版本化 REST API 提供给后续 Vue/ECharts 看板。服务层坚持三个边界：分析任务不直接承受前端查询、接口字段统一使用 lowerCamelCase、成功与失败响应均使用可追踪的标准信封结构。

## 2. 服务架构

```text
Hive DWS/ADS
    -> Python 动态 RFM 与分群购物篮分析
    -> outputs/analytics/*.csv|json
    -> 幂等导入器
    -> MySQL 8.0 服务表
    -> FastAPI /api/v1
    -> Vue/ECharts（下一节点）
```

核心实现：

- `ServingDataImporter` 在一个事务中先清理后导入，失败时整体回滚，重复执行不会制造重复记录；
- SQLAlchemy ORM 统一维护字段类型、复合唯一键和常用查询索引；
- FastAPI 使用应用工厂和请求级 Session，便于生产运行与 SQLite 隔离测试；
- 所有响应携带 `requestId`，分页接口返回 `page`、`pageSize`、`totalCount` 与 `totalPages`；
- OpenAPI 文档由 FastAPI 自动生成，地址为 `/docs`。

## 3. 真实数据导入结果

2026-07-21 在本机 MySQL 8.0 容器中执行：

```powershell
docker compose -f docker-compose.app.yml up -d mysql
intellibasket load-serving-data
```

导入结果如下：

| 服务表 | 记录数 | 说明 |
| --- | ---: | --- |
| `business_overview` | 1 | 全局经营概览 |
| `monthly_sale` | 25 | 月度销售序列 |
| `rfm_customer_snapshot` | 98,557 | 多时间切片客户 RFM 快照 |
| `rfm_segment_summary` | 200 | 各快照客群汇总 |
| `segment_migration` | 842 | 相邻快照客群迁移 |
| `association_rule` | 765 | 全局及分客群购物篮规则 |
| `rule_drift` | 193 | 跨年度规则漂移 |
| `top_product` | 100 | 高价值商品记录 |

真实导入识别并修复了一个订单数据边界：商品编码 `20725` 同时存在 `LUNCH BAG RED RETROSPOT` 与历史名称 `LUNCH BAG RED SPOTTY`。因此商品服务表采用 `(stockCode, productName)` 复合主键，避免错误覆盖或导入失败。

## 4. REST 接口清单

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/health/live` | 进程存活检查 |
| GET | `/api/v1/health/ready` | MySQL 依赖就绪检查 |
| GET | `/api/v1/overview` | 全局核心指标 |
| GET | `/api/v1/sales/monthly` | 月度趋势 |
| GET | `/api/v1/rfm/segments` | 指定或最新快照客群分布 |
| GET | `/api/v1/rfm/customers` | 客户明细与分页筛选 |
| GET | `/api/v1/rfm/migrations` | 客群迁移流向 |
| GET | `/api/v1/association-rules` | 分群规则筛选 |
| GET | `/api/v1/rule-drift` | 规则新增、消失与强弱变化 |
| GET | `/api/v1/products/top` | 高价值商品排行 |
| POST | `/api/v1/marketing-recommendations` | 按客群与主推商品生成可解释策略 |

成功响应示例：

```json
{
  "success": true,
  "data": {},
  "meta": {
    "requestId": "8a6f...",
    "generatedAt": "2026-07-21T08:00:00+00:00"
  }
}
```

失败响应使用相同追踪元数据，并返回稳定的业务错误码，例如 `REQUEST_VALIDATION_FAILED`、`DATABASE_UNAVAILABLE` 和 `OVERVIEW_NOT_FOUND`。

## 5. 真实接口验收

连接 MySQL 的 API 实例验收结果：

- `/api/v1/health/ready` 返回 `READY`；
- `/api/v1/overview` 返回 5,878 位客户、36,969 张购物篮、4,631 种商品和 £17,743,429.18 销售额；
- 最新 RFM 快照返回 8 个客群；
- 全局规则接口可返回 `POPPY'S PLAYHOUSE BEDROOM -> POPPY'S PLAYHOUSE KITCHEN`，置信度 0.850450、提升度 41.484005、覆盖 472 张购物篮；
- 中文客群名称按 UTF-8 完整往返；
- 商品编码筛选按 `|` 分隔的完整 token 匹配，避免子串误命中。

## 6. 自动化验证

```powershell
python -m ruff check src tests
python -m pytest tests/api tests/analytics tests/data -q
```

当前后端共 11 项测试通过，覆盖健康检查、统一响应、RFM 分页、可解释推荐、参数校验、数据接入、动态 RFM 和购物篮算法。测试产生的 Starlette `TestClient` 弃用提醒来自依赖库，不影响当前功能。

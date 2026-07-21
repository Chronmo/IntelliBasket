# Web 驾驶舱与联调验证记录

## 1. 展示目标

Web 端围绕答辩时最重要的“数据可信、分析有深度、结果能行动”设计，不把算法结果堆成静态表格。页面采用 Vue 3、TypeScript、Vue Router、Axios 与 ECharts 6.1，所有接口字段保持 lowerCamelCase，生产构建由 Nginx 托管并反向代理 `/api/v1`。

## 2. 四个演示页面

### 2.1 经营总览

- 以 £17,743,429 销售额、36,969 张购物篮、5,878 位客户和 4,631 种商品作为核心 KPI；
- 用 25 个月销售额折线与订单量柱状图展示季节性；
- 展示高价值商品排行和 £479.95 平均购物篮金额；
- 明确标注“发票号定义购物篮边界”，突出项目数据可靠性。

### 2.2 动态 RFM 客群

- 展示 8 类客群的人数与金额贡献；
- 用环图看客户结构，用双指标图看人数占比与金额占比的错位；
- 点击任一客群即可联动客户明细；
- 客户表展示 R/F/M 单项得分、最近消费、频次和累计金额。

### 2.3 分群购物篮

- 支持选择客群、最低提升度和最低置信度；
- 气泡面积表达覆盖购物篮数，颜色表达提升度；
- 同屏展示 93 条新兴、93 条消失、5 条增强和 2 条减弱规则；
- 规则表同时解释支持度、置信度、提升度和覆盖数。

### 2.4 营销策略中心

- 以“目标客群 + 主推商品 + 最低提升度”为业务输入；
- 调用 `POST /api/v1/marketing-recommendations` 实时生成策略；
- 返回组合折扣或交叉销售建议，并说明历史置信度、提升度和覆盖购物篮数；
- 默认商品 `22423` 在真实数据中可返回 6 个可信组合，便于现场演示。

## 3. 工程实现

- 路由组件懒加载，ECharts 按需注册折线、柱状、饼图和散点图；
- API Client 统一超时、基础路径与类型定义；
- 侧栏服务状态来自 `/health/ready` 的真实探测；
- 加载、空结果、接口错误和按钮禁用均有明确状态；
- CSS 使用设计 token 管理颜色、边框、阴影与强调语义，不依赖外部字体服务；
- `docker/frontend.Dockerfile` 使用 Node 构建与 Nginx 运行的多阶段镜像；
- `nginx.conf` 支持 Vue History 路由回退和 API 反向代理。

## 4. 验证结果

```powershell
cd frontend
npm run build
npm audit
```

- TypeScript 严格类型检查通过；
- Vite 生产构建成功，共转换 2,442 个模块；
- npm 安全审计为 0 个漏洞；
- 使用真实 MySQL/FastAPI 数据逐页联调，四条路由均正常；
- RFM 点击筛选后客户数由 5,878 正确更新为重要价值客户 1,316；
- 默认策略场景生成 6 个可信组合；
- 浏览器控制台错误与警告均为 0；
- 1,280 像素桌面视口无横向溢出。
- FastAPI 与 Nginx 生产镜像均构建成功；
- 通过 Nginx 的 `http://localhost:8080/api/v1/overview` 反向代理验收，返回 5,878 位客户和 36,969 张购物篮。

## 5. 本地运行

开发模式：

```powershell
intellibasket serve
cd frontend
npm run dev
```

访问 `http://localhost:5173`。

容器模式：

```powershell
docker compose -f docker-compose.app.yml up -d --build
```

访问 `http://localhost:8080`。首次启动空数据库前，应先执行 `intellibasket load-serving-data` 导入本地分析输出。

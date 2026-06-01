# Codex 阶段5：btc5m 市场完整性索引与 WebUI 接入

时间：2026-06-01 14:15（Asia/Shanghai）

## 项目现状

- WebUI 入口：`http://localhost:5175/`
- 5175 当前由 Windows Python 运行 `webui/api_server.py`
- 模拟盘/实盘循环没有被本次启动或点击
- 本次只做非破坏性检查、索引生成、后端接口和前端展示接入

## 已完成修改

1. 新增 `webui/market_integrity.py`
   - 流式读取 `btc5m数据/true_market/windows.jsonl`
   - 流式读取 `btc5m数据/trades.jsonl`、`btc5m数据/sim/trades.jsonl`
   - 流式读取 `btc5m数据/true_market/orderbook_ticks.jsonl`
   - 生成小型派生索引：`btc5m数据/derived/market_integrity.jsonl`
   - 生成汇总：`btc5m数据/derived/market_integrity_summary.json`
   - 原始数据不移动、不删除、不覆盖

2. 新增后端接口
   - `/api/market-integrity`
   - `/api/missing-markets` 优先读取完整性索引，不再只按窗口数量粗略估算
   - 索引超过 5 分钟会后台刷新一次，避免 WebUI 长期显示旧统计

3. WebUI 接入
   - 顶部 KPI 新增“数据完整性”：完整、残缺、异常、可回测、未结算
   - 市场数据页新增完整性概览卡片
   - 市场列表每个市场增加状态标记：完整、残缺、异常、未结算、待索引
   - 当前市场如果还没有进入索引，会显示“待索引”，避免伪装成完整数据

## 完整市场判断标准

当前“完整可回测”必须同时满足：

- 市场窗口存在
- 开盘价可靠：来自 Polymarket 平台校验、collector platform/exact/good/close，或已有交易记录中的平台开盘价
- 结算价存在：来自交易记录中的 Polymarket crypto price API 结算价
- 盘口完整：入场窗口最近 120 秒内有 orderbook 数据，且 Up/Down 两边都有
- token id 完整
- 未被 collector 标记为 exclude
- 市场已超过结算缓冲，不属于未结算

## btc5m 数据统计

最新索引时间：2026-06-01 14:09:45

- 预期市场：1675
- 已记录市场：1660
- 缺失市场：15
- 完整可回测市场：337
- 残缺市场：125
- 异常市场：1197
- 未结算市场：1
- 今日预期：170
- 今日已记录：170
- 今日缺失：0
- 今日完整：71
- 今日异常：98

主要异常原因：

- collector 标记排除：973
- PTB/open 质量 bad：973
- 平台结算价缺失：444
- token id 缺失：319
- 入场窗口盘口缺失：312
- 盘口 Up/Down 边不完整：310
- 可靠开盘价缺失：259
- PTB/open 仍 pending：237

## 实际浏览器验证记录

- 使用 Playwright 打开 `http://localhost:5175/`
- 切换交易控制页、市场数据页
- 验证 `/api/market-integrity` 返回 200
- 验证 `/api/missing-markets` 返回完整/残缺/异常/未结算字段
- 验证 Console：0 errors，0 warnings
- 构建命令通过：`npm run build`
- Python 编译通过：`python -m py_compile webui\api_server.py webui\market_integrity.py`

## 截图路径

- `C:\Users\yyq\Desktop\自动交易\webui\截图\新WebUI\Codex验收\20_市场数据_完整性索引.png`
- `C:\Users\yyq\Desktop\自动交易\webui\截图\新WebUI\Codex验收\21_交易控制_完整性刷新后.png`

## 仍需注意

1. 337 个“完整可回测”是严格口径，不代表全部历史都能用于深度参数回测。
2. 很多市场没有 `price_ticks`，因为 RTDS 官方价格源曾经降级；后续如果要做秒级价格曲线回测，需要进一步补齐或确认可替代的真实平台价格序列。
3. `btc5m数据/derived/` 被 `.gitignore` 忽略，派生索引留在本机，不提交到 Git。
4. 本次没有删除残缺数据，也没有移动隔离原始数据。

## 下一步建议

1. 先用完整性索引筛出 337 个完整市场，做第一轮训练/验证回测。
2. 对缺少 `price_ticks` 的完整市场再分层：有秒级价格曲线、只有平台开/结算价、只有交易入场价。
3. 回测不要只跑单一策略，要分训练区间和验证区间，并输出最大回撤、连续亏损和参数敏感性。
4. 回测确认后再让用户选择是否切换模拟盘策略；在用户确认前继续保持模拟盘/实盘不启动。

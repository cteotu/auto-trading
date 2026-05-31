# Codex 阶段1-2接管验收报告

时间：2026-06-01 04:15（Asia/Shanghai）

## 项目现状

- 新 WebUI 可访问：`http://localhost:5175/`
- 当前 5175 不再依赖 WSL 的 localhost relay，由 Windows Python 直接托管 `webui/dist` 和 API，避免 WSL relay 卡住导致 WebUI 打不开。
- 8878 WSL API 仍在运行，5175 是给用户打开的主入口。
- 当前只读检查显示：采集器进程仍在运行；模拟盘进程和实盘进程未运行。

## 实际浏览器验证记录

- 已用 Playwright 打开真实浏览器访问 `http://localhost:5175/`。
- 已检查并截图：交易控制、市场数据、数据分析、用户中心、市场自动切换后状态。
- 未点击会触发真实交易、删除数据、重置状态或不可逆操作的按钮。
- 控制台错误：0 个。
- 表格表头验证：`thead th` 已是 `position: sticky`。
- 市场结束后切换验证：顶部从 `btc-updown-5m-1780257900` 自动切到 `btc-updown-5m-1780258200`。

## 截图路径

目录：`C:\Users\yyq\Desktop\自动交易\webui\截图\新WebUI\Codex验收\`

- `14_交易控制_修复后.png`
- `15_市场数据_修复后.png`
- `16_数据分析_修复后.png`
- `17_用户中心_修复后.png`
- `18_市场自动切换后.png`

## 完整问题清单

必须修复：

- `总市场/今日市场` 原来是前端用交易记录硬算，已改为调用 `/api/missing-markets`。
- 顶部 `路线正常` 原来有硬编码风险，已改为 `/api/safety.route_ready`。
- 当前市场开盘价曾在 `/api/status` 和 `/api/market-windows` 中不一致，已修为不再使用坏 RTDS/PTB 估算。
- 市场回放原先使用 `Math.random()` 生成假曲线，已改为真实 `/api/market-tick-data`。
- 非交易页被左侧策略栏挤压，已隐藏左侧策略栏。
- 策略槽位原来是前端多选假状态，已改为单策略并调用 `/api/strategies/switch`。
- 实盘按钮在路线未就绪时已禁用并显示 `实盘未就绪`。

建议优化：

- 市场回放当前有盘口概率点，但 BTC 秒级价格点为 0，原因是 RTDS 官方价格降级后，collector 没有把 Coinbase display fallback 写入 `price_ticks`。不能伪造，需修采集器。
- 数据分析仍偏拥挤，后续可做成“总览 + 明细表 + 回测对比”三层。
- 用户中心应把“每日汇总”合并进来，并把钱包/授权/余额解释成用户语言。
- `mockData.ts` 已确认无引用，但仍建议后续删除，避免误用。

可选新增：

- 市场详情增加“数据来源覆盖率”：价格点数、盘口点数、结算来源、开盘价来源。
- 交易记录增加“为什么没买/为什么买”的可展开原因。
- 增加“可回测市场池”页面，单独展示完整、残缺、缺失、异常市场。

## 假数据和未连接功能清单

已修复：

- 市场回放图不再使用随机数据。
- 顶部路线状态不再硬编码为 true。
- 总市场/缺失市场不再由前端交易数推算。
- 策略切换和保存开始接后端接口。

仍需处理：

- `webui/src/data/mockData.ts` 保留但未被引用。
- 数据分析里的资金曲线来自交易文件，不是钱包链上余额。
- 用户中心的 `官方价格=降级` 是真实状态，不是 UI 问题；需要采集器修复 RTDS 或明确 fallback 采集。

## 已完成修改

- 统一当前市场开盘价来源，不可靠时显示待确认，不再用坏 PTB。
- 修复市场统计 KPI。
- 修复顶部实盘路线状态与实盘按钮安全状态。
- 修复策略槽位样式和后端连接。
- 调整交易记录默认分页为 20 条/页。
- 表头固定。
- 市场/分析/用户页全宽展示。
- 市场回放接真实 tick 接口。
- 数据分析重接口改为只在进入分析页时加载，避免全局 30 秒轮询拖慢页面。
- 增加 favicon，浏览器控制台 0 错误。

## 修改文件

- `webui/api_server.py`
- `webui/index.html`
- `webui/public/favicon.svg`
- `webui/src/App.tsx`
- `webui/src/api.ts`
- `webui/src/components/KPIRow.tsx`
- `webui/src/components/StrategyPanel.tsx`
- `webui/src/components/TopBar.tsx`
- `webui/src/components/TradeTable.tsx`
- `webui/src/pages/MarketDataPage.tsx`
- `webui/src/styles.css`

## 前后端字段映射结果

| WebUI字段/功能 | 前端组件 | 接口 | 后端字段/来源 | 状态 |
|---|---|---|---|---|
| 顶部市场/时间/倒计时 | `TopBar` | `/api/status` | `current_market` + `true_market_snapshot()` | 正常 |
| 现价 | `TopBar` | `/api/status` | `ticker.btc_price`，当前为 Coinbase fallback | 可用但官方价降级 |
| 开盘价 | `TopBar` | `/api/status` | `platform_crypto_price_api` 优先 | 正常 |
| Up/Down概率 | `TopBar` | `/api/status` | CLOB orderbook mid | 正常 |
| 总市场/缺失 | `KPIRow` | `/api/missing-markets` | `windows.jsonl` 去重并按5分钟推算 | 已修 |
| 交易记录 | `TradeTable` | `/api/trades` | `trades.jsonl` 格式化 | 可用，仍需继续核验真实性 |
| 策略切换 | `StrategyPanel` | `/api/strategies/switch` | `config.json`/sim/live config | 已接后端 |
| 策略保存 | `StrategyPanel` | `/api/strategies/update` | `config.json`/sim/live config | 已接后端 |
| 市场列表 | `MarketDataPage` | `/api/market-windows` | `windows.jsonl` + trades + platform price | 已修开盘价逻辑 |
| 市场回放 | `MarketDataPage` | `/api/market-tick-data` | `orderbook_ticks.jsonl` + `price_ticks.jsonl` | 盘口可用，价格点缺口 |
| 数据分析图 | `AnalyticsPage` | `/api/fund-trend` `/api/skip-reasons` | `trades.jsonl` 聚合 | 可用，需美化 |
| 用户中心钱包 | `UserCenterPage` | `/api/wallet` | CLOB health + Polygon RPC | 可用，当前余额 0 |
| 实盘安全按钮 | `TopBar` | `/api/safety` | `route_ready` | 已禁用未就绪实盘 |

## 数据刷新与性能验证

- 快速刷新：`/api/status` + `/api/trades?p=1&ps=100`，5 秒。
- 数据质量：`/api/data-quality`，5 秒。
- 慢速刷新：`/api/safety`、`/api/summary`、`/api/strategies`、`/api/wallet`、`/api/missing-markets`，30 秒。
- 重图表接口：`/api/fund-trend`、`/api/skip-reasons` 已改成只在数据分析页加载，60 秒刷新。
- `/api/market-windows` 仍是相对慢接口，只在进入市场页首次加载，后续需要做服务端缓存。

## 旧文件待删除清单

暂不删除。候选旧目录：

- `old-webui`
- `btc5m-webui`
- `legacy-polymarket项目`
- `legacy-polymarket资料`

删除前必须等用户确认，并先提交 Git 备份。

## btc5m数据统计

初筛标准（待确认）：已结束市场 + 可靠开盘价（`ptb_quality` 为 platform/exact/good/close 且未 `exclude_from_backtest`）+ 有结算价 + 至少一个盘口 tick。

- `windows.jsonl` BTC市场：1541
- 从第一条到最新应有市场：1556
- 缺失市场：15
- 当前/未结束：1
- 盘口覆盖到的市场：1239
- 异常或被排除市场：901
- `resolutions.jsonl` 当前不是可用结算价文件，里面主要是 CLOB `market_resolved/new_market` 原始事件，不含 `closePrice`。
- `trades.jsonl` 交易/跳过记录：1096
- 按现有交易字段可用的完整交易记录：773
- 不完整交易记录：323，常见原因是概率缺失、开盘价缺失或盘口缺失。

结论：不能直接用全部 1541 个市场做深度回测；下一步要先确定“完整市场”标准，再补齐/隔离不完整数据。

## 回测结果

尚未执行深度回测。原因：完整市场标准还需确认，并且历史数据里有较多 `exclude_from_backtest` 和缺概率记录。直接跑会得到虚假胜率。

## 推荐策略

本阶段不推荐新策略，不切换模拟盘策略。下一步建议先建立“可信样本池”，再做训练/验证拆分。

## 模拟盘运行方案

暂不启动模拟盘。确认数据标准和策略后再启动。

建议启动前准备：

- 固定金额模式：每单 $1。
- 固定比例模式：初始模拟本金 $10，任何订单低于 $1 的信号跳过。
- 运行方式应记录：信号、入场秒数、方向、概率、盘口可成交价、投入、手续费、结算价、盈亏和余额变化。

## 需要用户确认的事项

- 是否同意把“完整市场”定义为：可靠开盘价 + 平台结算价 + 盘口覆盖 + 非排除市场。
- 是否允许后续写一个修复脚本，用 Polymarket crypto price API 为历史窗口补 `platform_open_price/platform_close_price` 索引文件。
- 是否继续让 5175 使用 Windows Python 托管，避免 WSL localhost relay 问题。
- 是否现在保持模拟盘暂停，等回测完成再启动。

## 主动建议

- 下一步不要急着跑回测，先做一个 `market_integrity.jsonl` 索引，把每个市场的完整性、数据源、盘口覆盖率和是否可回测固化下来。
- 市场回放要加“价格点缺失”的显眼提示，避免看到概率线就误以为 BTC 价格也是秒级完整。
- 实盘按钮保持禁用，直到 CLOB余额、授权、路线和策略都显示通过。

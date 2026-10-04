# 市场状态过滤器

**可追溯的候选线质量研究与策略验证框架。**

基于已确认高低点构建支撑与阻力候选线，用机器学习评估线的可靠性和有效期限，并通过策略回测与可追溯报告验证结果。

## 能力与边界

```text
已收盘 OHLCV → 延迟确认高低点 → 支撑/阻力候选线
→ 过去特征 / 成熟标签 → 时间隔离训练 → 可靠性评分与期限估计
→ 同策略不同评分器回测 → JSON / Markdown / HTML / SVG 报告
→ AI 工具接口：查询报告、查询任务、登记研究任务
```

- **高低点**：左右窗口极值；右侧确认前不可使用。
- **候选线**：同方向两个已确认锚点连线，记录发现时间。
- **机器学习**：逻辑回归估计指定期限内未失效的评分；Ridge 估计截断有效期限。
- **验证**：时间顺序分割；训练只使用分割前已成熟标签；留出集不调参。
- **策略**：示例只做支撑反弹多头。规则评分与 ML 评分使用相同策略、手续费及滑点。
- **AI 接口**：认证 HTTP 工具；仅登记研究任务，**不执行任务、不晋级模型、不修改策略、不下单**。

这是可运行的研究演示，不代表已经证明策略盈利或预测优势。模型分数未经独立概率校准；有效期限是 horizon 内截断量，不是无限外推；样本之间可能重叠，尚无独立统计显著性结论。当前只有一次时间留出评估，尚未实现多轮 walk-forward、真实数据验收或自动重训练。

## 安装与离线演示

要求 Python 3.12+。

```powershell
cd E:\市场状态过滤器
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\market-state-filter.exe demo --output outputs/demo
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Linux/macOS 可用 `python3 -m venv .venv`，然后执行 `.venv/bin/python -m pip install -e .` 和 `.venv/bin/market-state-filter demo`。

打开 `outputs/demo/report.html` 查看图表、模型评估及回测对照；JSON 包含逐笔交易和留出样本评分。演示行情由固定随机种子生成，来源标记为 `SYNTHETIC`，不能当作真实市场表现。

## 使用自己的行情

```powershell
.\.venv\Scripts\market-state-filter.exe research --csv local_data/bars.csv --horizon 24 --output outputs/research
```

CSV 列：`timestamp,open,high,low,close,volume`。时间必须严格递增、无重复，OHLC 合法。调用者必须保证全部为已收盘 K 线、间隔一致且无缺口。程序验证基础格式和等间隔，不验证交易所来源和收盘状态；此类输入标记为 `LOCAL_CSV_UNVERIFIED`。

## 项目结构

| 文件 | 职责 |
|---|---|
| `data.py` | 合成行情、CSV 校验、因果 ATR |
| `lines.py` | 延迟确认拐点、候选线、成熟标签 |
| `learning.py` | 时间隔离训练、评分、截断期限估计及评估 |
| `backtest.py` | 评分器与策略接口、下一根开盘成交、成本和回撤 |
| `reporting.py` | 本地图表与 JSON/Markdown/HTML 报告 |
| `api.py` | 认证工具、受限任务登记 |
| `cli.py` | `demo` / `research` / `serve` 入口 |
| `tests/` | 未来数据隔离、确认延迟、训练隔离、成交成本、接口权限测试 |

## AI 与远程统筹接口

详见 [接口文档](docs/AI_INTERFACE.md)。服务默认只监听 `127.0.0.1`，不会自行开放公网。你可以给 AI 客户端提供工具定义并调用接口；本项目没有内置大模型或自主执行 Agent。远程访问需自行设置 HTTPS 反向代理及访问控制，不能直接把开发服务裸露到公网。

## 扩展接口

可以通过 `Scorer.score(line)` 与策略 `signal(...)` 接口扩展评分器和策略。当前接口围绕候选线质量研究设计。

## 后续范围

优先在公开数据上完成基线对照与 walk-forward，再讨论更丰富的候选线、评分校准及策略。多交易所执行、实盘、LLM 自主改代码都不属于本版本。

## 许可

许可证待项目维护者确定。

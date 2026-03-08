# 期权策略量化分析白皮书-v0.1

## 版本信息

- **文档名称**：期权策略量化分析白皮书-v0.1
- **适用范围**：美股单标的日频/准实时 Meso 层期权结构分析
- **定位**：方法论白皮书，不直接面向下单执行，不包含具体交易建议
- **研究目标**：基于 Market Chameleon 三类聚合字段，构建低过拟合、可解释、可实现的四维象限打分卡与事件过滤器，用于识别标的的方向偏置、波动偏置、中性观察状态及趋势变化

---

## 1. 摘要

本文提出一套基于美股期权成交量、名义金额、结构占比、隐含波动率与事件标签的 **Meso 层量化分析框架**。该框架不是逐笔订单流分析，也不是面向交易执行的信号引擎，而是一个 **symbol-day / symbol-session 级别的状态识别系统**，用于回答以下问题：

1. 今日期权流是否显著异常；
2. 异常流量更偏向上侧表达还是下侧表达；
3. 当前市场是在主动抬升波动率，还是在主动压缩波动率；
4. 当前观察到的结构更可能是方向观点、波动观点，还是事件前后的短期噪音；
5. 当前状态较过去数日是否发生了显著切换。

框架核心思想不是“字段越多越好”，而是将原始字段压缩为 **方向、波动、置信度、持续性** 四个中层因子，进一步映射到四维象限标签，并通过 **财报事件过滤器** 降低误判与过拟合风险。

---

## 2. 研究边界与限制

### 2.1 本框架能做什么

- 对单标的构建 **偏多 / 偏空 / 中性待观察** 的方向状态；
- 对单标的构建 **买波 / 卖波 / 中性** 的波动状态；
- 对结构质量进行评估，剔除低质量的噪音流；
- 对财报前、财报日、财报后进行事件过滤；
- 识别状态切换，而非做精确价格预测。

### 2.2 本框架不能稳健做什么

- 不能直接恢复逐笔成交中的主动买卖方向；
- 不能区分开仓与平仓；
- 不能识别期权期限、delta、moneyness、0DTE 占比；
- 不能从聚合的 multi-leg 数据中准确还原净方向；
- 不能替代逐笔 Greeks、盘口和微观结构分析。

### 2.3 方法论立场

**本框架是中观状态分类器，不是单点预测器。**

因此，设计原则应当是：

- 优先追求 **可解释性**；
- 优先追求 **稳定性**；
- 优先追求 **可验证性**；
- 对方向与波动的判断采用 **概率表达**，而不是确定性语言；
- 尽量使用 **少量中层因子**，避免原始字段重复记分导致过拟合。

---

## 3. 输入字段与映射规则

### 3.1 字段映射

```json
{
  "Relative Volume to 90-Day Avg": "RelVolTo90D",
  "Call Volume": "CallVolume",
  "Put Volume": "PutVolume",
  "Put %": "PutPct",
  "% Single-Leg": "SingleLegPct",
  "% Multi Leg": "MultiLegPct",
  "% ContingentPct": "ContingentPct",
  "Relative Notional to 90-Day Avg": "RelNotionalTo90D",
  "Call $Notional": "CallNotional",
  "Put $Notional": "PutNotional",
  "symbol": "symbol",
  "Volatility % Chg": "IV30ChgPct",
  "Current IV30": "IV30",
  "20-Day Historical Vol": "HV20",
  "1-Year Historical Vol": "HV1Y",
  "IV30 % Rank": "IVR",
  "IV30 52-Week Position": "IV_52W_P",
  "Current Option Volume": "Volume",
  "Open Interest % Rank": "OI_PctRank",
  "Earnings": "Earnings",
  "Trade Count": "Trade_Count"
}
```

### 3.2 字段分层归类

| 层级 | 字段 | 作用 |
|---|---|---|
| 成交异常层 | `RelVolTo90D`, `RelNotionalTo90D`, `Volume`, `Trade_Count` | 判断是否存在异常活跃 |
| 类型偏置层 | `CallVolume`, `PutVolume`, `CallNotional`, `PutNotional`, `PutPct` | 判断上侧/下侧表达偏向 |
| 结构质量层 | `SingleLegPct`, `MultiLegPct`, `ContingentPct` | 判断信号是否干净 |
| 波动层 | `IV30ChgPct`, `IV30`, `HV20`, `HV1Y`, `IVR`, `IV_52W_P` | 判断买波/卖波与 IV 所处位置 |
| 事件层 | `Earnings` | 剥离财报影响 |
| 持续性层 | `OI_PctRank` | 判断状态可延展性 |

---

## 4. 第一性原理拆解

这套数据本质上回答四个问题：

1. **有没有异常**：今天的成交量与名义金额是否显著偏离 90 日均值；
2. **偏向哪边**：异常主要来自 call 还是 put，且金额是否与张数一致；
3. **波动在扩还是收**：IV30 是否上行，IV 与 HV 的相对关系如何；
4. **结构是否可信**：单腿占比是否足够高，是否被 contingent / multi-leg 扰动，是否处于事件窗口。

基于这一拆解，原始字段不应直接映射成交易结论，而应先压缩为中层因子，再由中层因子映射为状态标签。

---

## 5. 中层因子设计

本文定义四个核心中层因子：

1. **方向偏置分** `S_dir`
2. **波动偏置分** `S_vol`
3. **结构置信度** `S_conf`
4. **持续性分** `S_pers`

### 5.1 标准化原则

所有可比较数值字段在横截面上进行以下处理：

1. 缺失值清洗；
2. Winsorize（建议 1% / 99%）；
3. 横截面分位数变换为 `0-100`；
4. 对重尾变量优先取对数或 log-ratio。

记 `R(x)` 为字段 `x` 在当日横截面中的分位数，范围为 `[0, 100]`。

---

## 6. 四维打分卡

## 6.1 方向偏置分 `S_dir`

### 6.1.1 基础不平衡

$$
VolImb = \frac{CallVolume - PutVolume}{CallVolume + PutVolume + \varepsilon}
$$

$$
NotImb = \frac{CallNotional - PutNotional}{CallNotional + PutNotional + \varepsilon}
$$

$$
TypeImb = 0.6 \cdot NotImb + 0.4 \cdot VolImb
$$

### 6.1.2 结构与强度加权

$$
S_{dir} = 100 \cdot TypeImb \cdot \left(0.5 + 0.5\frac{R(SingleLegPct)}{100}\right) \cdot \left(0.5 + 0.5\frac{R(RelNotionalTo90D)}{100}\right)
$$

### 6.1.3 解释

- `NotImb` 权重大于 `VolImb`，因为廉价 OTM 合约会放大张数噪音；
- `SingleLegPct` 越高，方向解释越纯；
- `RelNotionalTo90D` 越高，越说明市场真的投入 premium，而非仅是低成本投机。

---

## 6.2 波动偏置分 `S_vol`

### 6.2.1 波动差与位置

$$
VolGapS = \ln\left(\frac{IV30}{HV20}\right)
$$

$$
IVLevel = \frac{R(IVR) + R(IV\_52W\_P)}{2}
$$

### 6.2.2 综合得分

$$
S_{vol} = 2 \cdot \Big(0.5R(IV30ChgPct) + 0.3R(VolGapS) + 0.2IVLevel - 50\Big)
$$

### 6.2.3 解释

- `IV30ChgPct` 代表当日 IV 冲量，是最关键的短期波动因子；
- `IV30/HV20` 代表当前 implied 相对 realized 的偏离；
- `IVR` 与 `IV_52W_P` 反映 IV 当前处于一年区间中的什么位置；
- 若 `S_vol` 显著为正，更偏向买波环境；若显著为负，更偏向卖波环境。

---

## 6.3 结构置信度 `S_conf`

### 6.3.1 一致性度量

$$
ImbAgree = 1 - \frac{|VolImb - NotImb|}{2}
$$

### 6.3.2 综合得分

$$
S_{conf} = 0.35R(SingleLegPct) + 0.25(100 - R(ContingentPct)) + 0.20R(Trade\_Count) + 0.20R(ImbAgree)
$$

### 6.3.3 解释

- `SingleLegPct` 高，说明结构解释干净；
- `ContingentPct` 高，通常意味着更多对冲、配对或非纯观点流，应降权；
- `Trade_Count` 高于单纯 `Volume` 更接近真实广度；
- `VolImb` 与 `NotImb` 越一致，越说明方向解释可靠。

---

## 6.4 持续性分 `S_pers`

### 6.4.1 金额富集度

$$
MoneyRich = \ln\left(\frac{RelNotionalTo90D}{RelVolTo90D + \varepsilon}\right)
$$

### 6.4.2 综合得分

$$
S_{pers} = 0.40R(OI\_PctRank) + 0.30R(RelNotionalTo90D) + 0.15R(RelVolTo90D) + 0.15R(MoneyRich)
$$

### 6.4.3 解释

- `OI_PctRank` 高，说明标的期权链长期具备较高活跃度基础；
- `RelNotionalTo90D` 高于 `RelVolTo90D`，通常比单纯张数爆量更有信息量；
- `MoneyRich` 有助于识别“金额真投入”与“便宜合约堆量”的差异。

---

## 7. 四维象限标签体系

### 7.1 主象限：方向 × 波动

| 象限 | 条件 | 标签 | 解释 |
|---|---|---|---|
| Q1 | `S_dir > +25` 且 `S_vol > +20` | 偏多 + 买波 | 上侧凸性需求，通常对应看涨并付费扩波 |
| Q2 | `S_dir < -25` 且 `S_vol > +20` | 偏空 + 买波 | 下侧保护需求或负向预期抬升 |
| Q3 | `S_dir < -25` 且 `S_vol < -20` | 偏多 + 卖波 | put-writing、保护撤退或下侧 risk premium 回收 |
| Q4 | `S_dir > +25` 且 `S_vol < -20` | 中性偏空 + 卖波 | call overwrite、上盖压波，方向解释不应过强 |
| N | 其他情况 | 中性待观察 | 信号不足、冲突、或处于过渡状态 |

### 7.2 批判性说明

Q4 的方向性解释最不稳定，因为 `call 主导 + IV 下行` 可能来自：

- covered call；
- call overwrite；
- 上侧收益增强结构；
- 事件后 call 溢价回落；
- 多腿结构被压缩后的聚合残差。

因此，**Q4 不应表述为强偏空，而应表述为“中性偏空 + 卖波”或“上盖压波”**。

---

## 8. 事件过滤器设计

`Earnings` 不应被当作普通线性特征使用，而应作为 **硬过滤条件**。因为财报窗口会系统性扭曲方向、波动与结构三个层面的解释。

### 8.1 事件状态定义

- `None`
- `Future`
- `Today`
- `Previous`

### 8.2 过滤规则

#### A. Earnings = Today

- `S_dir_adj = 0.5 * S_dir`
- `S_vol_adj = 1.3 * S_vol`
- 默认输出：`事件主导`
- 仅当 `S_conf >= 70` 且 `S_pers >= 60` 时，允许保留强方向标签

#### B. Earnings = Future

- `S_dir_adj = 0.7 * S_dir`
- `S_vol_adj = 1.15 * S_vol`
- 若 `IVLevel > 80` 且 `S_vol > 0`：优先标签 `事件溢价累积`
- 若 `S_conf < 55`：仅输出买波/卖波环境，不输出多空方向

#### C. Earnings = Previous

- 若 `IV30ChgPct < 0` 且 `S_vol < 0`：优先标签 `财报后压波`
- 仅当 `S_pers > 60` 时，方向标签继续有效

#### D. Earnings = None

- 直接使用标准四维打分卡结果

---

## 9. 防止过度拟合的设计准则

### 9.1 去冗余

以下字段应避免重复记分：

- `PutPct`：只做校验，不直接进入主分；
- `MultiLegPct`：只作为置信度降权项，不做单独方向项；
- `IVR` 与 `IV_52W_P`：合并为 `IVLevel`；
- `Volume`：只做流动性底线，不做主要 alpha 因子。

### 9.2 采用粗粒度权重

不建议：

- 对每个字段做精细回归权重拟合；
- 对少量样本做参数搜索；
- 用多重交互项过度解释单一日样本。

建议：

- 使用 `0.4 / 0.3 / 0.2 / 0.1` 级别的粗权重；
- 采用分桶 + 分位数 + veto 机制；
- 优先构建稳健状态，而非追求样本内命中率极值。

### 9.3 先 veto，再评分

以下情况默认降级为 `中性待观察`：

- `S_conf < 45`
- `S_pers < 40`
- `ContingentPct` 处于横截面极高位置
- `|S_dir| < 20` 且 `|S_vol| < 20`
- `Earnings = Today` 且结构不干净

---

## 10. 趋势变化与状态机

### 10.1 基本原则

单日数据只适合做 **当前状态识别**，不适合直接做趋势变化判定。

要判断“趋势变化”，至少需要近 5 到 10 个交易日的连续得分序列。

### 10.2 变化检测指标

定义：

$$
\Delta Dir_t = S_{dir,t} - median(S_{dir,t-5:t-1})
$$

$$
\Delta Vol_t = S_{vol,t} - median(S_{vol,t-5:t-1})
$$

### 10.3 Regime Shift 规则

当满足以下条件时，标记为 `Regime Shift`：

1. 主象限发生变化；
2. `|ΔDir| > 20`；
3. `|ΔVol| > 20`；
4. `S_pers > 55`。

### 10.4 确认规则

- 单日切换：`pending`
- 连续 2/3 日延续：`confirmed`
- 否则：`none`

---

## 11. 输出字段设计

建议最小输出结构如下：

| 字段 | 类型 | 说明 |
|---|---|---|
| `symbol` | string | 标的代码 |
| `trade_date` | date | 交易日期 |
| `S_dir` | float | 方向偏置分，范围建议 `[-100, 100]` |
| `S_vol` | float | 波动偏置分，范围建议 `[-100, 100]` |
| `S_conf` | float | 结构置信度，范围建议 `[0, 100]` |
| `S_pers` | float | 持续性分，范围建议 `[0, 100]` |
| `event_regime` | string | `none/future/today/previous` |
| `quadrant` | string | `Q1/Q2/Q3/Q4/N` |
| `label` | string | 人类可读标签 |
| `shift_flag` | string | `none/pending/confirmed` |
| `prob_tier` | string | `high/mid/low` |
| `notes` | text | 降权原因、事件标签、异常说明 |

### 11.1 概率层级建议

- `high`：`S_conf >= 70` 且 `S_pers >= 65`
- `mid`：`S_conf >= 55` 且 `S_pers >= 50`
- `low`：其余

---

## 12. 回测与验证框架

### 12.1 核心原则

回测不是为了证明“分数越高越赚钱”，而是为了验证：

1. 状态标签是否具有可复现性；
2. 方向与波动标签是否在统计上对应不同的后验分布；
3. 事件过滤是否显著降低误判率；
4. Q1/Q2/Q3/Q4 的分布特征是否具备可区分性。

### 12.2 建议的验证方式

#### 方向验证

- 未来 1D / 3D / 5D 标的收益分布；
- 上涨概率、下跌概率、中位数收益、尾部分位数；
- 与基准组 `Neutral` 对照。

#### 波动验证

- 未来 5D / 10D 实现波动率变化；
- IV30 后续均值回复路径；
- 事件前后 IV crush 发生概率。

#### 稳定性验证

- 不同年份、不同板块、不同市值组的横向一致性；
- 训练期与验证期的一致性；
- 极端市场阶段下的行为差异。

### 12.3 不推荐的验证做法

- 在少量标的上人工微调阈值；
- 以单一收益指标反推全部权重；
- 将事件期和非事件期混合评估；
- 在没有 OOS 的情况下报告“高胜率”。

---

## 13. 实施建议

### 13.1 MVP 版本

MVP 建议仅包含：

- 日频导入；
- 横截面标准化；
- 四维打分卡计算；
- 财报事件过滤；
- 象限输出；
- 近 5 日状态切换；
- SQLite 落库与 CSV/Markdown 输出。

### 13.2 后续增强方向

可在后续版本扩展：

- Tenor 分桶；
- 0DTE / 1W / 1M 维度拆分；
- Delta bucket 分层；
- 开平仓近似判别；
- 与标的现货、短借、ETF 资金流联动；
- 与行业/主题横截面对比。

---

## 14. 风险提示

1. 期权聚合字段的解释天然存在歧义；
2. Multi-leg 与 contingent 会显著污染方向判断；
3. 事件窗口会扭曲 IV 与成交结构；
4. 高 `PutNotional` 不等价于明确偏空，也可能来自保护或组合再平衡；
5. 高 `CallNotional` 不等价于明确偏多，也可能来自收益增强或 overwrite；
6. 单日观测不应被表述为长期趋势结论。

---

## 15. 结论

本文构建了一套适用于美股单标的 Meso 层期权结构识别的四维框架。该框架用最少必要的中层因子，连接了以下五个关键维度：

- 异常活跃度；
- 类型偏向；
- 波动冲量；
- 结构洁净度；
- 事件过滤。

其核心价值不在于直接生成交易指令，而在于：

- 为研究员提供可解释的状态刻画；
- 为后续代码实现提供稳定接口；
- 为更高维度数据的接入提供统一抽象层；
- 通过少量稳健规则降低过拟合风险。

**最终建议**：将该框架作为“中观状态层”，而非最终执行层；将其输出作为后续研究、监控、复核与策略分层输入。

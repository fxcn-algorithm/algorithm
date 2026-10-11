# RFC-0001：撤回牌照记 0 分；35 个记录暂停评分

- 状态：**补登记**。两项变更已经在生产环境生效，生效前没有按本目录的流程公示 30 天。本文件公开说明这一偏离，并把规则与实现对齐。
- 提出者：FXCN 编辑团队
- 影响的算法版本：v1（规则文件新增 `status_zero`，权重不变）
- 登记日期：2026-10-11

## 偏离说明

`/algorithm` 页承诺权重和规则调整先在这里公示 30 天。下面两项没有这样做：

1. 2026-08-30 的数据迁移（编号 032）把 35 个记录的总分置为空。
2. 新增的 `withdrawn` 牌照状态在生产实现中记 0 分，但 `rules.json` 和 `score.py` 一直没有同步。

结果是，用 2026-08-28 快照复现得到的分数，与 2026-10-11 网站上的分数不一致。本 RFC 补上说明和代码，并在网站上同步更正文案。

## 变更一：撤回牌照记 0 分

**问题**：监管机构撤回某张牌照后，若仍按 Tier 加分，会把历史许可当成现行许可。

**规则**：`regulation.status_zero = ["withdrawn"]`。处于该状态的牌照，加分为 0，理由写明“历史牌照已撤回，不计为现行许可”。这与 `revoked`（吊销，扣 40 分）不同：撤回通常是公司主动放弃许可，不等于监管处罚。

**影响**：截至 2026-10-11，库中有 2 条牌照为 withdrawn。

## 变更二：35 个记录暂停评分（总分为空）

**问题**：某个维度缺少证据，表示“未知”，而不是“零分”。把这些记录照常评分，会给出有误导性的数字。

**做法**：以下记录保留在库中，但不给总分。网站显示“数据不足”，颜色为灰色。它们在快照中的 `published.total` 为 `null`，复现测试会跳过。

| 原因 | 数量 | 记录 |
|---|---|---|
| 无法把法律实体对应到现行一手或监管记录 | 22 | colmex-pro, finam, jfd-bank, lcg, orbex, swissmarkets, ufx, valutrades, xtrade, alpha-trading, avenue, bingx-fx, clear-corretora, mfm-securities, forex-club, fxgt, larson-holz, nordfx, olymp-trade, pocket-option, quotex, weltrade |
| 地区重复或历史重复记录 | 5 | fbs-cy, axitrader-au, plus500-il, libertex-ru, hf-markets-sa |
| 机构交易场所，不适用零售经纪商牌照评分 | 5 | 360t, cboe-fx, ebs, euronext-fx, refinitiv-fxall |
| 需确认是否属于零售外汇经纪商范围 | 3 | e-trade, fidelity, smart-prop |

**恢复条件**：完成实体与证据匹配后，以单独 PR 重新评分并附分数 diff。

## 同期的数据更新（不属于规则变更）

与 2026-08-28 快照相比，有 19 家分数不同：

- 其中 12 家来自 2026-10-11 的牌照复核：按官方登记册更正了撤回、失效或错配的牌照记录。
- 其余 7 家来自 8 月底至 10 月初的牌照数据更新。

| 记录 | 2026-08-28 | 2026-10-11 | 原因 |
|---|---|---|---|
| activtrades | 79 (yellow) | 78.4 (yellow) | 2026-10-11 牌照复核 |
| adss | 72.6 (yellow) | 61.8 (yellow) | 2026-10-11 牌照复核 |
| bank-de-binary | 41 (orange) | 44 (orange) | 2026-10-11 牌照复核 |
| bdswiss | 60.6 (yellow) | 63.6 (yellow) | 2026-10-11 牌照复核 |
| fbs | 59.9 (orange) | 60.5 (yellow) | 2026-10-11 牌照复核 |
| fxtm | 79 (yellow) | 77.5 (yellow) | 此前的牌照数据更新 |
| grand-capital | 44.6 (orange) | 29 (red) | 2026-10-11 牌照复核 |
| hycm | 79 (yellow) | 73 (yellow) | 此前的牌照数据更新 |
| icm-capital | 72.6 (yellow) | 61.8 (yellow) | 2026-10-11 牌照复核 |
| ifc-markets | 59.9 (orange) | 50.9 (orange) | 2026-10-11 牌照复核 |
| iq-option | 55.5 (orange) | 63 (yellow) | 2026-10-11 牌照复核 |
| kgi-securities | 69 (yellow) | 64.5 (yellow) | 此前的牌照数据更新 |
| naga | 78 (yellow) | 72 (yellow) | 2026-10-11 牌照复核 |
| octafx | 53.9 (orange) | 53.6 (orange) | 此前的牌照数据更新 |
| phillip-securities | 78 (yellow) | 76.5 (yellow) | 此前的牌照数据更新 |
| prime-xbt | 44.9 (orange) | 44.6 (orange) | 2026-10-11 牌照复核 |
| swissquote | 81 (yellow) | 79.5 (yellow) | 此前的牌照数据更新 |
| xp-investimentos | 70.2 (yellow) | 66.6 (yellow) | 此前的牌照数据更新 |
| zulutrade | 57.6 (orange) | 55.8 (orange) | 2026-10-11 牌照复核 |

## 复现

```
python3 tests/test_reproduce.py data/snapshot-2026-10-11.json   # 94 家一致，35 家跳过
python3 tests/test_reproduce.py data/snapshot-2026-08-28.json   # 129 家一致
```

## 今后

今后的规则变更都按 README 的流程先在本目录公示 30 天。数据更新后，受影响记录的分数必须当天重算，并更新快照。

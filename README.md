# fxcn 透明评分算法

[fxcn.com](https://fxcn.com) 给外汇经纪商打分用的完整算法、规则文件与公开数据快照。

**MIT 授权。任何人都可以下载、修改、用自己的数据复现完整评分。**

---

## 30 秒验证我们没有作弊

不需要装任何依赖,Python 3.8+ 即可:

```bash
git clone https://github.com/fxcn/fxcn-algorithm.git
cd fxcn-algorithm
python3 tests/test_reproduce.py data/snapshot-2026-08-28.json
```

它会用本仓库的算法重算快照里每一家的分数,逐家与 **fxcn.com 当时公布的分数**比对:

```
快照      : data/snapshot-2026-08-28.json
算法版本  : v1 · 快照日期 2026-08-28
比对      : 129 家(跳过 0 家未评分)

✓ 129 家全部复现一致(总分、五个维度、颜色)
```

任何一家对不上,退出码就是非 0。**这就是「算法 100% 开源」的可执行版本** ——
不是一句标语,是一条你能亲自跑的命令。

想看单独一家的逐条加减分依据:

```bash
python3 algorithm/score.py data/snapshot-2026-08-28.json ic-markets
```

```
ic-markets                85.00  green   reg=100.0  risk=90.0  trans=85.0  rep=50.0  disc=100.0  覆盖 4/5

逐条依据:
  [regulation  ] REG_LIC_ASIC        +30.00  持有 Tier 1 监管 (ASIC) 牌照  ← https://asic.gov.au/...
  [regulation  ] REG_LIC_CySEC       +30.00  持有 Tier 1 监管 (CySEC) 牌照 ← https://www.cysec.gov.cy
  [risk        ] RISK_FUND_SEG       +30.00  客户资金独立托管,可验证
  ...
```

---

## 这个仓库里有什么

```
algorithm/rules.json          全部权重、加减分、阈值 —— 规则与代码分离,便于逐行 review
algorithm/score.py            参考实现(零第三方依赖)
data/snapshot-YYYY-MM-DD.json 公开数据快照 + 官网当时的分数(用于比对)
tests/test_reproduce.py       复现验证:全部经纪商逐家比对
rfc/                          权重变更的 30 天公示流程
ALGORITHM.md                  规则全文说明
```

## 算法一句话版

```
总分 = 0.30×监管 + 0.20×风控 + 0.20×透明 + 0.20×口碑 + 0.10×披露
```

每个维度基础分 50,按规则加减后 clip 到 [0, 100]。完整规则见 [ALGORITHM.md](ALGORITHM.md)。

三个容易被忽略、但很关键的设计:

1. **监管处罚在维度封顶之后才扣。** 否则牌照多的大商对罚款免疫 ——
   4 张 Tier-1 牌照已经 50+120=170、封顶 100,再减 30 依然是 100。
2. **「未评估」不等于「差」。** 没有数据的维度停在基准 50 分,且**不参与降档判断**。
   否则口碑长期无数据会让所有经纪商永远拿不到 green。
3. **分数不是用户评价的聚合**,是算法评估。所以站上用 schema.org 的 `Review`
   (作者是 FXCN 这个机构)而不是 `AggregateRating`。

## 用你自己的数据跑

快照的字段格式见 [data/README.md](data/README.md)。按同样的结构准备一份 JSON,然后:

```bash
python3 algorithm/score.py your-data.json
```

## 想改规则?

改权重要走 [rfc/](rfc/) 里的 30 天公示流程 —— 这是 fxcn.com 对读者的承诺,
不是内部规矩。修实现 bug 不需要公示,但要单独开 PR 并附分数 diff。

## 数据与隐私

快照**只包含算法真正读取的字段**,并且**不含任何个人用户评论内容** ——
口碑维度只用到评论条数与平均分这两个聚合值。牌照与处罚的证据链接指向监管机构公开页面。

## 局限,写在前面

- **口碑维度目前几乎没有数据。** 129 家中评论数 ≥5 的为 0,所以这一维度基本停在基准 50。
  这不是算法缺陷,是数据缺失 —— 我们宁可标「未评估」也不编。
- **交易条件(最低入金、点差等)尚未进入评分。** 覆盖率还不够。
- **监管处罚记录目前为 0 条已确认。** 管线已就绪,但还没有经人工核实的记录入库。

这些都会随数据补齐而变化,每次变化都会有新的快照与 CHANGELOG。

## 相关

- 评分方法论(中文页):https://fxcn.com/algorithm
- 数据可追溯性说明:https://fxcn.com/transparency
- 编辑政策:https://fxcn.com/editorial-policy

---

## English

The complete scoring algorithm behind [fxcn.com](https://fxcn.com)'s forex broker ratings —
rules, reference implementation, and public data snapshots. **MIT licensed.**

Verify we are not cheating, in 30 seconds, with no dependencies:

```bash
python3 tests/test_reproduce.py data/snapshot-2026-08-28.json
# ✓ 129 brokers reproduce exactly (total, all five dimensions, colour band)
```

The script recomputes every broker from the public snapshot and compares against the
scores fxcn.com published on that date. If a single broker disagrees, it exits non-zero.

```
Total = 0.30×Regulation + 0.20×Risk + 0.20×Transparency + 0.20×Reputation + 0.10×Disclosure
```

Each dimension starts at 50, rules add or subtract, then it is clipped to [0, 100].
Full rules in [ALGORITHM.md](ALGORITHM.md); weight changes go through the
30-day public RFC in [rfc/](rfc/).

**Known limits, stated up front:** the reputation dimension has almost no data yet
(0 of 129 brokers have ≥5 reviews), trading conditions are not yet scored, and there are
currently 0 confirmed enforcement actions. We would rather label a dimension
"not assessed" than invent a number for it.

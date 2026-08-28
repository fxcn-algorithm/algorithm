# 数据快照

每份 `snapshot-YYYY-MM-DD.json` 是 fxcn.com 在该日期的**公开评分输入**的完整导出。
配合 `algorithm/score.py` 可以重算出当天 fxcn.com 上显示的每一个分数。

## 只导出算法真正读取的字段

多导一个字段就是多一份无谓的暴露面,所以快照里**没有**经纪商表的其余列。

```
brokers[]
  slug, name, name_en
  signals{}                     ← meta_json 中参与评分的 11 个键,详见下表
  licenses[]                    ← regulator_code, tier, license_status, license_no, evidence_url
  reviews{}                     ← 只有 count 与 avg_rating(**不含任何个人评论内容**)
  enforcement_actions[]         ← 仅 status=confirmed;id, regulator_code, action_type,
                                   severity, action_date, amount, currency, source_url
  published{}                   ← 官网当时公布的分数,供复现比对用,**不是算法输入**
meta{ algo_version, snapshot_date, broker_count, source, license }
```

### signals 各键含义

| 键 | 类型 | 参与维度 |
|---|---|---|
| `hq_matches_operation` | bool | transparency |
| `shareholders_disclosed` | bool | transparency |
| `annual_report_url` | url | transparency |
| `client_funds_segregated` | bool | risk |
| `client_funds_segregated_evidence` | url | risk(仅作证据链接) |
| `negative_balance_protection` | bool | risk |
| `compensation_scheme` | string | risk |
| `margin_close_out_pct` | number | risk |
| `risk_disclosure_url` | url | disclosure |
| `spread_history_url` | url | disclosure |
| `order_flow_disclosure` | bool | disclosure |

## 隐私

- **不导出任何个人用户评论**,只导出聚合的条数与平均分。评分算法本来也只用这两个值。
- 牌照与处罚记录的 `evidence_url` / `source_url` 指向监管机构的公开页面。

## 关于 `published`

它是**比对目标**,不是输入。`algorithm/score.py` 不读这个字段;
`tests/test_reproduce.py` 用它来验证复现结果是否与官网一致。

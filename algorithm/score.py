#!/usr/bin/env python3
"""
fxcn 透明评分算法 —— 独立参考实现(零第三方依赖)。

设计目标只有一个:**任何人拿这份代码 + 公开数据快照,能算出与 fxcn.com 上
一模一样的分数。** 复现不了,「算法 100% 开源」就是句空话。

用法:
    python3 algorithm/score.py data/snapshot-2026-08-28.json            # 打印全部
    python3 algorithm/score.py data/snapshot-2026-08-28.json ic-markets # 只看一家(含逐条依据)

生产实现是 PHP(src/Services/Score/ScoreService.php),这里是同一套规则的
Python 版。两者必须给出相同结果 —— tests/test_reproduce.py 会拿快照里
published 的官网分数逐家比对来证明这一点。
"""
import json
import math
import sys
from datetime import date, datetime
from pathlib import Path

RULES_PATH = Path(__file__).with_name("rules.json")


def php_round(value: float, precision: int = 0) -> float:
    """
    PHP 的 round() 是「四舍五入,.5 远离零」;Python 内建 round() 是银行家舍入
    (round(0.5)==0)。直接用 Python 的 round 会在 .5 边界上与生产实现分叉,
    所以这里显式实现 PHP 的语义。
    """
    if value is None:
        return None
    factor = 10 ** precision
    scaled = value * factor
    # 浮点噪声会让 2.675*100 变成 267.49999…,先做一次极小量的规整
    scaled = math.floor(abs(scaled) + 0.5 + 1e-9) * (1 if scaled >= 0 else -1)
    return scaled / factor


def clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class Item:
    """一条加减分依据。前台的『为什么是这个分』就是这些条目。"""
    __slots__ = ("dimension", "code", "delta", "reason", "evidence")

    def __init__(self, dimension, code, delta, reason, evidence=None):
        self.dimension = dimension
        self.code = code
        self.delta = float(delta)
        self.reason = reason
        self.evidence = evidence

    def as_dict(self):
        return {"dimension": self.dimension, "code": self.code, "delta": self.delta,
                "reason": self.reason, "evidence": self.evidence}


class Scorer:
    def __init__(self, rules: dict, today: date = None):
        self.r = rules
        # 处罚按年衰减,所以「今天」是算法输入之一。复现历史分数时要把它显式传进来,
        # 否则同一份快照在不同日期会算出不同结果。
        self.today = today or date.today()

    # ── 各维度 ──────────────────────────────────────────────
    def regulation(self, b) -> list:
        items = []
        rr = self.r["regulation"]
        licenses = b.get("licenses") or []
        if not licenses:
            items.append(Item("regulation", rr["no_license"]["code"],
                              rr["no_license"]["delta"], "未发现任何已验证监管牌照"))
            return items

        for lic in licenses:
            code = lic["regulator_code"]
            tier = str(int(lic.get("tier") or 3))
            delta = rr["tier_delta"].get(tier, rr["tier_delta"]["3"])
            reason = f"持有 Tier {tier} 监管 ({code}) 牌照"

            st = lic.get("license_status")
            if st in rr["status_delta"]:
                delta += rr["status_delta"][st]
                reason += f",但牌照状态为 {st}"
            elif st in rr.get("status_zero", []):
                # 历史牌照已撤回:不计为现行许可(RFC-0001)
                delta = 0
                reason = f"历史 Tier {tier} 监管 ({code}) 牌照已撤回,不计为现行许可"
            elif st in rr["status_halve"]:
                # 注意是「加分减半」,不是固定扣分
                delta = php_round(delta / 2)
                reason += ",待验证"

            items.append(Item("regulation", f"REG_LIC_{code}", delta, reason,
                              lic.get("evidence_url")))

        items.extend(self.enforcement(b))
        return items

    def enforcement(self, b) -> list:
        """监管处罚。仅 status=confirmed 的记录进快照,所以这里不再过滤。"""
        er = self.r["enforcement"]
        actions = b.get("enforcement_actions") or []
        if not actions:
            return []

        items, total = [], 0.0
        floor = float(er["floor"])
        for a in actions:
            base = er["base_penalty"].get(a.get("action_type"), er["base_penalty"]["other"])
            mult = er["severity_multiplier"].get(a.get("severity"), 1.0)
            delta = -php_round(base * mult * self.decay(a.get("action_date")), 1)
            if delta == 0.0:
                continue

            capped = False
            if total + delta < floor:
                # 必须取 floor - total(一个负数)。写成 max(floor - total, -0.0)
                # 是错的 —— -0.0 > -60,会把整条处罚静默清零。
                delta = min(0.0, floor - total)
                capped = True
            total += delta

            reason = f"{a.get('regulator_code')} {a.get('action_type')} ({a.get('action_date')})"
            if capped:
                reason = "[已触及处罚扣分下限] " + reason
            # 每一条前科都要出现在列表里,即使已不再影响分数 —— 触底就 break 是在美化
            items.append(Item("regulation",
                              f"REG_ACTION_{str(a.get('regulator_code','')).upper()}_{a.get('id')}",
                              php_round(delta, 1), reason, a.get("source_url")))
        return items

    def decay(self, action_date) -> float:
        d = self.r["enforcement"]["decay"]
        if not action_date:
            return 1.0
        try:
            ad = datetime.strptime(str(action_date)[:10], "%Y-%m-%d").date()
        except ValueError:
            return 1.0
        years = max(0.0, (self.today - ad).days / 365.25)
        if years <= d["grace_years"]:
            return 1.0
        return max(d["min"], d["factor"] ** (years - d["grace_years"]))

    def risk(self, b) -> list:
        items, s, rr = [], b.get("signals") or {}, self.r["risk"]
        if s.get("client_funds_segregated"):
            items.append(Item("risk", rr["client_funds_segregated"]["code"],
                              rr["client_funds_segregated"]["delta"], "客户资金独立托管,可验证",
                              s.get("client_funds_segregated_evidence")))
        if s.get("negative_balance_protection"):
            items.append(Item("risk", rr["negative_balance_protection"]["code"],
                              rr["negative_balance_protection"]["delta"], "提供负余额保护"))
        if s.get("compensation_scheme"):
            items.append(Item("risk", rr["compensation_scheme"]["code"],
                              rr["compensation_scheme"]["delta"],
                              f"加入投资者赔偿计划: {s['compensation_scheme']}"))
        if "margin_close_out_pct" in s and s["margin_close_out_pct"] is not None:
            p = float(s["margin_close_out_pct"])
            lo, hi = rr["margin_close_out_pct"]["low"], rr["margin_close_out_pct"]["high"]
            if p < lo["threshold_lt"]:
                items.append(Item("risk", lo["code"], lo["delta"], f"强平阈值 {p}% 较合理"))
            elif p > hi["threshold_gt"]:
                items.append(Item("risk", hi["code"], hi["delta"], f"强平阈值 {p}% 偏高"))
        return items

    def transparency(self, b) -> list:
        items, s, tr = [], b.get("signals") or {}, self.r["transparency"]
        if s.get("hq_matches_operation"):
            items.append(Item("transparency", tr["hq_matches_operation_true"]["code"],
                              tr["hq_matches_operation_true"]["delta"], "注册地与实际运营地一致"))
        elif "hq_matches_operation" in s and s["hq_matches_operation"] is False:
            items.append(Item("transparency", tr["hq_matches_operation_false"]["code"],
                              tr["hq_matches_operation_false"]["delta"], "离岸注册 + 远端运营,实控不透明"))
        if s.get("shareholders_disclosed"):
            items.append(Item("transparency", tr["shareholders_disclosed"]["code"],
                              tr["shareholders_disclosed"]["delta"], "股东与董事公开可查"))
        if s.get("annual_report_url"):
            items.append(Item("transparency", tr["annual_report_url"]["code"],
                              tr["annual_report_url"]["delta"], "提供可查的年度审计报告",
                              s["annual_report_url"]))
        return items

    def reputation(self, b) -> list:
        pr = self.r["reputation"]
        rev = b.get("reviews") or {}
        cnt = int(rev.get("count") or 0)
        if cnt < pr["min_reviews"]:
            # delta=0 的占位条目。它的含义是「数据不足以评估」,
            # 因此**不能算作已评估维度** —— 见 assessed 的判定。
            return [Item("reputation", pr["insufficient_code"], 0,
                         f"用户评论数 ({cnt}) 不足以评估")]
        avg = float(rev.get("avg_rating") or 0.0)
        f = pr["formula"]
        delta = php_round((avg - f["pivot"]) * f["scale"], 2)
        return [Item("reputation", f["code"], delta, f"已验证用户平均评分 {avg} (n={cnt})")]

    def disclosure(self, b) -> list:
        items, s, dr = [], b.get("signals") or {}, self.r["disclosure"]
        if s.get("risk_disclosure_url"):
            items.append(Item("disclosure", dr["risk_disclosure_url"]["code"],
                              dr["risk_disclosure_url"]["delta"], "官网公开风险声明",
                              s["risk_disclosure_url"]))
        if s.get("spread_history_url"):
            items.append(Item("disclosure", dr["spread_history_url"]["code"],
                              dr["spread_history_url"]["delta"], "点差/隔夜利息历史可下载",
                              s["spread_history_url"]))
        if s.get("order_flow_disclosure"):
            items.append(Item("disclosure", dr["order_flow_disclosure"]["code"],
                              dr["order_flow_disclosure"]["delta"], "披露订单流去向(LP)"))
        return items

    # ── 汇总 ────────────────────────────────────────────────
    def score(self, b) -> dict:
        items = (self.regulation(b) + self.risk(b) + self.transparency(b)
                 + self.reputation(b) + self.disclosure(b))

        base = self.r["dimension_base"]
        lo, hi = self.r["dimension_clip"]
        dims = {k: float(base) for k in self.r["weights"]}

        # 处罚必须在**封顶之后**再扣。
        # 例:某商有 4 张 Tier-1 牌照 → 50 + 120 = 170,封顶 100;
        # 若把 −30 罚款并进加总,170 − 30 = 140 仍然封顶 100,罚款等于没发生。
        penalties = {}
        for it in items:
            if it.code.startswith("REG_ACTION_"):
                penalties[it.dimension] = penalties.get(it.dimension, 0.0) + it.delta
            else:
                dims[it.dimension] += it.delta

        for k in dims:
            dims[k] = clip(dims[k], lo, hi)
        for dim, p in penalties.items():
            dims[dim] = clip(dims[dim] + p, lo, hi)

        total = php_round(sum(dims[d] * w for d, w in self.r["weights"].items()), 2)

        # 「已评估」= 至少产生过一条 delta≠0 且不是 *_INSUFFICIENT 的条目
        assessed = sorted({it.dimension for it in items
                           if it.delta != 0.0 and not it.code.endswith("_INSUFFICIENT")})

        return {
            "total": total,
            "dimensions": {k: php_round(v, 2) for k, v in dims.items()},
            "color": self.color(total, dims, assessed),
            "assessed": assessed,
            "coverage": f"{len(assessed)}/{len(self.r['weights'])}",
            "items": [i.as_dict() for i in items],
        }

    def color(self, total, dims, assessed) -> str:
        cb = self.r["color_bands"]
        judged = {k: v for k, v in dims.items() if k in assessed} if assessed else dict(dims)
        min_dim = min(judged.values()) if judged else 100

        if total >= cb["green"]["total_gte"]:
            return "yellow" if min_dim < cb["green"]["downgrade_to_yellow_if_min_assessed_dim_lt"] else "green"
        if total >= cb["yellow"]["total_gte"]:
            return "red" if dims["regulation"] < cb["yellow"]["downgrade_to_red_if_regulation_lt"] else "yellow"
        if total >= cb["orange"]["total_gte"]:
            return "orange"
        return "red"


def load(snapshot_path):
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    snap = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    return rules, snap


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    rules, snap = load(argv[1])
    # 快照日期就是「当时的今天」—— 用它而不是运行日期,处罚衰减才能复现
    today = datetime.strptime(snap["meta"]["snapshot_date"], "%Y-%m-%d").date()
    scorer = Scorer(rules, today=today)

    only = argv[2] if len(argv) > 2 else None
    for b in snap["brokers"]:
        if only and b["slug"] != only:
            continue
        r = scorer.score(b)
        d = r["dimensions"]
        print(f"{b['slug']:<24} {r['total']:>6.2f}  {r['color']:<7} "
              f"reg={d['regulation']:<6.1f} risk={d['risk']:<6.1f} "
              f"trans={d['transparency']:<6.1f} rep={d['reputation']:<6.1f} "
              f"disc={d['disclosure']:<6.1f} 覆盖 {r['coverage']}")
        if only:
            print("\n逐条依据:")
            for it in r["items"]:
                ev = f"  ← {it['evidence']}" if it["evidence"] else ""
                print(f"  [{it['dimension']:<12}] {it['code']:<28} {it['delta']:>+7.2f}  {it['reason']}{ev}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

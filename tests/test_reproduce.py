#!/usr/bin/env python3
"""
复现性验证 —— 本仓库存在的理由。

fxcn.com 声称「评分算法完全公开,任何人都能复现」。这个脚本就是那句话的证明:
拿本仓库的实现 + 公开数据快照重算,逐家与快照里 `published`(官网当时公布的分数)比对。

    python3 tests/test_reproduce.py data/snapshot-2026-08-28.json

**任何一家对不上就退出码非 0。** 我们不接受「大体一致」——
分数是本站的产品,差 0.01 也要能解释。
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "algorithm"))
from score import Scorer, load  # noqa: E402

TOL = 0.01          # 允许的浮点误差,不是「允许的偏差」
DIMS = ["regulation", "risk", "transparency", "reputation", "disclosure"]


def main(argv):
    snap_path = argv[1] if len(argv) > 1 else "data/snapshot-2026-08-28.json"
    rules, snap = load(snap_path)
    today = datetime.strptime(snap["meta"]["snapshot_date"], "%Y-%m-%d").date()
    scorer = Scorer(rules, today=today)

    checked = skipped = 0
    failures = []

    for b in snap["brokers"]:
        pub = b.get("published") or {}
        if pub.get("total") is None:
            skipped += 1
            continue
        got = scorer.score(b)
        checked += 1

        diffs = []
        if abs(got["total"] - float(pub["total"])) > TOL:
            diffs.append(f"total {got['total']} != {pub['total']}")
        for d in DIMS:
            if pub.get(d) is None:
                continue
            if abs(got["dimensions"][d] - float(pub[d])) > TOL:
                diffs.append(f"{d} {got['dimensions'][d]} != {pub[d]}")
        if pub.get("color") and got["color"] != pub["color"]:
            diffs.append(f"color {got['color']} != {pub['color']}")

        if diffs:
            failures.append((b["slug"], diffs))

    print(f"快照      : {snap_path}")
    print(f"算法版本  : {rules['algo_version']} · 快照日期 {snap['meta']['snapshot_date']}")
    print(f"比对      : {checked} 家(跳过 {skipped} 家未评分)")

    if failures:
        print(f"\n✗ {len(failures)} 家复现不一致:\n")
        for slug, diffs in failures[:40]:
            print(f"  {slug}")
            for d in diffs:
                print(f"      {d}")
        if len(failures) > 40:
            print(f"  …还有 {len(failures) - 40} 家")
        return 1

    print(f"\n✓ {checked} 家全部复现一致(总分、五个维度、颜色)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

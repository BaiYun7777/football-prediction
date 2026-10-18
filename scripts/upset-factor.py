#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
upset-factor.py —— 三层爆冷修正（L1 风格克制 / L2 状态变量 / L3 赛制红利）

配套 Football Prediction Expert v3.2.9（规则口径标注，2026-09-08）· 阶段 2.7
⚠️ 版本实况：脚本本体为 v3.2.6 打包时重建，爆冷修正算法自 v3.2.5 起未改动；
    规则口径已同步至 v3.2.9。本脚本**只做 L1/L2/L3 三层增量与爆冷分级**，
    v3.2.7 之后的规则修正（洲际降权、效率回摆、obs-7 口径）须由调用方另行叠加。
用法:
    python3 scripts/upset-factor.py --base "主胜,平,客胜" --l1 2 --l2 3 --l3 1
                                    [--fav home|away]

--fav 说明（2026-09-08 新增，修复调用方 prompt 与脚本接口不符的 bug）：
    手工指定「热门方」，默认（不传）= 自动取主胜/客胜中概率较高者。
    用于「概率最高方 ≠ 分析意义上的热门方」的场次，例如：
      - 客队让球（-1）但主胜概率略高 → 让球视角的热门方是客队，应 --fav away
      - 市场定价与独立模型判断背离，分析认定的强队概率并非最高时
      - 洲际周前/轮换场景下，名义强队实为非热门方
    ⚠️ 指定方的概率若低于另一方，脚本会**告警但仍按指定执行**（--fav 语义即覆盖自动判定）。

量化规则（SKILL.md 2.7）：
  - 每层 L0/L1/L2/L3 → +0 / +2.5 / +5.0 / +7.5 个百分点
  - 三层求和，总增量上限 +15pp
  - 增量从「热门方胜率」转移给「平局 + 弱队胜」，按两者基准占比分配 → 概率守恒
  - 爆冷等级 = P(弱队胜) + P(平局)：
        >=45%  Tier1    30-45%  Tier2    15-30%  Tier3    <15%  无
  - 输出三层贡献拆解，可解释是哪一层推高了爆冷概率

v3.2.5 联动说明（Tier 降仓解耦）：
  - 爆冷等级只作风险提示，**不自动触发降仓/防平**
  - 若热门方模型概率 p >= 60%（高置信方向），即使 Tier1/2 也不降仓、不强制防平，仅标注风险
  - Tier >= 2 时「让球深盘联动」仍然保留（赢盘率层面独立于方向置信度）

v3.2.5 平局对冲阈值：平局概率 >= 28-30% 才触发防平/双选胜平。

注：本文件为 v3.2.6 打包时依据 SKILL.md 接口规范重建，代码非原始实现。

2026-09-08 版本标注修订：此前仅写"v3.2.6"，与调用方 prompt 标称的 v3.2.9 错配；
    现如实标注本体 v3.2.6 / 规则口径 v3.2.9，调用方不得假设脚本已内含版本修正。
"""

import argparse
import sys

# 每层评分 → 概率增量（百分点）
LEVEL_INCREMENT = {0: 0.0, 1: 2.5, 2: 5.0, 3: 7.5}
TOTAL_CAP = 15.0          # 总增量上限（pp）

# v3.2.5 阈值
DRAW_HEDGE_THRESHOLD = 0.28     # 平局对冲阈值 28%（区间 28-30% 取下限）
HIGH_CONFIDENCE = 0.60          # 高置信方向阈值（Tier 降仓解耦）


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def classify_tier(upset_value: float):
    """upset_value = P(弱队胜) + P(平局)"""
    if upset_value >= 0.45:
        return "Tier 1", 1
    elif upset_value >= 0.30:
        return "Tier 2", 2
    elif upset_value >= 0.15:
        return "Tier 3", 3
    return "无（低爆冷）", 0


def apply_upset(base_home: float, base_draw: float, base_away: float,
                l1: int, l2: int, l3: int, fav_override=None):
    """
    返回 (修正后三元, 拆解字典)
    热门方 = 主胜/客胜中较高者（fav_override 非空时以指定方为准）；弱队 = 另一方。
    增量从热门方转移到 平局 + 弱队胜，按基准占比分配。

    fav_override: None（自动）| "home"（热门方=主胜）| "away"（热门方=客胜）
    """
    incs = {"L1 风格克制": LEVEL_INCREMENT[l1],
            "L2 状态变量": LEVEL_INCREMENT[l2],
            "L3 赛制红利": LEVEL_INCREMENT[l3]}
    raw_total = sum(incs.values())
    total = min(raw_total, TOTAL_CAP)          # 上限截断
    capped = raw_total > TOTAL_CAP

    # 判定热门方 / 弱队：--fav 覆盖时以指定方为准，否则取概率较高者
    if fav_override == "home":
        fav_name, fav_p = "主胜", base_home
        dog_name, dog_p = "客胜", base_away
    elif fav_override == "away":
        fav_name, fav_p = "客胜", base_away
        dog_name, dog_p = "主胜", base_home
    elif base_home >= base_away:
        fav_name, fav_p = "主胜", base_home
        dog_name, dog_p = "客胜", base_away
    else:
        fav_name, fav_p = "客胜", base_away
        dog_name, dog_p = "主胜", base_home

    delta = total / 100.0

    # 保护：转移量不得超过热门方胜率本身（留 1% 地板）
    if delta > fav_p - 0.01:
        delta = max(0.0, fav_p - 0.01)

    pool = base_draw + dog_p
    if pool <= 0:
        # 极端退化：平局与弱队胜均为 0，全部增量塞给平局
        draw_add, dog_add = delta, 0.0
    else:
        draw_add = delta * (base_draw / pool)
        dog_add = delta * (dog_p / pool)

    new_home = base_home
    new_away = base_away
    if fav_name == "主胜":
        new_home = base_home - delta
        new_away = base_away + dog_add
    else:
        new_away = base_away - delta
        new_home = base_home + dog_add
    new_draw = base_draw + draw_add

    # 数值兜底
    trio = (max(0.0, new_home), max(0.0, new_draw), max(0.0, new_away))
    s = sum(trio)
    trio = tuple(v / s for v in trio) if s > 0 else (0.0, 0.0, 0.0)

    fav_after = trio[0] if fav_name == "主胜" else trio[2]
    dog_after = trio[2] if fav_name == "主胜" else trio[0]
    upset_value = dog_after + trio[1]
    tier_name, tier_num = classify_tier(upset_value)

    breakdown = {
        "incs": incs,
        "raw_total": raw_total,
        "total": total,
        "capped": capped,
        "delta": delta,
        "fav_override": fav_override,
        "fav_name": fav_name,
        "dog_name": dog_name,
        "fav_before": fav_p,
        "fav_after": fav_after,
        "dog_before": dog_p,
        "dog_after": dog_after,
        "draw_before": base_draw,
        "draw_after": trio[1],
        "upset_value": upset_value,
        "tier_name": tier_name,
        "tier_num": tier_num,
    }
    return trio, breakdown


def main():
    ap = argparse.ArgumentParser(
        description="三层爆冷修正 (本体 v3.2.6 / 规则口径 v3.2.9)")
    ap.add_argument("--base", required=True,
                    help='基准三元概率，格式 "主胜,平,客胜"，可用百分比或小数')
    ap.add_argument("--l1", type=int, default=0, choices=[0, 1, 2, 3],
                    help="L1 风格克制 0-3")
    ap.add_argument("--l2", type=int, default=0, choices=[0, 1, 2, 3],
                    help="L2 状态变量 0-3")
    ap.add_argument("--l3", type=int, default=0, choices=[0, 1, 2, 3],
                    help="L3 赛制红利 0-3")
    ap.add_argument("--fav", default=None, choices=["home", "away"],
                    help='手工指定热门方：home=主胜为热门 / away=客胜为热门。'
                         '默认自动取主胜/客胜中概率较高者')
    args = ap.parse_args()

    # 解析 base
    parts = [p.strip() for p in args.base.replace("，", ",").split(",")]
    if len(parts) != 3:
        print('错误: --base 格式应为 "主胜,平,客胜"', file=sys.stderr)
        sys.exit(1)
    try:
        vals = [float(p.rstrip("%")) for p in parts]
    except ValueError:
        print("错误: --base 内含非数值", file=sys.stderr)
        sys.exit(1)
    # 若总和接近 100 则按百分比处理
    if abs(sum(vals) - 100.0) < 1.0:
        vals = [v / 100.0 for v in vals]
    s = sum(vals)
    if abs(s - 1.0) > 0.02:
        print(f"警告: 基准概率合计 {s:.4f}，未按 1.0 归一，已自动归一化", file=sys.stderr)
        vals = [v / s for v in vals]

    trio, b = apply_upset(vals[0], vals[1], vals[2], args.l1, args.l2, args.l3,
                          fav_override=args.fav)

    print(f"\n{'=' * 62}")
    print(" 三层爆冷修正 · 本体 v3.2.6 / 规则口径 v3.2.9")
    print(f"{'=' * 62}")
    print(f"\n【输入基准】")
    print(f"   主胜 {pct(vals[0]):>7}   平局 {pct(vals[1]):>7}   客胜 {pct(vals[2]):>7}")

    # 热门方来源（自动 / --fav 手工指定）+ 指定方概率偏低时的告警
    auto_fav = "主胜" if vals[0] >= vals[2] else "客胜"
    if b["fav_override"]:
        if b["fav_name"] != auto_fav:
            gap = abs(vals[0] - vals[2]) * 100
            print(f"   热门方指定: 手工 --fav {b['fav_override']} → 热门方 = {b['fav_name']}"
                  f"  ⚠️ 注意：自动判定本应为「{auto_fav}」，指定方概率低 {gap:.1f}pp，仍按指定执行")
        else:
            print(f"   热门方指定: 手工 --fav {b['fav_override']} → 热门方 = {b['fav_name']}（与自动判定一致）")
    else:
        print(f"   热门方指定: 自动判定 → {b['fav_name']}")

    print(f"\n【三层评分拆解】")
    for name, inc in b["incs"].items():
        bar = "▓" * int(inc / 2.5)
        print(f"   {name}:  +{inc:>4.1f}pp  {bar}")
    cap_note = f"  （原始 {b['raw_total']:.1f}pp，已截断至上限）" if b["capped"] else ""
    print(f"   {'合计增量':<12}:  +{b['total']:>4.1f}pp{cap_note}")

    print(f"\n【修正后概率】（增量自「{b['fav_name']}」转移给 平局 + {b['dog_name']}，概率守恒）")
    print(f"   主胜 {pct(trio[0]):>7}   平局 {pct(trio[1]):>7}   客胜 {pct(trio[2]):>7}   合计 {pct(sum(trio))}")
    print(f"\n   热门方 {b['fav_name']}: {pct(b['fav_before'])} → {pct(b['fav_after'])}"
          f"  ({(b['fav_after']-b['fav_before'])*100:+.1f}pp)")
    print(f"   弱队方 {b['dog_name']}: {pct(b['dog_before'])} → {pct(b['dog_after'])}"
          f"  ({(b['dog_after']-b['dog_before'])*100:+.1f}pp)")
    print(f"   平局:     {pct(b['draw_before'])} → {pct(b['draw_after'])}"
          f"  ({(b['draw_after']-b['draw_before'])*100:+.1f}pp)")

    print(f"\n【爆冷等级】")
    print(f"   爆冷值 = P({b['dog_name']}) + P(平局) = {pct(b['upset_value'])}")
    print(f"   等级   = {b['tier_name']}")

    print(f"\n【v3.2.5 联动判定】")
    # 注意：Tier 编号越小等级越高（Tier1 = 爆冷值 ≥45% 为最高）。
    # SKILL.md「爆冷等级 ≥ Tier 2」= Tier1 或 Tier2 → tier_num <= 2 且 > 0。
    if 0 < b["tier_num"] <= 2:
        print(f"   ⛔ 让球深盘联动生效：爆冷 {b['tier_name']}（≥ Tier2）"
              f" → 强制触发「让球深盘陷阱」，不投让球深盘方向")
    else:
        print(f"   ✓ 让球深盘联动未触发（{b['tier_name']}，低于 Tier2）")
    if b["fav_after"] >= HIGH_CONFIDENCE:
        print(f"   ✓ 热门方 p={pct(b['fav_after'])} ≥ 60% → 高置信方向，"
              f"不因 Tier 自动降仓/防平，仅标注风险")
    else:
        print(f"   ⚠️ 热门方 p={pct(b['fav_after'])} < 60% → 非高置信，按常规风险口径处理")
    if b["draw_after"] >= DRAW_HEDGE_THRESHOLD:
        print(f"   ⚠️ 平局 {pct(b['draw_after'])} ≥ 28% → 触发平局对冲（防平/双选胜平）")
    else:
        print(f"   ✓ 平局 {pct(b['draw_after'])} < 28% → 不触发平局对冲")

    print(f"\n[upset_adjusted] {trio[0]:.6f},{trio[1]:.6f},{trio[2]:.6f}")
    print()


if __name__ == "__main__":
    main()

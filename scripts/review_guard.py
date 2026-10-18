# review_guard.py — #6600221 复盘硬校验器（r17 内嵌版，零依赖）
# 用法: python3 review_guard.py /tmp/review_映射块.txt /tmp/review_对账块.txt
# 退出码: 0=PASS（打印凭证行） 1=FAIL（逐条点名）
import sys, re, hashlib, collections

errs = []
mp_path, tk_path = sys.argv[1], sys.argv[2]

# ---------- ① 译名映射块 ----------
try:
    mp = [l.strip() for l in open(mp_path, encoding="utf-8") if l.strip()]
except Exception as e:
    print("FAIL 读映射块失败:", e); sys.exit(1)
zh_seen, en_seen = {}, {}
for n, l in enumerate(mp, 1):
    if l.count("=") != 1:
        errs.append(f"映射行{n}「{l[:30]}」缺或多个 ="); continue
    zh, en = [x.strip() for x in l.split("=")]
    if not zh or not en:
        errs.append(f"映射行{n}「{l[:30]}」中/英文名为空")
    if zh in zh_seen:
        errs.append(f"映射行{n} 中文名重复「{zh}」(首次见行{zh_seen[zh]})")
    else:
        zh_seen[zh] = n
    key = en.casefold()
    if key in en_seen:
        # 核心: 两支不同球队映射到同一英文名 → FAIL（20261011 福图纳/特温特事故）
        errs.append(f"映射行{n} 英文名重复「{en}」← 行{en_seen[key]} 已映射同一英文名（不同主队不得共用英文名）")
    else:
        en_seen[key] = n

# ---------- ② 对账块 ----------
try:
    tk = [l.strip() for l in open(tk_path, encoding="utf-8") if l.strip()]
except Exception as e:
    print("FAIL 读对账块失败:", e); sys.exit(1)
if not tk or not re.match(r"^阈值=\d+$", tk[0]):
    errs.append("对账块首行必须是 阈值=<数值>（如 阈值=50）")
    thr = 50
else:
    thr = int(tk[0].split("=")[1])
rows = tk[1:]
HIT = {"命中", "未中(平)", "未中(错边)"}
NA = {"N/A", "待确认"}
seen_id = {}
hi_tot = hi_hit = lo_tot = lo_hit = 0
for n, l in enumerate(rows, 1):
    c = l.split("|")
    if len(c) != 5:
        errs.append(f"对账行{n} 列数{len(c)}≠5"); continue
    rid, pred, p, sc, hit = c
    m = re.match(r"^周[一二三四五六日]\d{3}$", rid)
    if not m:
        errs.append(f"对账行{n} 编号「{rid}」格式违规")
    if rid in seen_id:
        errs.append(f"对账行{n} 编号重复「{rid}」(首次见行{seen_id[rid]})")
    else:
        seen_id[rid] = n
    if pred not in {"主胜", "客胜", "—"}:
        errs.append(f"对账行{n} 预测「{pred}」∉主胜/客胜/—")
    if not re.match(r"^(\d+(\.\d+)?%|—)$", p):
        errs.append(f"对账行{n} p「{p}」格式违规")
    if not re.match(r"^(\d+-\d+|待确认|存疑|—)$", sc):
        errs.append(f"对账行{n} 赛果「{sc}」格式违规(主比分或 待确认/存疑/—)")
    if hit not in HIT | NA | {"存疑"}:
        errs.append(f"对账行{n} 命中「{hit}」∉枚举")
    # 交叉复算: 赛果 ↔ 命中 ↔ 预测
    if re.match(r"^\d+-\d+$", sc):
        if pred == "—":
            if hit != "N/A":
                errs.append(f"对账行{n} 预测=— 但命中={hit}（应为 N/A）")
        else:
            a, b = map(int, sc.split("-"))
            if a == b:
                exp = "未中(平)"
            elif (pred == "主胜") == (a > b):
                exp = "命中"
            else:
                exp = "未中(错边)"
            if hit != exp:
                errs.append(f"对账行{n} 复算矛盾: {pred} 赛果{sc} 应为「{exp}」实为「{hit}」")
    elif sc == "存疑":
        if hit != "存疑":
            errs.append(f"对账行{n} 赛果=存疑 但命中={hit}")
    else:  # 待确认 / —
        if hit not in NA:
            errs.append(f"对账行{n} 赛果={sc} 但命中={hit}（应为 待确认/N/A）")
    # 分层统计机械复算（p 有效且可核对时计数）
    if hit in HIT and p != "—":
        pv = float(p[:-1])
        if pv >= thr:
            hi_tot += 1; hi_hit += (hit == "命中")
        else:
            lo_tot += 1; lo_hit += (hit == "命中")

if errs:
    print(f"FAIL {len(errs)} 项:")
    for e in errs[:60]:
        print(" -", e)
    sys.exit(1)

data = "\n".join(tk).encode()
digest = hashlib.md5(data).hexdigest()[:16]
print(f"PASS 对账={len(rows)} 映射={len(mp)} 阈值={thr} 高p={hi_hit}/{hi_tot} 低p={lo_hit}/{lo_tot} md5={digest}")

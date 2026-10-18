# summary_guard.py — 摘要硬校验器（v3.6.0-r20 内嵌版 · 严禁修改，原样落盘后 python3 summary_guard.py 运行）
import re, sys, hashlib
txt = open("summary_block.txt", encoding="utf-8").read()
err = []
if txt.count("=====预测摘要开始=====") != 1 or txt.count("=====预测摘要结束=====") != 1:
    err.append("起止标记不成对")
lines = [l for l in txt.split("\n") if l.strip() and "=====" not in l]
HDR = "日期|编号|对阵|方向|p|p推导|λ主|λ客|情报|单关|档位|Tier|动作|HAD|HHAD|updateTime|让球预判|单关核实|数据血缘|开球时间"
if not lines or lines[0] != HDR:
    err.append("表头与20列定义不符")
ACT = {"稳单Top3", "单关Top3", "未达标", "观望", "不投"}
RX = {0: r"^\d{8}$", 3: r"^(主胜|平|客胜|—)$", 4: r"^(\d+\.\d{2}%|—)$",
      5: r"^(泊松\d+\.\d{2};[^;]*;→\d+\.\d{2}%|无HAD[^|]*)$", 6: r"^(\d+\.\d{3}|—)$", 7: r"^(\d+\.\d{3}|—)$",
      8: r"^(H|M|L|—)$", 9: r"^(仅串|可单关)$", 10: r"^(A|B|C|—)$", 11: r"^\d+$",
      13: r"^(—|\d+(\.\d+)?/\d+(\.\d+)?/\d+(\.\d+)?)$",
      14: r"^(—|\([+-]\d+\)\d+(\.\d+)?/\d+(\.\d+)?/\d+(\.\d+)?)$",
      15: r"^(\d{2}-\d{2} \d{2}:\d{2}|—)$", 19: r"^\d{2}-\d{2} \d{2}:\d{2}$",
      17: r"^一致$", 18: r"^(λ=市场反解v1\.11|λ=不可反解)"}
for n, l in enumerate(lines[1:], 1):
    c = l.split("|")
    if l.count("|") != 19 or len(c) != 20:
        err.append(f"行{n} 列数{len(c)}≠20"); continue
    for i, rx in RX.items():
        if not re.match(rx, c[i]): err.append(f"行{n} 列{i}「{c[i][:28]}」形态违规")
    if c[12] not in ACT: err.append(f"行{n} 动作「{c[12]}」∉五值域")
    if not c[5].endswith("→" + c[4]): err.append(f"行{n} p推导终值≠p")
md5 = hashlib.md5(txt.encode()).hexdigest()
if err:
    print("FAIL", len(err)); print("\n".join(err[:40])); sys.exit(1)
print(f"PASS 行={len(lines)-1} md5={md5}")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lambda-source.py —— λ 计算器（v1.11 · 2026-09-21）

用途（v1.11 重定位 · 用户决策方案A）：为竞彩场次提供**独立于赔率的第二意见**——
  ① 主报告泊松输入一律用**市场反解 λ**（竞彩 had 胜平负赔率扣水反解）；
  ② 真实 λ（历史进球/xG）**不再进模型**，仅用于【分歧探测】：与市场隐含 λ
     对比 TV 距离，输出 Top3 分歧场次 + 方向解读，供人工复核。
  回测依据（三赛季 9748 场）：真实 λ 最优口径仍逊市场 +0.007~0.025 LogLoss
  （差距源于信息量上限：伤病/战意/阵容市场已定价），替代进模型只会损失精度；
  唯一不可替代的价值是独立性——分歧大的场次才值得停下来看。

v1.11 新增（2026-09-21 · 方案A重定位 + ÷2口径修复）：
  - 🔴 **÷2 口径修复**：λ主 = 主队场均进 × 客队场均失 / (联赛每队场均进球)。
    原实现误用「每场总进球」作分母 → λ 系统性腰斩（三赛季回测：λ主均值 0.68
    vs 实际主队场均进球 1.54；线上函数实测阿森纳 v 切尔西 λ=(0.71,0.76)）。
    修复后量级归位（1.42/1.53）。修复依据：无偏性检验（预测均值应≈实际均值）。
  - 🔴 **用途重定位（方案A）**：真实 λ 不再作为预测输入，降级为【分歧探测器】
    的第二意见；主报告泊松输入一律市场反解 λ。
  - 新增 market_lambda/implied_probs/poisson_1x2/市场反解链路 + [分歧探测] 段：
    TV 距离 = 0.5×Σ|P真实-P市场|，Top3 + 方向解读（阈值 0.08/0.05 为经验
    初值，待头几轮分歧分布校准）。
  - MIN_SAMPLE 10→15（回测平衡点：主客口径样本 15 场时 TV 收窄至 +0.007
    且保住约 19% 场次的第二意见；25~30 场后差距不再收窄）。
  - tau 约束：市场反解的总进球 τ 用该联赛实际场均（无源场次退 2.6 先验）。

v1.10 新增（2026-09-20 · 韩职桥接修复 —— 实测 004 被判「联赛无源」而 XG_BRIDGE["KOR"] 空挂）：
  - **根因**：KOR 因 KOR=NOR 副本事故移出 EXTRA_SRC（黑名单正确），但 lgmap 仅由
    MAIN+EXTRA 构造 → 「韩国职业联赛」查不到 → 直接判「联赛无源」，FotMob 桥永远无机会生效。
  - `BRIDGE_ONLY`：fetch_all 以空行条目入 lgmap（不下载 football-data）。
  - 主流程 rows=[] 保护：桥接-only 联赛 xG 桥失败/样本不足 → 回退市场（缺口=桥接失败，
    gaps 新增 "bridge" 类），严禁进 team_stats（空行 IndexError）。
  - 实测：仁川联/大田市民 → FotMob 2026 赛季 28/29 场，λ=(1.302,1.439)；CN2EN 补富川。

v1.9 新增（2026-09-20 · 深加固 —— 探针实证任务侧境外连通性随时段波动）：
  - `_dl` **双域名轮换**：www.football-data.co.uk <-> football-data.co.uk 交替重试
    （302 目标域 = 同一数据两个入口）；重试 3->4 次、单次超时 30->20s（更快换手）。
  - **内容校验 `_csv_ok`**：长度阈值 + CSV 头行逗号数，防 0B/跳转页/WAF 页被误当
    成功写入缓存（v1.8 隐患：200 空体也写缓存 -> 污染后续缓存降级）；缓存兜底读出同样过校验。

v1.8 新增（2026-09-20 · 本地缓存降级 —— 任务沙箱境外源不可达缓解）：
  - `_dl` 成功拉取即写本地缓存（原子写 tmp+rename；目录候选见 `_cache_dir()`，
    独立于 `__file__`——内嵌兜底时脚本写在 /tmp，相对路径不持久）。
  - 重试全败且存在最近缓存 → 打 `[缓存降级]` 行并返回缓存内容（滞后 1-2 天，
    λ 用赛季累计统计影响极小）；无缓存才返回 None。命中缓存的文件仍走
    Div/Country 自证身份校验与跨源 MD5 去重，纪律不变。
  - 注：v1.7 已被 prompt 侧「源缺口 vs 样本不足」条目（2026-09-19）占用，脚本跳号。

v1.6 新增（中超接入 —— 附加源联赛全部具备 xG）：
  - xg-source.py 新增**后端 C PerformanceOdds**（performanceodds.com），覆盖 CHN 中超。
  - 🔴 **有 home/away 分组**（优于 FotMob）→ 直接用 split/blend，无需主场优势补丁。
  - 🔴 该源发布**每场均值**，xg-source 内部 ×played 还原为赛季总计（见其注释）。
  - 🔴 队名陷阱：该源用**旧称**（上海上港/河南建业/天津泰达…），
      而本脚本 CN2EN 按 football-data **现名**建 → 走 PO_ALIAS 别名桥接。
  - 恒等式三联验证通过：overall sum(xG)≈sum(xGA)、home sum(xG)≈away sum(xGA)。
  - 至此 **NOR/SWE/BRA/MEX/JPN/KOR/USA/ARG/CHN 九个附加源联赛全部有 xG**。

v1.5 新增（xG 源双后端 —— 日职/韩职/美职/阿甲接入）：
  - xg-source.py 新增**后端 B FotMob**（data.fotmob.com），覆盖 JPN/KOR/USA/ARG。
  - FotMob 只发布**赛季总计**（无 home/away 分组）→ 会抹平主场优势。
    脚本从 fixtures **逐场比分现算** `raw_ha = 主队场均进球/客队场均进球`，
    再取 `ha_eff = raw_ha ** 0.62`（指数收缩）施加到 λ（几何对称，总进球守恒）。
    α=0.62 由四联赛联合扫描得出（α=1.00→总偏差30.9 / α=0.62→8.80 / α=0.40→11.4）。
  - 平局校正**现场现算** `dc = 实际平局率 / 模型泊松平局率`，不写死常数。
  - **TLS 重试**：statz.ai 实测约 1/3 概率握手失败（curl rc=35），
    `fetch()` 与 `_fotmob_curl()` 均已加指数退避重试 3 次（1.5s/3s）。
  - **韩职特例**：xG 源已就位，但 football-data 的 KOR.csv 实为挪威 Eliteserien
    副本（MD5 相同）→ 仍列黑名单，待源恢复后译名即可自动生效。
  - **当时仍无源**：中超 CHN（statz sitemap 无；FotMob 仅有中甲且 shotmap 为空）。
    → **已于 v1.6 解决**（后端 C PerformanceOdds，见上）。

v1.3 新增（xG 源接入 —— 根本修复「泊松高估平局」）：
  - 当 football-data **只有实际进球口径**（附加源，无 xG）的联赛，
    先试 **xg-source.py** 取 xG/xGA，命中则用 xG 口径算 λ。
  - 实测收益（挪超 2026 本季 160 场）：
      实际进球口径 → 模型平均平局 35.4% → 偏差 +15.4pp ❌
      xG     口径 → 模型平均平局 22.4% → 偏差  +2.4pp ✅
    即：xG 口径**无需平局校正系数**，偏差自然收敛。这是根因修复。
  - 覆盖：v1.3 为 NOR/SWE/BRA/MEX；v1.5 扩至 8 个联赛；v1.6 扩至 9 个（含 CHN，见上）。
  - 三级兜底：xg-source 命中失败一律回退原口径，并逐场标 `[xG源缺失]`，禁用静默降级。

v1.2 新增（源缺口闭环）：
  - [源缺口] 清单：未命中场次逐场可见（联赛无源 / 队名未映射）
  - [疑似映射] 候选建议：自动探测候选队名，**仅供人工确认，严禁自动采用**
  - [源体检]：某联赛连续无源 → 疑源失效；某队反复缺映射 → 一次补上
  - 缺口清单落盘为 <out>-gaps.json
  - 数据源自证 + 跨源 MD5 去重（防副本污染，如 KOR=挪威 事故）

数据源（football-data.co.uk，免费 CSV，外部证实）：
  主源（含 xG 预期进球）：
    https://www.football-data.co.uk/mmz4281/2627/{CODE}.csv
    E0=英超 SP1=西甲 I1=意甲 D1=德甲 F1=法甲 N1=荷甲 P1=葡超
    B1=比甲 T1=土超 G1=希超 SC0=苏超
  附加源（无 xG，但含多赛季历史）：
    https://www.football-data.co.uk/new/{CODE}.csv
    JPN=日职 KOR=韩职 BRA=巴甲 SWE=瑞超 NOR=挪超 ARG=阿甲 CHN=中超 USA=美职 MEX=墨超
  第三方 xG 源（v1.6，仅用于「附加源联赛」，三后端）：
    后端 A statz.ai（经 xg-source.py）→ NOR SWE BRA MEX（有主客分组）
    后端 B FotMob （经 xg-source.py）→ JPN KOR USA ARG（仅赛季总计 + 逐场比分补主场优势）
    后端 C PerformanceOdds（经 xg-source.py）→ CHN 中超（有主客分组，场均口径）

λ 计算（攻防公式，Dixon-Coles 标准做法）：
  λ主 = (主队场均进球) × (客队场均失球) / (联赛场均进球)
  λ客 = (客队场均进球) × (主队场均失球) / (联赛场均进球)
  主源优先用 xG/xA（剥离运气）；附加源只能用实际进球；xG 源命中时优先 xG。

🔴 样本量门槛（v1.11 起 15 场，2026-09-19 由 10 调升·回测定标）：
  某场双方**任一方**样本 < 15 场 → 该场无第二意见，不参与分歧探测（主报告
  概率不受影响——一律用市场反解 λ）。

用法：
  python3 lambda-source.py --jc /tmp/jc_raw.json [--base lambda-base.json] [--out result.json]
  python3 lambda-source.py --jc ... --no-xg     # 禁用第三方 xG 源（排障用）

输出：
  每场一行：编号 | 对阵 | λ主 | λ客 | source=real/market | 样本 | 口径=xG/goal
"""

import argparse
import csv
import io
import json
import math
import os
import time
import unicodedata
import urllib.request
from collections import defaultdict

# 🔴 v3.5.0-r11 修复：r7 双自由度 market_lambda 依赖 numpy（np.arange 多起点粗扫），
# 但内嵌块此前漏掉此import。因 10-06 全批 had={} 导致调用段被整体跳过，
# 该缺陷被掩盖 —— r7 实跑从未真正执行过。补上。
try:
    import numpy as np
except ImportError:                      # 无 numpy 时降级为纯 Python 等价实现
    _np = None

    class _NPShim:
        @staticmethod
        def arange(a, b, s):
            out, x = [], a
            while x < b + 1e-12:
                out.append(round(x, 10))
                x += s
            return out

    np = _NPShim()

# ------------------------------------------------------------------ 数据源定义

MAIN_SRC = {  # 含 xG
    'E0': '英格兰超级联赛', 'E1': '英格兰冠军联赛', 'SP1': '西班牙甲级联赛',
    'I1': '意大利甲级联赛',
    'D1': '德国甲级联赛', 'F1': '法国甲级联赛', 'N1': '荷兰甲级联赛',
    'P1': '葡萄牙超级联赛', 'B1': '比利时甲级联赛', 'T1': '土耳其超级联赛',
    'G1': '希腊超级联赛', 'SC0': '苏格兰超级联赛',
}
EXTRA_SRC = {  # 无 xG
    'JPN': '日本职业联赛', 'BRA': '巴西甲级联赛',
    'SWE': '瑞典超级联赛', 'NOR': '挪威超级联赛', 'ARG': '阿根廷甲级联赛',
    'CHN': '中国超级联赛', 'USA': '美国职业大联盟', 'MEX': '墨西哥超级联赛',
    # 2026-09-19 扩充（实测有效）
    'AUT': '奥地利甲级联赛', 'DNK': '丹麦超级联赛', 'FIN': '芬兰超级联赛',
    'IRL': '爱尔兰超级联赛', 'POL': '波兰甲级联赛', 'ROU': '罗马尼亚甲级联赛',
    'RUS': '俄罗斯超级联赛', 'SWZ': '瑞士超级联赛',
}

# 🔴 失效源黑名单（2026-09-19 实测）：文件内容与标称联赛不符，严禁启用。
#   KOR.csv 实测为挪威 Eliteserien 的副本（与 NOR.csv MD5 完全相同 a0956327...），
#   若开启会「静默用挪威数据算韩职 λ」——比无源更危险，故永久禁用。
BLACKLIST = {'KOR': '内容实为挪威 Eliteserien（与 NOR.csv MD5 相同），服务端失效'}
MAIN_URL = 'https://www.football-data.co.uk/mmz4281/2627/%s.csv'
EXTRA_URL = 'https://www.football-data.co.uk/new/%s.csv'
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0'}

MIN_SAMPLE = 15   # 🔴 v1.11：真实λ参与分歧探测的门槛（2026-09-21 回测定标，原 10）

# ------------------------------------------------------------------ 第三方 xG 源桥接（v1.6）
# 用途：为「football-data 附加源（无 xG）」的联赛补 xG 口径。
# 映射：football-data 代码 -> xg-source.py 的联赛键
#
# 三个后端（由 xg-source.load_any 自动分派）：
#   后端 A statz.ai        —— 有 home/away 分组，支持 split/blend
#   后端 B FotMob          —— 只有赛季总计，但脚本已用「逐场比分现算的主场优势
#                             +平局率」补齐主客差异（详见 xg-source 注释）
#   后端 C PerformanceOdds —— 有 home/away 分组，发布场均口径（脚本内部还原为总计）
XG_BRIDGE = {
    # ── 后端 A：statz.ai ──
    'NOR': 'eliteserien',            # 挪威超级联赛（实测 20 场/队）
    'SWE': 'allsvenskan',            # 瑞典超级联赛（实测 21 场/队，168/168 有 xG）
    'BRA': 'campeonato-brasileiro',  # 巴西甲级联赛（实测 27 场/队）
    'MEX': 'liga-mx',                # 墨西哥超级联赛（实测 8 场/队）
    # ── 后端 B：FotMob（v1.5 新增，2026-09-19 攻克）──
    'JPN': 'j1',                     # 日本 J1 联赛（20 队，赛季总计）
    'KOR': 'k1',                     # 韩国 K 联赛 1（12 队）
    'USA': 'mls',                    # 美国职业足球大联盟（30 队）
    'ARG': 'arg',                    # 阿根廷甲级联赛（30 队）
    # ── 后端 C：PerformanceOdds（v1.6 新增，2026-09-19 攻克）──
    'CHN': 'chn',                    # 中国足球超级联赛（16 队，26 场/队，有主客分组）
    # ── 全部附加源联赛均已接入 xG ──
}

# 🔴 v1.10：桥接-only 联赛——football-data 附加源失效（KOR.csv 实为 NOR 副本，
#    2026-09-19 黑名单），数据唯一来源是 XG_BRIDGE（FotMob k1）。此前 KOR 不在
#    MAIN/EXTRA → lgmap 查不到 → 直接判「联赛无源」，XG_BRIDGE["KOR"] 永远空挂。
#    v1.10 以**空行条目**进 lgmap，主流程只走 xG 桥（rows=[] 保护见主流程）。
BRIDGE_ONLY = {"KOR": "韩国职业联赛"}
_XG_MOD = None      # 懒加载的 xg-source 模块
_XG_ERR = None      # 加载失败原因（首错锁定，避免重复刷屏）


def _load_xg():
    """加载 xg-source.py。查找顺序（与主脚本三级查找一致）：
       ① 同目录  ② skill scripts 目录  ③ /tmp
    失败返回 None，并把原因记入 _XG_ERR（**不抛异常**，由调用方降级）。
    """
    global _XG_MOD, _XG_ERR
    if _XG_MOD is not None or _XG_ERR:
        return _XG_MOD
    import importlib.util
    cands = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'xg-source.py'),
        '/root/.codebuddy/skills/football-prediction/scripts/xg-source.py',
        '/tmp/xg-source.py',
    ]
    for p in cands:
        if not os.path.exists(p):
            continue
        try:
            spec = importlib.util.spec_from_file_location('_xg_source', p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _XG_MOD = mod
            return _XG_MOD
        except Exception as e:
            _XG_ERR = '加载 %s 失败: %s' % (p, e)
            return None
    _XG_ERR = '未找到 xg-source.py（已试: %s）' % ' | '.join(cands)
    return None


# 缓存：每个联赛只抓一次 xG 表
_XG_DATA = {}


def xg_lambda(code, home_cn, away_cn, mode='auto'):
    """用 xG 源算一场的 λ。
    返回 (lam_h, lam_a, info) 或 (None, None, 原因字符串)。
    绝不抛异常——失败一律降级，由调用方走原口径。

    mode: 'blend'（默认）/ 'auto' / 'split' / 'overall'
      · statz 后端（有主客分组）→ 四种都可用
      · FotMob 后端（只有赛季总计）→ 四种等价（脚本内部已用逐场比分
        现算的主场优势 + 平局率补齐主客差异）
      ⚠️ 默认已从 'auto' 改为 'blend'：见 xg-source 的 λ 口径三分法回测
         （blend 总偏差 2.6pp，split 20.3pp，overall 18.2pp）

    ⚠️ 关键：xG 源内是**英文队名**，而竞彩给的是中文名。
       故先用 CN2EN 把中文名译成英文，再交给 xG 源。
       CN2EN 未命中的队 → 直接判「队名未映射」，禁止用近似名硬算。
    """
    # 🔴 2026-09-19 修正：XG_BRIDGE 的 key 统一为大写联赛代码，
    #    而调用方传入的 code 大小写不确定（竞彩接口 / 上游可能给小写）。
    #    此前未归一化 → 传 'chn' 时查表落空，静默返回「无 xG 桥接」，
    #    导致中超等联赛在端到端路径下**取不到 xG 却误判为「本就无桥接」**。
    key = XG_BRIDGE.get((code or '').strip().upper())
    if not key:
        return None, None, '无 xG 桥接'
    mod = _load_xg()
    if mod is None:
        return None, None, _XG_ERR or 'xg-source 不可用'
    # 中文名 → 英文名（复用本脚本的 CN2EN 映射）
    he = find_en(home_cn)
    ae = find_en(away_cn)
    if not he or not ae:
        miss = [t for t, e in ((home_cn, he), (away_cn, ae)) if not e]
        return None, None, 'xG源队名未映射: %s' % '/'.join(miss)
    if key not in _XG_DATA:
        try:
            # load_any：自动分派 statz / FotMob 后端
            _XG_DATA[key] = mod.load_any(key)
        except Exception as e:
            _XG_DATA[key] = e
    d = _XG_DATA[key]
    if isinstance(d, Exception):
        return None, None, 'xG 源抓取/解析失败: %s' % d
    try:
        lh, la, info = mod.lambdas(d, he, ae, mode=mode)
        return lh, la, info
    except Exception as e:
        return None, None, str(e)



# ------------- 本地缓存降级（v1.8 新增 · v1.9 深加固：双域名轮换 + 内容校验）
# 目的：源站不可达时（境外链路故障），用最近一次成功拉取的 CSV 降级计算。
#   λ 用赛季累计统计，缓存滞后 1-2 天对结果影响极小；命中缓存的文件仍走
#   Div/Country 自证身份校验与跨源 MD5 去重，纪律不变。
# 缓存目录候选（依次试建，须独立于 __file__：内嵌兜底时脚本写在 /tmp，
#   __file__ 相对路径不持久）：skill cache → /workspace/.fd_cache → ./fd_cache
import hashlib

CACHE_HITS = []          # 本次运行命中缓存的文件标签（mmz4281/2627/E0.csv 等）
_CACHE_DIR = None
_CACHE_INIT = False


def _cache_dir():
    """解析并试建缓存目录，返回可用目录或 None（全败则禁用缓存，不报错刷屏）"""
    global _CACHE_DIR, _CACHE_INIT
    if not _CACHE_INIT:
        _CACHE_INIT = True
        for d in ('/root/.codebuddy/skills/football-prediction/cache',
                  '/workspace/.fd_cache', './fd_cache'):
            try:
                os.makedirs(d, exist_ok=True)
                p = os.path.join(d, '.wtest')
                with open(p, 'w') as f:
                    f.write('1')
                os.remove(p)
                _CACHE_DIR = d
                break
            except Exception:
                continue
    return _CACHE_DIR


def _cache_path(url):
    """URL -> 缓存文件路径。文件名 = md5(url) 前 10 位 + 原文件名
    （防主源 mmz4281/2627/E0.csv 与附加源 new/E0.csv 同名撞车）"""
    d = _cache_dir()
    if not d:
        return None
    base = url.rstrip('/').split('/')[-1] or 'index'
    return os.path.join(d, '%s-%s' % (hashlib.md5(url.encode('utf-8')).hexdigest()[:10], base))


def _alt_url(url):
    """🔴 v1.9 双域名轮换：www <-> 裸域名（302 目标域，同一数据两个入口）。
    实测（2026-09-20 主会话侧）：www 域名 302 -> 裸域名后 200；两域连通性
    在任务侧随时段波动，交替重试显著提高穿透率。非本站 URL 原样返回。"""
    if '://www.football-data.co.uk/' in url:
        return url.replace('://www.football-data.co.uk/', '://football-data.co.uk/', 1)
    if '://football-data.co.uk/' in url:
        return url.replace('://football-data.co.uk/', '://www.football-data.co.uk/', 1)
    return url


def _csv_ok(t, url):
    """🔴 v1.9 内容校验：防 0B/跳转中间页/WAF 拦截页被误当成功数据。
    主源 mmz4281 赛季 CSV 赛季初即 >13KB 且头列 Div；附加源 new/ 体积小，放宽阈值。
    判据：长度 >= 阈值 且 前 400 字符内逗号 >= 5（CSV 头行必然满足，页面/提示不满足）。"""
    if not t:
        return False
    min_len = 5000 if '/mmz4281/' in url else 300
    if len(t) < min_len:
        return False
    return t[:400].count(',') >= 5


def _dl(url, retries=4):
    """下载主源 CSV；失败**双域名轮换重试**（指数退避），全败走缓存降级或 None。

    🔴 2026-09-19 修正：原实现异常时静默返回 None，且 `fetch_all` 里
       `if not t: continue` 会**静默丢弃整个联赛** → 该联赛场次被误标
       `[源缺口] 联赛无源`（实为「拉取失败」，属**误报**）。
       修复：① 加重试；② 失败必打 `[数据源告警]` 留痕，严禁静默降级。

    🔴 2026-09-20 v1.8 新增**本地缓存降级**：成功拉取即写缓存（原子写）；
       重试全败且存在最近缓存 → 打 `[缓存降级]` 行并返回缓存内容；
       无缓存才返回 None。缓存目录见 _cache_dir()。

    🔴 2026-09-20 v1.9 深加固（探针实证：任务侧境外连通性随时段波动）：
       ① **双域名轮换** —— www.football-data.co.uk 与裸域名 football-data.co.uk
         交替重试（302 目标域，同一数据两个入口）；
       ② 重试 3->4 次、退避 0.8/1.6/3.2s、单次超时 30->20s；
       ③ **内容校验 _csv_ok** —— 长度 + CSV 头行逗号数，FAIL 视同失败且**不写缓存**
         （v1.8 隐患：200 空体也会写缓存 → 污染后续缓存降级）；
       ④ 缓存兜底读出同样过校验，防历史坏缓存充当降级数据。
    """
    last = None
    tried = []
    for i in range(retries):
        u = url if i % 2 == 0 else _alt_url(url)      # 🔴 v1.9：偶数次原域名，奇数次备用域名
        if i:
            time.sleep((0.8, 1.6, 3.2)[min(i - 1, 2)])
        try:
            r = urllib.request.Request(u, headers=UA)
            t = urllib.request.urlopen(r, timeout=20).read().decode('utf-8-sig', errors='ignore')
            if not _csv_ok(t, url):                   # 🔴 v1.9：内容校验 FAIL 视同失败（不写缓存）
                host = u.split('//', 1)[-1].split('/', 1)[0]
                tried.append('%s=内容校验未过(len=%d)' % (host, len(t)))
                last = RuntimeError('content check failed: len=%d' % len(t))
                continue
            cp = _cache_path(url)                     # 🔴 成功即入缓存（原子写，失败不干扰主流程）
            if cp:
                try:
                    tmp = cp + '.tmp'
                    with open(tmp, 'w', encoding='utf-8', newline='') as f:
                        f.write(t)
                    os.replace(tmp, cp)
                except Exception:
                    pass
            return t
        except Exception as e:
            host = u.split('//', 1)[-1].split('/', 1)[0]
            tried.append('%s=%s' % (host, str(e)[:60]))
            last = e
    print('[数据源告警] 拉取失败（已重试 %d 次：%s）：%s' % (retries, ' | '.join(tried), url))
    cp = _cache_path(url)                             # 🔴 缓存降级：重试全败时用最近一次成功缓存
    if cp and os.path.exists(cp):
        try:
            with open(cp, 'r', encoding='utf-8', newline='') as f:
                t = f.read()
            if t and _csv_ok(t, url):                 # 🔴 v1.9：缓存兜底同样过内容校验
                age = max(0, int(time.time() - os.path.getmtime(cp)) // 86400)
                lbl = url.split('//', 1)[-1].split('/', 1)[-1]
                CACHE_HITS.append(lbl)
                print('[缓存降级] 源不可达，使用最近缓存（%d 天前拉取）：%s' % (age, lbl))
                return t
        except Exception:
            pass
    return None


def _norm(s):
    """归一化队名：去重音、小写、去常见后缀"""
    if not s:
        return ''
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = s.lower()
    for junk in [' fc', ' cf', ' afc', ' sc', ' ac', ' sk', ' bk', ' if', ' ff',
                 ' united', ' city', ' town', ' club', ' de ', ' the ']:
        s = s.replace(junk, ' ')
    return ''.join(ch for ch in s if ch.isalnum())


# ------------------------------------------------------------------ 抓取

def fetch_all():
    """返回 {联赛代码: [rows]}，主源与附加源统一为「当前赛季」行。

    🔴 完整性校验（2026-09-19）：抓到的文件必须**自证身份**——
      附加源须含 Country/League 列且与标称联赛一致；否则丢弃该源。
      目的：杜绝「文件内容与标称联赛不符」导致的静默错算（如 KOR=挪威 事故）。
    """
    data = {}
    _dl_fail = []                      # 🔴 拉取失败的联赛代码（留痕，供误报判定）
    for code in MAIN_SRC:
        t = _dl(MAIN_URL % code)
        if not t:
            _dl_fail.append(code)
            continue
        rows = [r for r in csv.DictReader(io.StringIO(t)) if r.get('FTHG') not in (None, '')]
        if not rows:
            continue
        # 🔴 自证身份：Div 列必须与请求代码一致（防服务端返回错联赛）
        divs = {(r.get('Div') or '').strip() for r in rows}
        if divs and code not in divs:
            print('[数据源告警] %s 返回 Div=%s，与请求不符，已丢弃' % (code, ','.join(sorted(divs))))
            continue
        data[code] = {'rows': rows, 'xg': True, 'league': MAIN_SRC[code],
                      'code': code,
                      'src_country': 'Div=' + (','.join(sorted(divs)) or code),
                      'src_league': MAIN_SRC[code], 'md5': _md5(t)}
    for code in EXTRA_SRC:
        if code in BLACKLIST:
            continue
        t = _dl(EXTRA_URL % code)
        if not t:
            _dl_fail.append(code)
            continue
        allrows = list(csv.DictReader(io.StringIO(t)))
        if not allrows:
            continue
        # 自证身份：Country / League 列须存在
        ctry = (allrows[0].get('Country') or '').strip()
        lg = (allrows[0].get('League') or '').strip()
        if not ctry or not lg:
            continue
        seasons = sorted(set(r.get('Season', '') for r in allrows))
        if not seasons:
            continue
        latest = seasons[-1]
        rows = [r for r in allrows if r.get('Season') == latest and r.get('HG') not in (None, '')]
        if rows:
            data[code] = {'rows': rows, 'xg': False, 'league': EXTRA_SRC[code],
                          'season': latest, 'code': code,
                          'src_country': ctry, 'src_league': lg,
                          'md5': _md5(t)}
    # 🔴 v1.10：桥接-only 联赛入表（lgmap 命中用）。rows=[] 表示「本源无 CSV 行」，
    #    主流程遇之只走 xG 桥，桥失败即回退市场（严禁进 team_stats）。
    for _bcode, _blg in BRIDGE_ONLY.items():
        data[_bcode] = {'rows': [], 'xg': False, 'league': _blg, 'code': _bcode,
                        'src_country': 'bridge-only', 'src_league': _blg, 'md5': None}
    # 🔴 把「拉取失败」名单挂到模块级，供主流程区分
    #    「联赛无源（事实）」与「拉取失败（故障）」——后者若被报成前者即误报。
    global _DL_FAILED
    _DL_FAILED = _dl_fail
    if CACHE_HITS:   # 🔴 v1.8：缓存降级汇总（数据可能滞后 1-2 天，λ 口径不变）
        print('[缓存降级] 本次共 %d 个文件使用最近缓存：%s' % (len(CACHE_HITS), '，'.join(CACHE_HITS)))
    return data


def _md5(s):
    import hashlib
    return hashlib.md5(s.encode('utf-8', errors='ignore')).hexdigest()


# 🔴 本轮拉取主源失败的联赛代码（由 fetch_all 填充）。
#    用途：区分「联赛本就无源」与「有源但本次拉取失败」——后者必须报
#    `[源缺口] 拉取失败` 并告警，严禁伪装成「联赛无源」。
_DL_FAILED = []

# 🔴 联赛中文名 → 联赛代码（主源 + 附加源，排除黑名单）。
#    用途：当某场次的联赛名在 lgmap 中未命中时，判断「该联赛是否本应有源」——
#    若有源却未命中，只能是拉取失败（故障），而非「联赛无源」（事实）。
_CODE_BY_LEAGUE = {}
for _c, _n in list(MAIN_SRC.items()) + list(EXTRA_SRC.items()):
    _CODE_BY_LEAGUE.setdefault(_n, _c)


def _drop_duplicate_sources(data):
    """🔴 跨源去重（2026-09-19）：内容完全相同（MD5 一致）的两个源，
    必有一个是服务端失效的副本（如 KOR=NOR 事故）。
    规则：MD5 撞车 → **两个源全部丢弃**，宁可无源回退市场，也不用可能错误的数据。
    """
    byhash = {}
    for code, d in data.items():
        m = d.get('md5')
        if not m:
            continue
        byhash.setdefault(m, []).append(code)
    bad = set()
    for m, codes in byhash.items():
        if len(codes) > 1:
            bad.update(codes)
            print('[数据源告警] MD5 撞车，疑为副本，已全部丢弃：%s' % ', '.join(codes))
    for code in bad:
        data.pop(code, None)
    return data


# ------------------------------------------------------------------ 统计

def team_stats(rows, tname, use_xg):
    """返回 (场均进球, 场均失球, 场次)。主源用 xG，附加源用实际进球。"""
    gf = ga = n = 0
    key_h = 'Home' if 'Home' in rows[0] else 'HomeTeam'
    key_a = 'Away' if 'Away' in rows[0] else 'AwayTeam'
    key_hg = 'HG' if 'HG' in rows[0] else 'FTHG'
    key_ag = 'AG' if 'AG' in rows[0] else 'FTAG'
    tn = _norm(tname)
    for r in rows:
        h, a = r.get(key_h, ''), r.get(key_a, '')
        try:
            fh, fa = int(r[key_hg]), int(r[key_ag])
        except Exception:
            continue
        xh = xa = None
        if use_xg:
            try:
                xh, xa = float(r.get('HxG')), float(r.get('AxG'))
            except Exception:
                pass
        hn, an = _norm(h), _norm(a)
        if tn and (tn == hn):
            n += 1
            gf += xh if (use_xg and xh is not None) else fh
            ga += xa if (use_xg and xa is not None) else fa
        elif tn and (tn == an):
            n += 1
            gf += xa if (use_xg and xa is not None) else fa
            ga += xh if (use_xg and xh is not None) else fh
    return (gf / n, ga / n, n) if n else (None, None, 0)


def league_avg(rows, use_xg):
    key_hg = 'HG' if 'HG' in rows[0] else 'FTHG'
    key_ag = 'AG' if 'AG' in rows[0] else 'FTAG'
    tot = n = 0
    for r in rows:
        try:
            tot += int(r[key_hg]) + int(r[key_ag])
            n += 1
        except Exception:
            pass
    return tot / n if n else 1.35


# ------------------------------------------------------------------ 队名映射

# 竞彩中文名关键词 -> 数据源英文名（可扩展）
CN2EN = {
    # 英超
    '托特纳姆': 'Tottenham', '阿斯顿维拉': 'Aston Villa', '埃弗顿': 'Everton',
    '伊普斯维奇': 'Ipswich', '纽卡斯尔': 'Newcastle', '赫尔城': 'Hull',
    '诺丁汉': "Nott'm Forest", '考文垂': 'Coventry', '利兹联': 'Leeds',
    '水晶宫': 'Crystal Palace', '伯恩茅斯': 'Bournemouth', '利物浦': 'Liverpool',
    '曼彻斯特城': 'Man City', '曼城': 'Man City', '桑德兰': 'Sunderland',
    '富勒姆': 'Fulham', '曼彻斯特联': 'Man United', '曼联': 'Man United',
    '阿森纳': 'Arsenal', '布莱顿': 'Brighton', '布伦特福德': 'Brentford',
    '切尔西': 'Chelsea', '西汉姆': 'West Ham', '狼': 'Wolves',
    # 英冠（E1，2026-09-19 新增）
    '斯托克城': 'Stoke', '斯托克': 'Stoke', '谢菲尔德联': 'Sheffield United',
    '谢菲联': 'Sheffield United', '伍尔弗汉普顿': 'Wolves', '西布罗姆维奇': 'West Brom',
    '西布罗姆': 'West Brom', '伯明翰': 'Birmingham', '布莱克本': 'Blackburn',
    '博尔顿': 'Bolton', '布里斯托尔城': 'Bristol City', '伯恩利': 'Burnley',
    '加的夫': 'Cardiff', '查尔顿': 'Charlton', '德比': 'Derby', '林肯': 'Lincoln',
    '米德尔斯堡': 'Middlesbrough', '米尔沃尔': 'Millwall', '诺维奇': 'Norwich',
    '朴茨茅斯': 'Portsmouth', '普雷斯顿': 'Preston', '女王公园巡游者': 'QPR',
    '南安普顿': 'Southampton', '斯旺西': 'Swansea', '沃特福德': 'Watford',
    '雷克斯汉姆': 'Wrexham',
    # 西甲
    '奥萨苏纳': 'Osasuna', '巴列卡诺': 'Vallecano', '毕尔巴鄂': 'Ath Bilbao',
    '阿拉维斯': 'Alaves', '塞尔塔': 'Celta', '桑坦德': 'Santander',
    '塞维利亚': 'Sevilla', '巴塞罗那': 'Barcelona', '巴萨': 'Barcelona',
    '赫塔费': 'Getafe', '马拉加': 'Malaga', '皇家马德里': 'Real Madrid',
    '皇马': 'Real Madrid', '马德里竞技': 'Ath Madrid', '马竞': 'Ath Madrid',
    '皇家贝蒂斯': 'Betis', '贝蒂斯': 'Betis', '比利亚雷': 'Villarreal',
    '巴伦西亚': 'Valencia', '瓦伦西亚': 'Valencia', '拉科鲁尼亚': 'La Coruna',
    '拉科': 'La Coruna', '莱万特': 'Levante', '埃尔切': 'Elche',
    '西班牙人': 'Espanol', '皇家社会': 'Sociedad',
    # 意甲
    '乌迪内斯': 'Udinese', '卡利亚里': 'Cagliari', '博洛尼亚': 'Bologna',
    '都灵': 'Torino', '罗马': 'Roma', '国际米兰': 'Inter', 'AC米兰': 'Milan',
    '米兰': 'Milan', '佛罗伦萨': 'Fiorentina', '那不勒斯': 'Napoli',
    '拉齐奥': 'Lazio', '威尼斯': 'Venezia', '弗洛西诺': 'Frosinone',
    '帕尔马': 'Parma', '热那亚': 'Genoa', '科莫': 'Como', '莱切': 'Lecce',
    '亚特兰大': 'Atalanta', '尤文图斯': 'Juventus', '蒙扎': 'Monza', '萨索洛': 'Sassuolo',
    # 德甲
    '法兰克福': 'Ein Frankfurt', '弗赖堡': 'Freiburg', '汉堡': 'Hamburg',
    '科隆': 'FC Koln', '门兴': "M'gladbach", '云达不来梅': 'Werder Bremen',
    '不来梅': 'Werder Bremen', '奥格斯堡': 'Augsburg', '斯图加特': 'Stuttgart',
    '多特蒙德': 'Dortmund', '拜仁': 'Bayern Munich', '美因茨': 'Mainz',
    '霍芬海姆': 'Hoffenheim', '帕德博恩': 'Paderborn', '勒沃库森': 'Leverkusen',
    '莱比锡': 'RB Leipzig', '柏林联合': 'Union Berlin', '沙尔克': 'Schalke 04',
    '埃尔沃斯堡': 'Elversberg', '沃尔夫斯堡': 'Wolfsburg',
    # 法甲
    '巴黎FC': 'Paris FC', '斯特拉斯堡': 'Strasbourg', '昂热': 'Angers',
    '特鲁瓦': 'Troyes', '里昂': 'Lyon', '雷恩': 'Rennes', '马赛': 'Marseille',
    '巴黎圣日尔曼': 'Paris SG', '巴黎圣曼': 'Paris SG', '摩纳哥': 'Monaco',
    '朗斯': 'Lens', '里尔': 'Lille', '尼斯': 'Nice', '图卢兹': 'Toulouse',
    '欧塞尔': 'Auxerre', '勒阿弗尔': 'Le Havre', '洛里昂': 'Lorient',
    '布雷斯特': 'Brest', '勒芒': 'Le Mans',
    # 荷甲
    '阿贾克斯': 'Ajax', 'SBV精英': 'Excelsior', '埃因霍温': 'PSV',
    '特温特': 'Twente', '费耶诺德': 'Feyenoord', '阿尔克马尔': 'AZ Alkmaar',
    # 葡超
    '里斯本竞技': 'Sp Lisbon', '阿罗卡': 'Arouca', '波尔图': 'Porto',
    '本菲卡': 'Benfica', '布拉加': 'Braga',
    # 日职
    '长崎航海': 'V-Varen Nagasaki', '大阪樱花': 'Cerezo Osaka', '藤枝': 'Fujieda',
    '大宫松鼠': 'Omiya', '横滨水手': 'Yokohama F. Marinos', '水户蜀葵': 'Mito',
    '町田泽维亚': 'Machida', '柏太阳神': 'Kashiwa Reysol', '大阪钢巴': 'Gamba Osaka',
    '神户胜利船': 'Vissel Kobe', '浦和红钻': 'Urawa Reds', '川崎前锋': 'Kawasaki Frontale',
    '名古屋鲸': 'Nagoya Grampus', '广岛三箭': 'Sanfrecce Hiroshima', '福冈黄蜂': 'Avispa Fukuoka',
    '清水鼓动': 'Shimizu S-Pulse', '东京FC': 'FC Tokyo', '东京绿茵': 'Verdy',
    '鹿岛鹿角': 'Kashima Antlers', '京都': 'Kyoto', '冈山': 'Okayama', '千叶': 'Chiba',
    # 韩职 K League 1（2026-09-19 新增，配 FotMob 后端 id=9080）
    # ⚠️ 注意：football-data 的 KOR.csv 失效（内容实为挪威 Eliteserien，已列黑名单），
    #    故这里仅补全译名，等 KOR 源恢复后即可自动生效。
    '首尔': 'FC Seoul', 'FC首尔': 'FC Seoul', '蔚山': 'Ulsan HD FC', '蔚山HD': 'Ulsan HD FC',
    '全北现代': 'Jeonbuk Hyundai Motors FC', '全北': 'Jeonbuk Hyundai Motors FC',
    '济州': 'Jeju SK', '济州联': 'Jeju SK', '江原': 'Gangwon FC', '江原FC': 'Gangwon FC',
    '大田市民': 'Daejeon Hana Citizen', '大田': 'Daejeon Hana Citizen',
    '仁川联': 'Incheon United', '仁川': 'Incheon United',
    '浦项制铁': 'Pohang Steelers', '浦项': 'Pohang Steelers',
    '安养': 'FC Anyang', '富川': 'Bucheon FC 1995', '富川FC': 'Bucheon FC 1995', '金泉尚武': 'Gimcheon Sangmu', '金泉': 'Gimcheon Sangmu',
    '富川': 'Bucheon FC 1995', '光州': 'Gwangju FC', '光州FC': 'Gwangju FC',
    # 美职 MLS（2026-09-19 新增，配 FotMob 后端 id=130）
    '迈阿密国际': 'Inter Miami CF', '温哥华白帽': 'Vancouver Whitecaps',
    '洛杉矶FC': 'Los Angeles FC', '洛杉矶银河': 'LA Galaxy',
    '费城联合': 'Philadelphia Union', '圣何塞地震': 'San Jose Earthquakes',
    '纽约红牛': 'Red Bull New York', '辛辛那提': 'FC Cincinnati',
    '芝加哥火焰': 'Chicago Fire FC', '明尼苏达联': 'Minnesota United',
    '奥兰多城': 'Orlando City', '新英格兰革命': 'New England Revolution',
    '圣路易斯城': 'St. Louis City', '夏洛特': 'Charlotte FC',
    # 阿甲（2026-09-19 新增，配 FotMob 后端 id=112）
    '河床': 'River Plate', '博卡青年': 'Boca Juniors', '博卡': 'Boca Juniors',
    '竞技俱乐部': 'Racing Club', '独立': 'Independiente',
    '圣洛伦索': 'San Lorenzo', '拉普拉塔大学生': 'Estudiantes',
    '萨斯菲尔德': 'Velez Sarsfield', '塔耶雷斯': 'Talleres',
    '阿根廷青年人': 'Argentinos Juniors', '罗萨里奥中央': 'Rosario Central',
    '纽维尔老男孩': 'Newell\'s Old Boys', '拉努斯': 'Lanus', '胡拉坎': 'Huracan',
    '戈多伊克鲁斯': 'Godoy Cruz', '防御与正义': 'Defensa y Justicia',
    '班菲尔德': 'Banfield', '科尔多瓦中央': 'Central Cordoba',
    '图库曼竞技': 'Atletico Tucuman', '贝尔格拉诺': 'Belgrano',
    '科隆竞技': 'Colon', '萨米恩托': 'Sarmiento', '普拉滕斯': 'Platense',
    '巴拉卡斯中央': 'Barracas Central', '里瓦达维亚独立': 'Independiente Rivadavia',
    '科尔多瓦学院': 'Instituto', '门多萨体操': 'Gimnasia Mendoza',
    # 中超（2026-09-19 新增，配 PerformanceOdds 后端 pid=16789）
    # ⚠️ 陷阱：football-data 用**现名**，PerformanceOdds 用**旧称/异名**，
    #    xg-source 内部再做一次「现名 → 旧称」的别名桥接（见 PO_ALIAS）。
    #    这里 CN2EN 统一按 **football-data 现名**，与主源口径一致。
    '上海海港': 'Shanghai Port', '上海上港': 'Shanghai Port',
    '上海申花': 'Shanghai Shenhua',
    '成都蓉城': 'Chengdu Rongcheng', '成都兴城': 'Chengdu Rongcheng',
    '北京国安': 'Beijing Guoan', '北京': 'Beijing Guoan',
    '山东泰山': 'Shandong Taishan', '山东鲁能': 'Shandong Taishan',
    '浙江队': 'Zhejiang Professional', '浙江职业': 'Zhejiang Professional',
    '浙江绿城': 'Zhejiang Professional',
    '河南': 'Henan Songshan Longmen', '河南建业': 'Henan Songshan Longmen',
    '天津津门虎': 'Tianjin Jinmen Tiger', '天津泰达': 'Tianjin Jinmen Tiger',
    '武汉三镇': 'Wuhan Three Towns',
    '云南玉昆': 'Yunnan Yukun',
    '大连英博': 'Dalian Yingbo', '大连人': 'Dalian Yingbo',
    '重庆铜梁龙': 'Chongqing Tonglianglong',
    '青岛海牛': 'Qingdao Hainiu',
    '深圳新鹏城': 'Shenzhen Xinpengcheng',
    '梅州客家': 'Meizhou Hakka',
    '长春亚泰': 'Changchun Yatai',
    '辽宁铁人': 'Liaoning Tieren', '辽宁沈阳': 'Liaoning Tieren',
    '青岛西海岸': 'Qingdao West Coast',
    # 瑞超
    '韦斯特罗斯': 'Vasteras SK', '韦斯特罗': 'Vasteras SK', '马尔默': 'Malmo FF',
    '米亚尔比': 'Mjallby', '哥德堡盖斯': 'GAIS', '哥德堡': 'Goteborg',
    '斯德哥尔摩AIK': 'AIK', '佐加顿斯': 'Djurgarden', '哈马比': 'Hammarby',
    '埃尔夫斯堡': 'Elfsborg', '哈尔姆斯塔德': 'Halmstad', '卡尔马': 'Kalmar',
    '布罗马波卡纳': 'Brommapojkarna', '代格福什': 'Degerfors', '赫根': 'Hacken',
    '厄格里特': 'Orgryte', '天狼星': 'Sirius',
    # 挪超
    '克里斯蒂安松': 'Kristiansund', '克里斯蒂': 'Kristiansund', '罗森博格': 'Rosenborg',
    '维京': 'Viking', '利勒斯特罗姆': 'Lillestrom', '博多格林特': 'Bodo/Glimt',
    '布兰': 'Brann', '莫尔德': 'Molde', '瓦勒伦加': 'Valerenga', '特罗姆瑟': 'Tromso',
    '桑德菲奥德': 'Sandefjord', '萨尔普斯堡': 'Sarpsborg 08', '斯塔特': 'Start',
    '阿勒松': 'Aalesund', '弗雷德里克斯塔': 'Fredrikstad', '汉坎': 'HamKam',
    # 巴甲（数据源真实名：Athletico-PR / Botafogo RJ / Atletico-MG 等）
    '米拉索尔': 'Mirassol', '博塔弗戈': 'Botafogo RJ', '巴拉纳竞技': 'Athletico-PR',
    '巴伊亚': 'Bahia', '帕尔梅拉斯': 'Palmeiras', '弗拉门戈': 'Flamengo RJ',
    '科林蒂安': 'Corinthians', '圣保罗': 'Sao Paulo', '格雷米奥': 'Gremio',
    '巴西国际': 'Internacional', '克鲁塞罗': 'Cruzeiro', '弗鲁米嫩塞': 'Fluminense',
    '瓦斯科达伽马': 'Vasco', '桑托斯': 'Santos', '布拉甘蒂诺': 'Bragantino',
    '科里蒂巴': 'Coritiba', '米内罗竞技': 'Atletico-MG', '维多利亚': 'Vitoria',
    '沙佩科恩斯': 'Chapecoense-SC', '雷莫': 'Remo',
}


def find_en(cn, rows=None):
    """中文名 -> 数据源英文名。

    🔴 安全阀（2026-09-19）：
      1. **精确命中** 直接返回；
      2. 否则做**受控子串匹配**——仅当「包含该中文键的候选映射**唯一**」时才采用；
         若命中 2 个及以上候选（歧义）→ 返回 None（**宁可回退市场，绝不猜**）。
    严禁无约束模糊猜测——猜错会用别的球队数据算 λ，比无源更危险。
    """
    if cn in CN2EN:
        return CN2EN[cn]
    hits = {CN2EN[k] for k in CN2EN if k and k in cn}
    return hits.pop() if len(hits) == 1 else None


CnNames = list(CN2EN.keys())


# ---------------------------------------------------------------- 源缺口处理

def src_teams(d):
    """列出某数据源当前赛季出现过的全部队名（用于候选探测）"""
    if not d:
        return []
    rows = d['rows']
    key_h = 'Home' if 'Home' in rows[0] else 'HomeTeam'
    key_a = 'Away' if 'Away' in rows[0] else 'AwayTeam'
    return sorted({r.get(key_h, '') for r in rows} | {r.get(key_a, '') for r in rows} - {''})


def propose_candidates(cn_name, d, exclude=(), topn=3):
    """🔴 候选探测（**只建议，绝不采用**）。

    在该数据源的队名池里找与中文名可能对应的候选，用于人工确认。

    ⚠️ 关键纪律：
      - `exclude` 传入本场**已知的另一支球队英文名**，从候选池中剔除，
        防止「拿客队名当主队候选」的串队误导（v1.2 初版曾犯此错）。
      - 中文名与英文名**无法可靠自动比对**，本函数只提供**有限线索**，
        结果**必须人工确认**，严禁自动写入 CN2EN。

    匹配策略（按线索强弱）：
      1. 中文名中的 ASCII 片段直接命中队名（如「藤枝MYFC」→ MYFC）→ 强线索；
      2. 中文名整体 vs 队名的拼音首字母（仅当中文名 ≥3 字）→ 弱线索。

    返回 [(候选英文名, 置信度)]，按置信度降序。
    """
    import difflib
    cands = [c for c in src_teams(d) if c and c not in set(exclude)]
    if not cands:
        return []
    scored = []
    ascii_parts = ''.join(ch for ch in cn_name if ch.isascii() and ch.isalnum())
    for c in cands:
        c_low = c.lower()
        best = 0.0
        # 线索 1：中文名里的 ASCII 片段是硬证据
        if len(ascii_parts) >= 2 and ascii_parts.lower() in c_low.replace(' ', ''):
            best = 0.85
        # 线索 2：拼音首字母序列出现在队名首字母中（弱，仅当中文名较长）
        if not best and len(cn_name) >= 3:
            py = ''.join(_py_initial(ch) for ch in cn_name)
            if len(py) >= 3 and py in _initials(c):
                best = 0.55
        if best:
            scored.append((c, best))
    scored.sort(key=lambda x: -x[1])
    return scored[:topn]


def _py_initial(ch):
    """极简拼音首字母映射（只覆盖常见足球队名用字，缺口返回空）"""
    table = {
        '阿': 'a', '埃': 'a', '爱': 'a', '安': 'a', '奥': 'a',
        '巴': 'b', '拜': 'b', '柏': 'b', '本': 'b', '比': 'b', '波': 'b', '布': 'b', '博': 'b',
        '查': 'c', '长': 'c', '川': 'c',
        '大': 'd', '德': 'd', '迪': 'd', '东': 'd', '多': 'd', '都': 'd', '代': 'd',
        '恩': 'e',
        '法': 'f', '费': 'f', '佛': 'f', '弗': 'f', '富': 'f', '福': 'f', '菲': 'f',
        '冈': 'g', '哥': 'g', '格': 'g', '广': 'g', '国': 'g',
        '哈': 'h', '海': 'h', '汉': 'h', '赫': 'h', '河': 'h', '横': 'h', '胡': 'h', '霍': 'h',
        '基': 'j', '吉': 'j', '加': 'j', '京': 'j', '尤': 'j', '金': 'j',
        '卡': 'k', '凯': 'k', '科': 'k', '克': 'k', '库': 'k', '拉': 'l', '莱': 'l', '兰': 'l',
        '勒': 'l', '雷': 'l', '里': 'l', '利': 'l', '林': 'l', '洛': 'l', '卢': 'l', '鹿': 'l',
        '马': 'm', '迈': 'm', '曼': 'm', '米': 'm', '蒙': 'm', '莫': 'm', '姆': 'm',
        '拿': 'n', '那': 'n', '奈': 'n', '南': 'n', '尼': 'n', '纽': 'n', '诺': 'n',
        '帕': 'p', '庞': 'p', '佩': 'p', '皮': 'p', '普': 'p',
        '切': 'q', '琴': 'q', '清': 'q', '秋': 'q',
        '日': 'r', '热': 'r', '仁': 'r', '若': 'r',
        '萨': 's', '塞': 's', '桑': 's', '沙': 's', '神': 's', '圣': 's', '斯': 's', '索': 's',
        '塔': 't', '泰': 't', '特': 't', '托': 't', '图': 't',
        '瓦': 'w', '威': 'w', '维': 'w', '文': 'w', '沃': 'w', '伍': 'w', '乌': 'w',
        '西': 'x', '希': 'x', '悉': 'x', '夏': 'x', '谢': 'x', '兴': 'x', '星': 'x',
        '亚': 'y', '雅': 'y', '伊': 'y', '因': 'y', '云': 'y',
        '泽': 'z', '扎': 'z', '詹': 'z', '芝': 'z', '中': 'z', '朱': 'z', '佐': 'z',
    }
    return table.get(ch, '')


def _initials(name):
    """取英文队名各单词首字母（小写）"""
    return ''.join(w[0].lower() for w in name.split() if w)


def build_gap_report(recs, data):
    """生成 [源缺口] 清单（v1.2 新增）。

    🔴 缺口类型由**主流程显式写入** `rec['缺口']`，本函数只做汇总——
    严禁事后用 sample/口径 反推类型（v1.2 初版曾因此把「葡超队名缺失」
    误判为「葡超联赛无源」，属危险误报）。
    类型：'联赛无源' / '队名未映射' / '拉取失败'；样本不足**不算缺口**（正常现象）。
    🔴 三分类（2026-09-19）：'拉取失败' 单列 —— 它是**故障**（有源但本次没拉到），
       不是事实，绝不能与 '联赛无源' 混为一谈，也不能落到 'team' 分支。
    """
    gaps = []
    for r in recs:
        kind = r.get('缺口')
        if not kind:
            continue
        who = [t.strip() for t in r['对阵'].split(' v ')]
        cls = {'联赛无源': 'league', '拉取失败': 'fetch', '桥接失败': 'bridge'}.get(kind, 'team')
        item = {'编号': r['编号'], '联赛': r['联赛'], '队名': who,
                '原因': kind, '类别': cls,
                '未映射队': r.get('未映射队', [])}
        if kind == '拉取失败':
            item['告警'] = r.get('告警', '')
        gaps.append(item)
    # 候选探测（仅对「队名未映射」的缺口，且**按单个队名独立探测**）
    lgmap = {d['league']: d for d in data.values()}
    for g in gaps:
        if g['类别'] != 'team':
            continue
        d = lgmap.get(g['联赛'])
        g['候选'] = []
        unmapped = g.get('未映射队') or [t for t in g['队名'] if find_en(t) is None]
        # 🔴 本场另一支已映射球队的英文名 → 从候选池剔除，防串队
        peers = [find_en(t) for t in g['队名'] if find_en(t)]
        for nm in unmapped:
            cands = propose_candidates(nm, d, exclude=peers)
            if cands:
                g['候选'].append((nm, cands))
    return gaps


def print_gap_report(gaps, recs):
    """打印缺口清单（可见化）+ 源体检提示"""
    league_gaps = [g for g in gaps if g['类别'] == 'league']
    team_gaps = [g for g in gaps if g['类别'] == 'team']
    print()
    print('=== [源缺口] 清单（这些场次回退市场，原因如下）===')
    if not gaps:
        print('[源缺口] 无')
    for g in gaps:
        print('[源缺口] %s | %s | %s | 原因=%s'
              % (g['编号'], g['联赛'], ' v '.join(g['队名']), g['原因']))
    if team_gaps:
        print()
        print('=== [疑似映射] 候选建议（⚠️ 仅供人工确认，严禁自动采用）===')
        for g in team_gaps:
            for nm, cands in g.get('候选', []):
                desc = ' / '.join('%s(%.2f)' % (c, s) for c, s in cands)
                print('[疑似映射] %s | %s → 候选：%s' % (g['编号'], nm, desc))
        print('  └─ 确认后补入 CN2EN 并三处同步（skill / 任务内嵌 / 任务附录）')
    # 源体检
    print()
    print('=== [源体检] ===')
    from collections import Counter
    c1 = Counter(g['联赛'] for g in league_gaps)
    for lg, n in c1.most_common():
        print('[源体检] %s：本批 %d 场全无源 —— 若连续多期出现，该联赛源可能已失效' % (lg, n))
    c2 = Counter(' v '.join(g['队名']) for g in team_gaps)
    for nm, n in c2.most_common():
        print('[源体检] %s：本批映射缺失 %d 次 —— 补一次永久解决' % (nm, n))
    ok = len([r for r in recs if r.get('source') == 'real'])
    print('[源体检] 本批真实 λ 命中 %d 场 / 共 %d 场' % (ok, len(recs)))


# ------------------------------------------------------------------ 市场反解 + 分歧探测（v1.11）

def _pois_pmf(lam, kmax=15):
    p = math.exp(-lam); pmf = [p]
    for k in range(1, kmax + 1):
        p *= lam / k; pmf.append(p)
    return pmf


def poisson_1x2(lh, la, kmax=15):
    """独立 Poisson 的胜平负概率（截断 kmax 后归一）。"""
    ph = _pois_pmf(lh, kmax); pa = _pois_pmf(la, kmax)
    cum = []; s = 0.0
    for g in range(kmax + 1):
        cum.append(s); s += pa[g]
    P_H = P_D = P_A = 0.0
    for g in range(kmax + 1):
        P_H += ph[g] * cum[g]
        P_D += ph[g] * pa[g]
        P_A += ph[g] * (s - cum[g] - pa[g])
    z = P_H + P_D + P_A
    return P_H / z, P_D / z, P_A / z


def implied_probs(h, d, a):
    """竞彩胜平负赔率扣水 → 隐含 1X2 概率（假设抽水均匀分配）。

    🔴 已知局限：竞彩返还率约 71%，均匀扣水会引入小偏差——
    用于分歧探测足够；用于精确定价需国际盘（Pinnacle 类）。
    """
    inv = 1.0 / h + 1.0 / d + 1.0 / a
    return (1.0 / h) / inv, (1.0 / d) / inv, (1.0 / a) / inv


# 🔴 v3.5.0-r7 τ 合理性护栏（2026-10-05 批复 #2）
TAU_LO, TAU_HI = 1.5, 4.5
# 🔴 v3.5.0-r7 λ 反解验收阈值（2026-10-05 批复 #4）
SSE_MAX = 1e-10
DEV_MAX_PP = 0.05          # 三路边际偏差上限（百分点）


def market_lambda(h, d, a, tau=None):
    """胜平负赔率反解 (λ主, λ客, SSE, 标记) —— v3.5.0-r7 双自由度拟合。

    🔴 r7 变更（2026-10-05 · 事故驱动）：旧版硬约束 λ主+λ客=tau（无源场次退 2.6 先验）
    且只拟合【主胜】一个边际。1 个自由度匹配 3 个边际 → 误差被挤向平/客，
    实测 10-05 批次平局偏差最高 −4.74pp（周一005），导致 3i 闸门漏触发：
        市场去水平局 31.09%（越过 pd≥28% 高危线） vs τ=2.6 模型 26.34%（未触发）
    r7 释放为 2 个自由度：λ主、λ客 均为待定参数，tau=λ主+λ客 内生，
    三路边际同时最小化 SSE。放弃 2.6 联赛场均先验（批复 #3）。

    求解：多起点粗扫（防卡边界）+ 坐标下降精修。
    护栏：tau 越界则回退 2.6 并标 [τ先验回退]（批复 #2）。
    验收：SSE ≤ 1e−10 且三路偏差各 ≤ 0.05pp，否则标 [反解未收敛]（批复 #4）。

    返回 (lam_h, lam_a, sse, flag)；flag ∈ {'', '[τ先验回退]', '[反解未收敛]'}。
    """
    tH, tD, tA = implied_probs(h, d, a)

    def _sse(lh, la):
        mH, mD, mA = poisson_1x2(lh, la)
        return (mH - tH) ** 2 + (mD - tD) ** 2 + (mA - tA) ** 2

    best = None
    for lh0 in np.arange(0.50, 3.051, 0.05):      # 多起点，避免粗网格卡边界
        for la0 in np.arange(0.10, 2.051, 0.05):
            lh, la, step = lh0, la0, 0.50
            while step > 1e-10:                    # 坐标下降精修
                improved = False
                for _dx, _dy in ((step, 0), (-step, 0), (0, step), (0, -step),
                                 (step, step), (-step, -step),
                                 (step, -step), (-step, step)):
                    if lh + _dx <= 0.05 or la + _dy <= 0.05:
                        continue
                    if _sse(lh + _dx, la + _dy) < _sse(lh, la):
                        lh, la = lh + _dx, la + _dy
                        improved = True
                if not improved:
                    step /= 2
            s = _sse(lh, la)
            if best is None or s < best[0]:
                best = (s, lh, la)

    sse_min, lam_h, lam_a = best
    flag = ''
    tau_fit = lam_h + lam_a
    if not (TAU_LO <= tau_fit <= TAU_HI):         # 批复 #2：合理性护栏
        lam_h, lam_a = tau / 2 if tau else 1.30, tau / 2 if tau else 1.30
        sse_min = _sse(lam_h, lam_a)
        flag = '[τ先验回退]'
        return lam_h, lam_a, sse_min, flag

    mH, mD, mA = poisson_1x2(lam_h, lam_a)       # 批复 #4：验收闸门
    dev = max(abs(mH - tH), abs(mD - tD), abs(mA - tA)) * 100
    if sse_min > SSE_MAX or dev > DEV_MAX_PP:
        flag = '[反解未收敛]'
    return lam_h, lam_a, sse_min, flag


# ------------------------------------------------------------------ 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jc', required=True, help='竞彩接口 JSON（含 subMatchList）')
    ap.add_argument('--out', default='lambda-result.json')
    ap.add_argument('--min-sample', type=int, default=MIN_SAMPLE)
    ap.add_argument('--xg-mode', default='blend',
                    choices=('blend', 'auto', 'split', 'overall'),
                    help='xG 源 λ 口径。blend=默认（2025赛季240场回测：总偏差2.6pp，'
                         '另两种为18-20pp）；auto=split样本足够才用split；'
                         'split/overall=强制单一口径')
    ap.add_argument('--xg', dest='xg', action='store_true', default=True,
                    help='启用第三方 xG 源（默认开）')
    ap.add_argument('--no-xg', dest='xg', action='store_false',
                    help='禁用第三方 xG 源（排障用）')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    jc = json.load(open(args.jc, encoding='utf-8'))
    subs = []
    if 'value' in jc:
        for mi in jc['value'].get('matchInfoList', []):
            subs += mi.get('subMatchList', [])
    else:
        subs = jc

    data = fetch_all()
    data = _drop_duplicate_sources(data)   # 🔴 跨源去重（防副本污染）
    lgmap = {}
    for code, d in data.items():
        lgmap[d['league']] = d

    out = []
    for m in subs:
        lg = m.get('leagueAllName', '')
        hn, an = m.get('homeTeamAllName', ''), m.get('awayTeamAllName', '')
        d = lgmap.get(lg)
        rec = {'编号': m.get('matchNumStr'), '对阵': f'{hn} v {an}', '联赛': lg,
               'lambda_home': None, 'lambda_away': None, 'source': 'market',
               'sample': 0, '口径': None}
        if d:
            use_xg = d['xg']
            he = find_en(hn)
            ae = find_en(an)

            # ★ v1.3+：附加源联赛（无 xG）优先试第三方 xG 源
            #   注意：xG 源内部是英文队名，故先经 CN2EN 译名再匹配。
            if not use_xg and args.xg:
                lh, la, info = xg_lambda(d['code'], hn, an, mode=args.xg_mode)
                if lh is not None:
                    # 🔴 门槛看**总样本**（split 样本天然是总数一半，不能拿来卡）
                    nt = min(info.get('home_played_total') or 0,
                             info.get('away_played_total') or 0)
                    if nt >= args.min_sample:
                        rec.update({
                            'lambda_home': round(lh, 3), 'lambda_away': round(la, 3),
                            'source': 'real', '口径': 'xg', 'sample': nt,
                            '联赛场均总进球': round(league_avg(d['rows'], False), 2),
                            '样本': '%d/%d(总) %d/%d(主客)' % (
                                info['home_played_total'], info['away_played_total'],
                                info['home_played_host'], info['away_played_away']),
                            '数据源': info['source'], '源联赛': 'xG口径（第三方）',
                            'xG口径明细': '%s(总%s/%s 主客%s/%s)' % (
                                info.get('mode', '?'),
                                info['home_played_total'], info['away_played_total'],
                                info['home_played_host'], info['away_played_away']),
                        })
                        out.append(rec)
                        continue
                    else:
                        rec['xG源样本不足'] = '总样本%d<%d' % (nt, args.min_sample)
                else:
                    # 「无 xG 桥接」= 该联赛本就没有 xG 源（事实，非故障）
                    # 其余情况 = 真有源但取数失败（该告警）
                    if '无 xG 桥接' in str(info):
                        rec['xG不适用'] = True
                    else:
                        rec['xG源缺失'] = info      # 🔴 显式标记，禁止静默降级

            # 🔴 v1.10：桥接-only 联赛（rows=[]，唯一数据源是 xG 桥）——
            #    桥失败/样本不足/未启用 xG 一律直接回退市场，
            #    严禁进 team_stats（rows=[] 会 IndexError）。
            if not d['rows']:
                rec['缺口'] = '桥接失败'
                out.append(rec)
                continue

            # 🔴 安全阀：任一队名未命中 → 该场直接回退市场，绝不用「近似球队」硬算
            if not he or not ae:
                rec['缺口'] = '队名未映射'          # 🔴 显式标记（禁止事后推断）
                rec['未映射队'] = [t for t, e in ((hn, he), (an, ae)) if not e]
                out.append(rec)
                continue
            rec['数据源'] = d.get('src_country') or d['league']
            rec['源联赛'] = d.get('src_league') or d['league']
            h1 = team_stats(d['rows'], he, use_xg)
            a1 = team_stats(d['rows'], ae, use_xg)
            n = min(h1[2], a1[2]) if (h1[2] and a1[2]) else 0
            if n >= args.min_sample:
                lav = league_avg(d['rows'], use_xg)
                # 🔴 v1.11 ÷2 修复：分母应为「每队场均进球」(lav/2)。原实现误用
                #    每场总进球(≈2.6)作分母 → λ 系统性腰斩（三赛季回测无偏性检验：
                #    修复前 λ主均值 0.68 vs 实际主队场均进球 1.54）。
                rec.update({
                    'lambda_home': round(h1[0] * a1[1] / (lav / 2), 3),
                    'lambda_away': round(a1[0] * h1[1] / (lav / 2), 3),
                    'source': 'real', 'sample': n,
                    '口径': 'xG' if use_xg else 'goal',
                    '联赛场均总进球': round(lav, 2),   # v1.11：市场反解 tau 约束用
                })
            else:
                rec['sample'] = n
                rec['口径'] = 'xG' if use_xg else 'goal'
        else:
            # 🔴 联赛根本不在源内（显式标记，不靠 sample/口径 反推）
            #    2026-09-19 修正：须先排除「有源但本次拉取失败」——否则会把
            #    网络抖动误报成「联赛无源」，掩盖真实故障。
            _code = _CODE_BY_LEAGUE.get(lg)
            if _code and _code in _DL_FAILED:
                rec['缺口'] = '拉取失败'
                rec['告警'] = '联赛 %s(%s) 有源但本次拉取失败（已重试 3 次）' % (lg, _code)
                print('[数据源告警] %s | %s v %s —— %s' % (
                    _code, hn, an, rec['告警']))
            else:
                rec['缺口'] = '联赛无源'
        out.append(rec)

    # ------ v1.11 分歧探测（方案A）：市场 λ 反解 + 真实 λ TV 距离 ------
    # 主报告泊松输入一律用市场反解 λ（回测 9748 场钉死：真实 λ 追不上市场）；
    # 真实 λ 仅作第二意见：与市场隐含 1X2 对比 TV 距离，Top3 供人工复核。
    for rec, m in zip(out, subs):          # 主循环每个 m 恰 append 一次 → 严格对齐
        had = m.get('had') or {}
        try:
            oh, od, oa = float(had['h']), float(had['d']), float(had['a'])
        except (KeyError, TypeError, ValueError):
            continue                        # 停售/无赔率场次：不探测，静默跳过
        rec['市场赔率'] = (oh, od, oa)
        # 🔴 v3.5.0-r7：τ 内生（不再用 2.6 先验硬约束），三路边际同时拟合
        tau = rec.get('联赛场均总进球')          # 仅护栏越界时回退用，正常不参与拟合
        lh, la, _sse, _flag = market_lambda(oh, od, oa, tau)
        rec['市场λ'] = (round(lh, 3), round(la, 3))
        rec['市场λSSE'] = float('%.3e' % _sse)
        rec['市场λ标记'] = _flag
        rec['市场P'] = tuple(round(p, 4) for p in implied_probs(oh, od, oa))
        if _flag:
            # [反解未收敛] → 该场 p 不得进入重点档、不得进串关（批复 #4）
            rec['反解未收敛'] = True
            print('[反解未收敛] 场次=%s | SSE=%.3e | 标记=%s'
                  % (m.get('matchNumStr', '?'), _sse, _flag))
        if rec['source'] == 'real':
            pr = poisson_1x2(rec['lambda_home'], rec['lambda_away'])
            rec['真实P'] = tuple(round(p, 4) for p in pr)
            rec['分歧TV'] = round(0.5 * sum(abs(a - b) for a, b in zip(pr, rec['市场P'])), 4)
            diff = pr[0] - rec['市场P'][0]      # 主胜概率差（真实 − 市场）
            if diff >= 0.05:
                rec['分歧方向'] = '市场高估客队（真实λ更看好主胜）'
            elif diff <= -0.05:
                rec['分歧方向'] = '市场高估主队（真实λ更看好客胜）'
            elif abs(pr[1] - rec['市场P'][1]) >= 0.05:
                rec['分歧方向'] = '双方对平局分歧大'
            else:
                rec['分歧方向'] = '方向不显著'

    json.dump(out, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    real = [r for r in out if r['source'] == 'real']
    gaps = build_gap_report(out, data)
    # 缺口清单落盘（供任务侧/人工查阅）
    gapfile = args.out.replace('.json', '-gaps.json')
    json.dump(gaps, open(gapfile, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    if not args.quiet:
        print('=== λ 来源结果（门槛: 样本 >= %d 场）===' % args.min_sample)
        for r in out:
            tag = '✅真实' if r['source'] == 'real' else '🟡市场'
            if r['source'] == 'real':
                # 口径标：xG 口径（主源或第三方）高亮，与 goal 区分
                kj = r.get('口径') or ''
                mark = 'xG' if kj.lower() == 'xg' else 'goal'
                src = r.get('数据源') or ''
                extra = ('  ← %s' % src) if (src and 'soccerway' not in src
                                             and not src.startswith('Div=')) else ''
                print('%s %s %-22s λ=(%.2f, %.2f) 样本%-7s [%s]%s'
                      % (tag, r['编号'], r['对阵'][:22], r['lambda_home'],
                         r['lambda_away'], str(r.get('样本', '')), mark, extra))
            else:
                warn = ''
                if r.get('xG源缺失'):
                    warn = '  🔴[xG源缺失: %s]' % str(r['xG源缺失'])[:40]
                elif r.get('xG源样本不足'):
                    warn = '  [xG源样本不足: %s]' % r['xG源样本不足']
                elif r.get('xG不适用'):
                    warn = '  [xG不适用: 该联赛无xG源]'
                print('%s %s %-22s 样本%2d（不足，回退市场）%s'
                      % (tag, r['编号'], r['对阵'][:22], r['sample'], warn))
        print()
        n_xg = len([r for r in real if (r.get('口径') or '').lower() == 'xg'])
        n_goal = len(real) - n_xg
        print('真实 λ: %d 场（xG口径 %d | goal口径 %d）| 回退市场: %d 场 | 合计 %d'
              % (len(real), n_xg, n_goal, len(out) - len(real), len(out)))
        # ------ v1.11 [分歧探测] Top3（方案A：真实 λ 的唯一用途） ------
        divs = sorted((r for r in out if '分歧TV' in r),
                      key=lambda r: r['分歧TV'], reverse=True)
        print('=== [分歧探测] 真实λ v 市场λ Top3（TV 🔴≥0.08 / 🟡≥0.05，经验初值待校准）===')
        if not divs:
            print('（本批无可探测场次：全部样本不足或赔率缺失）')
        for r in divs[:3]:
            tv = r['分歧TV']
            flag = '🔴' if tv >= 0.08 else ('🟡' if tv >= 0.05 else '·')
            print('%s %s %s TV=%.3f %s' % (
                flag, r['编号'], r['对阵'], tv, r.get('分歧方向', '')))
            print('    真实P=%s λ=(%.2f,%.2f) [%s样本%d]  |  市场P=%s λ=%s 赔率%s' % (
                r.get('真实P'), r['lambda_home'], r['lambda_away'],
                r.get('口径', '?'), r.get('sample', 0),
                r.get('市场P'), r.get('市场λ'), r.get('市场赔率')))
        if _XG_ERR and args.xg:
            print('[xG源告警] %s' % _XG_ERR)
        print_gap_report(gaps, out)
    print('[DONE] 已写出 %s（缺口清单 %s）' % (args.out, gapfile))


if __name__ == '__main__':
    main()

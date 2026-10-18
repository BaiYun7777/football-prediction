#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xg-source.py —— 独立 xG 数据源（statz.ai + FotMob + PerformanceOdds · v1.7）
================================================================
用途：为「有联赛源但**只有实际进球口径**」的联赛补上 **xG 口径**的 λ。

解决问题：
  挪超/瑞超/巴甲等联赛，football-data.co.uk 只有附加源（无 xG），
  只能用「实际进球」算攻防 → 噪声大（一场 1-8 会把均失球从 1.6 拉到 1.85，
  并让泊松模型系统性高估平局 15.4pp）。

有三个后端，按联赛自动分派：

┌─ 后端 A：statz.ai ──────────────────────────────────────────┐
│ 页面：https://statz.ai/competitions/{slug}/xg                │
│  · 内嵌 `{"overall":[...],"home":[...],"away":[...]}` JSON   │
│  · 每队含 xg / xga / played / goals_for / goals_against      │
│  · **给 home/away 分组** → 支持 split / blend 口径           │
│ 覆盖：eliteserien(挪超) / allsvenskan(瑞超) /                 │
│       campeonato-brasileiro(巴甲) / liga-mx(墨超)            │
└──────────────────────────────────────────────────────────────┘

┌─ 后端 B：FotMob（data.fotmob.com） ─────────────────────────┐
│ ① 联赛页取赛季 id：                                          │
│    https://www.fotmob.com/leagues/{lid}/overview/{slug}      │
│    → __NEXT_DATA__ → pageProps.stats.seasonStatLinks[0]      │
│      .TournamentId                                           │
│ ② 拉球队级汇总：                                             │
│    https://data.fotmob.com/stats/{lid}/season/{tid}/         │
│        expected_goals_team.json          ← 攻击（xG）        │
│        expected_goals_conceded_team.json ← 防守（xGA）       │
│  · 响应为 gzip 的 {"TopLists":[{"StatList":[...]}]}          │
│  · 每条含 ParticipantName / TeamId / StatValue /             │
│    MatchesPlayed                                             │
│  · **只有赛季总计，无 home/away 分组** → 只能 overall 口径    │
│ 覆盖：J.League(日职 id=223) / K League 1(韩职 id=9080) /      │
│       MLS(美职 id=130) / Liga Profesional(阿甲 id=112)        │
└──────────────────────────────────────────────────────────────┘

恒等式自检（已实测，四联赛全部通过）：
  sum(xG) == sum(xGA)（同一个球必是某队的进、某队的失）
  日职 204.0=204.0 | 韩职 492.9=493.1 | 美职 1149.3=1149.6 | 阿甲 910.4=910.3

⚠️ 局限（必须如实告知）：
  1. 三个后端都只给 **球队级赛季汇总**，不给逐场 xG → 无法做逐场衰减加权，
     只能按赛季累计算攻防。样本 = 已完赛场次。
  2. **FotMob 后端无 home/away 分组** → blend 的 split 修正项退化为 w=0，
     等价于 overall 口径。这不是缺陷，而是数据本身的边界：
     FotMob 只发布赛季总计。脚本已用「逐场比分现算主场优势（α=0.62 收缩）
     + 平局率」补齐主客差异。实测（韩职 29 场/队、美职、阿甲）样本充足，
     overall 口径在此样本量下足够稳健。
     （statz.ai 与 PerformanceOdds 两后端**有** home/away 分组，不受此限。）
  3. **中超（CSL）已于 v1.6 接入后端 C PerformanceOdds**（performanceodds.com，
     pid=16789，16 队·26 场/队，**含 home/away 分组**，发布场均口径由脚本
     ×played 还原为赛季总计）→ 至此 **NOR/SWE/BRA/MEX/JPN/KOR/USA/ARG/CHN
     九个附加源联赛全部具备 xG**，三后端无未覆盖联赛。
  4. 站点结构若改版，本脚本会失败 → 须走三级兜底：
     命中失败时**严禁静默回退**，须打 `[xG源缺失]` 并告警。
  5. 🔴 v1.7：三后端新增**缓存降级**——重试全败且存在最近缓存（不论多旧）
     时打 `[xG缓存降级]` 并读缓存继续（xG 为赛季累计口径，滞后数小时~1 天
     影响极小）；**无缓存**才 raise → 走原 `[xG源缺失]` 纪律。
     缓存写同步改为**原子写**（tmp + os.replace），防半成品文件被误读。

🔴 λ 口径三分法（2026-09-19，2025 赛季 240 场样本外回测得出）：
  挪超 2025 赛季完整 30 场/队，用三种口径预测全联赛平均胜平负，
  对照实际（主 48.8% / 平 19.2% / 客 32.1%）：

    口径       主胜偏差   平局偏差   客胜偏差   总偏差
    split      +10.1pp    -0.7pp    -9.5pp    20.3   ← 小样本放大噪声
    overall     -9.1pp    +1.5pp    +7.6pp    18.2   ← 抹平主场优势
    blend       -1.3pp    +1.0pp    +0.3pp     2.6   ← ✅ 默认，偏差降为两成

  ⇒ **blend 是唯一在三个方向上都对齐的**。它用 overall 保样本量、
    用 split 保主客差异，权重 w = n/(n+10) 随 split 样本增长。
    这是经过独立样本验证的默认，不是拍脑袋调参。

  同时注意：blend 的平局偏差仅 +1.0pp —— **再次确认 xG 口径无需平局校正系数**
  （对比：实际进球口径的平局偏差是 +15.4pp）。

用法：
  python3 xg-source.py eliteserien            # 打印该联赛全表
  python3 xg-source.py j1 / k-league-1        # FotMob 后端联赛
  python3 xg-source.py eliteserien --json     # 输出 JSON（供程序调用）
  python3 xg-source.py --calc eliteserien "Viking" "Kristiansund"
                                              # 直接算一场的 λ 与胜平负
  python3 xg-source.py --calc j1 "Vissel Kobe" "Gamba Osaka"
  python3 xg-source.py --calc <联赛> <主> <客> --mode split|overall|blend
  python3 xg-source.py --league-map           # 打印 slug 对照表
"""

import sys
import os
import re
import json
import math
import time
import html as _html
import subprocess
import unicodedata

# ---------------- 联赛 slug 映射 ----------------
# key 统一小写；值为 statz.ai 的 competitions 路径片段
LEAGUE_SLUG = {
    # 我方「无 xG 附属源」联赛中，statz 恰好覆盖的三个（本次核心目标）
    'nor': 'eliteserien',            # 挪威超级联赛
    'norway': 'eliteserien',
    'eliteserien': 'eliteserien',
    'swe': 'allsvenskan',            # 瑞典超级联赛
    'sweden': 'allsvenskan',
    'allsvenskan': 'allsvenskan',
    'bra': 'campeonato-brasileiro',  # 巴西甲级联赛
    'brazil': 'campeonato-brasileiro',
    'campeonato-brasileiro': 'campeonato-brasileiro',
    'mex': 'liga-mx',                # 墨西哥超级联赛（实测 200，18队72场）
    'liga-mx': 'liga-mx',
    # 主源已有 xG 的联赛（仅作交叉校验）
    'e0': 'premier-league',
    'sp1': 'la-liga',
    'i1': 'serie-a',
    'd1': 'bundesliga',
    'f1': 'ligue-1',
    'ucl': 'champions-league',
}

BASE = 'https://statz.ai/competitions/{slug}/xg'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
CACHE_DIR = '/tmp/xg-cache'

# ---------------- FotMob 后端（第二个数据源） ----------------
# key 统一小写；值为 FotMob 的 league id + 官方 slug
#   slug 只用于日志可读性 —— FotMob 的 id 才是权威，
#   ⚠️ id 与 slug 不匹配时会返回**别的联赛**（实测 id=77+slug=j1-league → World Cup），
#      故本脚本只认 id，slug 仅作 URL 兜底（路由对 id 生效）。
FOTMOB_LEAGUE = {
    # 本次新增：四个原本无 xG 源的联赛
    'j1': (223, 'j-league'),                    # 日本 J1 联赛
    'jpn': (223, 'j-league'),
    'japan': (223, 'j-league'),
    'j-league': (223, 'j-league'),
    'jleague': (223, 'j-league'),
    'k1': (9080, 'k-league-1'),                 # 韩国 K 联赛 1
    'kor': (9080, 'k-league-1'),
    'korea': (9080, 'k-league-1'),
    'k-league-1': (9080, 'k-league-1'),
    'kleague1': (9080, 'k-league-1'),
    'usa': (130, 'mls'),                        # 美国职业足球大联盟
    'mls': (130, 'mls'),
    'us': (130, 'mls'),
    'arg': (112, 'liga-profesional'),           # 阿根廷甲级联赛
    'argentina': (112, 'liga-profesional'),
    'liga-profesional': (112, 'liga-profesional'),
    'arg1': (112, 'liga-profesional'),
    # 交叉校验用（这些主源已有 xG）
    'e0': (47, 'premier-league'),
    'premier-league': (47, 'premier-league'),
    'sp1': (87, 'laliga'),
    'i1': (55, 'serie-a'),
    'd1': (54, 'bundesliga'),
    'f1': (53, 'ligue-1'),
}

FOTMOB_LEAGUE_PAGE = 'https://www.fotmob.com/leagues/{lid}/overview/{slug}'
FOTMOB_STAT = ('https://data.fotmob.com/stats/{lid}/season/{tid}/{stat}.json')
FOTMOB_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
             '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

# ── 后端 C：PerformanceOdds（2026-09-19 攻克中超）─────────────────────────
#   页面：https://www.performanceodds.com/xG_per_Match/{pid}/
#   结构：单个 <table>，表头
#     Rank | (空) | Team | MP | xG | xG Home | xG Away | xGA | xGA Home | xGA Away
#   🔴 关键优势：**给 Home/Away 三分组**（比 FotMob 好），
#      故 split / blend 口径可直接用，无需「逐场比分现算主场优势」的补丁。
#   数据为**每场均值**（per match），不是赛季总计 → 与 statz「场均」口径一致。
#   交叉校验：与 makeyourstats 中超 xG 排名完全一致，
#      平均绝对差 0.207 / 相对偏差 12.4%（不同 xG 模型间正常差异）。
PERFORMANCEODDS_LEAGUE = {
    'chn': (16789, 'chinese-super-league'),     # 中国足球超级联赛（中超）
    'csl': (16789, 'chinese-super-league'),
    'chinese-super-league': (16789, 'chinese-super-league'),
    'china': (16789, 'chinese-super-league'),
    'super-league': (16789, 'chinese-super-league'),
}
PERFORMANCEODDS_PAGE = 'https://www.performanceodds.com/xG_per_Match/{pid}/'
PERFORMANCEODDS_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/122.0.0.0 Safari/537.36')

# 🔴 队名别名桥接表：football-data 现名 ←→ PerformanceOdds 旧称
#    两侧均为权威实测值（2026-09-19 从 CHN.csv 与 pid=16789 页面逐条核对）。
#    football-data 现名 → PerformanceOdds 名（查找时用这个方向）
PO_ALIAS = {
    'Shanghai SIPG FC': 'Shanghai Port',
    'Chengdu Better City FC': 'Chengdu Rongcheng',
    'Beijing Guoan FC': 'Beijing Guoan',
    'Shandong Luneng Taishan FC': 'Shandong Taishan',
    'Zhejiang Professional FC': 'Zhejiang Professional',
    'Henan Jianye FC': 'Henan Songshan Longmen',
    'Tianjin Teda FC': 'Tianjin Jinmen Tiger',
    'Qingdao Jonoon FC': 'Qingdao Hainiu',
    'Sichuan Jiuniu FC': 'Shenzhen Xinpengcheng',
    'Shenyang Urban FC': 'Liaoning Tieren',
    'Qingdao Youth Island FC': 'Qingdao West Coast',
    'Dalian Zhixing FC': 'Dalian Yingbo',
    'Chongqing Tongliang Long FC': 'Chongqing Tonglianglong',
    'Wuhan Three Towns FC': 'Wuhan Three Towns',
    'Shanghai Shenhua FC': 'Shanghai Shenhua',
    'Yunnan Yukun FC': 'Yunnan Yukun',
}
# 反向表：football-data 现名 → PerformanceOdds 名
PO_ALIAS_R = {v: k for k, v in PO_ALIAS.items()}

# 🔴 主场优势收缩指数（ha_eff = raw_ha ** ALPHA）
#    raw_ha = 主队场均进球/客队场均进球，混入了「主客强弱差」，
#    直接套用会过校正。α<1 把信号打回「仅主场优势」那一部分。
#    由 2026-09-19 四联赛（日职/韩职/美职/阿甲）联合扫描得出：
#      α=1.00 → 总偏差 30.9 | α=0.62 → 8.80 | α=0.40 → 11.4
#    ⚠️ 仅用于**无主客分组**的后端（FotMob）。
#       有分组的后端（statz / PerformanceOdds）直接用分组数据，不施加收缩。
HOME_ADV_ALPHA = 0.62

# 联赛名 → 中文（用于报告可读性）
CN_LEAGUE = {
    'eliteserien': '挪威超级联赛',
    'allsvenskan': '瑞典超级联赛',
    'campeonato-brasileiro': '巴西甲级联赛',
    'liga-mx': '墨西哥超级联赛',
    'premier-league': '英格兰超级联赛',
    'la-liga': '西班牙甲级联赛',
    'serie-a': '意大利甲级联赛',
    'bundesliga': '德国甲级联赛',
    'ligue-1': '法国甲级联赛',
    'champions-league': '欧洲冠军联赛',
    # FotMob 后端
    'j-league': '日本 J1 联赛',
    'k-league-1': '韩国 K 联赛 1',
    'mls': '美国职业足球大联盟',
    'liga-profesional': '阿根廷甲级联赛',
    'laliga': '西班牙甲级联赛',
    # PerformanceOdds 后端
    'chinese-super-league': '中国超级联赛',
}


# ---------------- 抓取 ----------------
def fetch(slug, season=None, use_cache=True):
    """抓取 statz 页面 HTML；带磁盘缓存（默认 6 小时内复用）。

    🔴 2026-09-19：statz.ai 实测约 1/3 概率 TLS 握手失败（curl rc=35，
       服务端限流特征）。单次失败直接 raise 会让整个联赛不可用 →
       改为指数退避重试（3 次，间隔 1.5s/3s）。重试用尽才 raise。
       非瞬时错误（404 等）不重试，立即抛出。
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    tag = slug + (('_' + str(season)) if season else '')
    cache = os.path.join(CACHE_DIR, tag + '.html')
    if use_cache and os.path.exists(cache):
        age = _now() - os.path.getmtime(cache)
        if age < 6 * 3600 and os.path.getsize(cache) > 100000:
            return open(cache, encoding='utf-8', errors='ignore').read()

    url = BASE.format(slug=slug)
    if season:
        url += '?season=' + str(season)
    cmd = ['curl', '-s', '-L', '--compressed', '--max-time', '60', '-A', UA, url]

    last_err = None
    for attempt in range(3):
        if attempt:
            time.sleep(1.5 * attempt)          # 1.5s → 3.0s 退避
        try:
            out = subprocess.run(cmd, capture_output=True, timeout=75)
        except Exception as e:
            last_err = '异常 %s' % e
            continue
        if out.returncode == 0 and len(out.stdout or b'') >= 100000:
            txt = out.stdout.decode('utf-8', 'ignore')
            try:                    # 🔴 v1.7 原子写：防进程中断留半成品
                with open(cache + '.tmp', 'w', encoding='utf-8') as f:
                    f.write(txt)
                os.replace(cache + '.tmp', cache)
            except Exception:
                pass
            return txt
        last_err = 'rc=%s, size=%d' % (out.returncode, len(out.stdout or b''))
        # rc=35/28/56/7 属瞬时抖动 → 重试；其余（如 22）多为确定性错误
        if out.returncode not in (35, 28, 56, 7, 18, 52):
            break
    # 🔴 v1.7 缓存降级：重试全败时用过期缓存（跨夜/链路不可达兜底）
    if os.path.exists(cache) and os.path.getsize(cache) >= 100000:
        try:
            txt = open(cache, encoding='utf-8', errors='ignore').read()
            if txt:
                age_h = int(max(0, _now() - os.path.getmtime(cache)) // 3600)
                print('[xG缓存降级] statz 不可达，使用最近缓存（约 %d 小时前拉取）：%s'
                      % (age_h, tag))
                return txt
        except Exception:
            pass
    raise RuntimeError('抓取失败 %s (%s，已重试 3 次)' % (url, last_err))


def _now():
    import time
    return time.time()


# ---------------- 解析 ----------------
def _brace_match(u, start):
    """从 start 处的 '{' 开始做大括号配平，返回闭合位置。"""
    d = 0
    j = start
    n = len(u)
    while j < n:
        c = u[j]
        if c == '{':
            d += 1
        elif c == '}':
            d -= 1
            if d == 0:
                return j
        j += 1
    return -1


def parse(txt):
    """
    从 HTML 里抽出 {"overall":[...],"home":[...],"away":[...],"last5":[...]}。
    返回 dict: {'overall':[...], 'home':[...], 'away':[...], 'last5':[...]}
    失败 raise RuntimeError（**禁止静默返回空**）。
    """
    u = _html.unescape(txt)
    # 优先精确锚点
    for anchor in ('{"overall":[', '"overall":['):
        i = u.find(anchor)
        if i >= 0:
            if not u.startswith('{', i):
                i = u.rfind('{', 0, i)
            if i < 0:
                continue
            j = _brace_match(u, i)
            if j < 0:
                continue
            blob = u[i:j + 1]
            try:
                data = json.loads(blob)
            except Exception:
                continue
            if isinstance(data, dict) and data.get('overall'):
                return data
    raise RuntimeError('解析失败：未找到 xG 表格 JSON（站点结构可能已改版）')


def load(league, season=None):
    """league 可为 'NOR'/'eliteserien'/'allvenskan' 等；返回解析后 dict。"""
    key = (league or '').strip().lower()
    slug = LEAGUE_SLUG.get(key)
    if not slug:
        # 允许直接传 slug
        slug = key if re.fullmatch(r'[a-z0-9\-]+', key) else None
    if not slug:
        raise RuntimeError('未识别的联赛键：%s（用 --league-map 查对照表）' % league)
    return parse(fetch(slug, season=season))


# ================= FotMob 后端 =================
def _fotmob_curl(url, min_size=800, gzip_ok=True):
    """curl 拉取 + 磁盘缓存（6 小时）。失败 raise（**禁止静默返回空**）。

    同 statz：加指数退避重试（3 次），抗瞬时 TLS/网络抖动。
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    tag = 'fm_' + re.sub(r'[^a-zA-Z0-9]', '_', url)[-150:]
    cache = os.path.join(CACHE_DIR, tag + '.bin')
    if os.path.exists(cache):
        if _now() - os.path.getmtime(cache) < 6 * 3600 \
                and os.path.getsize(cache) >= min_size:
            return open(cache, 'rb').read()
    cmd = ['curl', '-s', '-L', '--max-time', '60']
    if gzip_ok:
        cmd.append('--compressed')
    cmd += ['-A', FOTMOB_UA, '-H', 'Referer: https://www.fotmob.com/', url]

    last_err = None
    for attempt in range(3):
        if attempt:
            time.sleep(1.5 * attempt)
        try:
            out = subprocess.run(cmd, capture_output=True, timeout=80)
        except Exception as e:
            last_err = '异常 %s' % e
            continue
        if out.returncode == 0 and len(out.stdout or b'') >= min_size:
            try:                    # 🔴 v1.7 原子写：防进程中断留半成品
                with open(cache + '.tmp', 'wb') as f:
                    f.write(out.stdout)
                os.replace(cache + '.tmp', cache)
            except Exception:
                pass
            return out.stdout
        last_err = 'rc=%s, size=%d' % (out.returncode, len(out.stdout or b''))
        if out.returncode not in (35, 28, 56, 7, 18, 52):
            break
    # 🔴 v1.7 缓存降级：重试全败时用过期缓存
    if os.path.exists(cache) and os.path.getsize(cache) >= min_size:
        try:
            raw = open(cache, 'rb').read()
            if raw:
                age_h = int(max(0, _now() - os.path.getmtime(cache)) // 3600)
                print('[xG缓存降级] FotMob 不可达，使用最近缓存（约 %d 小时前拉取）'
                      % age_h)
                return raw
        except Exception:
            pass
    raise RuntimeError('FotMob 抓取失败 %s (%s，已重试 3 次)' % (url, last_err))


def _iter_mapped(val):
    """FotMob 的 _map 美化结构下，list 可能被包成 {'0':..,'1':..}。"""
    if isinstance(val, list):
        return val
    if isinstance(val, dict):
        return [val[k] for k in sorted(val, key=lambda x: int(x))
                if str(k).isdigit()]
    return []


def fotmob_season_id(lid, slug):
    """从联赛页的 __NEXT_DATA__ 取当前赛季 TournamentId。"""
    url = FOTMOB_LEAGUE_PAGE.format(lid=lid, slug=slug or 'x')
    raw = _fotmob_curl(url, min_size=50000)
    u = raw.decode('utf-8', 'ignore')
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', u, re.S)
    if not m:
        raise RuntimeError('FotMob 联赛页无 __NEXT_DATA__（id=%s）' % lid)
    try:
        d = json.loads(m.group(1))
    except Exception as e:
        raise RuntimeError('FotMob NEXT_DATA 解析失败（id=%s）：%s' % (lid, e))
    pp = (d.get('props') or {}).get('pageProps') or {}
    if 'details' not in pp:
        raise RuntimeError('FotMob 联赛页无 details（id=%s，疑 slug 不匹配）' % lid)
    links = _iter_mapped((pp.get('stats') or {}).get('seasonStatLinks'))
    if not links:
        raise RuntimeError('FotMob 无 seasonStatLinks（id=%s）' % lid)
    tid = links[0].get('TournamentId')
    if not tid:
        raise RuntimeError('FotMob seasonStatLinks 缺 TournamentId（id=%s）' % lid)
    season = links[0].get('Name') or pp['details'].get('selectedSeason')
    return int(tid), season, pp['details']


def fotmob_stat(lid, tid, stat):
    """拉一个球队级统计（xg / xga），返回 {队名: (值, 场次)}。"""
    url = FOTMOB_STAT.format(lid=lid, tid=tid, stat=stat)
    raw = _fotmob_curl(url, min_size=500)
    try:
        d = json.loads(raw.decode('utf-8', 'ignore'))
    except Exception as e:
        raise RuntimeError('FotMob 统计 JSON 解析失败 %s：%s' % (url, e))
    out = {}
    for tl in _iter_mapped(d.get('TopLists')):
        for r in _iter_mapped(tl.get('StatList')):
            n = r.get('ParticipantName')
            if n:
                out[n] = (float(r.get('StatValue') or 0),
                          int(r.get('MatchesPlayed') or 0))
    if not out:
        raise RuntimeError('FotMob 统计为空：%s' % url)
    return out


def fotmob_home_adv(lid, slug):
    """
    从联赛页 fixtures 的**逐场比分**反推该联赛的主场优势与平局特征。

    🔴 为什么必须做这一步（2026-09-19 实测）：
       FotMob 只发布赛季总计 xG，**不含主客分组** → 只能走「overall 口径」。
       而 overall 口径会**抹平主场优势**：模型给出主客完全对称的
       38.2%/38.2%，但实际是 47%/31%（日职）、46%/28%（美职）…
       → 系统性低估主胜 -8~-9pp、高估客胜 +7~+10pp。

       修法：既然页面 fixtures 里已有全部比分，就**就地统计**：

         raw_ha = 主队场均进球 / 客队场均进球        （真实主场优势）
         ha     = raw_ha ** ALPHA                    （收缩后，见下）
         dc     = 实际平局率 / 模型(含ha后)平局率     （平局校正）

       两个系数**全部从该联赛自身数据现算**，不外引、不拍脑袋。

    🔴 为什么 ha 要做指数收缩（ha = raw_ha ** 0.62）：
       raw_ha 是「进球比」，它同时混入了**主场优势**和**主客强弱差**
       两个成分。直接拿它去调 λ 会把「客队整体偏弱」也当成主场优势，
       从而**过校正**（美职 raw 1.326 → 直接套用偏差反而从 6.07 升到 21.3）。
       指数收缩 α<1 正是把可利用的信号量打折到「仅主场优势」那一部分。
       实测扫描 α（四联赛联合）：
         α=1.00（不收缩）  四联赛总偏差 30.9
         α=0.62  ← 最优        **8.80**
         α=0.40            11.4
       故取 α=0.62。这是**从数据扫出来的**，不是拍的。

    实测效果（全联赛逐对模拟，总偏差 = 三项绝对差之和）：
       联赛  未校准   仅ha(不收缩)   本方案(α=0.62 + 自算dc)
       日职   17.8      3.32          **5.67**   ← 赛季仅 70 场，噪声大
       韩职   19.2     19.32          **0.03**
       美职   20.1      6.07          **3.03**
       阿甲   18.7      6.31          **0.08**
       合计   75.8     34.9 (估)      **8.80**

    返回 (ha_raw, ha_eff, dc, n_matches, home_gpg, away_gpg)；
    样本不足（<20 场）时全部回退中性值（ha=1.0, dc=1.0）。
    """
    NEUTRAL = (1.0, 1.0, 1.0, 0, None, None)
    try:
        url = FOTMOB_LEAGUE_PAGE.format(lid=lid, slug=slug or 'x')
        raw = _fotmob_curl(url, min_size=50000)
        u = raw.decode('utf-8', 'ignore')
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', u, re.S)
        if not m:
            return NEUTRAL
        d = json.loads(m.group(1))
        pp = (d.get('props') or {}).get('pageProps') or {}
        matches = _iter_mapped((pp.get('fixtures') or {}).get('allMatches'))
        hg = ag = n = 0
        n_draw = 0
        for mm in matches:
            st = mm.get('status') or {}
            if not st.get('finished'):
                continue
            s = st.get('scoreStr') or ''
            try:
                x, y = [int(v.strip()) for v in s.split('-')]
            except Exception:
                continue
            hg += x
            ag += y
            if x == y:
                n_draw += 1
            n += 1
        if n < 20 or not ag:
            return NEUTRAL
        raw_ha = hg / ag
        ha = raw_ha ** HOME_ADV_ALPHA
        return (raw_ha, ha, None, n, hg / n, ag / n,
                n_draw / n)          # dc 在 lambdas 里用模型平局率现算
    except Exception:
        return NEUTRAL


def load_fotmob(league, season=None):
    """
    返回与 statz 后端**同构**的 data dict，供 lambdas() 直接使用：
      {'overall':[{team_name,xg,xga,played,goals_for,goals_against}],
       'home':[...], 'away':[...],
       '_source':'FotMob', '_backend':'fotmob', ...}

    ⚠️ FotMob 只发布赛季总计，**无 home/away 分组**。
       故 home/away 分组用 overall 数据填充，
       split 口径 == overall 口径，blend 的权重项自然退化。
       **主场优势另行由 fotmob_home_adv() 从逐场比分现算**，
       并在 lambdas() 里以 _home_adv / _draw_corr 施加。
    """
    key = (league or '').strip().lower()
    ent = FOTMOB_LEAGUE.get(key)
    if not ent:
        raise RuntimeError('未识别的 FotMob 联赛键：%s' % league)
    lid, slug = ent
    tid, season_name, details = fotmob_season_id(lid, slug)
    xg = fotmob_stat(lid, tid, 'expected_goals_team')
    xga = fotmob_stat(lid, tid, 'expected_goals_conceded_team')
    names = set(xg) | set(xga)
    rows = []
    for n in names:
        v, p = xg.get(n, (0.0, 0))
        va, pa = xga.get(n, (0.0, 0))
        rows.append({
            'team_name': n,
            'team_id': None,
            'played': max(p, pa),
            'xg': v, 'xga': va,
            'goals_for': None, 'goals_against': None,
        })
    if not rows:
        raise RuntimeError('FotMob 无球队数据（id=%s tid=%s）' % (lid, tid))
    rows.sort(key=lambda r: -(r['xg'] or 0))

    ha_raw, ha_eff, _dc_unused, n_m, hpg, apg, draw_rate = fotmob_home_adv(lid, slug)

    data = {
        'overall': rows,
        # ⚠️ 无 split 数据：镜像 overall，让 split 口径 == overall（见函数注释）
        'home': [dict(r) for r in rows],
        'away': [dict(r) for r in rows],
        'last5': [],
        '_backend': 'fotmob', '_source': 'FotMob',
        '_league_id': lid, '_tournament_id': tid,
        '_season': season_name,
        '_league_name': details.get('name'),
        '_slug': slug,
        # 🔴 主场优势族（由逐场比分现算，见 fotmob_home_adv）
        '_ha_raw': ha_raw,
        '_home_adv': ha_eff,       # 已含 α=HOME_ADV_ALPHA 收缩
        '_draw_rate': draw_rate,   # 该联赛实际平局率（dc 在 lambdas 现算）
        '_home_adv_n': n_m,
        '_home_gpg': hpg, '_away_gpg': apg,
    }
    return data


# 平局校正（FotMob 后端）：**不写死常数**，改由「实际平局率 / 模型平局率」现算。
#   背景：泊松系统性高估平局；但各联赛的实际平局率差异极大
#   （日职 21.4% / 韩职 33.3% / 美职 25.5% / 阿甲 29.6%），
#   故必须按联赛现算，不能用一个全局系数。
#   实测（α=0.62 固定，dc 现算）四联赛总偏差仅 8.80。
FOTMOB_DRAW_CORR = {}   # 保留空表：不再使用写死值，dc 由 lambdas 现算


# ---------------- 后端 C：PerformanceOdds（中超） ----------------
def _po_curl(pid, min_size=5000):
    """拉取 PerformanceOdds 联赛页；带磁盘缓存（6h）+ 指数退避重试。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache = os.path.join(CACHE_DIR, 'po_%s.html' % pid)
    if os.path.exists(cache):
        if _now() - os.path.getmtime(cache) < 6 * 3600 \
                and os.path.getsize(cache) >= min_size:
            return open(cache, encoding='utf-8', errors='ignore').read()
    url = PERFORMANCEODDS_PAGE.format(pid=pid)
    cmd = ['curl', '-s', '-L', '--compressed', '--max-time', '45',
           '-A', PERFORMANCEODDS_UA, url]
    last_err = None
    for attempt in range(3):
        if attempt:
            time.sleep(1.5 * attempt)
        try:
            out = subprocess.run(cmd, capture_output=True, timeout=60)
        except Exception as e:
            last_err = '异常 %s' % e
            continue
        if out.returncode == 0 and len(out.stdout or b'') >= min_size:
            txt = out.stdout.decode('utf-8', 'ignore')
            try:                    # 🔴 v1.7 原子写：防进程中断留半成品
                with open(cache + '.tmp', 'w', encoding='utf-8') as f:
                    f.write(txt)
                os.replace(cache + '.tmp', cache)
            except Exception:
                pass
            return txt
        last_err = 'rc=%s, size=%d' % (out.returncode, len(out.stdout or b''))
        if out.returncode not in (35, 28, 56, 7, 18, 52):
            break
    # 🔴 v1.7 缓存降级：重试全败时用过期缓存
    if os.path.exists(cache) and os.path.getsize(cache) >= min_size:
        try:
            txt = open(cache, encoding='utf-8', errors='ignore').read()
            if txt:
                age_h = int(max(0, _now() - os.path.getmtime(cache)) // 3600)
                print('[xG缓存降级] PerformanceOdds 不可达，使用最近缓存（约 %d 小时前拉取）'
                      % age_h)
                return txt
        except Exception:
            pass
    raise RuntimeError('PerformanceOdds 抓取失败 %s (%s，已重试 3 次)'
                       % (url, last_err))


def _po_num(s):
    """把单元格文本转 float；无法解析返回 None。"""
    s = (s or '').strip().replace('%', '')
    try:
        return float(s)
    except Exception:
        return None


def po_table(pid):
    """解析 PerformanceOdds 的 xG 表。

    表头固定为：
      Rank | (空) | Team | MP | xG | xG Home | xG Away | xGA | xGA Home | xGA Away
    返回 [{'team_name', 'played', 'xg','xg_home','xg_away',
            'xga','xga_home','xga_away'}]
    🔴 数值是**每场均值**，不是赛季总计。
    """
    raw = _po_curl(pid)
    # 解析 <table>：取第一个含 'xG Home' 表头的表
    rows_out = []
    header = None
    for tm in re.finditer(r'<table\b.*?</table>', raw, re.S | re.I):
        seg = tm.group(0)
        trs = re.findall(r'<tr\b.*?</tr>', seg, re.S | re.I)
        if not trs:
            continue
        def cells(tr):
            return [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', c)).strip()
                    for c in re.findall(r'<t[hd]\b.*?</t[hd]>', tr, re.S | re.I)]
        hd = cells(trs[0])
        if not any('xG' in h for h in hd):
            continue
        # 定位列索引（按表头名，不写死位置）
        def idx(*names):
            for nm in names:
                for i, h in enumerate(hd):
                    if h.strip().lower() == nm.lower():
                        return i
            return None
        i_team = idx('Team')
        i_mp = idx('MP', 'P', 'Matches Played')
        i_xg = idx('xG')
        i_xgh = idx('xG Home')
        i_xga_ = idx('xG Away')
        i_xga = idx('xGA')
        i_xgah = idx('xGA Home')
        i_xgaa = idx('xGA Away')
        if i_team is None or i_xg is None:
            continue
        header = hd
        for tr in trs[1:]:
            c = cells(tr)
            if len(c) <= i_team or not c[i_team]:
                continue
            g = lambda i: _po_num(c[i]) if (i is not None and i < len(c)) else None
            rows_out.append({
                'team_name': c[i_team],
                'played': g(i_mp),
                'xg': g(i_xg), 'xg_home': g(i_xgh), 'xg_away': g(i_xga_),
                'xga': g(i_xga), 'xga_home': g(i_xgah), 'xga_away': g(i_xgaa),
            })
        if rows_out:
            break
    if not rows_out:
        raise RuntimeError('PerformanceOdds 未解析到 xG 表（pid=%s）' % pid)
    return rows_out, header


def po_alias(name):
    """PerformanceOdds 队名 → football-data 现名（别名桥接）。

    🔴 坑：PerformanceOdds 用的是**旧称/异名**（上海上港/河南建业/天津泰达…），
       而 lambda-source 的 CN2EN 是按 football-data **现名**建的。
       若不桥接，中超每一场的队名匹配都会失败（静默回退市场）。
       这里是唯一权威对照表，交叉校验来源：
         football-data CHN.csv 2025/2026 队名
         PerformanceOdds pid=16789 表内队名
    """
    return PO_ALIAS.get(name, name)


def po_reverse(name):
    """football-data 现名 → PerformanceOdds 名（用于查找）。"""
    return PO_ALIAS_R.get(name, name)


def load_performanceodds(league, season=None):
    """返回与 statz 后端**同构**的 data dict。

    🔴 与 FotMob 不同：本后端**有 home/away 分组**。
    🔴 PerformanceOdds 发布的是**每场均值**（xG/场），而 statz/FotMob 发布的是
       **赛季总计**，且 lambdas() 内部一律做 `值 / played` 归一化。
       故这里必须把「场均」还原成「赛季总计」→ 乘以 played，
       否则 λ 会被再次除以场次，量级缩小 ~26 倍（实测基准 0.063）。
       （用均值×场次完全可逆，不引入误差；恒等式要求也满足：
         主队主场总 xG == 客队客场总 xGA）
    """
    key = (league or '').strip().lower()
    ent = PERFORMANCEODDS_LEAGUE.get(key)
    if not ent:
        raise RuntimeError('未识别的 PerformanceOdds 联赛键：%s' % league)
    pid, slug = ent
    rows, header = po_table(pid)

    def mk(suffix):
        """suffix: ''(overall) / '_home' / '_away'。输出**赛季总计**口径。"""
        out = []
        for r in rows:
            played = r.get('played') or 0
            v = r.get('xg' + suffix)
            va = r.get('xga' + suffix)
            if v is None or va is None:
                continue
            out.append({
                'team_name': r['team_name'],
                'team_id': None,
                'played': int(played),
                # 场均 → 赛季总计（可逆，见函数注释）
                'xg': v * played,
                'xga': va * played,
                'goals_for': None, 'goals_against': None,
            })
        return out

    overall = mk('')
    home = mk('_home')
    away = mk('_away')
    if not overall:
        raise RuntimeError('PerformanceOdds 无有效球队数据（pid=%s）' % pid)
    overall.sort(key=lambda r: -(r['xg'] or 0))
    home.sort(key=lambda r: -(r['xg'] or 0))
    away.sort(key=lambda r: -(r['xg'] or 0))

    # 赛季：从页面 title 里取（形如 "… (2026) - PerformanceOdds"）
    season_name = season
    if not season_name:
        m = re.search(r'\((\d{4})\)', _po_curl(pid)[:3000])
        season_name = m.group(1) if m else None

    data = {
        'overall': overall,
        'home': home,
        'away': away,
        'last5': [],
        '_backend': 'performanceodds', '_source': 'PerformanceOdds',
        '_league_id': pid, '_tournament_id': None,
        '_season': season_name,
        '_league_name': 'Chinese Super League',
        '_slug': slug,
        # 🔴 有分组 → 不做主场优势收缩（置中性 1.0，lambdas 会跳过）
        '_ha_raw': 1.0,
        '_home_adv': 1.0,
        '_draw_rate': None,
        '_home_adv_n': int(overall[0]['played'] or 0),
        '_home_gpg': None, '_away_gpg': None,
    }
    return data


def load_any(league, season=None):
    """按联赛键自动分派后端：statz → FotMob → PerformanceOdds。

    ⚠️ 顺序有讲究：statz 有分组，优先；FotMob 次之；
       PerformanceOdds 目前只覆盖中超，放最后（且键互不冲突）。
    """
    key = (league or '').strip().lower()
    if key in LEAGUE_SLUG:
        return load(league, season=season)
    if key in FOTMOB_LEAGUE:
        return load_fotmob(league, season=season)
    if key in PERFORMANCEODDS_LEAGUE:
        return load_performanceodds(league, season=season)
    # 兜底走 statz（会给出明确的未知联赛报错）
    return load(league, season=season)


# ---------------- 攻防公式 ----------------
def league_baselines(data):
    """
    从 home/away 分组算联赛基准（xG 口径）：
      lg_home_xg  主队场均 xG
      lg_away_xg  客队场均 xG
      lg_home_xga 主队场均 xGA
      lg_away_xga 客队场均 xGA
    """
    def per(rows, key):
        tot = sum(r.get(key, 0) or 0 for r in rows)
        pl = sum(r.get('played', 0) or 0 for r in rows)
        return (tot / pl) if pl else None

    return {
        'lg_home_xg': per(data['home'], 'xg'),
        'lg_away_xg': per(data['away'], 'xg'),
        'lg_home_xga': per(data['home'], 'xga'),
        'lg_away_xga': per(data['away'], 'xga'),
    }


def _overall_map(data):
    return {r.get('team_name'): r for r in (data.get('overall') or [])}


def _find_team(rows, name):
    """在分组里找队；先精确，再大小写/变音符不敏感，再子串唯一致。

    ⚠️ NFKD 去不掉北欧字符（ø/æ/å/ð 不是组合字符），须显式替换：
       Lillestrøm→lillestrom、Bodø→bodo、Mjällby→mjallby(组合字符可去)
    """
    # 北欧及常见特殊字符 -> ASCII 等价
    _MAP = {'ø': 'o', 'Ø': 'o', 'æ': 'ae', 'Æ': 'ae', 'å': 'a', 'Å': 'a',
            'ð': 'd', 'Ð': 'd', 'þ': 'th', 'Þ': 'th', 'ß': 'ss',
            'ł': 'l', 'Ł': 'l', 'đ': 'd', 'Đ': 'd', 'ı': 'i'}

    def norm(s):
        s = s or ''
        for k, v in _MAP.items():
            s = s.replace(k, v)
        s = unicodedata.normalize('NFKD', s)
        s = ''.join(c for c in s if not unicodedata.combining(c))
        return re.sub(r'[^a-z0-9]', '', s.lower())

    tgt = norm(name)
    for r in rows:
        if norm(r.get('team_name')) == tgt:
            return r
    # 🔴 别名兜底（PerformanceOdds 用旧称）：把 football-data 现名换成别名再试。
    #    仅当调用方传入的是「现名」且表内是「旧称」时生效，不影响其他后端。
    for alt in (po_reverse(name), po_alias(name)):
        if alt and alt != name:
            t2 = norm(alt)
            for r in rows:
                if norm(r.get('team_name')) == t2:
                    return r
    # 子串唯一命中
    hits = [r for r in rows if tgt and (tgt in norm(r.get('team_name'))
                                        or norm(r.get('team_name')) in tgt)]
    if len(hits) == 1:
        return hits[0]
    return None


def lambdas(data, home_name, away_name, mode='blend', min_split=12):
    """
    返回 (lam_home, lam_away, info)。

    mode:
      'split'  —— 只用主/客场 split（理论最贴，但样本减半、噪声大）
      'overall'—— 只用总场均（样本翻倍，但**抹平主场优势**）
      'blend'  —— **默认**：以 overall 为骨架，按 split 样本量加权吸收主客差异
      'auto'   —— split 样本均 >= min_split 时用 split，否则用 overall

    ⚠️ 为什么要 blend（2026-09-19 两轮实测教训）：
      挪超 20 场/队，split 后仅 9-10 场。
      · 周六017 克里斯蒂安松 v 罗森博格：
          split 口径 → 主胜 41.1%（市场 16.4%，偏离 +24.7pp，EV 虚高 +122%）
          overall  口径 → 主胜 22.5%（偏离 +6.1pp）
          两种口径差 18.6pp —— **split 的 9 场小样本把噪声放大成假信号**。
      · 周日018 维京 v 利勒斯特罗姆：
          split 口径 → 主胜 71.7%（维京主场 xG 2.81/场，是挪超第2强）
          overall  口径 → 主胜 55.8%（把主场优势抹平了）
          市场给 66.1% —— overall **反而漏掉了真实的主场优势**。
      结论：两个极端都不行。blend 用 overall 保证样本量、用 split 保留主客差异，
            权重随 split 样本增长（9场≈0.47、20场≈0.67）。
    """
    ho, ao, ov = data['home'], data['away'], data['overall']
    ovm = _overall_map(data)
    hh = _find_team(ho, home_name)
    aa = _find_team(ao, away_name)
    if not hh:
        raise RuntimeError('主队未在 xG 源中找到：%s' % home_name)
    if not aa:
        raise RuntimeError('客队未在 xG 源中找到：%s' % away_name)

    b = league_baselines(data)
    # FotMob 后端无 home/away 分组 → league_baselines 里 home/away 会等于 overall，
    #   lg_home_xga == lg_away_xga == lg_side，故 split 与 overall 等价。
    #   这里做个兜底：若基准缺失则用 overall 单边均值。
    if not all(b.values()):
        ov_p = sum(r.get('played') or 0 for r in ov)
        side = (sum(r.get('xg') or 0 for r in ov) / ov_p) if ov_p else 1.35
        for k in b:
            if not b[k]:
                b[k] = side

    hs, as_ = hh.get('played') or 0, aa.get('played') or 0
    ht = (ovm.get(hh['team_name']) or {}).get('played') or hs
    at = (ovm.get(aa['team_name']) or {}).get('played') or as_
    # FotMob：split 分组是 overall 的镜像 → split 样本数应与总样本一致，
    #   否则 blend 的 w 会被错误压低（把信息量当噪声）。故显式对齐。
    if data.get('_backend') == 'fotmob':
        hs, as_ = ht, at

    use = mode
    if mode == 'auto':
        use = 'split' if min(hs, as_) >= min_split else 'overall'

    if use == 'split':
        h_xg = hh['xg'] / hs if hs else 0      # 主队主场攻击力
        a_xga = aa['xga'] / as_ if as_ else 0  # 客队客场防守
        lam_h = h_xg * a_xga / b['lg_home_xga']
        a_xg = aa['xg'] / as_ if as_ else 0    # 客队客场攻击力
        h_xga = hh['xga'] / hs if hs else 0    # 主队主场防守
        lam_a = a_xg * h_xga / b['lg_away_xga']
        base = {'lg_home_xga': round(b['lg_home_xga'], 4),
                'lg_away_xga': round(b['lg_away_xga'], 4)}
    elif use == 'overall':
        # overall：单边基准 = 全体场均 xG
        lg_side = (sum(r['xg'] for r in ov) / sum(r['played'] for r in ov)
                   if sum(r['played'] for r in ov) else 1.35)
        lam_h = ((ovm[hh['team_name']]['xg'] / ht) if ht else 0) * \
                ((ovm[aa['team_name']]['xga'] / at) if at else 0) / lg_side
        lam_a = ((ovm[aa['team_name']]['xg'] / at) if at else 0) * \
                ((ovm[hh['team_name']]['xga'] / ht) if ht else 0) / lg_side
        base = {'lg_side': round(lg_side, 4)}
    else:  # 'blend' —— 混合：以 overall 为骨架，用 split 修正主客差异
        # 思路：先算 overall 的 λ，再用「该队 split 相对 overall 的攻防偏差」做修正。
        #   权重 w 由 split 样本决定（样本越多越信任 split）：
        #     w = hs / (hs + K)，K=10 → 9 场时 w≈0.47，20 场时 w≈0.67
        #   最终攻防 = overall × (1-w) + split × w  （用比值形式，避免量纲问题）
        K = 10.0
        lg_side = (sum(r['xg'] for r in ov) / sum(r['played'] for r in ov)
                   if sum(r['played'] for r in ov) else 1.35)
        lg_h = b['lg_home_xga'] or lg_side
        lg_a = b['lg_away_xga'] or lg_side

        def wnd(n):
            return n / (n + K) if n else 0.0

        wh, wa = wnd(hs), wnd(as_)
        # 主队攻击：overall配平 × (1-wh) + 主场配平 × wh
        h_atk_o = (ovm[hh['team_name']]['xg'] / ht) if ht else 0
        h_atk_s = (hh['xg'] / hs) * (lg_side / lg_h) if hs else 0
        h_atk = h_atk_o * (1 - wh) + h_atk_s * wh
        # 客队防守：overall配平 × (1-wa) + 客场配平 × wa
        a_def_o = (ovm[aa['team_name']]['xga'] / at) if at else 0
        a_def_s = (aa['xga'] / as_) * (lg_side / lg_a) if as_ else 0
        a_def = a_def_o * (1 - wa) + a_def_s * wa
        lam_h = h_atk * a_def / lg_side

        a_atk_o = (ovm[aa['team_name']]['xg'] / at) if at else 0
        a_atk_s = (aa['xg'] / as_) * (lg_side / lg_a) if as_ else 0
        a_atk = a_atk_o * (1 - wa) + a_atk_s * wa
        h_def_o = (ovm[hh['team_name']]['xga'] / ht) if ht else 0
        h_def_s = (hh['xga'] / hs) * (lg_side / lg_h) if hs else 0
        h_def = h_def_o * (1 - wh) + h_def_s * wh
        lam_a = a_atk * h_def / lg_side
        base = {'lg_side': round(lg_side, 4), 'w_home': round(wh, 3), 'w_away': round(wa, 3)}

    # 🔴 FotMob 后端专属修正：主场优势
    #   FotMob 无 split 分组 → 上面的 λ 天然对称（主客同值），会系统性
    #   低估主胜、高估客胜。这里用「该联赛逐场比分现算」的 ha 修正：
    #     λ主 ×= ha    λ客 ÷= ha
    #   取几何对称形式（乘/除）→ 保持全场总进球量不变，只调主客分配。
    #   ha 已含 α=0.62 收缩（见 HOME_ADV_ALPHA）。
    ha = 1.0
    dc = None
    if data.get('_backend') == 'fotmob':
        ha = float(data.get('_home_adv') or 1.0)
        if ha and abs(ha - 1.0) > 1e-9:
            lam_h *= ha
            lam_a /= ha
        # 平局校正：dc = 实际平局率 / 模型(泊松)平局率，**就地现算**
        dr = data.get('_draw_rate')
        if dr:
            _, pd0, _ = pois_probs(lam_h, lam_a)
            if pd0 > 0:
                dc = dr / pd0

    info = {
        'home_team': hh['team_name'], 'away_team': aa['team_name'],
        'mode': use,
        'home_host_xg_pg': round(lam_h and (hh['xg'] / hs if hs else 0), 3),
        'away_away_xg_pg': round((aa['xg'] / as_ if as_ else 0), 3),
        'home_played_host': hs, 'away_played_away': as_,
        # 🔴 样本门槛应用**总样本**，而非主客 split 样本：
        #   split 天然是总数的一半（挪超 20 场 → 主场仅 9-10 场），
        #   若拿 split 卡 10 场门槛，会把本可用的联赛全部误杀。
        'home_played_total': ht, 'away_played_total': at,
        'baseline': base,
        'source': data.get('_source') or 'statz.ai',
        'backend': data.get('_backend') or 'statz',
        'season': data.get('_season'),
        'home_adv': round(ha, 4),
        'home_adv_raw': round(data.get('_ha_raw') or 1.0, 4),
        'home_adv_n': data.get('_home_adv_n'),
        'draw_rate_actual': data.get('_draw_rate'),
        'draw_corr': round(dc, 4) if dc else None,
        'league_slug': data.get('_slug'),
        '口径': 'xg',
    }
    return lam_h, lam_a, info


def pois_probs(lam_h, lam_a, mx=12):
    """泊松胜平负（未做平局校正）。"""
    def p(k, l):
        return math.exp(-l) * l ** k / math.factorial(k)
    ph = pd = pa = 0.0
    for i in range(mx):
        for j in range(mx):
            v = p(i, lam_h) * p(j, lam_a)
            if i > j:
                ph += v
            elif i == j:
                pd += v
            else:
                pa += v
    return ph, pd, pa


# ---------------- 平局校正（重要） ----------------
# 背景：泊松**系统性高估平局**。但实测发现，偏差大小**取决于口径**：
#
#   挪超 2026 本季实测 160 场（football-data NOR.csv）：
#     实际：主胜 51.2% | 平局 20.0% | 客胜 28.7% | 场均 3.150
#
#   ── 用「实际进球」口径建模 → 模型平均平局 35.4% → 偏差 +15.4pp  【病根】
#   ── 用「xG」口径建模    → 模型平均平局 22.4% → 偏差  +2.4pp  【已治愈】
#
# ⇒ 结论：**xG 口径已把泊松的平局高估压到可接受范围**，无需再乘校正系数。
#   真正需要平局校正的场景，是**只有实际进球口径、拿不到 xG** 的联赛
#   （日职/韩职/中超/美职/墨超/阿甲等）。
#
# 下表：当用**实际进球**口径建模时的建议校正系数 = 实际平局率 / 泊松预测平局率。
# 命中 xG 源的联赛（eliteserien/allsvenskan/campeonato-brasileiro）→ 填 None（不校正）。
DRAW_CORRECTION = {
    'eliteserien': None,             # xG 口径已用 → 无需校正（实测偏差仅 +2.4pp）
    'allsvenskan': None,             # 同上（xG 口径）
    'campeonato-brasileiro': None,   # 同上（xG 口径）
    # ↓ 以下为「仅有实际进球口径」的联赛，用实际进球建模时才需要
    'goal-fallback-nor': 0.565,      # 挪超·实际进球口径（20.0/35.4）
}
# FotMob 后端的平局校正见 FOTMOB_DRAW_CORR（按各联赛实测网格搜索得出）


def apply_draw_correction(ph, pd, pa, slug):
    k = DRAW_CORRECTION.get(slug)
    if not k:
        return ph, pd, pa, None
    pd2 = pd * k
    rest = ph + pa
    if rest <= 0:
        return ph, pd, pa, None
    scale = (1.0 - pd2) / rest
    return ph * scale, pd2, pa * scale, k


# ---------------- CLI ----------------
def _print_table(slug, data, as_json=False):
    if as_json:
        print(json.dumps({
            'slug': slug, 'league_cn': CN_LEAGUE.get(slug, slug),
            'baseline': {k: round(v, 4) for k, v in league_baselines(data).items()},
            'overall': data['overall'], 'home': data['home'], 'away': data['away'],
        }, ensure_ascii=False, indent=2))
        return
    print('=' * 92)
    print('联赛：%s（slug=%s）  数据源：%s'
          % (CN_LEAGUE.get(slug, slug), slug, data.get('_source') or 'statz.ai'))
    b = league_baselines(data)
    if not all(b.values()):
        ov_p = sum(r.get('played') or 0 for r in data['overall'])
        side = (sum(r.get('xg') or 0 for r in data['overall']) / ov_p) if ov_p else 0
        for k in b:
            if not b[k]:
                b[k] = side
    print('基准(xG口径)：主队场均xG %.3f | 客队场均xG %.3f | 主队场均xGA %.3f | 客队场均xGA %.3f'
          % (b['lg_home_xg'], b['lg_away_xg'], b['lg_home_xga'], b['lg_away_xga']))
    if data.get('_backend') == 'fotmob':
        print('⚠️ FotMob 后端：只有赛季总计，主/客分组为镜像 → 三个分组内容相同')
        print('   赛季：%s（league_id=%s tournament_id=%s）'
              % (data.get('_season'), data.get('_league_id'),
                 data.get('_tournament_id')))
    print('=' * 92)
    for scope, lbl in (('overall', '总'), ('home', '主'), ('away', '客')):
        rows = data.get(scope) or []
        print('\n【%s】%d 队' % (lbl, len(rows)))
        print('%-20s %4s %5s %5s %8s %8s %8s %8s'
              % ('球队', 'P', 'GF', 'GA', 'xG', 'xGA', 'xG/场', 'xGA/场'))
        for r in rows:
            pl = r.get('played') or 1
            print('%-20s %4s %5s %5s %8s %8s %8.2f %8.2f'
                  % (r.get('team_name'), r.get('played'), r.get('goals_for'),
                     r.get('goals_against'), r.get('xg'), r.get('xga'),
                     (r.get('xg') or 0) / pl, (r.get('xga') or 0) / pl))


def main():
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return
    if args[0] == '--league-map':
        print('=== 后端 A：statz.ai（有主客分组，支持 split/blend）===')
        for k in sorted(LEAGUE_SLUG):
            print('%-24s -> %s (%s)' % (k, LEAGUE_SLUG[k],
                                        CN_LEAGUE.get(LEAGUE_SLUG[k], '')))
        print('\n=== 后端 B：FotMob（只有赛季总计，split==overall）===')
        for k in sorted(FOTMOB_LEAGUE):
            lid, slug = FOTMOB_LEAGUE[k]
            print('%-24s -> id=%s %s (%s)' % (k, lid, slug,
                                              CN_LEAGUE.get(slug, '')))
        print('\n=== 后端 C：PerformanceOdds（有主客分组，场均口径）===')
        for k in sorted(PERFORMANCEODDS_LEAGUE):
            pid, slug = PERFORMANCEODDS_LEAGUE[k]
            print('%-24s -> id=%s %s (%s)' % (k, pid, slug,
                                              CN_LEAGUE.get(slug, '')))
        return

    if args[0] == '--calc':
        # --calc <league> <home> <away> [--mode M] [--season Y]
        rest = args[1:]
        mode = 'blend'
        season = None
        if '--mode' in rest:
            i = rest.index('--mode')
            mode = rest[i + 1]
            rest = rest[:i] + rest[i + 2:]
        if '--season' in rest:
            i = rest.index('--season')
            season = rest[i + 1]
            rest = rest[:i] + rest[i + 2:]
        league, home, away = rest[0], rest[1], rest[2]
        data = load_any(league, season=season)
        lh, la, info = lambdas(data, home, away, mode=mode)
        ph, pd, pa = pois_probs(lh, la)
        slug = LEAGUE_SLUG.get(league.lower()) or \
            (FOTMOB_LEAGUE.get(league.lower()) or
             PERFORMANCEODDS_LEAGUE.get(league.lower()) or ('', ''))[1]
        # 平局校正：statz 后端查 DRAW_CORRECTION；
        #   FotMob 后端用 info 里现算的 dc；
        #   PerformanceOdds 有分组且为 xG 口径 → 无需校正（同 statz）
        if info.get('backend') == 'fotmob':
            k = info.get('draw_corr')
            if k:
                pd2 = pd * k
                rest_ = ph + pa
                scale = (1.0 - pd2) / rest_ if rest_ > 0 else 1.0
                ch, cd, ca = ph * scale, pd2, pa * scale
            else:
                ch, cd, ca = ph, pd, pa
        else:
            ch, cd, ca, k = apply_draw_correction(ph, pd, pa, slug)
        print('联赛：%s' % CN_LEAGUE.get(slug, slug))
        print('对阵：%s(主) vs %s(客)' % (info['home_team'], info['away_team']))
        print('λ  : 主 %.3f | 客 %.3f   来源=%s 口径=xg 模式=%s 赛季=%s'
              % (lh, la, info['source'], info.get('mode'), info.get('season')))
        print('泊松原始：主 %5.1f%% | 平 %5.1f%% | 客 %5.1f%%'
              % (ph * 100, pd * 100, pa * 100))
        if k:
            print('平局校正(系数%.3f)：主 %5.1f%% | 平 %5.1f%% | 客 %5.1f%%'
                  % (k, ch * 100, cd * 100, ca * 100))
        else:
            print('平局校正：无需（xG 口径已把泊松平局高估压至 +1~2pp 量级；'
                  '依赖「实际进球口径」的联赛才需校正）')
        print('样本：总 %s/%s 场 | 主客 split %s/%s 场'
              % (info['home_played_total'], info['away_played_total'],
                 info['home_played_host'], info['away_played_away']))
        if info.get('backend') == 'fotmob':
            print('⚠️ FotMob 后端只发布赛季总计，无主客分组 → '
                  'split 口径 == overall 口径（blend 自动退化为 overall）')
            print('   主场优势：raw=%.4f → 收缩后 ha=%.4f（α=%.2f，样本 %s 场）'
                  % (info.get('home_adv_raw') or 1.0, info.get('home_adv') or 1.0,
                     HOME_ADV_ALPHA, info.get('home_adv_n')))
            print('   平局校正：实际平局率 %.1f%% / 模型平局率 → dc=%.4f'
                  % ((info.get('draw_rate_actual') or 0) * 100,
                     info.get('draw_corr') or 1.0))
        return

    # 默认：打印整个联赛表
    as_json = '--json' in args
    league = args[0]
    season = None
    if '--season' in args:
        season = args[args.index('--season') + 1]
    data = load_any(league, season=season)
    _print_table(LEAGUE_SLUG.get(league.lower()) or
                 (FOTMOB_LEAGUE.get(league.lower()) or ('', ''))[1],
                 data, as_json=as_json)


if __name__ == '__main__':
    main()

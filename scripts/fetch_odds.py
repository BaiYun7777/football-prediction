#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_odds.py — 竞彩足球实时赔率抓取（足彩推荐流水线数据源 · v1.1 · 2026-10-19）

用法:
    python3 fetch_odds.py                          # 自动模式：browser 快速试探 → curl 兜底
    python3 fetch_odds.py --mode browser           # 强制浏览器通道（3 轮指数退避，手动调试用）
    python3 fetch_odds.py --mode curl              # 强制 curl 通道（任务端云沙箱快路径）
    python3 fetch_odds.py --date 2026-10-20        # 指定 businessDate（默认当天）
    python3 fetch_odds.py --out /tmp/x.json        # 指定输出路径（默认 /tmp/odds_live_<日期>.json）

输出: 归一化 JSON（businessDate/matchNumDate/fetchedAt/matches[]，每场含四池赔率 +
      updateDate+updateTime + age_hours + single + matchStatus + poolStatus），
       stdout 打印摘要与时效统计；失败 exit 2（调用方回退到内嵌快照块）。

═══════════════════════════════════════════════════════════════════════
通道设计（2026-10-19 v1.1 · 任务端时间预算驱动）
═══════════════════════════════════════════════════════════════════════
auto 模式 = browser 快速单轮试探（约 40s）→ curl 兜底（约 15s）→ FETCH_FAIL。
**刻意不在 auto 内长退避**：WAF 临时屏蔽恢复期 10-30 分钟（10-19 实测屏蔽持续
超过 1 小时），单次任务执行窗内长睡无意义——快速失败让调用方按步骤 2b/2c
回退，次日 IP 恢复后自动恢复实时抓取。完整 3 轮指数退避（60/120s）仅
--mode browser 手动调试时启用。

═══════════════════════════════════════════════════════════════════════
通道说明（2026-10-19 实测存档）
═══════════════════════════════════════════════════════════════════════
webapi.sporttery.cn 前置腾讯云 EdgeOne WAF：
  - 顶层导航（Sec-Fetch-Mode: navigate）→ 567 拦截
  - Python urllib / 裸 curl → 403/567（TLS 指纹 + 无会话）
  - ✅ 可行路径 = 无头 Chromium 先访问 www.sporttery.cn 首页建立会话
    （等风控 SDK apkdata 落地），再用 page.request 以 XHR 语义头
    （Origin + Referer + Sec-Fetch-Mode: cors + Sec-Fetch-Site: same-site）调接口。
  - ⚠️ WAF 有行为评分：短时间高频打接口会触发临时 IP 屏蔽（403 升级）。
    生产用法（每日 1-2 次）无虞；调试请克制。被封后等 10-30 分钟恢复。
  - 任务端云沙箱历史上裸 curl 直连即可通（IP 声誉不同），故保留 curl 兜底通道。

接口坑位档案（任务 prompt v4.0.0 世代实战沉淀）:
  1. getMatchCalculatorV1.qry 不带 poolCode → 四池全返（约 91KB）；
     带多个 poolCode（如 hhad,had,ttg,hafu）时 had 会被遮蔽恒空 —— 要么不带，要么分池单抓。
  2. value.matchInfoList 按 businessDate 分桶，len 恒为 1，
     真实场次在 matchInfoList[0].subMatchList。
  3. 缺池归因看 poolList[]：poolCode 在列且 poolStatus=Selling 但赔率空
     → 抓取问题，按池重抓；poolCode 不在列 → 官方确实未开售，不得重试。
  4. updateDate+updateTime 必须成对读取，严禁只读 updateTime 推日期。
"""
import argparse, json, subprocess, sys, time
from datetime import datetime

API_URL = "https://webapi.sporttery.cn/gateway/jc/football/getMatchCalculatorV1.qry"
HOME_URL = "https://www.sporttery.cn/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
XHR_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": HOME_URL,
    "Origin": "https://www.sporttery.cn",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}
POOLS = ["had", "hhad", "hafu", "ttg"]
POOL_CODE = {"had": "HAD", "hhad": "HHAD", "hafu": "HAFU", "ttg": "TTG"}


def _valid_payload(body: str):
    """有效负载 = JSON 且含 value.matchInfoList[0].subMatchList"""
    try:
        d = json.loads(body)
    except Exception:
        return None
    try:
        if isinstance(d["value"]["matchInfoList"][0]["subMatchList"], list):
            return d
    except Exception:
        pass
    return None


# ─────────────────────────── 通道一：curl 二进制（任务端云沙箱快路径） ───────────────────────────
def fetch_via_curl(date_str: str, tries: int = 2):
    url = f"{API_URL}?param=90,0" + (f"&businessDate={date_str}" if date_str else "")
    hdr_args = []
    for k, v in XHR_HEADERS.items():
        hdr_args += ["-H", f"{k}: {v}"]
    for i in range(tries):
        try:
            r = subprocess.run(["curl", "-s", "--max-time", "20", "--compressed", url] + hdr_args,
                               capture_output=True, text=True, timeout=30)
            d = _valid_payload(r.stdout)
            if d:
                return d
            print(f"[curl] 第{i+1}次无效负载: {r.stdout[:60]}", file=sys.stderr)
        except Exception as e:
            print(f"[curl] 第{i+1}次 {type(e).__name__}: {e}", file=sys.stderr)
        if i < tries - 1:
            time.sleep(5)
    return None


# ─────────────────────────── 通道二：无头浏览器（本沙箱实测可行） ───────────────────────────
def fetch_via_browser(date_str: str, rounds: int = 3, backoff: bool = True):
    """playwright + 首页会话 + page.request。

    rounds=1 & backoff=False：快速单轮试探（约 40s），auto 模式首试用。
    rounds=3 & backoff=True：完整指数退避（60/120s），--mode browser 手动调试用。
    WAF 行为评分触发的临时屏蔽恢复期 10-30 分钟，单次任务执行窗内长睡无意义，
    故 auto 模式刻意不启用长退避——快速失败，让调用方走 2b/2c 回退。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[browser] playwright 不可用", file=sys.stderr)
        return None
    suffix = f"&businessDate={date_str}" if date_str else ""
    urls = [f"{API_URL}?param=90,0{suffix}",
            f"{API_URL}?param=90,0&poolCode=had&channel=c"]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = browser.new_context(user_agent=UA, locale="zh-CN")
        page = ctx.new_page()
        result = None
        for rnd in range(rounds):
            # 每轮重建首页会话（刷新 WAF 行为上下文）
            try:
                page.goto(HOME_URL, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)
            except Exception as e:
                print(f"[browser] 第{rnd+1}轮首页会话失败: {e}", file=sys.stderr)
            for url in urls:
                try:
                    r = ctx.request.get(url, headers=XHR_HEADERS, timeout=25000)
                    d = _valid_payload(r.text())
                    if d:
                        result = d
                        break
                    print(f"[browser] 第{rnd+1}轮 {r.status}: {r.text()[:50]}", file=sys.stderr)
                except Exception as e:
                    print(f"[browser] 第{rnd+1}轮 {type(e).__name__}: {e}", file=sys.stderr)
            if result:
                break
            if backoff and rnd < rounds - 1:
                wait = 60 * (rnd + 1)
                print(f"[browser] WAF 退避 {wait}s 后重建会话重试", file=sys.stderr)
                time.sleep(wait)
        browser.close()
        return result


# ─────────────────────────── 归一化 ───────────────────────────
def normalize(raw: dict) -> dict:
    bucket = raw["value"]["matchInfoList"][0]
    fetched_at = datetime.now()
    matches = []
    for m in bucket.get("subMatchList", []):
        listed = {p.get("poolCode"): p for p in m.get("poolList", [])}
        single = bool(listed["HAD"].get("single")) if "HAD" in listed else None
        rec = {
            "num": m.get("matchNumStr"),
            "matchId": m.get("matchId"),
            "home": m.get("homeTeamAllName"),
            "away": m.get("awayTeamAllName"),
            "league": m.get("leagueAbbName"),
            "kickoff": f"{m.get('matchDate')} {str(m.get('matchTime'))[:5]}",
            "matchStatus": m.get("matchStatus"),
            "sellStatus": m.get("sellStatus"),
            "single": single,
            "pools": {},
        }
        for pool in POOLS:
            po = m.get(pool) or {}
            if not po:
                continue
            entry = {"updateDate": po.get("updateDate"), "updateTime": po.get("updateTime"),
                     "poolStatus": listed.get(POOL_CODE[pool], {}).get("poolStatus")}
            if pool == "had":
                entry["odds"] = {"h": po.get("h"), "d": po.get("d"), "a": po.get("a")}
            elif pool == "hhad":
                entry["odds"] = {"h": po.get("h"), "d": po.get("d"), "a": po.get("a"),
                                 "goalLine": po.get("goalLine")}
            elif pool == "hafu":
                entry["odds"] = {k: po.get(k) for k in
                                 ["hh", "hd", "ha", "dh", "dd", "da", "ah", "ad", "aa"]}
            elif pool == "ttg":
                entry["odds"] = {k: po.get(k) for k in
                                 ["s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7"]}
            if po.get("updateDate") and po.get("updateTime"):
                try:
                    t = datetime.strptime(f"{po['updateDate']} {po['updateTime']}", "%Y-%m-%d %H:%M:%S")
                    entry["age_hours"] = round((fetched_at - t).total_seconds() / 3600, 1)
                except Exception:
                    pass
            rec["pools"][pool] = entry
        matches.append(rec)
    return {
        "source": "sporttery.cn getMatchCalculatorV1.qry",
        "businessDate": bucket.get("businessDate"),
        "matchNumDate": bucket.get("matchNumDate"),
        "fetchedAt": fetched_at.strftime("%Y-%m-%d %H:%M:%S"),
        "matchCount": len(matches),
        "matches": matches,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="", help="businessDate YYYY-MM-DD，默认当天")
    ap.add_argument("--mode", default="auto", choices=["auto", "curl", "browser"])
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    raw, via = None, None
    if args.mode == "auto":
        # auto = browser 快速单轮（约40s）→ curl 兜底（约15s）→ FETCH_FAIL。
        # 刻意不启用长退避：WAF 屏蔽恢复期 10-30 分钟，单次任务执行窗内长睡无意义，
        # 快速失败让调用方按 2b/2c 回退，次日 IP 恢复自动恢复实时抓取。
        # 完整 3 轮指数退避仅 --mode browser 手动调试时启用。
        raw = fetch_via_browser(date_str, rounds=1, backoff=False)
        if raw:
            via = "browser"
        else:
            print("[auto] browser 快速试探未通，切换 curl 通道", file=sys.stderr)
            raw = fetch_via_curl(date_str)
            if raw:
                via = "curl"
    else:
        raw = fetch_via_curl(date_str) if args.mode == "curl" else fetch_via_browser(date_str)
        if raw:
            via = args.mode
    if raw is None:
        print("FETCH_FAIL: 所有通道均未取得有效数据（WAF 临时屏蔽/网络不可达）——"
              "调用方应回退到内嵌快照块并如实标注", file=sys.stderr)
        sys.exit(2)

    data = normalize(raw)
    data["fetchedVia"] = via
    out = args.out or f"/tmp/odds_live_{date_str.replace('-', '')}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    print(f"FETCH_OK via={via} businessDate={data['businessDate']} "
          f"期号={data['matchNumDate']} 场数={data['matchCount']} -> {out}")
    fresh = stale = 0
    for m in data["matches"]:
        had = m["pools"].get("had")
        age = had.get("age_hours") if had else None
        flag = ""
        if age is not None:
            if age <= 24:
                fresh += 1
            else:
                stale += 1
                flag = f"  ⚠️陈旧{age}h"
        odds = f"{had['odds']['h']}/{had['odds']['d']}/{had['odds']['a']}" if had else "—"
        sg = "可单关" if m["single"] else "仅串"
        print(f"  {m['num']} {m['home']} v {m['away']} [{m['league']}] {m['kickoff']} "
              f"HAD {odds} 单关={sg} 状态={m['matchStatus']}{flag}")
    print(f"[时效] HAD 24h内={fresh} 陈旧>24h={stale}")
    sys.exit(0)


if __name__ == "__main__":
    main()

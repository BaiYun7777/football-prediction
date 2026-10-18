import json, urllib.parse, urllib.request, datetime
sendkey = "SCT384767TZNO2cRRvt3MzQdmHLdl0RCN9"
today = datetime.date.today().isoformat()
hhmm = datetime.datetime.now().strftime("%H:%M")
# 同日重复执行时，把 suffix 置为 f" · 重跑{hhmm}" 或 f" · 沿用{hhmm}"；当日首次执行置为 ""
suffix = ""
title = f"足彩每日复盘 {today} · 升级建议待你决定{suffix}"
path = f"/workspace/每日复盘-{today.replace('-','')}.md"
try:
    desp = open(path, encoding="utf-8").read()
except Exception as e:
    desp = f"报告生成失败: {e}"
# 🔴 v3.6.0-r15：全文直发（10-08 实证 Server酱不截 4000，4000 硬切废止）；
# 保险丝：>30000 字符属报告失控，截断至 30000 并尾部显式标注，严禁无声丢失
if len(desp) > 30000:
    desp = desp[:30000] + f"\n\n---\n🔴 报告超长（{len(desp)}字符）已截断至 30000——报告失控事故，须精简结构后重跑"
url = f"https://sctapi.ftqq.com/{sendkey}.send"
data = urllib.parse.urlencode({"title": title, "desp": desp}).encode()
req = urllib.request.Request(url, data=data, method="POST")
resp = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
print("code:", resp.get("code"), "| message:", resp.get("message"))
pushid = resp.get("data", {}).get("pushid")
readkey = resp.get("data", {}).get("readkey")
if pushid and readkey:
    rc = f"https://sctapi.ftqq.com/push?id={pushid}&readkey={readkey}"
    r2 = json.loads(urllib.request.urlopen(rc, timeout=30).read().decode())
    wx = r2.get("data", {}).get("wxstatus")
    if isinstance(wx, str):
        try:
            wx = json.loads(wx)
        except Exception:
            pass
    if isinstance(wx, dict):
        print("微信送达:", wx.get("errcode") == 0, "| errmsg:", wx.get("errmsg"))

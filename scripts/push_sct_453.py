import json, urllib.parse, urllib.request, datetime
sendkey = "SCT384767TZNO2cRRvt3MzQdmHLdl0RCN9"
today = datetime.date.today().isoformat()
title = f"足彩推荐 {today}"
path = f"/workspace/足彩推荐-{today.replace('-','')}.md"
try:
    desp = open(path, encoding="utf-8").read()
except Exception as e:
    desp = f"(报告未生成: {e})"
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
    if isinstance(wx, dict):
        print("微信送达:", wx.get("errcode") == 0, "| errmsg:", wx.get("errmsg"))

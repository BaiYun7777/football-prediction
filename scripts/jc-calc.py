import math
def pmf(k,l): return math.exp(-l)*l**k/math.factorial(k) if l>0 else (1.0 if k==0 else 0.0)
def tau(x,y,a,b,r=-0.05):
    if x==0 and y==0: return 1-a*b*r
    if x==0 and y==1: return 1+a*r
    if x==1 and y==0: return 1+b*r
    if x==1 and y==1: return 1-r
    return 1.0
def mx(l1,l2,mg=12):
    m={(i,j):pmf(i,l1)*pmf(j,l2)*tau(i,j,l1,l2) for i in range(mg+1) for j in range(mg+1)}
    s=sum(m.values()); return {k:v/s for k,v in m.items()}
def hhad(m,gl):          # gl=让球数，正=主受让（如 +1）；负=主让球（如 -3）
    h=d=a=0.0
    for (i,j),p in m.items():
        z=i-j+gl
        if z>0: h+=p
        elif z==0: d+=p
        else: a+=p
    return h,d,a
def ttg(m):
    o=[0.0]*8
    for (i,j),p in m.items(): o[min(i+j,7)]+=p
    return o
def devig(odds):         # 竞彩赔率 -> 去水共识概率（超赔约 12.7%）
    r=[1.0/o for o in odds]; s=sum(r); return [x/s for x in r]
# 例：m=mx(1.55,1.25); print(hhad(m,+1)); print(devig([1.43,4.20,5.20]))
# ⚠️ 本块为 jc-calc.py 内联副本，改 jc-calc.py 必须同步改此处（见上方维护提示）

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GMI 数据抓取脚本（行业优先版）
  美股      -> Finnhub 免费 API (需环境变量 FINNHUB_API_KEY)
  A股/港股  -> akshare (封装东方财富/新浪，免费)

行业优先机制（重点关注：AI / 科技 / 能源 / 太空 / 通信 / 生物科学）：
  · 每条新闻/动态/新股按关键词打 sectors 标签
  · 命中关注赛道的条目【排到最前】（稳定排序，不丢弃其它条目）
  · 美股：额外按赛道维护重点个股清单，抓 company-news（真·行业内容）
  · A股：额外抓概念板块，挑出关注赛道的热门板块

容错：每块独立 try/except；抓失败保留上次成功的 JSON，绝不写空覆盖。
"""
import os, json, time, datetime, traceback

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ========== 关注赛道：id, 中文, 英文, 关键词(中英混合,小写匹配) ==========
SECTORS = [
  ("ai",     "AI产业", "AI",
     ["人工智能","大模型","算力","智算","机器学习","生成式","深度学习","gpu","openai","英伟达",
      "nvidia","chatgpt","llm","artificial intelligence","deepseek","anthropic","ai "]),
  ("tech",   "科技", "Tech",
     ["半导体","芯片","晶圆","科技","软件","云计算","量子","数据中心","操作系统",
      "semiconductor","chip","quantum","cloud","software","data center","wafer"]),
  ("comm",   "通信", "Comms",
     ["5g","6g","通信","运营商","基站","光模块","光通信","物联网","卫星通信",
      "telecom","network","fiber","wireless","broadband"]),
  ("energy", "能源", "Energy",
     ["能源","新能源","光伏","锂电","储能","氢能","核电","风电","油气","充电桩",
      "solar","battery","lithium","nuclear","renewable","hydrogen","oil","gas ","energy"]),
  ("space",  "太空", "Space",
     ["航天","卫星","火箭","太空","商业航天","深空","低轨",
      "space","satellite","rocket","launch","aerospace","orbital","spacex"]),
  ("bio",    "生物科学", "Bio",
     ["生物","医药","基因","创新药","疫苗","细胞","抗体","制药","mrna",
      "biotech","pharma","gene","vaccine","clinical","therapeutics","fda","biopharma"]),
]
SECTOR_IDS = [s[0] for s in SECTORS]

def tag(*texts):
    blob = " ".join(str(t) for t in texts if t).lower()
    return [sid for sid,_,_,kws in SECTORS if any(k in blob for k in kws)]

def prioritize(items):
    """命中赛道的排前（稳定排序保留各自原始顺序）"""
    items.sort(key=lambda x: 0 if x.get("sectors") else 1)
    return items

# 美股各赛道重点个股（抓 company-news 用）
US_WATCH = {
  "ai":    ["NVDA","AMD","PLTR"],
  "tech":  ["MSFT","AAPL","TSM","AVGO"],
  "comm":  ["CSCO","TMUS","ERIC"],
  "energy":["FSLR","ENPH","XOM"],
  "space": ["RKLB","ASTS","LMT"],
  "bio":   ["MRNA","REGN","CRSP"],
}

# ---------- 工具 ----------
def now_iso(tz_hours):
    tz = datetime.timezone(datetime.timedelta(hours=tz_hours))
    return datetime.datetime.now(tz).isoformat(timespec="seconds")

def load_existing(market):
    p = os.path.join(DATA_DIR, f"{market}.json")
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f: return json.load(f)
        except Exception: pass
    return {}

def write_json(market, obj):
    p = os.path.join(DATA_DIR, f"{market}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"  [写入] {market}.json  指数{len(obj.get('indices',[]))} 新闻{len(obj.get('news',[]))} "
          f"动态{len(obj.get('corporate',[]))} 新股{len(obj.get('ipo',[]))} 板块{len(obj.get('boards',[]))}")

def pick(row, *names, default=""):
    for n in names:
        if n in row and str(row[n]).strip() not in ("", "nan", "None", "-"):
            return row[n]
    return default

def to_num(x, default=0.0):
    try: return float(str(x).replace(",", "").replace("%", "").strip())
    except Exception: return default

def section(market, name, fn):
    try:
        out = fn(); print(f"  [OK] {market}.{name}: {len(out)} 条"); return out
    except Exception as e:
        print(f"  [FAIL] {market}.{name}: {e}"); return None

# ---------- 语言过滤: 仅保留中文 / 英文 (排除日韩泰阿拉伯西里尔等) ----------
import re as _re
_R_ZH = _re.compile(r"[\u4e00-\u9fff]")
_R_EN = _re.compile(r"[a-zA-Z]")
_R_JK = _re.compile(r"[\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]")   # 平/片假名、谚文
_R_CY = _re.compile(r"[\u0400-\u04ff]")                              # 西里尔
_R_AR = _re.compile(r"[\u0600-\u06ff]")                              # 阿拉伯
_R_TH = _re.compile(r"[\u0e00-\u0e7f]")                              # 泰文
def is_zh_or_en(text: str) -> bool:
    if not text: return False
    return bool(_R_ZH.search(text) or _R_EN.search(text)) and \
           not _R_JK.search(text) and not _R_CY.search(text) and \
           not _R_AR.search(text) and not _R_TH.search(text)
def filt(items, key=None):
    """过滤掉非中英内容; key 默认取 'title'/'title_zh'/'name_zh'/'name_en' 之一"""
    def _k(it):
        if key: return it.get(key, "")
        for k in ("title_zh", "title_en", "name_zh", "name_en", "title", "name"):
            v = it.get(k)
            if v: return v
        return ""
    return [it for it in items if is_zh_or_en(_k(it))]

def finalize(name, obj, old, keys=("indices","news","corporate","ipo")):
    """失败的板块用旧数据补；过滤非中英内容；对内容板块做赛道优先排序"""
    for k in keys:
        if obj.get(k) is None: obj[k] = old.get(k, [])
    for k in ("news","corporate","ipo"):
        if isinstance(obj.get(k), list):
            obj[k] = filt(obj[k])          # 过滤掉日韩泰阿拉伯等非中英内容
            prioritize(obj[k])
    return obj

# =========================================================
#  美股 — Finnhub
# =========================================================
def fetch_us():
    import requests
    KEY = os.environ.get("FINNHUB_API_KEY", "").strip()
    BASE = "https://finnhub.io/api/v1"
    old = load_existing("us")
    if not KEY:
        print("  [跳过] 未设置 FINNHUB_API_KEY，保留旧 us.json"); return old or {}

    def get(path, **params):
        params["token"] = KEY
        r = requests.get(f"{BASE}{path}", params=params, timeout=20); r.raise_for_status()
        return r.json()

    def indices():
        out=[]
        for sym, zh, en in [("SPY","标普500","S&P 500"),("QQQ","纳斯达克100","Nasdaq 100"),("DIA","道琼斯","Dow Jones")]:
            q = get("/quote", symbol=sym)
            out.append({"name_zh":zh,"name_en":en,"value":to_num(q.get("c")),
                        "change":to_num(q.get("d")),"change_pct":to_num(q.get("dp"))})
        return out

    def news():
        seen=set(); out=[]
        frm=(datetime.date.today()-datetime.timedelta(days=3)).isoformat()
        to=datetime.date.today().isoformat()
        # 1) 各赛道重点个股的 company-news（真行业内容）
        for sid, syms in US_WATCH.items():
            for sym in syms:
                try: arr = get("/company-news", symbol=sym, **{"from":frm,"to":to})[:2]
                except Exception: arr=[]
                for a in arr:
                    h=a.get("headline","")
                    if not h or h in seen: continue
                    seen.add(h); ts=a.get("datetime",0)
                    tm=datetime.datetime.fromtimestamp(ts,datetime.timezone(datetime.timedelta(hours=-4))).strftime("%m-%d %H:%M") if ts else ""
                    out.append({"time":tm,"title_en":h,"title_zh":h,
                                "summary_en":a.get("summary",""),"summary_zh":a.get("summary",""),
                                # 上下文标签(标注原文来源语言 + 待翻译状态),前端可显示在副标题位
                                "context_en":f"📰 Source: {sym} · {a.get('source','')} · English original",
                                "context_zh":f"📰 来源: {sym} · {a.get('source','')} · 英文原文(未翻译)",
                                "source":f"{sym} · "+a.get("source",""),"url":a.get("url",""),
                                "sectors":sorted(set([sid]+tag(h,a.get("summary",""))))})
                time.sleep(0.2)
        # 2) 大盘综合新闻（补充，打标签）
        for a in get("/news", category="general")[:20]:
            h=a.get("headline","")
            if not h or h in seen: continue
            seen.add(h); ts=a.get("datetime",0)
            tm=datetime.datetime.fromtimestamp(ts,datetime.timezone(datetime.timedelta(hours=-4))).strftime("%m-%d %H:%M") if ts else ""
            out.append({"time":tm,"title_en":h,"title_zh":h,
                        "summary_en":a.get("summary",""),"summary_zh":a.get("summary",""),
                        "context_en":f"📰 Source: Finnhub / {a.get('source','')} · English original",
                        "context_zh":f"📰 来源: Finnhub / {a.get('source','')} · 英文原文(未翻译)",
                        "source":"Finnhub / "+a.get("source",""),"url":a.get("url",""),
                        "sectors":tag(h,a.get("summary",""))})
        return out

    def corporate():
        today=datetime.date.today()
        data=get("/calendar/earnings",**{"from":today.isoformat(),"to":(today+datetime.timedelta(days=10)).isoformat()}).get("earningsCalendar",[])[:30]
        out=[]
        for e in data:
            sym=e.get("symbol","")
            out.append({"tag":"earnings",
                        "title_en":f"{sym} earnings · EPS est {e.get('epsEstimate','-')}",
                        "title_zh":f"{sym} 财报 · 预期EPS {e.get('epsEstimate','-')}",
                        "code":sym,"time":e.get("date",""),"sectors":tag(sym)})
        return out

    def ipo():
        today=datetime.date.today()
        data=get("/calendar/ipo",**{"from":today.isoformat(),"to":(today+datetime.timedelta(days=30)).isoformat()}).get("ipoCalendar",[])[:30]
        out=[]
        for p in data:
            price=p.get("price",""); nm=p.get("name","")
            out.append({"name_en":nm,"name_zh":nm,"code":p.get("symbol",""),"date":p.get("date",""),
                        "price":(f"${price}" if price else ""),"market_en":p.get("exchange",""),
                        "market_zh":p.get("exchange",""),"sectors":tag(nm)})
        return out

    obj={"market":"us","updated_at":now_iso(-4),
         "indices":section("us","indices",indices),"news":section("us","news",news),
         "corporate":section("us","corporate",corporate),"ipo":section("us","ipo",ipo)}
    return finalize("us", obj, old)

# =========================================================
#  A股 — akshare
# =========================================================
def fetch_cn():
    import akshare as ak
    old = load_existing("cn")

    def indices():
        df=ak.stock_zh_index_spot_em(symbol="沪深重要指数")
        want={"上证指数":"SSE Composite","深证成指":"SZSE Component","创业板指":"ChiNext","沪深300":"CSI 300"}
        out=[]
        for r in df.to_dict("records"):
            nm=str(pick(r,"名称","name"))
            if nm in want:
                out.append({"name_zh":nm,"name_en":want[nm],"value":to_num(pick(r,"最新价","最新","price")),
                            "change":to_num(pick(r,"涨跌额")),"change_pct":to_num(pick(r,"涨跌幅"))})
        return out

    def news():
        df=ak.stock_info_global_em()
        out=[]
        for r in df.head(30).to_dict("records"):
            title=str(pick(r,"标题","title")); summ=str(pick(r,"摘要","内容","summary"))[:120]
            out.append({"time":str(pick(r,"发布时间","时间","datetime"))[-8:-3] if pick(r,"发布时间","时间") else "",
                        "title_zh":title,"title_en":title,"summary_zh":summ,
                        "source":"东方财富","url":str(pick(r,"链接","url",default="")),
                        "sectors":tag(title,summ)})
        return out

    def corporate():
        df=ak.stock_info_cjzc_em()
        out=[]
        for r in df.head(25).to_dict("records"):
            title=str(pick(r,"标题","title","内容"))[:60]
            out.append({"tag":"公告","title_zh":title,
                        "time":str(pick(r,"发布时间","时间",default="今日"))[-8:-3] if pick(r,"发布时间","时间") else "今日",
                        "code":"","sectors":tag(title)})
        return out

    def ipo():
        df=ak.stock_xgsglb_em(symbol="全部股票")
        out=[]
        for r in df.head(25).to_dict("records"):
            nm=str(pick(r,"股票简称","名称","简称"))
            out.append({"name_zh":nm,"code":str(pick(r,"股票代码","代码")),
                        "date":str(pick(r,"申购日期","发行日期"))[-5:] if pick(r,"申购日期","发行日期") else "",
                        "price":("¥"+str(pick(r,"发行价格","发行价"))) if pick(r,"发行价格","发行价") else "",
                        "market_zh":str(pick(r,"板块",default="A股")),"sectors":tag(nm)})
        return out

    def boards():
        df=ak.stock_board_concept_name_em()
        out=[]
        for r in df.to_dict("records"):
            nm=str(pick(r,"板块名称","名称","板块"))
            s=tag(nm)
            if s: out.append({"name":nm,"change_pct":to_num(pick(r,"涨跌幅")),"sectors":s})
        out.sort(key=lambda x:-x["change_pct"])
        return out[:12]

    obj={"market":"cn","updated_at":now_iso(8),
         "indices":section("cn","indices",indices),"news":section("cn","news",news),
         "corporate":section("cn","corporate",corporate),"ipo":section("cn","ipo",ipo),
         "boards":section("cn","boards",boards)}
    obj=finalize("cn", obj, old)
    if obj.get("boards") is None: obj["boards"]=old.get("boards",[])
    return obj

# =========================================================
#  港股 — akshare
#  企业动态：stock_hk_profit_forecast_et (券商研报/业绩预测)
#  IPO 参考：stock_zh_ah_spot_em (A+H 双重上市,头部几条作准新股参考)
# =========================================================
def fetch_hk():
    import akshare as ak
    old = load_existing("hk")

    def indices():
        df=ak.stock_hk_index_spot_em()
        want={"恒生指数":"Hang Seng","恒生科技指数":"HS Tech","国企指数":"HSCEI","恒生中国企业指数":"HSCEI"}
        out=[]
        for r in df.to_dict("records"):
            nm=str(pick(r,"名称","name"))
            if nm in want:
                out.append({"name_zh":nm,"name_en":want[nm],"value":to_num(pick(r,"最新价","最新","price")),
                            "change":to_num(pick(r,"涨跌额")),"change_pct":to_num(pick(r,"涨跌幅"))})
        return out

    def news():
        df=ak.stock_info_global_em()
        out=[]
        for r in df.head(20).to_dict("records"):
            title=str(pick(r,"标题","title")); summ=str(pick(r,"摘要","内容"))[:120]
            out.append({"time":str(pick(r,"发布时间","时间"))[-8:-3] if pick(r,"发布时间","时间") else "",
                        "title_zh":title,"title_en":title,"summary_zh":summ,"source":"东方财富",
                        "sectors":tag(title,summ)})
        return out

    def corporate():
        """港股企业动态: 券商业绩预测 + 分红派息公告,合成近期动态列表"""
        out=[]
        # 1) 券商研报/业绩预测 (48 行,按更新时间倒序保留最近)
        try:
            df = ak.stock_hk_profit_forecast_et()
            for r in df.to_dict("records"):
                fy = str(pick(r,"财政年度"))
                bro = str(pick(r,"证券商"))
                rating = str(pick(r,"评级"))
                tgt = pick(r,"目标价")
                upd = str(pick(r,"更新日期"))
                eps = pick(r,"每股盈利")
                tag_lbl = "评级" if rating else "业绩"
                title_zh = f"[{bro}] {fy}财年 评级={rating or '-'} 目标价={tgt} EPS={eps}"
                title_en = f"[{bro}] FY{fy} Rating={rating or '-'} Target={tgt} EPS={eps}"
                out.append({"tag":tag_lbl,"title_zh":title_zh,"title_en":title_en,
                            "code":str(pick(r,"证券商","code",default=""))[:0]+"",  # 券商研报无个股代码
                            "time":upd,"sectors":tag(fy+str(tgt)+str(eps))})
        except Exception as e:
            print(f"  [WARN] hk.profit_forecast: {e}")
        # 2) 分红派息公告
        try:
            df = ak.stock_hk_dividend_payout_em()
            for r in df.head(10).to_dict("records"):
                plan = str(pick(r,"分红方案"))
                fy = str(pick(r,"财政年度"))
                upd = str(pick(r,"最新公告日期"))
                out.append({"tag":"分红","title_zh":f"{fy}财年 分红方案: {plan}",
                            "title_en":f"FY{fy} Dividend: {plan}",
                            "code":"","time":upd,"sectors":tag(plan)})
        except Exception as e:
            print(f"  [WARN] hk.dividend: {e}")
        # 按时间倒序
        out.sort(key=lambda x: x.get("time","") or "", reverse=True)
        return out[:30]

    def ipo():
        """港股 IPO 参考: A+H 双重上市股(近期活跃,作为准新股展示); akshare 无专门的港股 IPO 实时接口"""
        out=[]
        try:
            df = ak.stock_zh_ah_spot_em().head(10)
            for r in df.to_dict("records"):
                nm = str(pick(r,"名称"))
                code_h = str(pick(r,"H股代码"))
                price_h = pick(r,"最新价-HKD","")
                out.append({"name_zh":nm,"name_en":nm,
                            "code":code_h.zfill(5) if code_h else "",
                            "date":"","price":f"HK${price_h}" if price_h else "",
                            "market_zh":"港股","market_en":"HKEX",
                            "sectors":tag(nm)})
        except Exception as e:
            print(f"  [WARN] hk.ipo (A+H): {e}")
        return out

    obj={"market":"hk","updated_at":now_iso(8),
         "indices":section("hk","indices",indices),"news":section("hk","news",news),
         "corporate":section("hk","corporate",corporate),"ipo":section("hk","ipo",ipo)}
    return finalize("hk", obj, old)

# =========================================================
def run_market(name, fn):
    print(f"== {name} ==")
    try:
        obj=fn()
        if any(obj.get(k) for k in ("indices","news","corporate","ipo")):
            write_json(name, obj)
        else:
            print(f"  [保留] {name} 全部为空，沿用旧 json")
    except Exception:
        print(f"  [异常] {name} 整体失败，保留旧 json"); traceback.print_exc()

if __name__ == "__main__":
    run_market("cn", fetch_cn)
    run_market("hk", fetch_hk)
    run_market("us", fetch_us)
    print("== 完成 ==")

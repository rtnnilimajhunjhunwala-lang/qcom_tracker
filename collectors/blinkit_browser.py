"""
Blinkit collector via a REAL browser (Playwright).
==================================================
Plain HTTP requests get 403'd by Blinkit's Cloudflare. A real Chromium browser
passes, because it *is* a browser. Slower than raw requests, but it actually
works. One browser session is reused for all SKUs (efficient).

Returns the same field shape as collectors/blinkit.py so everything downstream
is unchanged.
"""
import json, re

FIELDS = ["listing_name","price","mrp","discount_pct","inventory",
          "state","rating","merchant_id","note"]

def _blank(note):
    d={k:None for k in FIELDS}; d["note"]=note; return d

def _parse(html, pid):
    out={k:None for k in FIELDS}; out["note"]=""
    for m in re.finditer(r'"common_attributes":\s*(\{[^}]*\})', html):
        try: a=json.loads(m.group(1))
        except Exception: continue
        if str(a.get("product_id"))!=str(pid): continue
        if a.get("mrp") is not None:
            try: out["mrp"]=float(a["mrp"])
            except Exception: pass
        if a.get("price") is not None:
            try: out["price"]=float(a["price"])
            except Exception: pass
        if a.get("inventory") is not None:
            try: out["inventory"]=int(a["inventory"])
            except Exception: pass
        if a.get("state"): out["state"]=a["state"]
        if a.get("rating"):
            try: out["rating"]=round(float(a["rating"]),2)
            except Exception: pass
        if a.get("merchant_id") is not None: out["merchant_id"]=a["merchant_id"]
        break
    m=re.search(r'name="og:title" content="([^"]+)"', html)
    if m: out["listing_name"]=m.group(1).split(" Price - Buy Online")[0]
    if out["mrp"] and out["price"]:
        out["discount_pct"]=round(max(0.0,(out["mrp"]-out["price"])/out["mrp"]*100),1)
    if not out["state"] and out["price"] is not None:
        out["state"]="available" if (out["inventory"] or 0)>0 else "out_of_stock"
    if out["price"] is None and out["mrp"] is None:
        out["note"]="no_data_parsed"
    return out

def fetch_all(skus, headless=True, progress=None):
    """skus: list of (product_id,). Returns {pid: parsed_dict}. One browser for all."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return {"_error": _blank("playwright_missing_%s" % type(e).__name__)}

    results={}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=headless, args=[
            "--no-sandbox","--disable-blink-features=AutomationControlled"])
        ctx=browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width":1280,"height":800}, locale="en-IN")
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page=ctx.new_page()
        first_block=0
        for i,pid in enumerate(skus):
            try:
                r=page.goto("https://blinkit.com/prn/x/prid/%s"%pid,
                            wait_until="domcontentloaded", timeout=30000)
                if r and r.status==403:
                    results[pid]=_blank("http_403"); first_block+=1
                else:
                    page.wait_for_timeout(1200)
                    results[pid]=_parse(page.content(), pid)
                    first_block=0
            except Exception as e:
                results[pid]=_blank("err_%s"%type(e).__name__)
            if progress: progress(i+1, len(skus), pid, results[pid])
            # if the first several all 403, bail (real block, not worth grinding)
            if i>=5 and first_block>=6:
                break
            page.wait_for_timeout(800)
        browser.close()
    return results

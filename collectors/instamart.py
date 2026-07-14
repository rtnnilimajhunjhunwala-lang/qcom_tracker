"""
Swiggy Instamart collector (Playwright).
========================================
Instamart is a single-page app behind bot protection (returns a 202 empty shell
to plain HTTP requests) and shows no products until a delivery location is set.
Same approach as Zepto: real browser + spoofed geolocation, run from a
RESIDENTIAL IP. Will not work from a free cloud server.

Returns the same field shape as the other collectors so downstream analysis is
platform-agnostic. Degrades gracefully with a `note` on failure.
"""

import json, re

FIELDS = ["listing_name", "price", "mrp", "discount_pct", "inventory",
          "state", "rating", "merchant_id", "note"]


def _blank(note):
    d = {k: None for k in FIELDS}
    d["note"] = note
    return d


def fetch_batch(skus, location, headless=True):
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return {"_error": _blank(f"playwright_missing_{type(e).__name__}")}

    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=[
            "--disable-blink-features=AutomationControlled", "--no-sandbox",
        ])
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/126.0.0.0 Safari/537.36",
            geolocation={"latitude": location["lat"], "longitude": location["lng"]},
            permissions=["geolocation"],
            locale="en-IN",
            viewport={"width": 412, "height": 915},
        )
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()

        try:
            resp = page.goto("https://www.swiggy.com/instamart",
                             wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            if resp and resp.status in (403, 429):
                browser.close()
                return {"_error": _blank(f"blocked_{resp.status}_datacenter_ip")}
            _set_location(page, location)
        except Exception as e:
            browser.close()
            return {"_error": _blank(f"session_init_{type(e).__name__}")}

        for sku in skus:
            iid = sku["ids"].get("instamart")
            key = iid or sku["search_name"]
            try:
                results[key] = _fetch_by_search(page, sku["search_name"])
            except Exception as e:
                results[key] = _blank(f"error_{type(e).__name__}")
            page.wait_for_timeout(1800)

        browser.close()
    return results


def _set_location(page, location):
    try:
        page.click("text=/set.*location|other|search.*delivery|add.*address/i", timeout=5000)
        page.wait_for_timeout(1200)
        box = page.locator("input[placeholder*='area' i], input[placeholder*='search' i], input[type='text']").first
        box.fill(location.get("pincode", ""))
        page.wait_for_timeout(1800)
        page.locator("[data-testid*='address'], li, [role='option']").first.click(timeout=5000)
        page.wait_for_timeout(2500)
    except Exception:
        pass


def _fetch_by_search(page, name):
    out = {k: None for k in FIELDS}
    out["note"] = ""
    try:
        page.goto(f"https://www.swiggy.com/instamart/search?custom_back=true&query={name.replace(' ', '%20')}",
                  wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
    except Exception:
        return _blank("nav_failed")

    # Instamart exposes product data via its internal API responses; scrape DOM.
    try:
        card = page.locator("[data-testid='ItemWidgetContainer'], div[class*='ProductCard'], div[class*='item']").first
        text = card.inner_text(timeout=5000)
        pm = re.search(r"₹\s?(\d+)", text)
        if pm: out["price"] = float(pm.group(1))
        mm = re.findall(r"₹\s?(\d+)", text)
        if len(mm) >= 2:
            vals = sorted(set(int(x) for x in mm))
            out["price"] = float(vals[0]); out["mrp"] = float(vals[-1])
        out["listing_name"] = text.split("\n")[0][:120]
        out["state"] = "available" if out["price"] else None
    except Exception:
        return _blank("no_card_found")

    # Instamart rarely exposes a numeric inventory count publicly; when a card
    # shows "Only N left" we capture it as the inventory proxy.
    try:
        only = page.locator("text=/only\\s+\\d+\\s+left/i").first.inner_text(timeout=1500)
        im = re.search(r"only\s+(\d+)\s+left", only, re.I)
        if im: out["inventory"] = int(im.group(1))
    except Exception:
        pass

    if out["mrp"] and out["price"]:
        out["discount_pct"] = round(max(0.0, (out["mrp"] - out["price"]) / out["mrp"] * 100), 1)
    if out["price"] is None:
        out["note"] = "no_data_parsed"
    return out

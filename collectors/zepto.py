"""
Zepto collector (Playwright).
=============================
Zepto blocks datacenter IPs at the firewall (HTTP 403) and renders products
client-side only after a delivery location is set. So we drive a real browser
with a spoofed geolocation.

IMPORTANT: run this from a RESIDENTIAL connection (home/office wifi). It will
NOT work from a free cloud server / GitHub Actions runner (those are datacenter
IPs that Zepto blocks). Blinkit is the cloud backbone; Zepto/Instamart are the
residential add-ons.

Returns the same field shape as the Blinkit collector so everything downstream
is platform-agnostic. On failure it returns a row with a `note` explaining why,
rather than crashing the whole run.
"""

import json, re

FIELDS = ["listing_name", "price", "mrp", "discount_pct", "inventory",
          "state", "rating", "merchant_id", "note"]


def _blank(note):
    d = {k: None for k in FIELDS}
    d["note"] = note
    return d


def fetch_batch(skus, location, headless=True):
    """
    Fetch many Zepto SKUs in one browser session (efficient — one location set,
    many product loads). Returns {sku_key: parsed_dict}.
    `sku_key` is the zepto product id if present, else the search_name.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return {"_error": _blank(f"playwright_missing_{type(e).__name__}")}

    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
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
        # light stealth
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()

        # Establish session + location once
        try:
            resp = page.goto("https://www.zeptonow.com/", wait_until="domcontentloaded", timeout=45000)
            if resp and resp.status == 403:
                browser.close()
                return {"_error": _blank("blocked_403_datacenter_ip")}
            page.wait_for_timeout(2500)
            _set_location(page, location)
        except Exception as e:
            browser.close()
            return {"_error": _blank(f"session_init_{type(e).__name__}")}

        for sku in skus:
            zid = sku["ids"].get("zepto")
            key = zid or sku["search_name"]
            try:
                if zid:
                    results[key] = _fetch_by_id(page, zid)
                else:
                    results[key] = _fetch_by_search(page, sku["search_name"])
            except Exception as e:
                results[key] = _blank(f"error_{type(e).__name__}")
            page.wait_for_timeout(1500)

        browser.close()
    return results


def _set_location(page, location):
    """Best-effort: open location picker and search the pincode."""
    try:
        # Zepto usually shows a location CTA on first load
        page.click("text=/select location|detect|add address/i", timeout=4000)
        page.wait_for_timeout(1000)
        box = page.locator("input[placeholder*='search' i], input[type='text']").first
        box.fill(location.get("pincode", ""))
        page.wait_for_timeout(1500)
        page.keyboard.press("Enter")
        page.wait_for_timeout(1500)
        # pick first suggestion
        page.locator("[role='option'], li").first.click(timeout=4000)
        page.wait_for_timeout(2000)
    except Exception:
        pass  # location may already be set via geolocation permission


def _extract_from_page(page):
    """Pull product fields from Zepto's embedded __NEXT_DATA__ or DOM."""
    out = {k: None for k in FIELDS}
    out["note"] = ""
    html = page.content()

    # Zepto embeds product state in __NEXT_DATA__ (Next.js)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            blob = json.dumps(data)
            # heuristic field extraction from the serialized product state
            price = re.search(r'"sellingPrice":\s*(\d+)', blob)
            mrp = re.search(r'"mrp":\s*(\d+)', blob)
            inv = re.search(r'"(?:availableQuantity|inventory|stockQuantity)":\s*(\d+)', blob)
            name = re.search(r'"name":\s*"([^"]{5,120})"', blob)
            if price: out["price"] = float(int(price.group(1)) / 100 if int(price.group(1)) > 10000 else int(price.group(1)))
            if mrp: out["mrp"] = float(int(mrp.group(1)) / 100 if int(mrp.group(1)) > 10000 else int(mrp.group(1)))
            if inv: out["inventory"] = int(inv.group(1))
            if name: out["listing_name"] = name.group(1)
        except Exception:
            pass

    # DOM fallback for price / out-of-stock
    if out["price"] is None:
        try:
            txt = page.locator("text=/₹\\s?\\d+/").first.inner_text(timeout=3000)
            pm = re.search(r"₹\s?(\d+)", txt)
            if pm: out["price"] = float(pm.group(1))
        except Exception:
            pass
    try:
        if page.locator("text=/out of stock|sold out|notify me/i").count() > 0:
            out["state"] = "out_of_stock"
        elif out["price"] is not None:
            out["state"] = "available"
    except Exception:
        pass

    if out["mrp"] and out["price"]:
        out["discount_pct"] = round(max(0.0, (out["mrp"] - out["price"]) / out["mrp"] * 100), 1)
    if out["price"] is None:
        out["note"] = "no_data_parsed"
    return out


def _fetch_by_id(page, zid):
    page.goto(f"https://www.zeptonow.com/pn/x/pvid/{zid}",
              wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2500)
    return _extract_from_page(page)


def _fetch_by_search(page, name):
    page.goto(f"https://www.zeptonow.com/search?query={name.replace(' ', '%20')}",
              wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2500)
    try:
        page.locator("a[href*='/pn/']").first.click(timeout=5000)
        page.wait_for_timeout(2500)
    except Exception:
        return _blank("search_no_result")
    return _extract_from_page(page)

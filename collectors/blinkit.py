"""
Blinkit collector.
==================
Server-rendered product pages expose price, MRP, live inventory, availability
and rating in embedded JSON. No login, no browser engine needed. Works from
any IP (datacenter or residential).
"""

import json, re
try:
    from .fetch_util import fetch_html
except ImportError:
    from fetch_util import fetch_html


def _parse(body, product_id):
    out = {
        "listing_name": None, "price": None, "mrp": None, "discount_pct": None,
        "inventory": None, "state": None, "rating": None, "merchant_id": None,
        "note": "",
    }

    # JSON-LD Product block: name, price, availability
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', body, re.DOTALL):
        try:
            d = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and d.get("@type") == "Product":
            out["listing_name"] = d.get("name")
            offers = d.get("offers") or {}
            if offers.get("price") is not None:
                try: out["price"] = float(offers["price"])
                except (TypeError, ValueError): pass
            avail = offers.get("availability", "")
            if "InStock" in avail: out["state"] = "available"
            elif "OutOfStock" in avail: out["state"] = "out_of_stock"
            break

    # Deep tracking blob: mrp, live inventory, rating, merchant
    for m in re.finditer(r'"common_attributes":\s*(\{[^}]*\})', body):
        try:
            attrs = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if str(attrs.get("product_id")) != str(product_id):
            continue
        if attrs.get("mrp") is not None:
            try: out["mrp"] = float(attrs["mrp"])
            except (TypeError, ValueError): pass
        if out["price"] is None and attrs.get("price") is not None:
            try: out["price"] = float(attrs["price"])
            except (TypeError, ValueError): pass
        if attrs.get("inventory") is not None:
            try: out["inventory"] = int(attrs["inventory"])
            except (TypeError, ValueError): pass
        if not out["state"] and attrs.get("state"):
            out["state"] = attrs["state"]
        if attrs.get("rating"):
            try: out["rating"] = round(float(attrs["rating"]), 2)
            except (TypeError, ValueError): pass
        if attrs.get("merchant_id") is not None:
            out["merchant_id"] = attrs["merchant_id"]
        break

    if out["mrp"] and out["price"]:
        out["discount_pct"] = round(max(0.0, (out["mrp"] - out["price"]) / out["mrp"] * 100), 1)

    if out["price"] is None and out["mrp"] is None:
        out["note"] = "no_data_found"
    return out


def fetch(product_id, location=None, retries=2):
    """Fetch one Blinkit product via the robust rotating fetcher."""
    url = "https://blinkit.com/prn/x/prid/%s" % product_id
    body, note = fetch_html(url, retries=max(2, retries))
    if not body:
        return {"listing_name": None, "price": None, "mrp": None,
                "discount_pct": None, "inventory": None, "state": None,
                "rating": None, "merchant_id": None, "note": note}
    out = _parse(body, product_id)
    return out

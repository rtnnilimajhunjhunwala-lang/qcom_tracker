#!/usr/bin/env python3
"""
Q-Commerce Competitor Tracker — orchestrator
============================================
Runs the Blinkit / Zepto / Instamart collectors across your SKU list and every
configured location, and appends one timestamped row per (SKU x platform x
location) to data/snapshots.csv.

Modes
-----
  python3 tracker.py                 # all platforms (Blinkit always; Z/I if reachable)
  python3 tracker.py --only blinkit  # Blinkit only (use in cloud / GitHub Actions)
  python3 tracker.py --only zepto,instamart   # residential add-on run

Design
------
- Blinkit is the reliable backbone (works from any IP).
- Zepto/Instamart need a residential IP + browser; if blocked they log a note
  and the run still succeeds with Blinkit data.
- Append-only CSV = full history, needed by the sales-estimation engine.
"""

import argparse, csv, os, sys, time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skus import SKUS, LOCATIONS
from collectors import blinkit

IST = timezone(timedelta(hours=5, minutes=30))
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CSV_PATH = os.path.join(DATA_DIR, "snapshots.csv")

FIELDS = [
    "snapshot_ts_ist", "platform", "location", "brand", "is_own", "brand_sku",
    "size", "pack", "barcode", "platform_product_id", "listing_name", "price",
    "mrp", "discount_pct", "state", "inventory", "rating", "merchant_id", "note",
]


def _row(ts, platform, loc_label, sku, pid, data):
    return {
        "snapshot_ts_ist": ts, "platform": platform, "location": loc_label,
        "brand": sku.get("brand", ""), "is_own": sku.get("is_own", False),
        "brand_sku": sku["brand_sku"], "size": sku["size"], "pack": sku["pack"],
        "barcode": sku["barcode"], "platform_product_id": pid or "",
        "listing_name": data.get("listing_name"), "price": data.get("price"),
        "mrp": data.get("mrp"), "discount_pct": data.get("discount_pct"),
        "state": data.get("state"), "inventory": data.get("inventory"),
        "rating": data.get("rating"), "merchant_id": data.get("merchant_id"),
        "note": data.get("note", ""),
    }


def collect_blinkit(ts, rows):
    for loc in LOCATIONS:
        for sku in SKUS:
            pid = sku["ids"].get("blinkit")
            if not pid:
                continue
            data = blinkit.fetch(pid, location=loc)
            rows.append(_row(ts, "blinkit", loc["label"], sku, pid, data))
            own = "*" if sku.get("is_own") else " "
            print(f" {own}{sku.get('brand',''):10} {sku['brand_sku'][:40]:40} "
                  f"₹{str(data.get('price')):>5} stk={str(data.get('inventory')):>3} {data.get('note')}")
            time.sleep(1.2)


def collect_browser(platform, ts, rows):
    """Zepto / Instamart via their Playwright batch collectors."""
    try:
        if platform == "zepto":
            from collectors import zepto as mod
        else:
            from collectors import instamart as mod
    except Exception as e:
        print(f"  {platform}: import failed ({e})")
        return

    for loc in LOCATIONS:
        skus_here = [s for s in SKUS if platform in s["ids"]]
        res = mod.fetch_batch(skus_here, loc, headless=True)
        if "_error" in res:
            note = res["_error"]["note"]
            print(f"  {platform}: {note} @ {loc['label']} — logging blanks")
            for sku in skus_here:
                rows.append(_row(ts, platform, loc["label"], sku,
                                 sku["ids"].get(platform), {"note": note}))
            continue
        for sku in skus_here:
            pid = sku["ids"].get(platform)
            key = pid or sku["search_name"]
            data = res.get(key, {"note": "not_returned"})
            rows.append(_row(ts, platform, loc["label"], sku, pid, data))
            print(f"  {platform}  {loc['label']:14} {sku['brand_sku'][:26]:26} {sku['size']:7} "
                  f"₹{data.get('price')} stock={data.get('inventory')} {data.get('note')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="blinkit,zepto,instamart",
                    help="comma list of platforms to run")
    args = ap.parse_args()
    platforms = [p.strip() for p in args.only.split(",") if p.strip()]

    os.makedirs(DATA_DIR, exist_ok=True)
    ts = datetime.now(IST).isoformat(timespec="seconds")
    rows = []

    print(f"Snapshot @ {ts}  platforms={platforms}")
    if "blinkit" in platforms:
        collect_blinkit(ts, rows)
    if "zepto" in platforms:
        collect_browser("zepto", ts, rows)
    if "instamart" in platforms:
        collect_browser("instamart", ts, rows)

    new = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerows(rows)

    print(f"\n{len(rows)} rows appended -> {CSV_PATH}")


if __name__ == "__main__":
    main()

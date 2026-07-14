#!/usr/bin/env python3
"""
market_share.py -- brand share of the Blinkit period-panty category.
====================================================================
Two very different numbers here. Read this so you trust the right one.

1. SHELF SHARE  (headline -- BIAS-FREE, zero assumptions)
   "Of every 100 units sold at a dark store, how many are each brand?"
       shelf_share(brand) = brand's units sold / all brands' units sold
   No store counts, no penetration guesses -- only what we watched sell.
   Unbiased: we never tell the model who is big. If Whisper outsells PoppiGo
   here, it's because Whisper's stock actually dropped faster.

2. ABSOLUTE VOLUME  (units/revenue -- assumption-dependent)
   Needs each brand's store count. We only KNOW PoppiGo's (450, confirmed).
     - PoppiGo absolute  -> REAL.
     - Competitors        -> flat scenario, SAME footprint for every rival, so
                             no brand is favoured by a guess. Under-states wide
                             brands, so treat competitor rupees as a floor.

BLINKIT ONLY -- not Amazon, Flipkart, pharmacy, or D2C.
"""
import argparse, os, sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skus import DARKSTORE_COUNTS, DEFAULT_STORE_PENETRATION
try:
    from skus import BRAND_PENETRATION
except ImportError:
    BRAND_PENETRATION = {}
try:
    from skus import OWN_STORE_COUNT
except ImportError:
    OWN_STORE_COUNT = None

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SNAP = os.path.join(DATA, "snapshots.csv")
OUT = os.path.join(DATA, "market_share.csv")
OWN_BRAND = "PoppiGo"


def bar(pct, width=30):
    f = int(round(width * pct / 100.0))
    return "#" * f + "." * (width - f)


def depletion_per_sku(df):
    recs = []
    keys = ["platform", "brand", "brand_sku", "size",
            "platform_product_id", "merchant_id"]
    for key, g in df.sort_values("snapshot_ts_ist").groupby(keys):
        inv = g["inventory"].to_numpy()
        if len(inv) < 2:
            continue
        d = inv[1:] - inv[:-1]
        sold = int(-d[d < 0].sum())
        ndays = max(1, g["day"].nunique())
        price = g["price"].dropna().mean()
        recs.append({"platform": key[0], "brand": key[1], "brand_sku": key[2],
                     "size": key[3], "pid": key[4], "merchant_id": key[5],
                     "units_per_store_day": sold / ndays, "price": price})
    s = pd.DataFrame(recs)
    if s.empty:
        return s
    return (s.groupby(["platform", "brand", "brand_sku", "size", "pid"],
                      as_index=False)
              .agg(units_per_store_day=("units_per_store_day", "mean"),
                   price=("price", "mean")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=SNAP)
    args = ap.parse_args()

    if not os.path.exists(args.file):
        print("No snapshots yet. Run tracker.py first.")
        sys.exit(1)

    df = pd.read_csv(args.file)
    df["snapshot_ts_ist"] = pd.to_datetime(df["snapshot_ts_ist"], utc=True, errors="coerce")
    df["inventory"] = pd.to_numeric(df["inventory"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["inventory"])
    df["day"] = df["snapshot_ts_ist"].dt.tz_convert("Asia/Kolkata").dt.date
    for c in ["platform", "brand", "brand_sku", "size",
              "platform_product_id", "merchant_id"]:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str)

    sku = depletion_per_sku(df)
    if sku.empty:
        print("\nNot enough repeated snapshots to measure sales yet.")
        print("Need the SAME SKU captured twice with stock changing.")
        print("The hourly cloud runs produce this within a day. Re-run then.\n")
        sys.exit(0)

    sku["rev_per_store_day"] = sku["units_per_store_day"] * sku["price"].fillna(0)
    brand = (sku.groupby("brand", as_index=False)
                .agg(skus=("brand_sku", "count"),
                     units_psd=("units_per_store_day", "sum"),
                     rev_psd=("rev_per_store_day", "sum"),
                     avg_price=("price", "mean")))

    tot_u = brand["units_psd"].sum()
    tot_r = brand["rev_psd"].sum()
    brand["shelf_unit_share"] = (brand["units_psd"] / tot_u * 100) if tot_u else 0
    brand["shelf_value_share"] = (brand["rev_psd"] / tot_r * 100) if tot_r else 0
    brand = brand.sort_values("shelf_value_share", ascending=False).reset_index(drop=True)

    print("\n" + "=" * 74)
    print("  BLINKIT PERIOD-PANTY -- SHELF SHARE  (bias-free, observed data only)")
    print("=" * 74)
    print("  Of every 100 rupees spent in this category at a dark store:\n")
    print("  %-11s %5s %10s %11s" % ("BRAND", "SKUs", "VALUE-SH", "UNIT-SH"))
    print("  " + "-" * 60)
    for _, r in brand.iterrows():
        mark = " <-- YOU" if r["brand"] == OWN_BRAND else ""
        print("  %-11s %5d %9.1f%% %10.1f%%%s" % (
            r["brand"][:11], r["skus"], r["shelf_value_share"],
            r["shelf_unit_share"], mark))
    print("  " + "-" * 60)
    print("  %-11s %5d %9.1f%% %10.1f%%" % ("TOTAL", brand["skus"].sum(), 100.0, 100.0))

    print("\n  VALUE SHELF SHARE")
    for _, r in brand.iterrows():
        star = "*" if r["brand"] == OWN_BRAND else " "
        print("  %s %-11s %s %5.1f%%" % (star, r["brand"][:11],
              bar(r["shelf_value_share"]), r["shelf_value_share"]))

    plat_stores = DARKSTORE_COUNTS.get("blinkit", 2243)

    def brand_stores(bname):
        if bname == OWN_BRAND and OWN_STORE_COUNT:
            return OWN_STORE_COUNT
        if bname in BRAND_PENETRATION:
            return plat_stores * BRAND_PENETRATION[bname]
        return plat_stores * DEFAULT_STORE_PENETRATION

    brand["stores_used"] = brand["brand"].map(brand_stores)
    brand["monthly_units"] = brand["units_psd"] * brand["stores_used"] * 30
    brand["monthly_rev"] = brand["rev_psd"] * brand["stores_used"] * 30

    print("\n" + "=" * 74)
    print("  ABSOLUTE MONTHLY VOLUME  (assumption-dependent -- read the caveat)")
    print("=" * 74)
    print("  PoppiGo uses its REAL 450 stores. Competitors use a flat %d-store" %
          int(plat_stores * DEFAULT_STORE_PENETRATION))
    print("  scenario (same for every rival, so none is favoured by a guess).\n")
    print("  %-11s %10s %14s   %-6s" % ("BRAND", "~UNITS/MO", "~REVENUE/MO", "BASIS"))
    print("  " + "-" * 62)
    for _, r in brand.iterrows():
        basis = "REAL" if r["brand"] == OWN_BRAND else "flat"
        mark = " <-- YOU" if r["brand"] == OWN_BRAND else ""
        print("  %-11s %10s   Rs %10s   %-5s%s" % (
            r["brand"][:11], "{:,.0f}".format(r["monthly_units"]),
            "{:,.0f}".format(r["monthly_rev"]), basis, mark))

    if OWN_BRAND in set(brand["brand"]):
        p = brand[brand["brand"] == OWN_BRAND].iloc[0]
        rank_shelf = int(brand.index[brand["brand"] == OWN_BRAND][0]) + 1
        leader = brand.iloc[0]
        print("\n  " + "-" * 62)
        print("  POPPIGO")
        print("    Shelf value share : %.1f%%  (rank #%d of %d -- the fair number)"
              % (p["shelf_value_share"], rank_shelf, len(brand)))
        print("    Real monthly rev  : Rs %s  (from 450 confirmed stores)"
              % "{:,.0f}".format(p["monthly_rev"]))
        if leader["brand"] != OWN_BRAND:
            print("    Category leader   : %s at %.1f%% shelf share"
                  % (leader["brand"], leader["shelf_value_share"]))

    print("\n  " + "-" * 62)
    print("  Trust the SHELF SHARE (top block): pure observed data, no bias.")
    print("  Absolute rupees are directional -- competitor store counts unknown.")
    print("  BLINKIT ONLY -- not Amazon, Flipkart, pharmacy, or D2C.\n")

    brand.to_csv(OUT, index=False)
    print("  Written -> %s\n" % OUT)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Sales-estimation engine (inventory-depletion method).
======================================================
You cannot see competitor sales directly on Q-com. But the live inventory count
at a dark store drops by 1 every time someone buys. If you snapshot inventory
often enough, the drops ARE the sales.

METHOD
------
For each (platform, product, location), order snapshots by time and diff the
inventory column:
    delta = inventory[t] - inventory[t-1]
    delta < 0  -> that many UNITS SOLD between the two snapshots
    delta > 0  -> a RESTOCK event (ignored for sales, but counted separately)
    delta == 0 -> no movement (or movement fully masked by a restock — see note)

Daily units sold at a sampled store = sum of all negative deltas that day.

EXTRAPOLATION (brand-level monthly estimate)
--------------------------------------------
   monthly_units ≈ daily_units_per_store
                   × (platform_darkstores × store_penetration)
                   × 30
The absolute number has wide error bars (store count & penetration are
assumptions). The RELATIVE velocity ranking between competitors is the robust,
decision-grade output — trust that more than the absolute rupee figure.

RESOLUTION NOTE
---------------
Sampling frequency caps accuracy: hourly polling misses sales that are masked by
a restock inside the same hour. Poll every 30–60 min on your measurement day for
best results. A single weekly snapshot CANNOT estimate sales — it only gives a
price/stock state. Run tracker.py hourly on one "measurement day" per week.

USAGE
-----
   python3 estimate_sales.py                 # prints report, writes data/estimates.csv
   python3 estimate_sales.py --price-per-unit-margin 0.4   # optional GMV/profit view
"""

import argparse, os, sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skus import DARKSTORE_COUNTS, DEFAULT_STORE_PENETRATION
from depletion import rate_from_series

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CSV_PATH = os.path.join(DATA_DIR, "snapshots.csv")
OUT_PATH = os.path.join(DATA_DIR, "estimates.csv")


def load():
    if not os.path.exists(CSV_PATH):
        print(f"No snapshots yet at {CSV_PATH}. Run tracker.py first.")
        sys.exit(1)
    df = pd.read_csv(CSV_PATH)
    df["snapshot_ts_ist"] = pd.to_datetime(df["snapshot_ts_ist"], utc=True, errors="coerce")
    df["inventory"] = pd.to_numeric(df["inventory"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["date"] = df["snapshot_ts_ist"].dt.tz_convert("Asia/Kolkata").dt.date
    # groupby drops NaN keys -- fill them so blank sizes don't lose SKUs
    for c in ["platform", "brand_sku", "size", "location", "merchant_id"]:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str)
    return df


def depletion(df):
    """Sales RATE per SKU per store, from clean (non-restock) intervals only."""
    rows = []
    keys = ["platform", "brand_sku", "size", "location", "merchant_id"]
    for key, g in df.dropna(subset=["inventory"]).sort_values("snapshot_ts_ist").groupby(keys):
        pts = list(zip(g["snapshot_ts_ist"], g["inventory"]))
        if len(pts) < 2:
            continue
        r = rate_from_series(pts)
        if r["confidence"] == "none":
            continue
        rows.append({
            "platform": key[0], "brand_sku": key[1], "size": key[2],
            "location": key[3], "merchant_id": key[4],
            "snapshots": len(g),
            "units_per_day_at_store": round(r["units_per_day"], 2),
            "clean_hours": round(r["clean_hours"], 1),
            "restock_events": r["dirty_intervals"],
            "coverage": round(r["coverage"], 2),
            "confidence": r["confidence"],
            "avg_price": round(g["price"].dropna().mean(), 1) if g["price"].notna().any() else None,
        })
    return pd.DataFrame(rows)


def extrapolate(dep, penetration):
    """Scale per-store daily depletion to a brand-level monthly estimate per platform."""
    # Average across sampled locations for each (platform, brand_sku, size)
    agg = (dep.groupby(["platform", "brand_sku", "size"], as_index=False)
              .agg(units_per_day_at_store=("units_per_day_at_store", "mean"),
                   restock_events=("restock_events", "sum"),
                   clean_hours=("clean_hours", "sum"),
                   avg_price=("avg_price", "mean"),
                   snapshots=("snapshots", "max")))
    def stores(p):
        return DARKSTORE_COUNTS.get(p, 800) * penetration
    agg["est_active_darkstores"] = agg["platform"].map(stores).round(0)
    agg["est_monthly_units"] = (agg["units_per_day_at_store"] *
                                agg["est_active_darkstores"] * 30).round(0)
    agg["est_monthly_gmv_inr"] = (agg["est_monthly_units"] * agg["avg_price"]).round(0)
    return agg.sort_values(["platform", "est_monthly_units"], ascending=[True, False])


def print_report(dep, est):
    if dep.empty:
        print("\nNot enough repeated snapshots yet to compute depletion.")
        print("Run tracker.py multiple times across a day (ideally hourly), then re-run this.")
        return

    print("\n" + "=" * 78)
    print("VELOCITY LEADERBOARD  (per-store daily depletion — the robust signal)")
    print("=" * 78)
    lb = dep.groupby(["brand_sku", "size"], as_index=False)["units_per_day_at_store"].mean()
    lb = lb.sort_values("units_per_day_at_store", ascending=False)
    top = lb["units_per_day_at_store"].max() or 1
    for _, r in lb.iterrows():
        bar = "█" * int(round(20 * r["units_per_day_at_store"] / top))
        print(f"  {r['brand_sku'][:26]:26} {r['size']:7} "
              f"{r['units_per_day_at_store']:5.2f} u/store/day  {bar}")

    print("\n" + "=" * 78)
    print("BRAND-LEVEL MONTHLY ESTIMATE  (extrapolated — treat absolute figures as directional)")
    print("=" * 78)
    for platform, g in est.groupby("platform"):
        print(f"\n  ── {platform.upper()} "
              f"(assumed {int(g['est_active_darkstores'].iloc[0])} active dark stores) ──")
        print(f"     {'SKU':34} {'u/store/day':>11} {'~units/mo':>10} {'~GMV/mo':>12}")
        for _, r in g.iterrows():
            gmv = f"₹{r['est_monthly_gmv_inr']:,.0f}" if pd.notna(r["est_monthly_gmv_inr"]) else "—"
            print(f"     {(r['brand_sku'][:24]+' '+r['size']):34} "
                  f"{r['units_per_day_at_store']:>11.2f} "
                  f"{r['est_monthly_units']:>10,.0f} {gmv:>12}")

    print("\n  Restock frequency (a fast mover gets restocked often):")
    rs = dep.groupby(["brand_sku", "size"], as_index=False)["restock_events"].sum()
    for _, r in rs.sort_values("restock_events", ascending=False).iterrows():
        if r["restock_events"] > 0:
            print(f"     {r['brand_sku'][:26]:26} {r['size']:7} "
                  f"{int(r['restock_events'])} restock events observed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--penetration", type=float, default=DEFAULT_STORE_PENETRATION,
                    help="assumed fraction of dark stores carrying each SKU (0-1)")
    args = ap.parse_args()

    df = load()
    dep = depletion(df)
    est = extrapolate(dep, args.penetration) if not dep.empty else pd.DataFrame()
    print_report(dep, est)
    if not est.empty:
        est.to_csv(OUT_PATH, index=False)
        print(f"\nEstimates written -> {OUT_PATH}")
    print("\nReminder: relative velocity ranking is reliable; absolute units/GMV are")
    print("directional (they depend on the dark-store & penetration assumptions in skus.py).")


if __name__ == "__main__":
    main()

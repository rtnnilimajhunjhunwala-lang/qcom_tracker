"""
depletion.py -- the one correct way to turn stock readings into a sales rate.
=============================================================================

THE PROBLEM WITH THE NAIVE METHOD
---------------------------------
Naive: "sum every drop in stock = units sold."

That silently loses sales. If a store sells 2 units and restocks 10 in the same
hour, stock goes 2 -> 10. Net +8. The naive method sees a restock and records
ZERO sales for that hour -- the 2 real sales vanish.

Worse, it's BIASED: fast-selling brands restock more often, so they lose more
intervals, so the naive method UNDER-states exactly the market leaders. That's
the opposite of what you want from a competitive tool.

THE FIX: RATE-BASED ESTIMATION
------------------------------
Split consecutive readings into intervals. An interval is:

  CLEAN   -- stock went down or stayed flat (no restock). We know exactly how
             many units sold, and exactly how long it took.
  DIRTY   -- stock went UP. A restock happened. We CANNOT know how many sold in
             that window, because the restock masks it.

So we compute a rate from the CLEAN intervals only:

      units_per_hour = (units sold in clean intervals)
                       / (hours covered by clean intervals)

then scale that rate to a full day:

      units_per_day = units_per_hour * ACTIVE_HOURS

Dirty intervals are simply DROPPED from the sample -- not counted as zero sales.
Dropping is unbiased; counting them as zero is not. A restock reduces how much we
observed, it does not mean nothing sold.

WHY MORE HOURS = MORE ACCURATE (and it genuinely does)
------------------------------------------------------
  - More snapshots  -> shorter intervals -> fewer sales hidden inside a restock,
                       so more of the day lands in the CLEAN sample.
  - More clean hours-> the rate is averaged over a bigger sample, so random noise
                       (a quiet hour, a rush hour) cancels out.
  - More days       -> weekday/weekend and restock cycles average out.

With 2 snapshots you have at best 1 interval and the rate is nearly meaningless.
With 16/day for a week you have ~100 intervals per SKU and the rate is solid.
The estimate converges; it does not drift.

NO BIAS BY CONSTRUCTION
-----------------------
Nothing here knows or cares which brand is "big". Every SKU is measured the same
way, from its own observed stock movement. No brand-specific constants exist.
"""

ACTIVE_HOURS = 15.0   # we sample 08:00-23:00 IST; treat that as the selling day
MIN_HOURS = 0.25      # ignore intervals shorter than 15 min (noise / double runs)
MAX_HOURS = 6.0       # an interval longer than this is a gap; don't trust it


def rate_from_series(points):
    """
    points: list of (datetime, inventory) for ONE sku at ONE store, any order.

    Returns dict:
      units_per_day     -- estimated units sold per day at this store
      units_per_hour    -- underlying rate
      clean_units       -- units actually observed selling (hard data)
      clean_hours       -- hours of usable observation
      dirty_intervals   -- restock windows we had to drop
      intervals         -- total intervals examined
      coverage          -- clean_hours / (clean_hours + dirty_hours); 1.0 = perfect
      confidence        -- 'none' | 'low' | 'medium' | 'high'
    """
    pts = sorted(points, key=lambda p: p[0])
    clean_units = 0.0
    clean_hours = 0.0
    dirty_hours = 0.0
    dirty = 0
    intervals = 0

    for i in range(1, len(pts)):
        t0, i0 = pts[i - 1]
        t1, i1 = pts[i]
        hours = (t1 - t0).total_seconds() / 3600.0
        if hours < MIN_HOURS or hours > MAX_HOURS:
            continue
        intervals += 1
        delta = i1 - i0
        if delta > 0:
            # stock went UP -> restock. Sales in this window are unknowable.
            # DROP it (do not record zero sales -- that would bias us down).
            dirty += 1
            dirty_hours += hours
        else:
            # stock fell or held flat: we know exactly what sold, and over how long.
            clean_units += -delta
            clean_hours += hours

    if clean_hours <= 0:
        return {
            "units_per_day": 0.0, "units_per_hour": 0.0,
            "clean_units": 0.0, "clean_hours": 0.0,
            "dirty_intervals": dirty, "intervals": intervals,
            "coverage": 0.0, "confidence": "none",
        }

    uph = clean_units / clean_hours
    total_hours = clean_hours + dirty_hours
    coverage = clean_hours / total_hours if total_hours else 0.0

    # Confidence: driven by how much clean time we actually observed.
    if clean_hours >= 40:
        conf = "high"        # ~3+ full days of usable observation
    elif clean_hours >= 12:
        conf = "medium"      # ~1 day
    elif clean_hours >= 3:
        conf = "low"
    else:
        conf = "none"

    return {
        "units_per_day": uph * ACTIVE_HOURS,
        "units_per_hour": uph,
        "clean_units": clean_units,
        "clean_hours": clean_hours,
        "dirty_intervals": dirty,
        "intervals": intervals,
        "coverage": coverage,
        "confidence": conf,
    }

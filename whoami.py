#!/usr/bin/env python3
"""
whoami.py -- which dark store am I reading, and is my connection working?
=========================================================================
Blinkit picks the dark store from YOUR IP address, server-side. There is no
pincode input. This tells you which store your current connection reads, so you
always know whose shelf your numbers came from.

Uses the same robust, retrying fetcher as the tracker, so it survives Cloudflare's
intermittent 403s instead of crashing on them.
"""
import json
import re
import sys
import urllib.request

sys.path.insert(0, __file__.rsplit("/", 1)[0] if "/" in __file__ else ".")
try:
    from collectors.fetch_util import fetch_html
except Exception:
    from fetch_util import fetch_html

PROBE_PID = "493008"   # Whisper -- widely stocked canary


def main():
    url = "https://blinkit.com/prn/x/prid/%s" % PROBE_PID
    body, note = fetch_html(url, retries=4)

    if not body:
        print("")
        print("  COULD NOT REACH BLINKIT (%s)" % note)
        print("  " + "-" * 50)
        if note.startswith("http_403"):
            print("  Cloudflare temporarily blocked this connection.")
            print("  This is intermittent and IP-based. Try:")
            print("    1. Wait 2-3 minutes and run again.")
            print("    2. Turn wifi off/on (new IP from your router), retry.")
            print("    3. The tracker auto-switches to browser mode when this")
            print("       happens, which gets past the block -- so collection")
            print("       still works even when this quick check shows 403.")
        else:
            print("  Check your internet connection and try again.")
        print("")
        return

    merchant, inv, price = None, None, None
    for m in re.finditer(r'"common_attributes":\s*(\{[^}]*\})', body):
        try:
            a = json.loads(m.group(1))
        except Exception:
            continue
        if str(a.get("product_id")) != PROBE_PID:
            continue
        merchant = a.get("merchant_id")
        inv = a.get("inventory")
        price = a.get("price")
        break

    loc = None
    lm = re.search(r'"(?:locality|landmark|address)":"([^"]{3,60})"', body)
    if lm:
        loc = lm.group(1)

    try:
        ip = urllib.request.urlopen("https://api.ipify.org", timeout=8).read().decode()
    except Exception:
        ip = "unknown"

    print("")
    print("  WHICH DARK STORE AM I READING?")
    print("  " + "-" * 46)
    print("  Your public IP     : %s" % ip)
    print("  Blinkit merchant_id: %s   <-- this IS the dark store" % merchant)
    print("  Serving locality   : %s" % (loc or "not exposed on page"))
    print("  Canary (Whisper)   : Rs %s, stock %s units" % (price, inv))
    print("")
    print("  Record this merchant_id. If it changes between runs, snapshots are")
    print("  from DIFFERENT stores -- the tracker already handles that (it never")
    print("  compares one store's stock against another's).")
    print("")
    if str(merchant) == "31719":
        print("  Note: 31719 = Blinkit's default store (Gurugram). If you see this")
        print("  from Mumbai wifi, Blinkit isn't giving you a local store -- your")
        print("  numbers are Gurugram numbers. Still valid for RANKING brands.")
        print("")


if __name__ == "__main__":
    main()

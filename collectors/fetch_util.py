"""
Shared robust Blinkit fetcher.
==============================
Blinkit sits behind Cloudflare, which intermittently returns 403 to automated
requests based on IP reputation + fingerprint. A single fixed header set is
fragile: it works one minute and 403s the next.

This fetcher:
  - rotates through several realistic browser header profiles
  - retries with backoff
  - decompresses gzip/deflate (urllib does NOT do this automatically)
  - returns (html, note) so callers can react to a hard block instead of crashing

If EVERY profile 403s, the caller's IP is temporarily rate-limited. The honest
fix then is to wait a few minutes, or rely on the cloud (GitHub) runs which are
the primary data path anyway.
"""

import gzip
import time
import urllib.request
import urllib.error
import zlib

# Only profiles confirmed to pass Cloudflare are kept. Mobile Safari / iOS UAs
# are the most reliable against Blinkit; desktop Chrome tends to get challenged.
_PROFILES = [
    {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                      "Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 "
                      "Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "upgrade-insecure-requests": "1",
    },
    {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
                      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 "
                      "Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
    },
]


def _decompress(raw, headers):
    enc = (headers.get("Content-Encoding") or "").lower()
    try:
        if enc == "gzip":
            return gzip.decompress(raw)
        if enc == "deflate":
            try:
                return zlib.decompress(raw)
            except zlib.error:
                return zlib.decompress(raw, -zlib.MAX_WBITS)
    except Exception:
        pass
    return raw


def fetch_html(url, retries=3, timeout=15):
    """
    Return (html_str, note). note == "" on success; otherwise a short reason.
    Rotates header profiles and retries before giving up.
    """
    last = "unknown"
    attempt = 0
    for cycle in range(retries):
        for prof in _PROFILES:
            attempt += 1
            try:
                # Do NOT advertise br (brotli); urllib can't decode it.
                headers = dict(prof)
                headers["Accept-Encoding"] = "gzip, deflate"
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    raw = r.read()
                    body = _decompress(raw, r.headers).decode("utf-8", "ignore")
                    if len(body) > 2000:            # a real product page is big
                        return body, ""
                    last = "short_response"
            except urllib.error.HTTPError as e:
                last = "http_%s" % e.code
            except Exception as e:
                last = "err_%s" % type(e).__name__
            time.sleep(1.2)
        time.sleep(2 + cycle * 2)                   # backoff between full cycles
    return "", last

# Poppigo Tracker — Mac Setup

Blinkit blocks GitHub's servers, so data is collected on your Mac (which also
gives you a **Mumbai** dark store). The dashboard still lives online and updates
by itself. After setup you never touch anything.

## One-time setup (~10 min)

1. Unzip the folder somewhere permanent — e.g. **Documents** (NOT Downloads,
   things get cleaned out of there).

2. Open **Terminal** (Cmd+Space → "Terminal"). Paste this exactly, press Enter:
   ```
   cd ~/Documents/qcom_tracker && git init && git remote add origin https://github.com/rtnnilimajhunjhunwala-lang/qcom_tracker.git && git branch -M main && git pull origin main
   ```
   If it asks you to sign in to GitHub, do it. This links your Mac to your repo
   so it can publish data. (One time only.)

3. Double-click **`Install Auto-Collection.command`**.
   - If macOS blocks it: right-click → **Open** → **Open** (first time only).
   - It sets up automatic hourly collection and runs once immediately.

**That's the whole setup. You're done.**

## What happens now (automatically)

- Collects all 55 products **every hour your Mac is awake**
- **Restarts itself after a reboot** — no need to reinstall
- **Catches up after sleep** — a missed run fires when you reopen the Mac
- Only runs **8am–11pm** (skips the quiet night hours)
- Publishes to your dashboard each time — your bookmarked URL just updates

The only time it pauses is when the Mac is **fully shut down**. Open the lid and
it resumes. For overnight coverage, keep it plugged in with lid open; otherwise
a MacBook Air deep-sleeps with the lid closed (fine — daytime data is what
matters for sales).

## Using it

Just open your dashboard bookmark. That's it. The data fills in on its own.

Give it a day before trusting the sales numbers — the banner at the top tells you
when there's enough (⏳ too early → 📈 building → ✅ good).

## Controls

- **`Collect Poppigo Data`** — force a collection right now (don't need to, but handy)
- **`Check Which Store`** — shows which dark store you're reading
- **`Stop Auto-Collection`** — turns the automatic runs off
- **`Install Auto-Collection`** — turn them back on (safe to run again anytime)

## If something looks off
- Dashboard not updating? Open the Mac, wait for the next hourly run, hard-refresh
  the page (Cmd+Shift+R).
- Want to see what happened? Open `_auto_log.txt` in the folder — every run logs there.

# Q-Com Recon — Setup Guide

**What this is:** an automatic competitor tracker for Blinkit. It watches 55 period-panty
SKUs across 15 brands (including PoppiGo) and works out **how much each brand is selling**
and **their market share** — by watching their stock go down.

**Once set up, it runs itself.** Nobody has to do anything. You just open a webpage.

**Cost: ₹0.** Forever.

---

## Part 1 — One-time setup (25 minutes, done once)

### Step 1 — Make a GitHub account
1. Go to **github.com**
2. Click **Sign up**. Use a work email. Free plan — don't pay for anything.

### Step 2 — Make a repository
1. Click the **+** at the top right → **New repository**
2. **Repository name:** `qcom-tracker`
3. Choose **Public**
   *(Must be Public for the free dashboard webpage. There are no secrets in here — just
   competitor prices anyone can already see on Blinkit.)*
4. Click **Create repository**

### Step 3 — Upload the files
1. Click the link **"uploading an existing file"**
2. Open the `qcom_tracker` folder on your computer
3. Select **everything inside it** and drag it into the browser
4. Click **Commit changes**

**Then check one thing.** In your repo's file list you must see a folder called
**`.github`**. If it's not there, go to *"If .github didn't upload"* at the bottom and fix
it — nothing works without it.

### Step 4 — Let the robot save its work
1. **Settings** (top menu)
2. Left sidebar → **Actions** → **General**
3. Scroll to **Workflow permissions**
4. Select **Read and write permissions**
5. Click **Save**

### Step 5 — Turn on the dashboard webpage
1. Still in **Settings**
2. Left sidebar → **Pages**
3. Under **Source**, choose **GitHub Actions**
4. Nothing to save — that's it

### Step 6 — Start it
1. Click the **Actions** tab
2. If asked, click the green **"I understand my workflows, go ahead and enable them"**
3. Left side: click **Snapshot + publish dashboard**
4. Right side: **Run workflow** → green **Run workflow** button
5. Wait ~2 minutes, refresh. You want a green tick.

### Step 7 — Get your dashboard link
1. **Settings** → **Pages**
2. Your live link appears at the top:

   **`https://YOUR-USERNAME.github.io/qcom-tracker/`**

3. **Open it. Bookmark it. That's the dashboard.**

**Done. Never touch this again.**

---

## Part 2 — Using it

**Open the bookmark.** That's the entire job. The page updates itself.

| When | What happens |
|---|---|
| **Monday, 9:00 AM** | Price + stock snapshot of all 55 SKUs |
| **Wednesday, hourly, 8am–10pm** | Watches stock move — **this is what measures sales** |

The Wednesday run is the important one. Sales can only be seen by watching stock *drop*
between checks. One weekly snapshot gives prices; hourly checks give sales.

**Want fresh data right now?** Actions tab → **Run workflow**. Two minutes.

---

## Part 3 — Reading the dashboard

**Top cards** — PoppiGo's rank vs all brands, estimated category size, who's out of stock
(a competitor OOS is losing sales today).

**Velocity leaderboard** — the most important thing on the page. Units sold per store per
day. **PoppiGo is gold with a "YOU" badge.** If Sirona is 30 and PoppiGo is 5, Sirona sells
6× faster. Click brand chips to filter.

**Live shelf** — every SKU's price, discount, stock, rating. Click headers to sort. Best
way to spot who just cut their price.

---

## The one number that makes this accurate

Everything rests on one assumption: **what % of Blinkit's 2,243 dark stores carry each brand.**

**Ask our Blinkit KAM: "how many dark stores is PoppiGo listed in?"**

One email. They know. Then drag the **store penetration slider** to that number
(250 stores ÷ 2,243 = 11%).

Our revenue line becomes *real* instead of estimated, and every competitor comparison gets
sharper. **That single number is worth more than everything else here.**

---

## What to trust

| | |
|---|---|
| ✅ **Shelf share %** | **Bias-free.** Built only from observed stock movement — no store-count guesses. This is the fair way to compare brands. |
| ✅ **The velocity ranking** | Rock solid. Who outsells whom at the shelf. |
| ✅ **Price, discount, stock, rating** | Read straight off Blinkit. Exact. |
| ⚠️ **Absolute rupees/units** | Directional. PoppiGo's is real (450 stores); competitors' use a flat scenario that *under*-states big brands. |
| ❌ **National market share** | This is **Blinkit only**. Not Amazon, Flipkart, pharmacy, D2C. |

**On bias:** competitors are all given the *same* store-count assumption, so no rival
is inflated by a guess. We do **not** tell the model who is big — the shelf-share ranking
comes entirely from which brand's stock actually moved. Only PoppiGo uses a real store
count (450), and only for its own absolute volume line.

**If whoami.py or a run shows a 403:** that's Cloudflare's intermittent IP block. The code
now retries with rotating browser profiles automatically. If it still fails: wait 2-3 min,
or toggle wifi for a new IP. It never affects the cloud runs.

---

## Troubleshooting

**Dashboard link 404s** — the first run must finish before the page exists. Check Actions
for a green tick. Red? Usually Step 4 (permissions) was missed.

**Loads but says no data** — run the workflow once manually.

**Leaderboard empty, but shelf table has data** — normal at the start. Sales need stock to
move *between* snapshots. Fills in after the first Wednesday hourly run.

**Red X on a run** — click it, read the red line. Almost always Step 4.

**If `.github` didn't upload**
GitHub's drag-and-drop sometimes skips dot-folders. Fix it manually:
1. **Add file** → **Create new file**
2. Filename box, type exactly: `.github/workflows/tracker.yml`
   *(the slashes create the folders automatically)*
3. Open `tracker.yml` from `qcom_tracker/.github/workflows/` on your computer in
   TextEdit/Notepad. Select all, copy.
4. Paste into the big box on GitHub. **Commit changes.**

---

## For whoever is technical (optional)

`python3 tracker.py --only blinkit` needs no packages at all.

- **`whoami.py`** — important. Blinkit picks the dark store from your **IP address**; there
  is no pincode setting (tested and confirmed — location cookies are ignored). GitHub's
  servers read Blinkit's default store (Gurugram); your Mumbai wifi should read a Mumbai
  store. Run this to see which store a given connection actually reads. Consistency is what
  matters for ranking.
- **`market_share.py`** — brand share table in the terminal.
- **`skus.py`** — add/remove SKUs, tune `BRAND_PENETRATION`.
- **`run_local.sh`** — adds Zepto + Instamart. They **block datacenter IPs**, so they only
  work from normal wifi, never from GitHub's servers. Needs
  `pip install -r requirements.txt` then `python3 -m playwright install chromium`.

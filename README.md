# IFVG Command Center — Full Dashboard (frontend complete)

This is the finalized dashboard: every section we planned is built and wired
to real data, styled as a dark, mouse-reactive HUD. It's one web app — same
URL on your phone and your computer, same live data on both, because
everything lives in one database on the server.

## What's live now

- **Pre-Market Briefing** — a composite view: today's calendar events, live
  setups, account health, and risk used, all in one glance.
- **Live Setup Tracker** — latest alert per symbol/timeframe, color-coded by
  how many of the 5 conditions are met. Auto-refreshes every 30s.
- **Active Trade Management** — check off your 5 conditions to unlock a
  calculator: breakeven, risk/reward, and exact contracts to take based on
  your dollar risk and stop distance.
- **Trade Journal** — manual entry or bulk import from a Tradovate CSV
  export (fills get paired into round-turn trades automatically, duplicates
  are skipped on re-import).
- **Alert History** — every alert ever sent, with a "did you take it?"
  tracker.
- **Multi-Account Overview** — add every account (Apex now, more later),
  see balance, distance to drawdown floor, distance to profit target, and
  combined totals across everything. Includes a daily/weekly risk cap
  tracker fed by the risk amounts you log per trade.
- **Economic Calendar & News** — log red/orange/yellow events manually for
  now (see limitations below), plus a curated list of fast-breaking news
  accounts (Walter Bloomberg, RANsquawk, etc.) as a starting point.
- **Psychology & Rule Compliance** — win rate on trades where you followed
  all 5 conditions vs. trades where you didn't, so you can see whether
  losses come from bad setups or from skipping your own rules.
- **Goals & Milestones** — track progress toward an account's profit
  target, or any custom goal, with a progress bar.
- **Stats** — win rate and P/L, overall and by session.
- **Correlation Matrix & Backtesting** — intentionally left as placeholder
  tabs for now. Both genuinely need a live market data feed / historical
  data source, which is real backend work, not just UI. That's next.

## What's NOT automated yet (the "backend phase")

- **Economic calendar events are manual entry.** A real automated feed
  (scraping or an API for Forex Factory-style red/orange/yellow events)
  is backend work we haven't built.
- **News links are a static curated list**, not a live feed pulling actual
  headlines.
- **Correlation Matrix and Backtesting** need a live/historical price data
  source — not built yet, tabs are placeholders explaining why.
- **Tradovate is CSV import only**, not live sync — see the note further
  down on why, and what a live sync would take.
- **No login yet**, per your request — anyone with the URL can see and
  edit everything. Worth adding once this is more than just you using it.

## Design notes

Dark navy background with a cyan/green glow that follows your cursor
across the whole page, panel borders that light up on hover, corner-bracket
framing on panels (HUD-style), and a live pulsing status indicator — built
to feel like an instrument panel, not a form.

## Deploying this (same Render service as before)

1. Replace the contents of your `ifvg-alerts` GitHub repo with everything
   in this project: `app.py`, `db.py`, `tradovate_import.py`,
   `requirements.txt`, `Procfile`, `templates/dashboard.html`,
   `static/style.css`, `static/script.js`.
2. Commit and push — Render auto-redeploys (or trigger manually).
3. Start Command should be `gunicorn app:app`.
4. Your `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` env vars, and your
   TradingView webhook URL, all stay exactly the same.
5. Open your Render URL in a browser on your phone or computer — that's
   the dashboard.

## Automatic trade logging (Tradovate CSV import)

In the Trade Journal tab, click **Import from Tradovate CSV**:

1. In Tradovate (web or desktop), go to **Reports → Orders** (or **Fills**
   — not Performance), pick your date range, and export the CSV.
2. Upload it in the Trade Journal tab.
3. It reports how many trades were imported and skips anything already
   imported before, so re-exporting an overlapping date range is safe.

**Honest limitations of this importer:**

- Tradovate's export is one row per *fill*; this pairs entry/exit fills
  into trades via FIFO matching, which is correct in the vast majority of
  cases but worth spot-checking the first few times against your statement.
- P/L uses standard point values for common futures contracts (ES, NQ, MES,
  MNQ, GC, CL, etc.). Anything not on that list gets flagged with P/L left
  blank for you to fill in.
- Session (London/NY AM/Asian) is a rough hour-based guess from the fill
  timestamp, not exact killzone matching.

**Why not live Tradovate sync?** Tradovate's official paid API (the "API
Access Add-on," $25/month) requires a live funded account with a $1,000+
balance, and explicitly excludes prop firm and evaluation accounts — so it
won't work for your Apex account. Third-party tools like TradeLog claim
real-time sync with Apex/Tradeify accounts using a login-based approach
instead of the paid add-on. That's the next thing worth testing, but it's
undocumented for prop accounts and needs to be verified with your real
login before we build on it.

## One important note on the database

This uses SQLite (`dashboard.db`), a simple file-based database — great for
building fast at zero cost, but **Render's free tier has an ephemeral
filesystem**, meaning a restart or redeploy can wipe that file. Fine while
testing, but before trusting this with real trade history, we should move
to Render's free PostgreSQL, which doesn't get wiped. Quick swap whenever
you're ready — just say the word.

## Local testing

```
pip install -r requirements.txt
python app.py
```
Then open `http://localhost:5000` in your browser.

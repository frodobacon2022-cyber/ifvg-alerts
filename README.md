# IFVG Early Warning System

Full pipeline: TradingView chart -> Pine Script detects a forming IFVG setup ->
webhook -> Telegram message to your phone, before the setup fully confirms.
Entirely free — no Twilio, no trial credits, no per-message cost.

## Files

- `ifvg_early_warning.pine` — the indicator/alert logic. Paste into TradingView's
  Pine Editor, add to your chart, then create an alert off of it.
- `webhook_server.py` — small server that receives the TradingView alert and
  sends you a Telegram message.
- `requirements.txt` / `Procfile` — for deploying the server to Render (or
  similar) for free.

## What the Pine Script checks

1. **HTF trend + liquidity target** — daily/4H structure direction, is there
   a clear high/low to target.
2. **Liquidity sweep** — price wicks past a prior swing point and closes back
   inside it.
3. **Old FVG alignment** — does that sweep level line up with a fair value
   gap from further back on the chart.
4. **Killzone timing** — London, NY AM, or Asian session windows.
5. **Clean move (low chop)** — strong-bodied candle + directional range vs
   ATR, matching Dodgy's "no chop" grading criteria.
6. **SMT divergence** — compares against a correlated symbol (defaults to
   ES for NQ) to confirm smart-money divergence.

The alert fires when the setup is **forming** — sweep + trend + FVG + session +
chop + SMT all present — but *before* the candle closes and fully confirms.
That's the buffer you asked for: time to pull up the chart, watch the final
confirmation candle, and decide instead of getting told after the move's gone.

## Setup steps

### 1. Pine Script
- Open TradingView -> Pine Editor -> paste `ifvg_early_warning.pine` -> Add to Chart.
- Set the "Correlated Symbol" input to whatever matches what you trade (ES for
  NQ, QQQ for SPY, etc).
- Right-click the chart -> Add Alert -> Condition: this indicator -> choose
  "Bullish IFVG Setup Forming" or "Bearish IFVG Setup Forming".
- In the alert's Notifications tab, paste your webhook URL (see step 3).

### 2. Telegram bot (free, no limits)
- Open Telegram, message @BotFather, send `/newbot`, follow the prompts.
- BotFather gives you a token like `123456789:ABCdefGhIJKlmNoPQRstuVwxYZ`.
- Search for your new bot's username and send it any message (e.g. "hi").
- Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser —
  you'll see a `"chat":{"id": ...}` field. That number is your chat ID.

### 3. Deploy the webhook server (free)
- Push `webhook_server.py`, `requirements.txt`, and `Procfile` to a small
  GitHub repo.
- Create a free Web Service on render.com pointing at that repo.
- Set environment variables: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- Once deployed, your webhook URL is `https://<your-app>.onrender.com/webhook`
  — paste that into the TradingView alert.

## Known limitations / next steps to refine

- **Liquidity target logic is simplified.** Right now it just checks the last
  couple of HTF highs/lows rather than tracking truly unmitigated swing
  points. Worth tightening once you're testing live.
- **Chop filter is a proxy**, not a direct replica of Dodgy's visual grading —
  it's a reasonable mechanical stand-in but won't catch every nuance a human
  eye would.
- **No probability score** — intentionally left out per your call, since
  there isn't enough trade history yet to make one meaningful. Worth
  revisiting once you're logging enough trades through this system.
- **Free hosting tiers can spin down when idle** and take a few seconds to
  wake up on the next webhook — shouldn't matter for this use case, but worth
  knowing.
- This has **not been backtested or forward-tested** — treat every alert as a
  "go look at the chart" prompt, not a trade signal, until you've validated
  it against real setups.

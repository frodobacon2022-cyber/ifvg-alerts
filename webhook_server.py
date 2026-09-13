"""
IFVG Alert Webhook Receiver
----------------------------
Receives the JSON alert from TradingView (fired by ifvg_early_warning.pine),
formats it into a readable text, and sends it to you via a Telegram bot —
completely free, no message limits, official API.

HOW TO RUN THIS FOR FREE, 24/7:
1. Create a free account at https://render.com (or Railway, Fly.io — all have
   free tiers suitable for a low-traffic webhook like this).
2. Push this file to a small GitHub repo with the requirements.txt below.
3. Deploy it as a "Web Service" on Render. It'll give you a public URL like
   https://your-app-name.onrender.com
4. In TradingView, when creating your alert, paste that URL + "/webhook"
   (e.g. https://your-app-name.onrender.com/webhook) into the "Webhook URL"
   field in the alert's Notifications tab.
5. Create a Telegram bot (free, takes 2 minutes):
   - Open Telegram, search for "@BotFather", start a chat, send /newbot
   - Follow the prompts (name it anything) — BotFather gives you a token
     that looks like 123456789:ABCdefGhIJKlmNoPQRstuVwxYZ
   - Send any message to your new bot (search its username, hit Start)
   - Get your chat_id by visiting this URL in a browser (with your token):
     https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
     — after sending your bot a message, this will show a "chat":{"id": ...}
     field. That number is your chat_id.
6. Set the environment variables below (on Render, under "Environment").

NOTE ON COST: Render's free tier can "spin down" when idle and take a few
seconds to wake up on the next request — for an alert-based system that's
usually fine since a few seconds of delay doesn't matter here. Telegram's
Bot API itself is entirely free with no message limits.
"""

import os
import json
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Set these as environment variables in your hosting platform — never hardcode them.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram not configured. Would have sent:\n", text)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    resp = requests.post(url, json=payload, timeout=10)
    if resp.status_code != 200:
        print("Telegram send failed:", resp.status_code, resp.text)


def format_alert_message(data: dict) -> str:
    """Turn the parsed TradingView JSON payload into a clean, readable text."""
    direction = data.get("direction", "UNKNOWN")
    symbol = data.get("symbol", "?")
    timeframe = data.get("timeframe", "?")
    time_str = data.get("time", "?")
    reasons = data.get("reasons", [])
    status = data.get("status", "")

    reasons_text = "\n".join(f"  - {r}" for r in reasons)

    message = (
        f"{direction} IFVG setup forming\n"
        f"Symbol: {symbol}\n"
        f"Timeframe: {timeframe}\n"
        f"Time: {time_str}\n\n"
        f"Conditions met:\n{reasons_text}\n\n"
        f"Status: {status}"
    )
    return message


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw_body = request.get_data(as_text=True)
        data = json.loads(raw_body)
    except (json.JSONDecodeError, TypeError):
        return jsonify({"error": "Invalid JSON payload"}), 400

    text_message = format_alert_message(data)
    send_telegram_message(text_message)

    return jsonify({"status": "received"}), 200


@app.route("/", methods=["GET"])
def health_check():
    # Simple endpoint so you (or a free uptime pinger) can confirm the
    # service is alive.
    return "IFVG webhook server is running.", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

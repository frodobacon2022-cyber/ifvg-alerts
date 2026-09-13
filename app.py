"""
IFVG Trading Dashboard - Phase 1
---------------------------------
Extends the original webhook server: still receives TradingView alerts and
sends Telegram notifications exactly as before, but now also:
  - Stores every alert in a database (powers the Live Setup Tracker + Alert
    History Log)
  - Serves a mobile/desktop-friendly dashboard with a Trade Journal you can
    log trades into manually

Same deployment target as before (Render). See README.md for setup steps.
"""

import os
import json
import requests
from flask import Flask, request, jsonify, render_template

import db
import tradovate_import

app = Flask(__name__)
db.init_db()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


# ---------------------------------------------------------------------------
# Telegram (unchanged from original webhook server)
# ---------------------------------------------------------------------------

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
    direction = data.get("direction", "UNKNOWN")
    symbol = data.get("symbol", "?")
    timeframe = data.get("timeframe", "?")
    time_str = data.get("time", "?")
    reasons = data.get("reasons", [])
    status = data.get("status", "")
    reasons_text = "\n".join(f"  - {r}" for r in reasons)
    return (
        f"{direction} IFVG setup forming\n"
        f"Symbol: {symbol}\n"
        f"Timeframe: {timeframe}\n"
        f"Time: {time_str}\n\n"
        f"Conditions met:\n{reasons_text}\n\n"
        f"Status: {status}"
    )


# ---------------------------------------------------------------------------
# Webhook (receives from TradingView, unchanged behavior + now logs to DB)
# ---------------------------------------------------------------------------

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw_body = request.get_data(as_text=True)
        data = json.loads(raw_body)
    except (json.JSONDecodeError, TypeError):
        return jsonify({"error": "Invalid JSON payload"}), 400

    text_message = format_alert_message(data)
    send_telegram_message(text_message)

    conn = db.get_conn()
    conn.execute(
        """INSERT INTO alerts (received_at, symbol, timeframe, direction, status, reasons, raw_payload)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            db.now_iso(),
            data.get("symbol", "?"),
            data.get("timeframe", "?"),
            data.get("direction", "UNKNOWN"),
            data.get("status", ""),
            json.dumps(data.get("reasons", [])),
            raw_body,
        ),
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "received"}), 200


# ---------------------------------------------------------------------------
# API - Alerts (Setup Tracker + Alert History)
# ---------------------------------------------------------------------------

@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    limit = int(request.args.get("limit", 100))
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    alerts = []
    for r in rows:
        d = dict(r)
        try:
            d["reasons"] = json.loads(d["reasons"]) if d["reasons"] else []
        except (json.JSONDecodeError, TypeError):
            d["reasons"] = []
        alerts.append(d)
    return jsonify(alerts)


@app.route("/api/alerts/<int:alert_id>", methods=["PATCH"])
def update_alert(alert_id):
    data = request.get_json(force=True)
    conn = db.get_conn()
    conn.execute(
        "UPDATE alerts SET taken = ?, outcome_note = ? WHERE id = ?",
        (data.get("taken"), data.get("outcome_note"), alert_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "updated"})


# ---------------------------------------------------------------------------
# API - Trade Journal
# ---------------------------------------------------------------------------

TRADE_FIELDS = [
    "symbol", "direction", "session", "timeframe", "entry_price", "stop_price",
    "target_price", "exit_price", "contracts", "risk_amount", "pnl",
    "account_name", "cond_htf_trend", "cond_liquidity_sweep", "cond_killzone",
    "cond_smt_divergence", "cond_clean_move", "result", "notes", "alert_id",
    "source", "external_key",
]


@app.route("/api/trades", methods=["GET"])
def get_trades():
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM trades ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/trades", methods=["POST"])
def create_trade():
    data = request.get_json(force=True)
    values = {f: data.get(f) for f in TRADE_FIELDS}
    conn = db.get_conn()
    cols = ", ".join(values.keys())
    placeholders = ", ".join(["?"] * len(values))
    conn.execute(
        f"INSERT INTO trades (created_at, {cols}) VALUES (?, {placeholders})",
        (db.now_iso(), *values.values()),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "created"}), 201


@app.route("/api/trades/<int:trade_id>", methods=["PUT"])
def update_trade(trade_id):
    data = request.get_json(force=True)
    values = {f: data.get(f) for f in TRADE_FIELDS}
    conn = db.get_conn()
    set_clause = ", ".join(f"{k} = ?" for k in values.keys())
    conn.execute(
        f"UPDATE trades SET {set_clause} WHERE id = ?",
        (*values.values(), trade_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "updated"})


@app.route("/api/trades/<int:trade_id>", methods=["DELETE"])
def delete_trade(trade_id):
    conn = db.get_conn()
    conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})


@app.route("/api/import/tradovate", methods=["POST"])
def import_tradovate_csv():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]
    file_bytes = file.read()

    parsed_trades, warnings = tradovate_import.parse_tradovate_csv(file_bytes)
    if not parsed_trades and warnings:
        return jsonify({"imported": 0, "skipped_duplicates": 0, "warnings": warnings}), 200

    conn = db.get_conn()
    imported = 0
    skipped = 0
    for t in parsed_trades:
        created_at = t.pop("created_at_override", None)
        created_at = created_at.isoformat() if created_at else db.now_iso()
        values = {f: t.get(f) for f in TRADE_FIELDS}
        try:
            cols = ", ".join(values.keys())
            placeholders = ", ".join(["?"] * len(values))
            conn.execute(
                f"INSERT INTO trades (created_at, {cols}) VALUES (?, {placeholders})",
                (created_at, *values.values()),
            )
            imported += 1
        except db.sqlite3.IntegrityError:
            # external_key already exists — this fill pairing was already imported
            skipped += 1
    conn.commit()
    conn.close()

    return jsonify({"imported": imported, "skipped_duplicates": skipped, "warnings": warnings}), 200


# ---------------------------------------------------------------------------
# API - Accounts (Multi-Account Overview)
# ---------------------------------------------------------------------------

ACCOUNT_FIELDS = [
    "name", "firm", "account_type", "starting_balance", "current_balance",
    "profit_target", "max_drawdown", "status",
]


@app.route("/api/accounts", methods=["GET"])
def get_accounts():
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM accounts ORDER BY id").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/accounts", methods=["POST"])
def create_account():
    data = request.get_json(force=True)
    values = {f: data.get(f) for f in ACCOUNT_FIELDS}
    conn = db.get_conn()
    cols = ", ".join(values.keys())
    placeholders = ", ".join(["?"] * len(values))
    conn.execute(
        f"INSERT INTO accounts (created_at, {cols}) VALUES (?, {placeholders})",
        (db.now_iso(), *values.values()),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "created"}), 201


@app.route("/api/accounts/<int:account_id>", methods=["PUT"])
def update_account(account_id):
    data = request.get_json(force=True)
    values = {f: data.get(f) for f in ACCOUNT_FIELDS}
    conn = db.get_conn()
    set_clause = ", ".join(f"{k} = ?" for k in values.keys())
    conn.execute(f"UPDATE accounts SET {set_clause} WHERE id = ?", (*values.values(), account_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "updated"})


@app.route("/api/accounts/<int:account_id>", methods=["DELETE"])
def delete_account(account_id):
    conn = db.get_conn()
    conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})


# ---------------------------------------------------------------------------
# API - Economic Calendar
# ---------------------------------------------------------------------------

CALENDAR_FIELDS = ["event_date", "event_time", "title", "impact", "notes"]


@app.route("/api/calendar", methods=["GET"])
def get_calendar_events():
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT * FROM calendar_events ORDER BY event_date, event_time"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/calendar", methods=["POST"])
def create_calendar_event():
    data = request.get_json(force=True)
    values = {f: data.get(f) for f in CALENDAR_FIELDS}
    conn = db.get_conn()
    cols = ", ".join(values.keys())
    placeholders = ", ".join(["?"] * len(values))
    conn.execute(
        f"INSERT INTO calendar_events (created_at, {cols}) VALUES (?, {placeholders})",
        (db.now_iso(), *values.values()),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "created"}), 201


@app.route("/api/calendar/<int:event_id>", methods=["DELETE"])
def delete_calendar_event(event_id):
    conn = db.get_conn()
    conn.execute("DELETE FROM calendar_events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})


# ---------------------------------------------------------------------------
# API - Goals / Milestones
# ---------------------------------------------------------------------------

GOAL_FIELDS = ["title", "account_id", "starting_value", "target_value", "current_value", "target_date", "notes"]


@app.route("/api/goals", methods=["GET"])
def get_goals():
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM goals ORDER BY id").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/goals", methods=["POST"])
def create_goal():
    data = request.get_json(force=True)
    values = {f: data.get(f) for f in GOAL_FIELDS}
    conn = db.get_conn()
    cols = ", ".join(values.keys())
    placeholders = ", ".join(["?"] * len(values))
    conn.execute(
        f"INSERT INTO goals (created_at, {cols}) VALUES (?, {placeholders})",
        (db.now_iso(), *values.values()),
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "created"}), 201


@app.route("/api/goals/<int:goal_id>", methods=["PUT"])
def update_goal(goal_id):
    data = request.get_json(force=True)
    values = {f: data.get(f) for f in GOAL_FIELDS}
    conn = db.get_conn()
    set_clause = ", ".join(f"{k} = ?" for k in values.keys())
    conn.execute(f"UPDATE goals SET {set_clause} WHERE id = ?", (*values.values(), goal_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "updated"})


@app.route("/api/goals/<int:goal_id>", methods=["DELETE"])
def delete_goal(goal_id):
    conn = db.get_conn()
    conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})


# ---------------------------------------------------------------------------
# API - Settings (risk caps, etc.)
# ---------------------------------------------------------------------------

@app.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify({
        "daily_risk_cap": db.get_setting("daily_risk_cap"),
        "weekly_risk_cap": db.get_setting("weekly_risk_cap"),
    })


@app.route("/api/settings", methods=["POST"])
def update_settings():
    data = request.get_json(force=True)
    if "daily_risk_cap" in data:
        db.set_setting("daily_risk_cap", data["daily_risk_cap"])
    if "weekly_risk_cap" in data:
        db.set_setting("weekly_risk_cap", data["weekly_risk_cap"])
    return jsonify({"status": "updated"})


# ---------------------------------------------------------------------------
# API - Psychology / Rule Compliance (derived from trade journal data)
# ---------------------------------------------------------------------------

@app.route("/api/psychology", methods=["GET"])
def get_psychology_stats():
    conn = db.get_conn()
    trades = conn.execute("SELECT * FROM trades").fetchall()
    conn.close()

    cond_keys = ["cond_htf_trend", "cond_liquidity_sweep", "cond_killzone", "cond_smt_divergence", "cond_clean_move"]

    total = len(trades)
    full_compliance = 0  # all 5 conditions present
    partial_compliance = 0  # 1-4 present
    no_conditions = 0  # 0 present

    compliant_wins = compliant_losses = 0
    noncompliant_wins = noncompliant_losses = 0

    for t in trades:
        count = sum(1 for k in cond_keys if t[k])
        if count == 5:
            full_compliance += 1
        elif count == 0:
            no_conditions += 1
        else:
            partial_compliance += 1

        result = (t["result"] or "").lower()
        if count == 5:
            if result == "win":
                compliant_wins += 1
            elif result == "loss":
                compliant_losses += 1
        else:
            if result == "win":
                noncompliant_wins += 1
            elif result == "loss":
                noncompliant_losses += 1

    def win_rate(wins, losses):
        d = wins + losses
        return round((wins / d) * 100, 1) if d else None

    return jsonify({
        "total_trades": total,
        "full_compliance": full_compliance,
        "partial_compliance": partial_compliance,
        "no_conditions": no_conditions,
        "compliant_win_rate": win_rate(compliant_wins, compliant_losses),
        "noncompliant_win_rate": win_rate(noncompliant_wins, noncompliant_losses),
        "compliant_trades": compliant_wins + compliant_losses,
        "noncompliant_trades": noncompliant_wins + noncompliant_losses,
    })


# ---------------------------------------------------------------------------
# API - Stats (basic, powers small summary cards on the dashboard)
# ---------------------------------------------------------------------------

@app.route("/api/stats", methods=["GET"])
def get_stats():
    conn = db.get_conn()
    trades = conn.execute("SELECT * FROM trades").fetchall()
    conn.close()

    total = len(trades)
    wins = len([t for t in trades if (t["result"] or "").lower() == "win"])
    losses = len([t for t in trades if (t["result"] or "").lower() == "loss"])
    decided = wins + losses
    win_rate = round((wins / decided) * 100, 1) if decided else None
    total_pnl = sum(t["pnl"] for t in trades if t["pnl"] is not None)

    by_session = {}
    for t in trades:
        s = t["session"] or "Unspecified"
        by_session.setdefault(s, {"wins": 0, "losses": 0, "total_pnl": 0})
        if (t["result"] or "").lower() == "win":
            by_session[s]["wins"] += 1
        elif (t["result"] or "").lower() == "loss":
            by_session[s]["losses"] += 1
        if t["pnl"] is not None:
            by_session[s]["total_pnl"] += t["pnl"]

    return jsonify({
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "total_pnl": round(total_pnl, 2),
        "by_session": by_session,
    })


@app.route("/api/risk-status", methods=["GET"])
def get_risk_status():
    from datetime import datetime, timezone, timedelta
    conn = db.get_conn()
    trades = conn.execute("SELECT created_at, risk_amount FROM trades WHERE risk_amount IS NOT NULL").fetchall()
    conn.close()

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    risked_today = 0.0
    risked_week = 0.0
    for t in trades:
        try:
            ts = datetime.fromisoformat(t["created_at"])
        except (ValueError, TypeError):
            continue
        if ts >= today_start:
            risked_today += t["risk_amount"] or 0
        if ts >= week_start:
            risked_week += t["risk_amount"] or 0

    daily_cap = db.get_setting("daily_risk_cap")
    weekly_cap = db.get_setting("weekly_risk_cap")

    return jsonify({
        "risked_today": round(risked_today, 2),
        "risked_week": round(risked_week, 2),
        "daily_cap": float(daily_cap) if daily_cap else None,
        "weekly_cap": float(weekly_cap) if weekly_cap else None,
    })


# ---------------------------------------------------------------------------
# Dashboard frontend + health check
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def dashboard():
    return render_template("dashboard.html")


@app.route("/health", methods=["GET"])
def health_check():
    return "IFVG dashboard server is running.", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

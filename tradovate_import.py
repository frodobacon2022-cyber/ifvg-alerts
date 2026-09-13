"""
Tradovate CSV Import
---------------------
Tradovate's export (from Reports > Orders or Reports > Fills) gives one row
PER FILL (i.e. per execution), not per round-trip trade. A single trade you
took shows up as at least two rows: the entry fill and the exit fill. This
module pairs those fills back into actual trades (FIFO, per account+contract)
so the journal shows one row per trade like you'd expect.

Column names in Tradovate's export can vary slightly depending on which
report tab you export from and whether it's the web or desktop client, so
this parses headers case-insensitively against a list of known aliases
rather than expecting one exact format.
"""

import csv
import hashlib
import io
from collections import defaultdict
from datetime import datetime

# Common futures point values ($ per 1.00 move per contract), used to estimate
# P/L when the export doesn't include a realized P/L column directly. This
# list covers the most common CME/CBOT contracts; unrecognized symbols are
# left with pnl=None rather than guessing.
POINT_VALUES = {
    "ES": 50, "MES": 5,
    "NQ": 20, "MNQ": 2,
    "YM": 5, "MYM": 0.5,
    "RTY": 50, "M2K": 5,
    "GC": 100, "MGC": 10,
    "CL": 1000, "MCL": 100,
    "SI": 5000, "SIL": 1000,
    "ZB": 1000, "ZN": 1000, "ZF": 1000, "ZT": 2000,
    "6E": 125000, "6B": 62500, "6J": 12500000, "6A": 100000, "6C": 100000,
}

# Column alias groups -> canonical field name
COLUMN_ALIASES = {
    "account": ["account", "accountname"],
    "side": ["b/s", "buy/sell", "side", "action"],
    "contract": ["contract", "symbol", "product"],
    "qty": ["filledqty", "filled qty", "qty", "quantity", "orderqty"],
    "price": ["avgprice", "avg fill price", "price", "fillprice"],
    "fill_time": ["fill time", "filltime", "timestamp", "date", "time"],
    "pnl": ["realized pnl", "realizedpnl", "pnl", "p/l", "net p/l"],
}


def _normalize_header(h):
    return h.strip().lower().replace("_", " ")


def _map_columns(fieldnames):
    """Map this file's actual column names to our canonical field names."""
    normalized = {_normalize_header(f): f for f in fieldnames}
    mapping = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                mapping[canonical] = normalized[alias]
                break
    return mapping


def _contract_root(contract_str):
    """Pull the root symbol off a futures contract string, e.g. 'NQZ5' -> 'NQ',
    'MESH6' -> 'MES', 'M2KZ5' -> 'M2K'. Futures contracts end in a single-letter
    month code followed by 1-2 digits for the year, so we strip the trailing
    digits, then strip the month-code letter that remains."""
    if not contract_str:
        return ""
    s = contract_str.strip().upper()
    i = len(s)
    while i > 0 and s[i - 1].isdigit():
        i -= 1
    without_year = s[:i]
    if without_year and without_year[-1].isalpha():
        return without_year[:-1]
    return without_year


def _parse_side(raw):
    raw = (raw or "").strip().lower()
    if raw in ("b", "buy", "long"):
        return "buy"
    if raw in ("s", "sell", "short"):
        return "sell"
    return None


def _parse_time(raw):
    if not raw:
        return None
    raw = raw.strip()
    formats = [
        "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S %p",
        "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y", "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _classify_session(dt):
    """Rough UTC-hour based session classifier. Approximate — treat as a
    starting point, not a precise killzone match."""
    if dt is None:
        return "Unspecified"
    hour = dt.hour  # assumes fill_time is in UTC or close enough to be useful as an approximation
    if 7 <= hour < 10:
        return "London"
    if 13 <= hour < 16:
        return "NY AM"
    if 0 <= hour < 6:
        return "Asian"
    return "Other"


def parse_tradovate_csv(file_bytes):
    """
    Parses a Tradovate fills/orders CSV export and pairs fills into round-turn
    trades using FIFO matching per (account, contract).

    Returns (trades: list[dict], warnings: list[str])
    """
    warnings = []
    text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        return [], ["Couldn't read any columns from this file — is it a CSV export from Tradovate?"]

    mapping = _map_columns(reader.fieldnames)
    required = ["side", "contract", "qty", "price"]
    missing = [f for f in required if f not in mapping]
    if missing:
        return [], [
            f"This file is missing columns this importer needs: {', '.join(missing)}. "
            f"Found columns: {', '.join(reader.fieldnames)}. "
            f"Make sure you exported from Tradovate's Orders or Fills report (not Performance)."
        ]

    fills = []
    for row in reader:
        side = _parse_side(row.get(mapping["side"]))
        contract = (row.get(mapping["contract"]) or "").strip()
        try:
            qty = float(row.get(mapping["qty"]) or 0)
        except ValueError:
            qty = 0
        try:
            price = float(row.get(mapping["price"]) or 0)
        except ValueError:
            price = None
        fill_time = _parse_time(row.get(mapping.get("fill_time"), "")) if mapping.get("fill_time") else None
        account = (row.get(mapping.get("account", ""), "") or "").strip() if mapping.get("account") else ""

        if not side or not contract or not qty or price is None:
            continue
        fills.append({
            "account": account, "contract": contract, "side": side,
            "qty": qty, "price": price, "fill_time": fill_time,
        })

    if not fills:
        return [], ["No usable fill rows found in this file."]

    # Sort fills chronologically (fills without a parsed time sink to the end,
    # keeping their original relative order stable)
    fills.sort(key=lambda f: (f["fill_time"] is None, f["fill_time"]))

    # FIFO pairing per (account, contract root)
    open_lots = defaultdict(list)  # key -> list of {side, qty_remaining, price, time}
    trades = []

    for f in fills:
        key = (f["account"], _contract_root(f["contract"]))
        queue = open_lots[key]

        if not queue or queue[0]["side"] == f["side"]:
            # Opens or adds to a position in the same direction
            queue.append({
                "side": f["side"], "qty_remaining": f["qty"], "price": f["price"],
                "time": f["fill_time"], "contract": f["contract"],
            })
            continue

        # Opposite side — this closes existing lots (FIFO)
        remaining = f["qty"]
        matched_entry_value = 0.0
        matched_qty = 0.0
        entry_time = None
        while remaining > 0 and queue and queue[0]["side"] != f["side"]:
            lot = queue[0]
            take = min(remaining, lot["qty_remaining"])
            matched_entry_value += take * lot["price"]
            matched_qty += take
            entry_time = entry_time or lot["time"]
            lot["qty_remaining"] -= take
            remaining -= take
            if lot["qty_remaining"] <= 0:
                queue.pop(0)

        if matched_qty > 0:
            avg_entry = matched_entry_value / matched_qty
            # direction is based on which side opened the matched lots (the
            # opposite of the closing fill's side)
            opened_side = "buy" if f["side"] == "sell" else "sell"
            direction = "long" if opened_side == "buy" else "short"

            root = _contract_root(f["contract"])
            point_value = POINT_VALUES.get(root)
            pnl = None
            if point_value is not None:
                if direction == "long":
                    pnl = round((f["price"] - avg_entry) * matched_qty * point_value, 2)
                else:
                    pnl = round((avg_entry - f["price"]) * matched_qty * point_value, 2)
            else:
                warnings.append(
                    f"Unrecognized contract root '{root}' (from '{f['contract']}') — "
                    f"P/L left blank for that trade, fill it in manually."
                )

            ext_key_raw = f"{key[0]}|{root}|{entry_time}|{f['fill_time']}|{avg_entry}|{f['price']}|{matched_qty}"
            external_key = "tradovate:" + hashlib.sha256(ext_key_raw.encode()).hexdigest()[:24]

            trades.append({
                "symbol": root or f["contract"],
                "direction": direction,
                "session": _classify_session(entry_time),
                "timeframe": None,
                "entry_price": round(avg_entry, 4),
                "exit_price": round(f["price"], 4),
                "contracts": matched_qty,
                "pnl": pnl,
                "account_name": f["account"] or None,
                "result": ("win" if pnl > 0 else "loss" if pnl is not None and pnl < 0 else "breakeven") if pnl is not None else None,
                "notes": "Imported from Tradovate CSV",
                "source": "tradovate_csv",
                "external_key": external_key,
                "created_at_override": (entry_time or f["fill_time"]),
            })

        # Any leftover quantity opens a new position in the new direction
        if remaining > 0:
            queue.append({
                "side": f["side"], "qty_remaining": remaining, "price": f["price"],
                "time": f["fill_time"], "contract": f["contract"],
            })

    return trades, warnings

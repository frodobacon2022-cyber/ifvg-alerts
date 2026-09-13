"""
Forex Factory Calendar Sync
-----------------------------
Forex Factory itself has no official public API. This uses JBlanked's
documented third-party API (https://www.jblanked.com/news/api/docs/calendar/),
which mirrors Forex Factory's calendar data through an authenticated,
legitimate endpoint (not scraping).

Requires a free API key from https://www.jblanked.com/api/key/ set as the
JBLANKED_API_KEY environment variable.

IMPORTANT LIMITATION: JBlanked's free tier is rate-limited to 1 request per
day as of this writing. This module is built to be called manually (a "Sync
now" button), not on every page load, so that quota isn't burned
accidentally. Their site has also noted the Forex Factory endpoints are
"currently being serviced" — treat sync failures as possible, not a bug in
this code.
"""

import os
import hashlib
import requests
from datetime import datetime, timedelta

JBLANKED_BASE = "https://www.jblanked.com/news/api/forex-factory/calendar/range/"

IMPACT_MAP = {
    "high": "red",
    "medium": "orange",
    "low": "yellow",
    "none": "yellow",
}


def _parse_jblanked_date(date_str):
    """JBlanked dates look like '2024.02.08 15:30:00'."""
    try:
        return datetime.strptime(date_str, "%Y.%m.%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def sync_forexfactory_calendar(days_ahead=7):
    """
    Pulls Forex Factory events for [today, today + days_ahead] via JBlanked's
    API. Returns (events: list[dict], error: str|None).
    """
    api_key = os.environ.get("JBLANKED_API_KEY")
    if not api_key:
        return [], (
            "No JBLANKED_API_KEY set. Get a free key at "
            "https://www.jblanked.com/api/key/ and add it as an environment "
            "variable on Render."
        )

    today = datetime.utcnow().date()
    date_from = today.isoformat()
    date_to = (today + timedelta(days=days_ahead)).isoformat()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Api-Key {api_key}",
    }
    params = {"from": date_from, "to": date_to}

    try:
        resp = requests.get(JBLANKED_BASE, headers=headers, params=params, timeout=15)
    except requests.RequestException as e:
        return [], f"Couldn't reach JBlanked's API: {e}"

    if resp.status_code == 429:
        return [], "Rate limited — JBlanked's free tier allows 1 request per day. Try again tomorrow."
    if resp.status_code != 200:
        return [], f"JBlanked API returned {resp.status_code}: {resp.text[:200]}"

    try:
        raw_events = resp.json()
    except ValueError:
        return [], "JBlanked API didn't return valid JSON."

    if not isinstance(raw_events, list):
        return [], "Unexpected response shape from JBlanked API."

    events = []
    for e in raw_events:
        dt = _parse_jblanked_date(e.get("Date", ""))
        if dt is None:
            continue
        impact_raw = (e.get("Impact") or "none").strip().lower()
        impact = IMPACT_MAP.get(impact_raw, "yellow")
        title = e.get("Name") or "Untitled event"
        currency = e.get("Currency") or ""

        ext_key_raw = f"ff:{currency}:{title}:{dt.isoformat()}"
        external_key = "ff:" + hashlib.sha256(ext_key_raw.encode()).hexdigest()[:24]

        notes_parts = []
        if currency:
            notes_parts.append(currency)
        if e.get("Forecast") not in (None, ""):
            notes_parts.append(f"forecast {e['Forecast']}")
        if e.get("Previous") not in (None, ""):
            notes_parts.append(f"previous {e['Previous']}")

        events.append({
            "event_date": dt.date().isoformat(),
            "event_time": dt.strftime("%H:%M"),
            "title": f"{title} ({currency})" if currency else title,
            "impact": impact,
            "notes": " · ".join(notes_parts) if notes_parts else None,
            "source": "forexfactory",
            "external_key": external_key,
        })

    return events, None

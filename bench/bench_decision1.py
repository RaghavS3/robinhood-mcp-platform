"""Latency benchmark for decision models (Microsoft-Decision-1 vs TypeSafe Jev) through OpenRouter.

Usage:
    export OPENROUTER_API_KEY=...      # never paste the key into code or chat
    python3 bench/bench_decision1.py

Without a key it only measures the network path to OpenRouter.
A full run makes about 120 small calls (well under $0.01).
"""

import http.client
import json
import os
import statistics
import sys
import time

HOST = "openrouter.ai"
PATH = "/api/alpha/decisions"
MODELS = ["microsoft/microsoft-decision-1", "typesafe/jev-1.13"]
API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# Sample input only. Prices and headline are made up for timing.
HEADLINE = "FED CUTS RATES BY 50 BPS, MORE THAN THE 25 BPS EXPECTED"
SNAPSHOT_SMALL = {
    "headline": HEADLINE,
    "source": "sample",
    "spy": {"price": 571.20, "change_today_pct": 0.35, "move_since_headline_pct": 0.0},
    "vix": 17.8,
    "minutes_to_close": 118,
}
SNAPSHOT_LARGE = dict(
    SNAPSHOT_SMALL,
    market_summary=(
        "Stocks drifted higher this morning ahead of the 2:00 PM FOMC decision. "
        "Futures priced a 25 bp cut as near-certain and a 50 bp cut as unlikely. "
        "Tech led gains; Treasury yields slipped after softer jobless claims. "
    ) * 6,
    recent_headlines=[
        "TREASURY 10Y YIELD FALLS TO 3.98%",
        "JOBLESS CLAIMS 214K VS 225K EXPECTED",
        "OIL DOWN 1.2% ON SUPPLY OUTLOOK",
        "MEGACAP TECH UP 0.8% AHEAD OF FED",
    ] * 5,
    scheduled_today=["2:00 PM ET FOMC statement", "2:30 PM ET Fed chair press conference"],
)

Q_ACTION = {
    "type": "choice",
    "instructions": "Given the headline and market snapshot, which single action is best "
                    "for a short-term SPY options trade over the next 15 minutes?",
    "criteria": {
        "BUY_CALL": "SPY is likely to rise meaningfully soon",
        "BUY_PUT": "SPY is likely to fall meaningfully soon",
        "NO_TRADE": "Unclear, already priced in, or not market-moving",
    },
}
Q_ALL = {
    "moves_spy": {
        "type": "noul",
        "instructions": "Will this headline move SPY by more than 0.2% within 15 minutes?",
        "criteria": {"true": "Likely to move SPY more than 0.2% within 15 minutes",
                     "false": "Unlikely to move SPY that much"},
    },
    "action": Q_ACTION,
    "priced_in": {
        "type": "noul",
        "instructions": "Has SPY already moved on this news before now?",
        "criteria": {"true": "SPY has already reacted to this news",
                     "false": "SPY has not reacted yet"},
    },
    "size": {
        "type": "score",
        "instructions": "How large is the likely SPY move?",
        "criteria": ["Small: under 0.2%", "Medium: 0.2% to 0.5%", "Large: over 0.5%"],
    },
}


def new_conn():
    return http.client.HTTPSConnection(HOST, timeout=10)


def call(conn, model, state, questions):
    """One decisions request. Returns (ms, status, parsed body)."""
    body = json.dumps({"model": model, "state": state, "questions": questions})
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = "Bearer " + API_KEY
    t0 = time.perf_counter()
    conn.request("POST", PATH, body=body, headers=headers)
    resp = conn.getresponse()
    raw = resp.read()
    ms = (time.perf_counter() - t0) * 1000
    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = {"raw": raw[:200].decode("utf-8", "replace")}
    return ms, resp.status, parsed


def summarize(label, times):
    times = sorted(times)
    p90 = times[max(0, int(round(0.9 * len(times))) - 1)]
    print(f"  {label:<38} n={len(times):<3} p50={statistics.median(times):6.0f} ms"
          f"  p90={p90:6.0f} ms  max={times[-1]:6.0f} ms")


def run(model, label, n, state, questions, reuse=True):
    times, last = [], None
    conn = new_conn()
    for _ in range(n):
        if not reuse:
            conn.close()
            conn = new_conn()
        ms, status, body = call(conn, model, state, questions)
        if status != 200 and API_KEY:
            print(f"  {label}: HTTP {status} {json.dumps(body)[:300]}")
            return None
        times.append(ms)
        last = body
    conn.close()
    summarize(label, times)
    return last


def main():
    print(f"Network path to {HOST} (no model work; server answers before the model runs):")
    conn = new_conn()
    times = []
    for _ in range(10):
        t0 = time.perf_counter()
        conn.request("GET", "/api/v1/models/microsoft/microsoft-decision-1/endpoints")
        conn.getresponse().read()
        times.append((time.perf_counter() - t0) * 1000)
    conn.close()
    summarize("warm connection, small GET", times[1:])

    if not API_KEY:
        print("\nOPENROUTER_API_KEY is not set, so model timing was skipped.")
        sys.exit(0)

    for model in MODELS:
        print(f"\n{model}:")
        run(model, "warm-up (ignored)", 3, SNAPSHOT_SMALL, {"action": Q_ACTION})
        run(model, "new connection every call", 5, SNAPSHOT_SMALL, {"action": Q_ACTION}, reuse=False)
        run(model, "reused connection, 1 question", 15, SNAPSHOT_SMALL, {"action": Q_ACTION})
        run(model, "reused connection, 4 questions", 15, SNAPSHOT_SMALL, Q_ALL)
        last = run(model, "reused, 4 questions, large snapshot", 15, SNAPSHOT_LARGE, Q_ALL)
        if last:
            print("  sample answer (large snapshot):")
            print("  " + json.dumps(last.get("answers", last))[:800])
            print("  usage:", json.dumps(last.get("usage", {})))


if __name__ == "__main__":
    main()

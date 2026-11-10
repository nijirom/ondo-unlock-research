"""Descriptive diagnostics for the two completed ONDO January unlocks.

Run: python data/ondo-event-robustness.py
Two events on one token. Rules replayed here were written after seeing both
episodes, so this is a description of the past and not an out-of-sample test.
"""
from pathlib import Path
import datetime as dt
import json
import math
import statistics as st

HERE = Path(__file__).resolve().parent
D = dt.date.fromisoformat
REF = "2026-11-08"


def add(d, n):
    return (D(d) + dt.timedelta(days=n)).isoformat()


def series(raw, key, field):
    d = raw[key]["data"]["data"]
    f = [x["field"] for x in d["point_schema"]]
    i = f.index(field)
    return [(p[0], p[i]) for p in d["points"] if p[i] is not None]


def day(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat()


candles = json.loads((HERE / "ondo-coinbase-candles.json").read_text())
O = {r["date"]: r["close"] for r in candles["ONDO-USD"]}
B = {r["date"]: r["close"] for r in candles["BTC-USD"]}
VOL = {r["date"]: r["volume"] * r["close"] for r in candles["ONDO-USD"]}
raw = json.loads((HERE / "ondo-blockworks-history.json").read_text())
SUP = {day(t): v for t, v in series(raw, "ondo_supply", "circulating-supply")}
trace = json.loads((HERE / "allium-ondo-unlock" / "trace_result.json").read_text())
days = sorted(d for d in O if d <= REF)


def supply(d):
    while d not in SUP:
        d = add(d, -1)
    return SUP[d]


def beta(end, n=90):
    w = [d for d in days if add(end, -n) <= d <= end]
    ro = [math.log(O[b] / O[a]) for a, b in zip(w, w[1:])]
    rb = [math.log(B[b] / B[a]) for a, b in zip(w, w[1:])]
    mo, mb = st.mean(ro), st.mean(rb)
    return sum((x - mo) * (y - mb) for x, y in zip(ro, rb)) / sum((y - mb) ** 2 for y in rb), len(ro)


def funding(key, lo, hi, entry):
    """Short's funding P&L as a fraction of entry notional, constant token size, daily close as mark."""
    tot = rate_sum = 0.0
    n = 0
    seen = set()
    for t, r in series(raw, key, "fundingRate"):
        d = day(t)
        if t in seen or not (lo < d <= hi):
            continue
        seen.add(t)
        tot += r * O.get(d, O[add(d, -1)]) / entry
        rate_sum += r
        n += 1
    return {"pnl_fraction_entry_notional": tot, "rate_sum": rate_sum, "settlements": n}


out = {"scope": "Descriptive. Two events, one token, Bitcoin fell in both. Not a backtest.", "events": {}}
for ev in ("2025-01-18", "2026-01-18"):
    e0, e1, pre = add(ev, -30), add(ev, 90), add(ev, -1)
    s0, s1 = supply(add(ev, -3)), supply(add(ev, 3))  # provider posts the step a day late
    res = {"float_before": s0, "float_after": s1, "float_increase": s1 / s0 - 1,
           "flat_cap_price_change": s0 / s1 - 1}
    res["windows"] = {}
    for a in (-70, -30, -14, -1):
        for b in (30, 60, 90):
            x, y = add(ev, a), add(ev, b)
            res["windows"][f"T{a:+d}..T{b:+d}"] = {
                "ondo": O[y] / O[x] - 1, "btc": B[y] / B[x] - 1,
                "circulating_cap_change": O[y] * supply(y) / (O[x] * supply(x)) - 1}
    bt, n = beta(e0)
    ro, rb = math.log(O[e1] / O[e0]), math.log(B[e1] / B[e0])
    res["pre_event_beta_90d"] = {"beta": bt, "n": n, "ondo_log": ro, "btc_log": rb,
                                 "residual_log": ro - bt * rb, "residual_simple": math.exp(ro - bt * rb) - 1}
    # replay: short at T-30 close, target = flat-cap price, stop = daily close 20% above entry
    entry = O[e0]
    target, stop = entry * s0 / s1, entry * 1.20
    path = [d for d in days if e0 < d <= e1]
    exit_day, why = e1, "time"
    for d in path:
        if O[d] >= stop:
            exit_day, why = d, "stop"
            break
        if O[d] <= target:
            exit_day, why = d, "target"
            break
    held = [d for d in path if d <= exit_day]
    f = funding("funding_binance_ONDOUSDT", e0, exit_day, entry)
    worst = max(held, key=lambda d: O[d])
    res["replay_T-30_entry"] = {"entry": entry, "target": target, "stop": stop, "exit_day": exit_day,
                                "exit_reason": why, "exit_price": O[exit_day], "days_held": len(held),
                                "price_return_short": 1 - O[exit_day] / entry,
                                "worst_adverse_close": O[worst] / entry - 1, "worst_adverse_day": worst,
                                "funding_binance": f,
                                "net_after_funding": 1 - O[exit_day] / entry + f["pnl_fraction_entry_notional"],
                                "funding_full_window": funding("funding_binance_ONDOUSDT", e0, e1, entry)}
    # same replay, but closed once funding paid reaches 5% of entry notional
    paid, cap_day = 0.0, None
    for t, r in sorted(set(series(raw, "funding_binance_ONDOUSDT", "fundingRate"))):
        d = day(t)
        if e0 < d <= exit_day:
            paid += r * O.get(d, O[add(d, -1)]) / entry
            if paid <= -0.05:
                cap_day = d
                break
    res["replay_with_5pct_funding_cap"] = None if cap_day is None else {
        "exit_day": cap_day, "price_return_short": 1 - O[cap_day] / entry, "net_after_funding": 1 - O[cap_day] / entry + paid}
    res["funding_7d_before_entry_rate_sum"] = funding("funding_binance_ONDOUSDT", add(e0, -7), e0, entry)["rate_sum"]
    out["events"][ev] = res

# every 120-day window, overlapping, for context
roll = [(d, O[add(d, 120)] / O[d] - 1) for d in days if add(d, 120) in O and add(d, 120) <= REF]
vals = sorted(v for _, v in roll)
out["rolling_120d"] = {"n_overlapping": len(vals), "median": st.median(vals),
                       "share_down_26pct_or_more": sum(v <= -0.26 for v in vals) / len(vals),
                       "share_up_20pct_or_more": sum(v >= 0.20 for v in vals) / len(vals),
                       "event_percentiles": {ev: sum(v <= out["events"][ev]["windows"]["T-30..T+90"]["ondo"] for v in vals) / len(vals)
                                             for ev in out["events"]}}

# long run: price, float, circulating cap since the day before the first unlock
a = "2025-01-17"
out["since_first_unlock"] = {"from": a, "to": REF, "ondo": O[REF] / O[a] - 1, "btc": B[REF] / B[a] - 1,
                             "float": supply(REF) / supply(a) - 1,
                             "circulating_cap_from": O[a] * supply(a), "circulating_cap_to": O[REF] * supply(REF),
                             "circulating_cap_change": O[REF] * supply(REF) / (O[a] * supply(a)) - 1}
caps = [O[d] * supply(d) for d in days if d >= "2025-01-18"]
out["circulating_cap_range_since_2025_unlock"] = {"min": min(caps), "median": st.median(caps), "max": max(caps)}

# dollar value of distributor payouts at the day's close
rel = trace["released_by_day"]
for y, lo, hi in (("2025", "2025-01-01", "2025-12-31"), ("2026_to_8_Nov", "2026-01-01", REF)):
    usd = sum(v * O[d] for d, v in rel.items() if lo <= d <= hi)
    tok = sum(v for d, v in rel.items() if lo <= d <= hi)
    out.setdefault("distributor_payouts", {})[y] = {"tokens": tok, "usd_at_daily_close": usd, "avg_price": usd / tok}

# positioning today
pos = {}
for key in ("funding_binance_ONDOUSDT", "funding_bybit_ONDOUSDT", "funding_hyperliquid_ONDO"):
    pos[key] = {f"{n}d_rate_sum_to_shorts": funding(key, add(REF, -n), REF, O[REF])["rate_sum"] for n in (30, 90, 365)}
oi = 0.0
for key in ("perp_binance", "perp_bybit", "perp_hl"):
    s = [(day(t), v) for t, v in series(raw, key, "openInterestUSD")]
    last = [v for d, v in s if add(REF, -30) < d <= REF]
    pos[key] = {"oi_30d_avg": st.mean(last), "oi_ref": dict(s).get(REF)}
    oi += st.mean(last)
pos["oi_30d_avg_total"] = oi
pos["oi_share_of_circulating_cap"] = oi / (O[REF] * supply(REF))
w30 = [d for d in days if add(REF, -30) < d <= REF]
pos["closes_last_30d"] = {"max": max(O[d] for d in w30), "min": min(O[d] for d in w30),
                          "change_from_30d_high": O[REF] / max(O[d] for d in w30) - 1}
out["positioning"] = pos

# the proposed trade: entry at the reference close (71 days before the unlock), target $0.26, stop $0.42
ENTRY, TARGET, STOP, HOLD = O[REF], 0.26, 0.42, 161
G, L = 1 - TARGET / ENTRY, STOP / ENTRY - 1
early = {}
for ev in ("2025-01-18", "2026-01-18"):
    e0, e = add(ev, -71), out["events"][ev]
    tgt, stp, res = O[e0] * (1 + e["flat_cap_price_change"]), O[e0] * 1.20, ("time", add(ev, 90))
    for d in [x for x in days if e0 < x <= add(ev, 90)]:
        if O[d] >= stp:
            res = ("stop", d)
            break
        if O[d] <= tgt:
            res = ("target", d)
            break
    early[ev] = {"entry_day": e0, "entry": O[e0], "target": tgt, "stop": stp, "exit_reason": res[0],
                 "exit_day": res[1], "exit_price": O[res[1]], "price_return_short": 1 - O[res[1]] / O[e0]}
first = {"target": 0, "stop": 0, "neither": 0}
starts = [d for d in days if add(d, HOLD) <= REF]
for d in starts:
    hit = "neither"
    for x in [y for y in days if d < y <= add(d, HOLD)]:
        r = O[x] / O[d] - 1
        if r >= L:
            hit = "stop"
            break
        if r <= -G:
            hit = "target"
            break
    first[hit] += 1
out["proposed_trade"] = {"entry": ENTRY, "target": TARGET, "stop_daily_close_above": STOP, "gain": G, "loss": L,
                         "days_to_unlock": 71, "holding_days": HOLD,
                         "breakeven_target_probability": {f"cost_{int(c * 100)}pct": (L + c) / (G + L) for c in (0, .02, .05)},
                         "replay_entry_71_days_before": early,
                         "first_touch_all_start_days": {"starts": len(starts), **{k: v / len(starts) for k, v in first.items()}}}
(HERE / "ondo-event-robustness.json").write_text(json.dumps(out, indent=1) + "\n")
for ev, r in out["events"].items():
    print(ev, {k: r[k] for k in ("float_before", "float_after", "float_increase", "flat_cap_price_change")})
    print("  replay", r["replay_T-30_entry"]); print("  cap5", r["replay_with_5pct_funding_cap"], "pre7d", r["funding_7d_before_entry_rate_sum"])

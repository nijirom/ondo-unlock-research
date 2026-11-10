"""Rebuild the ONDO short's inputs from the saved research snapshot.

Run from any directory: python data/ondo-thesis-model.py
Arithmetic on stated assumptions. Not a fair-value estimate and not a backtest.
"""
from pathlib import Path
import datetime as dt
import json

HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def calculate():
    market = load("ondo-finalist-refresh.json")["market"]
    raw = load("ondo-blockworks-history.json")["revenue"]["data"]["data"]
    idx = [f["field"] for f in raw["point_schema"]].index("netRevenueUSD")
    revenue = {dt.datetime.fromtimestamp(p[0], dt.timezone.utc).date().isoformat(): p[idx]
               for p in raw["points"] if p[idx] is not None}
    current = sum(v for d, v in revenue.items() if "2026-10-11" <= d <= "2026-11-07")
    prior = sum(v for d, v in revenue.items() if "2026-09-13" <= d <= "2026-10-10")
    annual = current * 365 / 28
    price, total, float_ = market["price"], market["totalSupply"], market["circulation"]
    # Five equal annual steps, read from the Foundation's graphics revised 6 Dec 2024.
    five = {"ecosystem_growth": 5210869545 * .76 / 5, "protocol_development": 3300000000 / 5,
            "private_sales": 1290246044 / 5}
    # Four steps for the two smaller allocations reproduces the 1.94bn shown by Blockworks' tracker.
    four = {"ecosystem_growth": five["ecosystem_growth"], "protocol_development": 3300000000 / 4,
            "private_sales": 1290246044 / 4}
    unlock = sum(five.values())
    target, stop = 0.26, 0.42
    gain, loss = 1 - target / price, stop / price - 1
    return {
        "scope": "Research snapshot at the 8 Nov 2026 close. No probability forecast.",
        "market": market,
        "unlock": {"five_step": five, "five_step_total": unlock, "share_of_float": unlock / float_,
                   "usd_at_reference": unlock * price,
                   "four_step_total": sum(four.values()), "four_step_share_of_float": sum(four.values()) / float_,
                   "four_step_flat_cap_change": float_ / (float_ + sum(four.values())) - 1,
                   "caveat": "Vesting contracts not read. Schedule size is not a forecast of transfers or sales."},
        "trade": {"direction": "short ONDO, unhedged", "entry": price, "target": target,
                  "stop_daily_close_above": stop, "gain_at_target": gain, "loss_at_stop": loss,
                  "flat_cap_price": price * float_ / (float_ + unlock),
                  "circulating_cap_at_entry": price * float_, "circulating_cap_at_target": target * (float_ + unlock),
                  "circulating_cap_at_stop": stop * float_,
                  "latest_exit": "2027-04-18",
                  "breakeven_probability_target_first": {f"costs_{int(c * 100)}pct": (loss + c) / (gain + loss)
                                                         for c in (0, .02, .05)},
                  "btc_rally_to_stop_at_beta_1.26": loss / 1.26},
        "revenue": {"window": ["2026-10-11", "2026-11-07"], "net_28d": current, "previous_28d": prior,
                    "annualized": annual, "fdv_to_revenue": market["fdv"] / annual,
                    "fdv_to_twice_revenue": market["fdv"] / (2 * annual),
                    "buyback_at_40pct": annual * .4,
                    "buyback_share_of_circulating_cap": annual * .4 / market["circulatingMarketcap"],
                    "revenue_for_2pct_fdv_yield_at_40pct": market["fdv"] * .02 / .4,
                    "caveat": "Provider-tracked net protocol revenue from 31 May 2026. Not income to ONDO holders."},
        "provenance": {"market": "ondo-finalist-refresh.json", "revenue": "ondo-blockworks-history.json",
                       "event_diagnostics": "ondo-event-robustness.json",
                       "tracing": "allium-ondo-unlock/trace_result.json"},
    }


if __name__ == "__main__":
    result = calculate()
    (HERE / "ondo-finalist-model.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("unlock", "trade", "revenue")}, indent=1))

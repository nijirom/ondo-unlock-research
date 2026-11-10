# ONDO unlock research

Code and result files behind a short thesis on ONDO written for the Franklin Crypto Research Competition at the University Blockchain Conference 2026. Market data is as of the 8 November 2026 close.

## What is here

| Path | Contents |
|---|---|
| `data/ondo-thesis-model.py` | Unlock size, entry/target/stop arithmetic, break-even odds, revenue multiples. Writes `ondo-finalist-model.json`. |
| `data/ondo-event-robustness.py` | The two completed unlock windows: float, price and circulating cap, beta-adjusted residuals, replays, base rates, funding and open interest. Writes `ondo-event-robustness.json`. |
| `data/ondo-coinbase-candles.json` | ONDO-USD and BTC-USD daily candles from the public Coinbase Exchange API, 1 Oct 2024 to 9 Nov 2026. |
| `data/allium-ondo-unlock/queries.sql` | The Allium queries used to export ONDO transfers and address labels. |
| `data/allium-ondo-unlock/trace.py`, `prorata.py` | Forward tracing of tokens from the distributor wallets to the first exchange-like address, first-in first-out and pro rata. |
| `data/allium-ondo-unlock/trace_result.json`, `trace_groups.json` | Tracing results. |
| `figures/` | Scripts for the two figures and the PDFs they produce. |

## What is not here

The raw Blockworks API responses and the raw Allium exports are not included, because they were obtained through competition access. The scripts read them from `data/ondo-blockworks-history.json`, `data/ondo-finalist-refresh.json` and the Allium export files named in `queries.sql`, so the scripts will not run end to end from this repository alone. The result files they wrote are included so the numbers can be checked against the code.

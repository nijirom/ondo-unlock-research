"""Pro-rata (haircut) variant of the trace: an outflow carries traced supply in proportion to the
wallet's traced share of balance. Balances are built from the >=100k edge list from 1 Oct 2024."""
import collections, json
from trace import EDGES, STATS, RESERVE, DIST_A, DIST_B, VENUE, classify, day

def run(sources, lo, hi, hub=500, busy=1000):
    bal = collections.defaultdict(float)                              # total balance seen in edges
    tb = collections.defaultdict(lambda: collections.defaultdict(float))  # addr -> t0_day_epoch -> traced amt
    arr = collections.defaultdict(lambda: collections.defaultdict(float))
    released = 0.0
    for e in EDGES:
        f, t, a, s = e['F'], e['T'], e['A'], e['S']
        moved = {}
        if f in sources:
            if not (t in sources or t == RESERVE) and lo <= day(s) < hi:
                moved = {s: a}
                released += a
        else:
            T = tb.get(f)
            if T:
                tt = sum(T.values())
                B = max(bal[f], a, tt)
                frac = a / B
                for k in list(T):
                    m = T[k] * frac
                    if m > 1:
                        moved[k] = m
                    T[k] -= m
                    if T[k] <= 1:
                        del T[k]
            bal[f] = max(0.0, bal[f] - a)
        bal[t] += a
        if not moved:
            continue
        c = classify(t, hub, busy)
        for k, m in moved.items():
            if c or t in sources or t == RESERVE:
                lag = (s - k) / 86400.0
                for w in (1, 7, 30, 90, 1e9):
                    if lag <= w:
                        arr[c or 'returned'][w] += m
            else:
                tb[t][k] += m
    still = sum(sum(v.values()) for v in tb.values())
    return released, arr, still

for label, lo, hi in (('2025', '2025-01-01', '2026-01-01'), ('2026', '2026-01-01', '2026-11-09'), ('all', '2025-01-01', '2026-11-09')):
    rel, arr, still = run({DIST_A, DIST_B}, lo, hi)
    cex = {w: arr['cex'].get(w, 0) / rel * 100 for w in (1, 7, 30, 90, 1e9)}
    ven = {w: sum(arr[c].get(w, 0) for c in VENUE) / rel * 100 for w in (1, 7, 30, 90, 1e9)}
    print(f'pro-rata {label}: released {rel/1e6:.1f}M | cex 1d/7d/30d/90d/ever ' + '/'.join(f'{cex[w]:.1f}' for w in cex) + ' | venue ' + '/'.join(f'{ven[w]:.1f}' for w in ven) + f' | not at venue {still/rel*100:.1f}%')

"""Forward-trace ONDO leaving a set of source wallets to the first venue-like address.

Model: parcels move FIFO and tainted tokens leave a wallet before untainted ones. Exact for
fresh pass-through wallets; overstates speed where a wallet already held ONDO (see purity).
Only transfers >= 100k ONDO are in the edge list, so smaller onward transfers are untraced.
"""
import collections, datetime as dt, json

RESERVE = '0x677fd4ed8ae623f2f625deb2d64f2070e46ca1a1'
DIST_A = '0x524083970c7a1e62fbaa61d38781f87a4f191fd0'
DIST_B = '0xea5785e1727de2ba2cefd102cb2dd91e018675e1'
MAX_HOPS = 8
DEX = {'dex', 'mev', 'dex_aggregator', 'solvers', 'dex_settler'}
VENUE = ('cex', 'hub_unlabelled', 'market_maker', 'dex')
WINDOWS = (1, 7, 30, 90, 1e9)

EDGES = json.load(open('edges100k.json'))
STATS = {r['A']: r for r in json.load(open('addr_stats.json'))}


def classify(a, hub=500, busy=1000):
    s = STATS.get(a)
    if not s:
        return None
    c = s['CATEGORY']
    if c == 'cex':
        return 'cex'
    if c == 'market_maker':
        return 'market_maker'
    if c in DEX:
        return 'dex'
    if c == 'bridge':
        return 'bridge'
    if c:
        return None if c in ('fund', 'fund_decentralized') else 'other_labelled'
    if s['NS'] >= hub or s['NR'] >= hub or s['N_IN'] >= busy or s['N_OUT'] >= busy:
        return 'hub_unlabelled'
    return None


def day(s):
    return dt.datetime.fromtimestamp(s, dt.timezone.utc).strftime('%Y-%m-%d')


def trace(sources, start='2000-01-01', hub=500, busy=1000):
    """sources: set of addresses whose every outflow (>= start) is tainted."""
    held = collections.defaultdict(collections.deque)   # addr -> [amt, t0, hops]
    arrivals = []                                       # (class, amt, lag_days, hops, dest, day, t0_day)
    released = collections.defaultdict(float)           # day -> amt leaving sources
    tainted_in = collections.defaultdict(float)
    for e in EDGES:
        f, t, a, s = e['F'], e['T'], e['A'], e['S']
        if f in sources:
            if t in sources or t == RESERVE or day(s) < start:
                continue
            parcels = [[a, s, 0]]
            released[day(s)] += a
        else:
            q = held.get(f)
            if not q:
                continue
            parcels, need = [], a
            while q and need > 0:
                p = q[0]
                take = min(p[0], need)
                parcels.append([take, p[1], p[2]])
                p[0] -= take
                need -= take
                if p[0] <= 1e-6:
                    q.popleft()
        c = classify(t, hub, busy)
        for amt, t0, hops in parcels:
            if c or t in sources or t == RESERVE:
                arrivals.append((c or 'returned', amt, (s - t0) / 86400.0, hops + 1, t, day(s), day(t0)))
            elif hops + 1 >= MAX_HOPS:
                arrivals.append(('hop_limit', amt, (s - t0) / 86400.0, hops + 1, t, day(s), day(t0)))
            else:
                held[t].append([amt, t0, hops + 1])
                tainted_in[t] += amt
    return held, arrivals, released, tainted_in


def summarize(held, arrivals, released, tainted_in, lo, hi, label, verbose=True):
    """Summary for parcels that left the sources on days in [lo, hi)."""
    tot = sum(v for d, v in released.items() if lo <= d < hi)
    rows = [x for x in arrivals if lo <= x[6] < hi]
    by = collections.defaultdict(lambda: collections.defaultdict(float))
    for c, amt, lag, hops, dest, d, d0 in rows:
        for w in WINDOWS:
            if lag <= w:
                by[c][w] += amt
    still = collections.defaultdict(float)
    for addr, q in held.items():
        for amt, t0, hops in q:
            if lo <= day(t0) < hi:
                still[addr] += amt
    key = lambda w: str(int(w)) if w < 1e9 else 'ever'
    res = {'label': label, 'from': lo, 'to': hi, 'released': tot,
           'pct': {c: {key(w): by.get(c, {}).get(w, 0) / tot * 100 for w in WINDOWS} for c in VENUE + ('bridge', 'other_labelled', 'returned', 'hop_limit')}}
    res['pct']['venue_total'] = {key(w): sum(by.get(c, {}).get(w, 0) for c in VENUE) / tot * 100 for w in WINDOWS}
    res['not_at_venue'] = sum(still.values())
    proj = collections.defaultdict(float)
    hops = collections.defaultdict(float)
    dest = collections.defaultdict(float)
    for c, amt, lag, h, d_, d, d0 in rows:
        if c == 'cex':
            proj[STATS[d_]['PROJECT']] += amt
        if c in VENUE:
            hops[h] += amt
        dest[(c, d_)] += amt
    res['cex_by_project'] = dict(sorted(proj.items(), key=lambda kv: -kv[1]))
    res['hops'] = dict(sorted(hops.items()))
    # purity: of everything the pass-through wallets on these paths ever received, how much was traced supply
    inter = [a for a in tainted_in if a in STATS]
    gin = sum(STATS[a]['GIN'] for a in inter)
    res['intermediaries'] = len(tainted_in)
    res['purity_pct'] = sum(tainted_in[a] for a in inter) / gin * 100 if gin else None
    if verbose:
        print(f'\n=== {label}: released {tot/1e6:.1f}M between {lo} and {hi}')
        print(f'{"first venue":18s} {"<=1d":>8s} {"<=7d":>8s} {"<=30d":>8s} {"<=90d":>8s} {"ever":>8s}   (% of released)')
        for c in VENUE + ('venue_total',):
            print(f'{c:18s} ' + ' '.join(f'{res["pct"][c][key(w)]:8.1f}' for w in WINDOWS))
        print(f'not at a venue: {res["not_at_venue"]/1e6:.1f}M = {res["not_at_venue"]/tot*100:.1f}% in {len(still)} wallets;'
              f' returned {res["pct"]["returned"]["ever"]:.1f}%, hop limit {res["pct"]["hop_limit"]["ever"]:.1f}%')
        print('cex by project (M):', {k: round(v / 1e6, 1) for k, v in list(res['cex_by_project'].items())[:10]})
        print('hops to venue (M):', {h: round(v / 1e6, 1) for h, v in res['hops'].items()})
        for (c, a), v in sorted(dest.items(), key=lambda kv: -kv[1])[:8]:
            s_ = STATS.get(a, {})
            print(f'   {a} {v/1e6:8.2f}M {c:15s} {s_.get("PROJECT")} | {s_.get("NAME")}')
        for a, v in sorted(still.items(), key=lambda kv: -kv[1])[:6]:
            s_ = STATS.get(a, {})
            print(f'   held {a} {v/1e6:8.2f}M ns={s_.get("NS")} nr={s_.get("NR")} gin={(s_.get("GIN") or 0)/1e6:.1f} gout={(s_.get("GOUT") or 0)/1e6:.1f}')
    return res


if __name__ == '__main__':
    out = {}
    tr = trace({DIST_A, DIST_B})
    held, arrivals, released, tainted_in = tr
    out['dist_2025'] = summarize(*tr, '2025-01-01', '2026-01-01', 'Distributors, calendar 2025')
    out['dist_2026'] = summarize(*tr, '2026-01-01', '2026-11-09', 'Distributors, 2026 to 8 Nov')
    out['dist_all'] = summarize(*tr, '2025-01-01', '2026-11-09', 'Distributors, all')
    print('purity of pass-through wallets: %.1f%% (%d wallets)' % (out['dist_all']['purity_pct'], out['dist_all']['intermediaries']))
    for name, kw in (('hub>=2000/busy>=5000', dict(hub=2000, busy=5000)), ('labelled only', dict(hub=10**9, busy=10**9))):
        r = summarize(*trace({DIST_A, DIST_B}, **kw), '2025-01-01', '2026-11-09', name, verbose=False)
        print(f'sensitivity {name}: cex<=30d {r["pct"]["cex"]["30"]:.1f}%, venue<=30d {r["pct"]["venue_total"]["30"]:.1f}%, venue ever {r["pct"]["venue_total"]["ever"]:.1f}%, hop_limit {r["pct"]["hop_limit"]["ever"]:.1f}%')
    month = collections.defaultdict(lambda: collections.defaultdict(float))
    for d, v in released.items():
        month[d[:7]]['released'] += v
    for c, amt, lag, h, d_, d, d0 in arrivals:
        if c in VENUE and lag <= 30:
            month[d0[:7]]['cex30' if c == 'cex' else 'other30'] += amt
        if c == 'cex':
            month[d[:7]]['cex_arrivals'] += amt
    out['monthly'] = {m: dict(v) for m, v in sorted(month.items())}
    out['released_by_day'] = dict(sorted(released.items()))
    print('\nmonth      released  cex<=30d  othervenue<=30d  (M)')
    for m, v in sorted(month.items()):
        print(m, f'{v["released"]/1e6:9.1f} {v["cex30"]/1e6:9.1f} {v["other30"]/1e6:9.1f}')
    json.dump(out, open('trace_result.json', 'w'), indent=1)

"""Figure 1: ONDO price, float and circulating cap; cap around each completed unlock."""
import datetime as dt, json
import matplotlib; matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

plt.rcParams.update({'font.family': 'Times New Roman', 'font.size': 8.5, 'text.color': 'black', 'axes.labelcolor': 'black', 'xtick.color': 'black', 'ytick.color': 'black', 'axes.spines.top': False, 'axes.spines.right': False, 'pdf.fonttype': 42})
NAVY, MID, LIGHT, RED, MUTED = '#17384D', '#6F93A8', '#C9D6DE', '#A23B2A', '#58656E'
ROOT = __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))) + '/'
c = json.load(open(ROOT + 'data/ondo-coinbase-candles.json'))
O = {r['date']: r['close'] for r in c['ONDO-USD']}
raw = json.load(open(ROOT + 'data/ondo-blockworks-history.json'))['ondo_supply']['data']['data']
i = [f['field'] for f in raw['point_schema']].index('circulating-supply')
SUP = {dt.datetime.fromtimestamp(p[0], dt.timezone.utc).date().isoformat(): p[i] for p in raw['points'] if p[i] is not None}
REF, BASE = '2026-11-08', '2025-01-17'
D = dt.date.fromisoformat
add = lambda d, n: (D(d) + dt.timedelta(days=n)).isoformat()


def supply(d):
    while d not in SUP:
        d = add(d, -1)
    return SUP[d]


fig = plt.figure(figsize=(7.0, 2.25))
ax = fig.add_axes([0.075, 0.2, 0.40, 0.56])
bx = fig.add_axes([0.60, 0.2, 0.385, 0.56])

days = [d for d in sorted(O) if BASE <= d <= REF]
x = [D(d) for d in days]
cap0, p0, s0 = O[BASE] * supply(BASE), O[BASE], supply(BASE)
ax.plot(x, [supply(d) / s0 * 100 for d in days], color=MID, lw=1.2, label='Float')
ax.plot(x, [O[d] * supply(d) / cap0 * 100 for d in days], color=RED, lw=1.1, label='Circulating cap')
ax.plot(x, [O[d] / p0 * 100 for d in days], color=NAVY, lw=1.2, label='Price')
ax.axhline(100, color=MUTED, lw=0.5)
ax.set_yscale('log')
ax.set_yticks([25, 50, 100, 200, 400])
ax.set_yticklabels(['25', '50', '100', '200', '400'])
ax.minorticks_off()
ax.set_ylim(17, 450)
ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %y'))
ax.set_ylabel('17 Jan 2025 = 100 (log scale)')
ax.legend(frameon=False, fontsize=7.5, ncol=3, loc='lower left', bbox_to_anchor=(0, 1.02), borderaxespad=0, handlelength=1.5, columnspacing=1.0)
fig.text(0.075, 0.975, 'A. Float up 237%, price down 73%, cap down 10%', fontsize=9, fontweight='bold', va='top')

offs = list(range(-30, 91))
bx.axvline(0, color=MUTED, lw=0.7, ls=(0, (3, 2)))
bx.axhline(100, color=MUTED, lw=0.5)
for ev, col in (('2025-01-18', MID), ('2026-01-18', NAVY)):
    b = add(ev, -30)
    base = O[b] * supply(b)
    bx.plot(offs, [O[add(ev, k)] * supply(add(ev, k)) / base * 100 for k in offs], color=col, lw=1.2, label=ev[:4])
bx.set_xlabel('Days from unlock')
bx.set_ylabel('Cap, 30 days before = 100')
bx.set_xticks([-30, 0, 30, 60, 90])
bx.set_ylim(50, 230)
bx.set_yticks([50, 100, 150, 200])
bx.legend(frameon=False, fontsize=7.5, ncol=2, loc='lower left', bbox_to_anchor=(0, 1.02), borderaxespad=0, handlelength=1.5, columnspacing=1.0)
fig.text(0.60, 0.975, 'B. Cap jumps on the date, then gives it back', fontsize=9, fontweight='bold', va='top')

fig.savefig(ROOT + 'figures/ondo-unlock-event-study.pdf')
fig.savefig('fig_cap.png', dpi=110)
print('ok')

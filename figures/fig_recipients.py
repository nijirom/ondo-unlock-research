import json, datetime as dt
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams.update({'font.family': 'Times New Roman', 'font.size': 8.5, 'text.color': 'black', 'axes.labelcolor': 'black', 'xtick.color': 'black', 'ytick.color': 'black', 'axes.spines.top': False, 'axes.spines.right': False, 'pdf.fonttype': 42})
NAVY, MID, LIGHT, RED, MUTED = '#17384D', '#6F93A8', '#C9D6DE', '#A23B2A', '#58656E'
ROOT = __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))) + '/'
res = json.load(open(ROOT + 'data/allium-ondo-unlock/trace_result.json'))
c = json.load(open(ROOT + 'data/ondo-coinbase-candles.json'))
O = {r['date']: r['close'] for r in c['ONDO-USD']}
months = [f'{y}-{m:02d}' for y in (2025, 2026) for m in range(1, 13) if f'{y}-{m:02d}' <= '2026-10']
mon = res['monthly']
rel = [mon.get(m, {}).get('released', 0) / 1e6 for m in months]
cex = [mon.get(m, {}).get('cex30', 0) / 1e6 for m in months]
oth = [mon.get(m, {}).get('other30', 0) / 1e6 for m in months]
rest = [max(0, r - a - b) for r, a, b in zip(rel, cex, oth)]

fig = plt.figure(figsize=(7.0, 2.1))
ax = fig.add_axes([0.075, 0.23, 0.455, 0.48])
bx = fig.add_axes([0.795, 0.23, 0.195, 0.48])
x = list(range(len(months)))
ax.bar(x, cex, color=NAVY, width=0.72, label='Exchange within 30 days')
ax.bar(x, oth, bottom=cex, color=MID, width=0.72, label='Other venue within 30 days')
ax.bar(x, rest, bottom=[a + b for a, b in zip(cex, oth)], color=LIGHT, width=0.72, label='Not at venue within 30 days')
ax.set_ylabel('ONDO distributed (m)')
ax.set_xticks([0, 6, 12, 18, 21])
ax.set_xticklabels(['Jan 25', 'Jul 25', 'Jan 26', 'Jul 26', 'Oct 26'])
for ev in ('2025-01', '2026-01'):
    ax.axvline(months.index(ev) + 0.08, color=MUTED, lw=0.7, ls=(0, (3, 2)))
ax.set_ylim(0, 560)
ax2 = ax.twinx()
ax2.spines['right'].set_visible(True)
ax2.spines['right'].set_color('black')


def last_day(m):
    y, mo = int(m[:4]), int(m[5:])
    return (dt.date(y + (mo == 12), mo % 12 + 1, 1) - dt.timedelta(days=1)).isoformat()


price = [O[last_day(m)] for m in months]
price_line, = ax2.plot(x, price, color=RED, lw=1.2, marker='o', ms=2.2, label='Price (US$, right axis)')
ax2.set_ylim(0, 1.9)
ax2.set_yticks([0, 0.5, 1.0, 1.5])
handles, labels = ax.get_legend_handles_labels()
ax.legend(handles + [price_line], labels + [price_line.get_label()],
          loc='lower left', bbox_to_anchor=(0, 1.05), borderaxespad=0,
          ncol=2, frameon=False, fontsize=7.5, handlelength=1.3,
          columnspacing=0.9, labelspacing=0.35)
fig.text(0.075, 0.97, 'A. Distributions and destinations', fontsize=9, fontweight='bold', va='top')

names = {'coinbase': 'Coinbase', 'bybit': 'Bybit', 'binance': 'Binance', 'gate.io': 'Gate.io', 'coinbase_prime': 'Coinbase Prime', 'okx': 'OKX', 'kucoin': 'KuCoin'}
p25, p26 = res['dist_2025']['cex_by_project'], res['dist_2026']['cex_by_project']
order = sorted(names, key=lambda k: -(p25.get(k, 0) + p26.get(k, 0)))
y = list(range(len(order)))
bx.barh([i - 0.19 for i in y], [p25.get(k, 0) / 1e6 for k in order], height=0.36, color=MID, label='2025')
bx.barh([i + 0.19 for i in y], [p26.get(k, 0) / 1e6 for k in order], height=0.36, color=NAVY, label='2026')
bx.set_yticks(y)
bx.set_yticklabels([names[k] for k in order])
bx.invert_yaxis()
bx.set_xlabel('ONDO received (m)')
bx.legend(frameon=False, fontsize=8, loc='lower left', bbox_to_anchor=(0, 1.05),
          borderaxespad=0, ncol=2, handlelength=1.1, columnspacing=0.8)
fig.text(0.795, 0.97, 'B. First exchange', fontsize=9, fontweight='bold', va='top')

fig.canvas.draw()
rd = fig.canvas.get_renderer()
boxes = [('legend', ax.get_legend().get_window_extent(rd))] + [('label', t.get_window_extent(rd)) for t in ax.texts]
hits = []
for name, bb in boxes:
    for patch in ax.patches:
        if patch.get_height() > 0 and bb.overlaps(patch.get_window_extent(rd)):
            hits.append((name, 'bar', round(patch.get_x() + 0.36)))
    for xi, p in zip(x, price):
        px, py = ax2.transData.transform((xi, p))
        if bb.x0 - 3 <= px <= bb.x1 + 3 and bb.y0 - 3 <= py <= bb.y1 + 3:
            hits.append((name, 'price point', xi))
print('overlaps:', hits, '| month-end prices', [round(p, 2) for p in price])
fig.savefig(ROOT + 'figures/ondo-unlock-recipients.pdf')
fig.savefig('fig_recipients.png', dpi=110)

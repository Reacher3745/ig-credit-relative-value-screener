"""
IG Credit Relative Value Screener
----------------------------------
Builds a rating-bucket relative value model on IG corporate bond OAS spread data,
flagging cheap/rich signals via rolling z-scores, with an excl-self benchmark fix
to remove benchmark-contamination bias.

Data source: FRED (ICE BofA US Corporate Index OAS series)
"""

from fredapi import Fred
import pandas as pd
import matplotlib.pyplot as plt
import os

# ---- Step 1: Pull data ----
fred = Fred(api_key=os.environ.get('FRED_API_KEY'))  # replace with your FRED API key

series = {
    'AAA': 'BAMLC0A1CAAA',
    'AA': 'BAMLC0A2CAA',
    'A': 'BAMLC0A3CA',
    'BBB': 'BAMLC0A4CBBB',
    'IG': 'BAMLC0A0CM'
}

data = {name: fred.get_series(code) for name, code in series.items()}
df = pd.DataFrame(data).dropna()

ratings = ['AAA', 'AA', 'A', 'BBB']
window = 252  # ~1 trading year

# ---- Step 2: Plot raw spreads ----
fig, ax = plt.subplots(figsize=(12, 6))
for col in ratings + ['IG']:
    ax.plot(df.index, df[col], label=col)
ax.legend()
ax.set_title('IG Corporate OAS by Rating')
ax.set_ylabel('OAS (%)')
plt.savefig('spreads.png')
plt.close()

# ---- Step 3: V1 - naive z-score vs blended IG benchmark ----
for r in ratings:
    df[f'{r}_vs_IG'] = df[r] - df['IG']
    col = f'{r}_vs_IG'
    df[f'{r}_zscore'] = (df[col] - df[col].rolling(window).mean()) / df[col].rolling(window).std()

fig, ax = plt.subplots(figsize=(12, 6))
for r in ratings:
    ax.plot(df.index, df[f'{r}_zscore'], label=r)
ax.axhline(0, color='black', linewidth=0.5)
ax.axhline(2, color='red', linestyle='--', linewidth=0.5)
ax.axhline(-2, color='red', linestyle='--', linewidth=0.5)
ax.legend()
ax.set_title('Relative Value Z-Score by Rating (vs IG benchmark) - V1 Naive')
plt.savefig('zscore_v1_naive.png')
plt.close()

# ---- Step 4: V2 - excl-self benchmark fix ----
for r in ratings:
    others = [x for x in ratings if x != r]
    df[f'{r}_exself_bench'] = df[others].mean(axis=1)
    df[f'{r}_vs_exself'] = df[r] - df[f'{r}_exself_bench']
    col = f'{r}_vs_exself'
    df[f'{r}_exself_zscore'] = (df[col] - df[col].rolling(window).mean()) / df[col].rolling(window).std()

fig, ax = plt.subplots(figsize=(12, 6))
for r in ratings:
    ax.plot(df.index, df[f'{r}_exself_zscore'], label=r)
ax.axhline(0, color='black', linewidth=0.5)
ax.axhline(2, color='red', linestyle='--', linewidth=0.5)
ax.axhline(-2, color='red', linestyle='--', linewidth=0.5)
ax.legend()
ax.set_title('Relative Value Z-Score (Excl-Self Benchmark) - V2 Fixed')
plt.savefig('zscore_v2_exself.png')
plt.close()

# ---- Step 5: Final trade-idea table ----
def signal(z):
    if z > 1.5:
        return 'CHEAP (Buy candidate)'
    elif z < -1.5:
        return 'RICH (Avoid/Sell candidate)'
    else:
        return 'FAIR VALUE'

latest = df.iloc[-1]
trade_ideas = pd.DataFrame({
    'Rating': ratings,
    'Current_Spread': [latest[r] for r in ratings],
    'Zscore_exself': [latest[f'{r}_exself_zscore'] for r in ratings]
})
trade_ideas['Signal'] = trade_ideas['Zscore_exself'].apply(signal)
trade_ideas = trade_ideas.sort_values('Zscore_exself', ascending=False)

print(trade_ideas.to_string(index=False))
trade_ideas.to_csv('trade_ideas_latest.csv', index=False)

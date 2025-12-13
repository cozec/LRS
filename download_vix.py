import yfinance as yf
import os

DATA_DIR = 'data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

print("Downloading VIX data...")
vix = yf.download('^VIX', start='2000-01-01', progress=False)

if vix.empty:
    print("Error: VIX download failed.")
else:
    path = os.path.join(DATA_DIR, 'vix.csv')
    vix.to_csv(path)
    print(f"Saved VIX data to {path} ({len(vix)} rows)")
    print(vix.head())

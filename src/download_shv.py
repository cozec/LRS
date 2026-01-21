import yfinance as yf
import os

DATA_DIR = 'data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

print("Downloading SHV (Short Treasury Bond ETF) data...")
shv = yf.download('SHV', start='2000-01-01', progress=False)

if shv.empty:
    print("Error: SHV download failed.")
else:
    path = os.path.join(DATA_DIR, 'shv.csv')
    shv.to_csv(path)
    print(f"Saved SHV data to {path} ({len(shv)} rows)")
    print(shv.head())

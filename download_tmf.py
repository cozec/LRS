import yfinance as yf
import os

DATA_DIR = 'data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

print("Downloading TMF (Direxion Daily 20+ Year Treasury Bull 3X Shares) data...")
tmf = yf.download('TMF', start='2000-01-01', progress=False)

if tmf.empty:
    print("Error: TMF download failed.")
else:
    path = os.path.join(DATA_DIR, 'tmf.csv')
    tmf.to_csv(path)
    print(f"Saved TMF data to {path} ({len(tmf)} rows)")
    print(tmf.head())

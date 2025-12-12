import pandas as pd
import matplotlib.pyplot as plt
import os

DATA_DIR = 'data'
PLOTS_DIR = 'plots'
START_DATE = '2025-04-01'

def plot_asset(ticker, filename):
    path = os.path.join(DATA_DIR, f'{ticker.lower()}.csv')
    if not os.path.exists(path):
        print(f"Error: {path} not found.")
        return

    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df = df[df.index >= START_DATE]
    
    if df.empty:
        print(f"No data for {ticker} from {START_DATE}")
        return
        
    plt.figure(figsize=(10, 6))
    plt.plot(df.index, df['Close'], label=f'{ticker} Close Price', color='blue')
    plt.title(f'{ticker} Price Chart (From {START_DATE})')
    plt.xlabel('Date')
    plt.ylabel('Price ($)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    output_path = os.path.join(PLOTS_DIR, filename)
    plt.savefig(output_path)
    plt.close()
    print(f"Saved {output_path}")

if __name__ == "__main__":
    if not os.path.exists(PLOTS_DIR):
        os.makedirs(PLOTS_DIR)
        
    plot_asset('TQQQ', 'tqqq_price_2025.png')
    plot_asset('UPRO', 'upro_price_2025.png')

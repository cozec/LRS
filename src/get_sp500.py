"""Download sp500 daily bars to data/sp500.csv via the shared downloader."""
from update_data import update_ticker

if __name__ == "__main__":
    update_ticker('sp500')

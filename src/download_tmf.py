"""Download tmf daily bars to data/tmf.csv via the shared downloader."""
from update_data import update_ticker

if __name__ == "__main__":
    update_ticker('tmf')

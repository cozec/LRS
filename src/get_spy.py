"""Download spy daily bars to data/spy.csv via the shared downloader."""
from update_data import update_ticker

if __name__ == "__main__":
    update_ticker('spy')

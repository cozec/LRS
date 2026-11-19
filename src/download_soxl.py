"""Download soxl daily bars to data/soxl.csv via the shared downloader."""
from update_data import update_ticker

if __name__ == "__main__":
    update_ticker('soxl')

import yfinance as yf
import pandas as pd

def main():
    print("Downloading S&P 500 data (^GSPC) from 1928-01-01 to present...")
    # Download data
    df = yf.download("^GSPC", start="1928-01-01", progress=False)

    if df.empty:
        print("Error: No data downloaded.")
        return

    # Check for MultiIndex columns (common in newer yfinance versions even for single ticker)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Ensure Date is saved as a column (it's the index by default)
    output_file = "data/sp500.csv"
    df.to_csv(output_file)
    
    print(f"Successfully saved {len(df)} rows to {output_file}")
    print("First 5 rows:")
    print(df.head())
    print("\nLast 5 rows:")
    print(df.tail())

if __name__ == "__main__":
    main()

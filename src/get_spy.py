import yfinance as yf
import pandas as pd

def main():
    print("Downloading SPY data (SPY) from max available history...")
    # Download data
    df = yf.download("SPY", period="max", progress=False)

    if df.empty:
        print("Error: No data downloaded.")
        return

    # Check for MultiIndex columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Ensure Date is saved as a column (it's the index by default)
    output_file = "data/spy.csv"
    df.to_csv(output_file)
    
    print(f"Successfully saved {len(df)} rows to {output_file}")
    print("First 5 rows:")
    print(df.head())
    print("\nLast 5 rows:")
    print(df.tail())

if __name__ == "__main__":
    main()

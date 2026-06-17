#!/usr/bin/env python3
"""
Download SOXL historical data from yfinance.
"""

import os
import pandas as pd
import yfinance as yf

# Use absolute path relative to project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')

def main():
    """Download SOXL data from yfinance and save as csv."""
    print("Downloading SOXL data from yfinance...")
    
    # SOXL inception was 2010-03-11. We download from 2010-03-11.
    df = yf.download("SOXL", start="2010-03-11", auto_adjust=False, multi_level_index=False)
    
    if df.empty:
        print("Error: No data downloaded for SOXL.")
        return
        
    # Check for MultiIndex columns and flatten them
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    # Ensure index name is 'Date'
    df.index.name = 'Date'
    
    # Keep only the requested columns: Open, High, Low, Close, Volume
    columns_to_keep = ['Open', 'High', 'Low', 'Close', 'Volume']
    df = df[columns_to_keep]
    
    output_file = os.path.join(DATA_DIR, 'soxl.csv')
    df.to_csv(output_file)
    
    print(f"Successfully saved {len(df)} rows to {output_file}")
    print("First 5 rows:")
    print(df.head())
    print("\nLast 5 rows:")
    print(df.tail())

if __name__ == "__main__":
    main()

from lrs_backtest import run_comparison
import pandas as pd

if __name__ == "__main__":
    df, metrics = run_comparison(start_date='2010-01-01')
    
    print("\nDEBUG INFO:")
    print("Columns:", df.columns)
    
    if 'SPX_3x_Return' in df.columns and 'TQQQ_Return' in df.columns:
        print("\nCorrelation:")
        print(df[['SPX_3x_Return', 'TQQQ_Return']].corr())
        
        print("\nFirst 10 rows:")
        print(df[['SPX_3x_Return', 'TQQQ_Return']].head(10))
        
        diff = (df['SPX_3x_Return'] - df['TQQQ_Return']).abs().sum()
        print(f"\nTotal Absolute Difference: {diff}")
        
        if diff < 1e-6:
            print("WARNING: DATA IS IDENTICAL!")
        else:
            print("Data is different.")
    else:
        print("Required columns missing.")

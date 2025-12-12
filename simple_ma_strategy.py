import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def run_strategy(spx_filepath='data/sp500.csv', upro_filepath='data/upro.csv', ma_windows=[10, 20, 50, 100, 200]):
    print(f"Loading data from {spx_filepath} and {upro_filepath}...")
    try:
        df_spx = pd.read_csv(spx_filepath, parse_dates=['Date'], index_col='Date').sort_index()
        df_upro = pd.read_csv(upro_filepath, parse_dates=['Date'], index_col='Date').sort_index()
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    # Calculate Market Returns for Benchmark (SPX)
    df_spx['Market_Returns'] = df_spx['Close'].pct_change()
    
    # Calculate UPRO Returns
    df_upro['UPRO_Returns'] = df_upro['Close'].pct_change()
    
    # Combine into one DF to ensure date alignment
    # We want rows where we have both if we are comparing day-to-day, 
    # but signals come from SPX history (which is long).
    
    # Calculate Signals on full SPX history first
    for window in ma_windows:
        ma_col = f'MA_{window}'
        df_spx[ma_col] = df_spx['Close'].rolling(window=window).mean()
        
        signal_col = f'Signal_{window}'
        df_spx[signal_col] = np.where(df_spx['Close'] > df_spx[ma_col], 1, 0)
        
        # Position is shifted signal
        pos_col = f'Position_{window}'
        df_spx[pos_col] = df_spx[signal_col].shift(1)

    # Join UPRO returns to SPX
    # We use inner join or left join? 
    # We need UPRO returns to trade. So we are limited by UPRO history.
    df_combined = df_spx.join(df_upro[['UPRO_Returns']], how='inner')
    
    # Filter for the requested time period (User wanted Oct 1928 to Dec 2020)
    # But UPRO starts 2009. So we use Max(Start, UPRO_Start) to Dec 2020.
    start_date = '1928-10-01' # Effectively starts 2009-06-25
    end_date = '2020-12-31'
    
    df_common = df_combined.loc[start_date:end_date].copy()
    
    if df_common.empty:
        print("Error: No data in specified range after merge.")
        return

    # Create a results container
    results = {}
    
    # Buy & Hold SPX (Benchmark)
    df_common['bh_cum_returns'] = (1 + df_common['Market_Returns']).cumprod()
    
    # Buy & Hold UPRO (Benchmark 2)
    df_common['upro_bh_cum_returns'] = (1 + df_common['UPRO_Returns']).cumprod()

    # Calculate stats for Benchmarks
    total_years = (df_common.index[-1] - df_common.index[0]).days / 365.25
    
    bh_total_return = df_common['bh_cum_returns'].iloc[-1] - 1
    bh_cagr = (1 + bh_total_return)**(1/total_years) - 1
    results['Buy & Hold (SPX)'] = {'Total Return': bh_total_return, 'CAGR': bh_cagr}
    
    upro_bh_total_return = df_common['upro_bh_cum_returns'].iloc[-1] - 1
    upro_bh_cagr = (1 + upro_bh_total_return)**(1/total_years) - 1
    results['Buy & Hold (UPRO)'] = {'Total Return': upro_bh_total_return, 'CAGR': upro_bh_cagr}

    # Plotting setup
    plt.figure(figsize=(14, 7))
    plt.plot(df_common.index, df_common['bh_cum_returns'], label='Buy & Hold (SPX)', color='black', linewidth=1.5, linestyle='--', alpha=0.6)
    plt.plot(df_common.index, df_common['upro_bh_cum_returns'], label='Buy & Hold (UPRO)', color='grey', linewidth=1, alpha=0.4)

    print("\n--- Performance Summary (UPRO Tradable Era) ---")
    print(f"Period: {df_common.index[0].date()} to {df_common.index[-1].date()}")
    
    for window in ma_windows:
        # Calculate Strategy Returns using UPRO Returns
        # Strategy: If Position_window == 1 (Buy), return = UPRO_Return
        #           If Position_window == 0 (Cash), return = 0
        
        pos_col = f'Position_{window}'
        strat_ret_col = f'Strat_Ret_{window}'
        
        # Note: pos_col comes from SPX df, so it should be in df_common
        df_common[strat_ret_col] = df_common[pos_col] * df_common['UPRO_Returns']
        
        # Cum Returns
        cum_returns = (1 + df_common[strat_ret_col]).cumprod()
        
        # Stats
        total_ret = cum_returns.iloc[-1] - 1
        cagr = (1 + total_ret)**(1/total_years) - 1
        
        results[f'MA {window}'] = {'Total Return': total_ret, 'CAGR': cagr}
        
        # Plot
        plt.plot(df_common.index, cum_returns, label=f'MA {window} (Trade UPRO)', linewidth=1)

    # Print Table
    print(f"{'Strategy':<20} | {'CAGR':<10} | {'Total Return':<15}")
    print("-" * 50)
    sorted_strategies = sorted(results.keys(), key=lambda x: results[x]['CAGR'], reverse=True)
    
    for key in sorted_strategies:
        print(f"{key:<20} | {results[key]['CAGR']:.2%}     | {results[key]['Total Return']:.2%}")
        
    print("-" * 50)

    plt.title(f'Strategies: Signal on SPX, Trade UPRO ({start_date} to {end_date})')
    plt.xlabel('Date')
    plt.ylabel('Cumulative Return (Growth of $1)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.yscale('log')
    
    output_img = 'upro_ma_strategy_comparison.png'
    plt.savefig(output_img)
    print(f"\nPlot saved to {output_img}")

if __name__ == "__main__":
    run_strategy()

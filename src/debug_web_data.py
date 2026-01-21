import sys
import os
import pandas as pd
import json

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

try:
    from lrs_web_utils import get_hybrid_sniper_data
    print("Import successful.")
    
    print("Fetching data...")
    df = get_hybrid_sniper_data()
    print(f"Data fetched. Shape: {df.shape}")
    print("Columns:", df.columns.tolist())
    
    # Simulate API serialization
    data = df.reset_index().copy()
    data['Date'] = data['Date'].dt.strftime('%Y-%m-%d')
    data = data.where(pd.notnull(data), None)
    
    cols = ['Date', 'Close', 'SMA_200', 'RSI', 'Signal', 'LRS_Sniper_Value', 'BH_TQQQ_Value']
    result = data[cols].to_dict(orient='records')
    
    # Try dumping to JSON to catch serialization errors
    json_str = json.dumps(result)
    print("JSON serialization successful.")
    
except Exception as e:
    print("\nXXX ERROR OCCURRED XXX")
    print(e)
    import traceback
    traceback.print_exc()

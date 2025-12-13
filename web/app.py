from flask import Flask, render_template, jsonify
import sys
import os
import pandas as pd
import numpy as np
import json

# Add project root to sys.path to import lrs_web_utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from lrs_web_utils import get_hybrid_sniper_data, get_latest_signals

app = Flask(__name__)

# Global cache for data (simple for local host)
DATA = None

def load_data():
    global DATA
    if DATA is None:
        DATA = get_hybrid_sniper_data()
    return DATA

@app.route('/')
def index():
    df = load_data()
    status = get_latest_signals(df)
    return render_template('index.html', status=status)

@app.route('/api/data')
def api_data():
    try:
        df = load_data()
        
        # Reset index to get Date column
        data = df.reset_index().copy()
        
        # Ensure 'Date' column exists (handle unnamed index)
        if 'Date' not in data.columns:
            if 'index' in data.columns:
                data.rename(columns={'index': 'Date'}, inplace=True)
            else:
                return jsonify({'error': 'Date column missing in data'}), 500
        
        # Rename Date for JSON
        data['Date'] = data['Date'].dt.strftime('%Y-%m-%d')
        
        # Replace NaN with null for JSON
        data = data.where(pd.notnull(data), None)
        
        # Select columns to convert
        cols = ['Date', 'Close', 'SMA_200', 'RSI', 'Signal', 'LRS_Sniper_Value', 'BH_TQQQ_Value']
        
        # Check if columns exist
        missing = [c for c in cols if c not in data.columns]
        if missing:
             return jsonify({'error': f'Missing columns: {missing}'}), 500
        
        # Convert to JSON records
        result = data[cols].to_dict(orient='records')
        
        # Calculate Entry/Exit Flags
        events = []
        if 'Signal' in df.columns:
             # Identify signal changes
            df['Signal_Change'] = df['Signal'].diff()
            
            # Changes
            changes = df[df['Signal_Change'] != 0].dropna()
            
            for date, row in changes.iterrows():
                # Determine Type
                change = row['Signal_Change']
                signal = row['Signal']
                
                event_type = "UNKNOWN"
                if change > 0: # Buy / Increase
                    if signal == 0.5: event_type = "SNIPER ENTRY"
                    elif signal == 1.0: event_type = "TREND ENTRY"
                elif change < 0: # Sell / Decrease
                    if signal == 0.5: event_type = "PARTIAL EXIT" 
                    elif signal == 0.0: event_type = "EXIT TO CASH"
                    
                events.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'price': row['Close'],
                    'type': event_type,
                    'signal_new': signal
                })
        
        return jsonify({
            'history': result,
            'events': events
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8050)

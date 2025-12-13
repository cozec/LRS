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
        
        # Calculate 2% Buffer Bands (Buffer Magic) BEFORE sanitization
        if 'SMA_200' in data.columns:
            data['SMA_200_Upper'] = data['SMA_200'] * 1.02
            data['SMA_200_Lower'] = data['SMA_200'] * 0.98

        # Replace NaN with null for JSON
        # Cast to object first to ensure None is accepted in float columns
        data = data.astype(object).where(pd.notnull(data), None)
        
        # Select columns to convert
        cols = ['Date', 'Close', 'SMA_200', 'SMA_200_Upper', 'SMA_200_Lower', 'MA_10', 'RSI', 'Signal', 'Regime', 'TQQQ_Close', 'LRS_Sniper_Value', 'BH_TQQQ_Value']
        
        # Check if columns exist
        missing = [c for c in cols if c not in data.columns]
        if missing:
             return jsonify({'error': f'Missing columns: {missing}'}), 500
        
        # Convert to JSON records
        result = data[cols].to_dict(orient='records')
        
        # Calculate Entry/Exit Flags (Use REGIME for Signal Date)
        events = []
        if 'Regime' in df.columns:
             # Identify signal changes (Regime change = Signal generated at Close)
            df['Regime_Change'] = df['Regime'].diff()
            
            # Changes
            changes = df[df['Regime_Change'] != 0].dropna()
            
            for date, row in changes.iterrows():
                # Determine Type
                change = row['Regime_Change']
                state = row['Regime']
                
                event_type = "UNKNOWN"
                # Logic: 0.0 -> 0.5 (Sniper), 0.5 -> 1.0 (Trend), etc.
                # However, Regime contains 0.0, 0.5, 1.0
                
                if state == 0.5 and (row['Regime_Change'] > 0 or row['Regime_Change'] == 0.5): 
                    event_type = "SNIPER SIGNAL"
                elif state == 1.0: 
                    event_type = "TREND SIGNAL"
                elif state == 0.0:
                    event_type = "EXIT SIGNAL"
                elif change < 0 and state == 0.5: # 1.0 -> 0.5
                    event_type = "REDUCE SIGNAL"
                    
                events.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'price': row['Close'],
                    'rsi': row['RSI'],
                    'type': event_type,
                    'signal_new': state
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

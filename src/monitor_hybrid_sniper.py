#!/usr/bin/env python3
"""
Hybrid Sniper Strategy Monitor
Runs every hour during market hours, calculates signals, and sends email alerts.
"""

import os
import sys
import time
import json
import smtplib
import argparse
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import strategy utilities
try:
    from src.lrs_web_utils import get_hybrid_sniper_data, get_latest_signals
except ImportError:
    # Fallback for different execution contexts
    from lrs_web_utils import get_hybrid_sniper_data, get_latest_signals

# Load environment variables
load_dotenv()

# Configuration
STATE_FILE = os.path.join('results', 'monitor_state.json')
LOG_FILE = os.path.join('logs', 'monitor.log')

def log(message):
    """Log a message to console and file."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)
    
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(log_msg + '\n')

def send_email(subject, body, dry_run=False):
    """Send an email alert."""
    if dry_run:
        log(f"[DRY-RUN] Email alert: {subject}")
        log(f"[DRY-RUN] Body: {body}")
        return True

    sender_email = os.getenv('SENDER_EMAIL')
    sender_password = os.getenv('SENDER_PASSWORD')
    recipient_email = os.getenv('RECIPIENT_EMAIL')
    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', 587))

    if not all([sender_email, sender_password, recipient_email]):
        log("ERROR: SMTP configuration missing in .env")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        log(f"Email sent successfully: {subject}")
        return True
    except Exception as e:
        log(f"ERROR sending email: {e}")
        return False

def get_market_status():
    """Check if market is open using the utility function."""
    # Since lrs_web_utils.py is already present and imported
    # We can use its is_market_open if available, or implement a simple one here.
    # Looking at src/lrs_web_utils.py, it doesn't seem to have is_market_open in the version I read (lines 1-149).
    # Wait, the root version had it, but src/ version didn't? Let me double check src/lrs_web_utils.py.
    # Actually, let's implement a robust one here to be safe.
    import pytz
    from datetime import time as dt_time
    
    et_tz = pytz.timezone('America/New_York')
    now = datetime.now(et_tz)
    
    if now.weekday() >= 5:  # Weekend
        return False
        
    market_open = dt_time(9, 30)
    market_close = dt_time(16, 0)
    current_time = now.time()
    
    return market_open <= current_time <= market_close

def load_state():
    """Load the last known signal state."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            log(f"Error loading state: {e}")
    return {"last_signal": None, "last_regime": None, "last_ma_cross": None}

def save_state(state):
    """Save the current signal state."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    except Exception as e:
        log(f"Error saving state: {e}")

def check_signals(dry_run=False):
    """Fetch latest data, calculate signals, and alert on changes."""
    log("Checking signals...")
    
    try:
        # Fetch fresh data (force_refresh=True to get latest yfinance data)
        df = get_hybrid_sniper_data(force_refresh=True)
        latest = get_latest_signals(df)
        
        current_alloc = latest['signal_alloc']
        current_regime = latest['regime']
        current_ma10 = latest['ma_10']
        current_sma200 = latest['sma_200']
        ma_below = bool(current_ma10 < current_sma200)
        
        state = load_state()
        last_alloc = state.get('last_signal')
        last_ma_below = state.get('last_ma_cross') # True if was below last time
        
        log(f"Current Signal Allocation: {current_alloc} | Last Signal: {last_alloc}")
        log(f"Current MA10: {current_ma10:.2f} | SMA200: {current_sma200:.2f} | Below: {ma_below}")

        if last_alloc is not None and current_alloc != last_alloc:
            # Change detected!
            emoji = "🚀" if current_alloc > last_alloc else "📉"
            subject = f"{emoji} Hybrid Sniper Alert: Signal Change to {current_alloc}"
            
            # Determine if Entry or Exit
            if current_alloc > last_alloc:
                action = "ENTRY / INCREASE POSITION 🚀"
            else:
                action = "EXIT / DECREASE POSITION 📉"
                
            body = f"""
HYBRID SNIPER ALERT

Action: {action}
New Allocation: {current_alloc * 100}%
Previous Allocation: {last_alloc * 100}%

Market Mode: {latest['mode']}
Signal Date: {latest['date']}

S&P 500 Price: {latest['price']:.2f}
200-day SMA: {latest['sma_200']:.2f}
RSI (14): {latest['rsi']:.2f}

Please check your terminal or dashboard for more details.
"""
            send_email(subject, body, dry_run=dry_run)
        
        # Check for MA10 crossing below SMA200 Warning
        # Only alert if it JUST crossed (last state was False/None and current is True)
        if ma_below and not last_ma_below:
            warn_subject = "⚠️ ALERT: MA10 Crossed Below SMA200"
            warn_body = f"""
HYBRID SNIPER WARNING

Trend Shift: The 10-day Moving Average (MA10) has crossed below the 200-day Moving Average (SMA200).

Current Status:
MA10: {current_ma10:.2f}
SMA200: {current_sma200:.2f}

Note: The strategy has NOT necessarily triggered an exit yet.
The exit trigger requires MA10 to be below SMA200 * 0.98.
This is a pre-warning of potential weakness.

Signal Date: {latest['date']}
"""
            send_email(warn_subject, warn_body, dry_run=dry_run)
        elif not ma_below and last_ma_below:
            # Recovery alert
            recover_subject = "✅ RECOVERY: MA10 Back Above SMA200"
            recover_body = f"The MA10 ({current_ma10:.2f}) has recovered and is now above SMA200 ({current_sma200:.2f})."
            send_email(recover_subject, recover_body, dry_run=dry_run)

        # Update state regardless of change (to track current)
        state['last_signal'] = current_alloc
        state['last_regime'] = current_regime
        state['last_ma_cross'] = ma_below
        state['last_check'] = datetime.now().isoformat()
        save_state(state)
        
    except Exception as e:
        log(f"ERROR checking signals: {e}")
        import traceback
        log(traceback.format_exc())

def main():
    parser = argparse.ArgumentParser(description="Hybrid Sniper Monitor")
    parser.add_argument('--dry-run', action='store_true', help="Run without sending emails")
    parser.add_argument('--test-email', action='store_true', help="Send a general test email and exit")
    parser.add_argument('--test-alert', action='store_true', help="Send a simulated strategy alert and exit")
    parser.add_argument('--test-warning', action='store_true', help="Send a simulated trend warning and exit")
    parser.add_argument('--once', action='store_true', help="Run once and exit")
    args = parser.parse_args()

    if args.test_email:
        send_email("🧪 Hybrid Sniper Test Email", "This is a test alert from the monitoring system.", dry_run=args.dry_run)
        return

    if args.test_alert:
        send_email("🚀 Hybrid Sniper Alert: Signal Change to 1.0", "SIMULATED ALERT\n\nAction: ENTRY / INCREASE POSITION 🚀\nNew Allocation: 100%\nPrevious Allocation: 0%\n\nMarket Mode: TREND MODE (100% TQQQ)\nSignal Date: 2026-03-19", dry_run=args.dry_run)
        return

    if args.test_warning:
        send_email("⚠️ ALERT: MA10 Crossed Below SMA200", "SIMULATED WARNING\n\nTrend Shift: The 10-day Moving Average (MA10) has crossed below the 200-day Moving Average (SMA200).\n\nCurrent Status:\nMA10: 6500.00\nSMA200: 6550.00\n\nNote: The strategy has NOT necessarily triggered an exit yet.", dry_run=args.dry_run)
        return

    log("Starting Hybrid Sniper Monitor loop...")
    dry_run_env = os.getenv('DRY_RUN', 'False').lower() == 'true'
    is_dry_run = args.dry_run or dry_run_env
    
    if is_dry_run:
        log("RUNNING IN DRY_RUN MODE - No emails will be sent.")

    while True:
        if get_market_status():
            check_signals(dry_run=is_dry_run)
        else:
            log("Market is closed. Skipping check.")
            # During market close, we could still check once at start or just wait.
            # Let's just log and wait.
            
        if args.once:
            break
            
        log("Sleeping for 1 hour...")
        time.sleep(3600)

if __name__ == "__main__":
    main()

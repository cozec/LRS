#!/usr/bin/env python3
"""
Hybrid Sniper Strategy Monitor

Checks the strategy once per completed daily bar (after 16:15 ET) and
emails an alert when that close's decision changes the allocation.
Alerts are for execution at the next market open.
"""

import os
import sys
import time
import json
import smtplib
import argparse
import datetime as dt
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv

# Import from src/ (this file's directory), never the stale root copies
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)
sys.path.insert(0, SRC_DIR)

from lrs_web_utils import get_hybrid_sniper_data, get_latest_signals  # noqa: E402
from update_data import ET, BAR_FINAL_TIME, drop_incomplete_bar  # noqa: E402

# Load environment variables
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# Configuration
STATE_FILE = os.path.join(PROJECT_ROOT, 'results', 'monitor_state.json')
LOG_FILE = os.path.join(PROJECT_ROOT, 'logs', 'monitor.log')
CHECK_INTERVAL_SECONDS = 30 * 60


def log(message):
    """Log a message to console and file."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(log_msg + '\n')


def send_email(subject, body, dry_run=False):
    """
    Send an email alert.

    Returns:
    bool: True if the email was sent (or logged in dry-run mode).
    """
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


def expected_bar_date(now=None):
    """
    Date of the most recent daily bar that should be final by ``now``.

    Weekdays only; exchange holidays are not modelled (on a holiday the
    expected bar never arrives and the monitor simply re-checks).

    Parameters:
    now (datetime, optional): Current time; defaults to now in US/Eastern.

    Returns:
    datetime.date: Today after 16:15 ET on a weekday, else the previous
    weekday.
    """
    now = (now or datetime.now(ET)).astimezone(ET)
    day = now.date()
    if now.weekday() < 5 and now.time() >= BAR_FINAL_TIME:
        return day
    day -= dt.timedelta(days=1)
    while day.weekday() >= 5:
        day -= dt.timedelta(days=1)
    return day


def should_check(state, now=None):
    """
    Tell whether a newer completed bar than the last processed one is due.

    Parameters:
    state (dict): Monitor state with optional 'last_bar_date' (ISO date).
    now (datetime, optional): Current time, see ``expected_bar_date``.

    Returns:
    bool: True if the monitor should fetch data now.
    """
    last = state.get('last_bar_date')
    if last is None:
        return True
    return dt.date.fromisoformat(last) < expected_bar_date(now)


def load_state():
    """Load the last known signal state."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            log(f"Error loading state: {e}")
    return {"last_regime": None, "last_ma_cross": None, "last_bar_date": None}


def save_state(state):
    """Save the current signal state."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    except Exception as e:
        log(f"Error saving state: {e}")


def regime_alert(latest, last_regime):
    """
    Build the subject and body for an allocation-change alert.

    Parameters:
    latest (dict): Output of ``get_latest_signals`` for a final close.
    last_regime (float): Previously alerted allocation.

    Returns:
    tuple: (subject, body).
    """
    new_regime = latest['regime']
    up = new_regime > last_regime
    emoji = "🚀" if up else "📉"
    action = "ENTRY / INCREASE POSITION 🚀" if up else "EXIT / DECREASE POSITION 📉"
    subject = f"{emoji} Hybrid Sniper Alert: Signal Change to {new_regime}"
    body = f"""
HYBRID SNIPER ALERT

Action: {action}
New Allocation: {new_regime * 100}% TQQQ
Previous Allocation: {last_regime * 100}% TQQQ
Execute: at the next market open

Decision based on the close of: {latest['date']}

S&P 500 Close: {latest['price']:.2f}
MA10: {latest['ma_10']:.2f}
200-day SMA: {latest['sma_200']:.2f}
RSI (14): {latest['rsi']:.2f}

Please check your terminal or dashboard for more details.
"""
    return subject, body


def check_signals(dry_run=False):
    """
    Fetch data, evaluate the latest completed close, and alert on changes.

    The state for an alert is only updated after its email is sent, so a
    failed send is retried on the next check instead of being lost. The
    first run records the current state without alerting.
    """
    log("Checking signals...")

    try:
        df = get_hybrid_sniper_data(force_refresh=True)
        # Decide only on final closes, never on an intraday bar
        df = drop_incomplete_bar(df)
        latest = get_latest_signals(df)

        bar_date = latest['date']
        current_regime = float(latest['regime'])
        current_ma10 = latest['ma_10']
        current_sma200 = latest['sma_200']
        ma_below = bool(current_ma10 < current_sma200)

        state = load_state()
        last_regime = state.get('last_regime')
        last_ma_below = state.get('last_ma_cross')

        log(f"Close {bar_date}: allocation for next open {current_regime} "
            f"| last alerted {last_regime}")
        log(f"MA10: {current_ma10:.2f} | SMA200: {current_sma200:.2f} "
            f"| Below: {ma_below}")
        all_sent = True

        if last_regime is None:
            log("First run: recording current state without alerting.")
            state['last_regime'] = current_regime
        elif current_regime != last_regime:
            subject, body = regime_alert(latest, last_regime)
            if send_email(subject, body, dry_run=dry_run):
                state['last_regime'] = current_regime
            else:
                all_sent = False

        # MA10 vs SMA200 pre-warning (the exit itself needs SMA200 * 0.98)
        if last_ma_below is None:
            state['last_ma_cross'] = ma_below
        elif ma_below and not last_ma_below:
            warn_subject = "⚠️ ALERT: MA10 Crossed Below SMA200"
            warn_body = f"""
HYBRID SNIPER WARNING

Trend Shift: The 10-day Moving Average (MA10) has crossed below the 200-day Moving Average (SMA200).

Current Status (close of {bar_date}):
MA10: {current_ma10:.2f}
SMA200: {current_sma200:.2f}

Note: The strategy has NOT necessarily triggered an exit yet.
The exit trigger requires MA10 to be below SMA200 * 0.98.
This is a pre-warning of potential weakness.
"""
            if send_email(warn_subject, warn_body, dry_run=dry_run):
                state['last_ma_cross'] = ma_below
            else:
                all_sent = False
        elif not ma_below and last_ma_below:
            recover_subject = "✅ RECOVERY: MA10 Back Above SMA200"
            recover_body = (f"The MA10 ({current_ma10:.2f}) has recovered and is now "
                            f"above SMA200 ({current_sma200:.2f}) as of the close of {bar_date}.")
            if send_email(recover_subject, recover_body, dry_run=dry_run):
                state['last_ma_cross'] = ma_below
            else:
                all_sent = False

        # Leave last_bar_date behind on a failed send so the loop retries
        if all_sent:
            state['last_bar_date'] = bar_date
        state['last_check'] = datetime.now().isoformat()
        save_state(state)

    except Exception as e:
        log(f"ERROR checking signals: {e}")
        import traceback
        log(traceback.format_exc())


def main():
    """Parse arguments and run the monitor loop (or a one-off action)."""
    parser = argparse.ArgumentParser(description="Hybrid Sniper Monitor")
    parser.add_argument('--dry-run', action='store_true', help="Run without sending emails")
    parser.add_argument('--test-email', action='store_true', help="Send a general test email and exit")
    parser.add_argument('--test-alert', action='store_true', help="Send a simulated strategy alert and exit")
    parser.add_argument('--test-warning', action='store_true', help="Send a simulated trend warning and exit")
    parser.add_argument('--once', action='store_true', help="Check the latest completed close now and exit")
    args = parser.parse_args()

    if args.test_email:
        send_email("🧪 Hybrid Sniper Test Email", "This is a test alert from the monitoring system.", dry_run=args.dry_run)
        return

    if args.test_alert:
        send_email("🚀 Hybrid Sniper Alert: Signal Change to 1.0", "SIMULATED ALERT\n\nAction: ENTRY / INCREASE POSITION 🚀\nNew Allocation: 100% TQQQ\nPrevious Allocation: 0% TQQQ\nExecute: at the next market open\n\nDecision based on the close of: 2026-03-19", dry_run=args.dry_run)
        return

    if args.test_warning:
        send_email("⚠️ ALERT: MA10 Crossed Below SMA200", "SIMULATED WARNING\n\nTrend Shift: The 10-day Moving Average (MA10) has crossed below the 200-day Moving Average (SMA200).\n\nCurrent Status:\nMA10: 6500.00\nSMA200: 6550.00\n\nNote: The strategy has NOT necessarily triggered an exit yet.", dry_run=args.dry_run)
        return

    dry_run_env = os.getenv('DRY_RUN', 'False').lower() == 'true'
    is_dry_run = args.dry_run or dry_run_env
    if is_dry_run:
        log("RUNNING IN DRY_RUN MODE - No emails will be sent.")

    if args.once:
        check_signals(dry_run=is_dry_run)
        return

    log("Starting Hybrid Sniper Monitor loop (checks each completed close after 16:15 ET)...")
    while True:
        if should_check(load_state()):
            check_signals(dry_run=is_dry_run)
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

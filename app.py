import streamlit as st
import pandas as pd
import ccxt
import time

# === CONFIG ===
TIMEFRAMES = ['1m', '3m', '5m', '10m', '15m', '20m', '30m', '1h', '2h', '4h', '6h', '8h', '10h', '12h', '16h', '1d', '1w']
BITGET = ccxt.bitget()

# === HELPER FUNCTIONS ===
def fetch_ohlcv(symbol, timeframe, limit=100):
    try:
        ohlcv = BITGET.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception:
        return None

def detect_swing_points(df, left=2, right=2):
    highs = df['high']
    lows = df['low']
    swing_highs = (highs.shift(left) < highs) & (highs.shift(-right) < highs)
    swing_lows = (lows.shift(left) > lows) & (lows.shift(-right) > lows)
    df['swing_high'] = swing_highs
    df['swing_low'] = swing_lows
    return df

def classify_trend(df):
    swings = df[(df['swing_high']) | (df['swing_low'])].copy()
    swings = swings[['timestamp', 'high', 'low', 'swing_high', 'swing_low']]
    labels = []
    last_high = last_low = None
    trend_status = "No Trend"
    bos = False
    choch = False

    for i in range(len(swings)):
        row = swings.iloc[i]
        if row['swing_high']:
            label = 'HH' if last_high is None or row['high'] > last_high else 'LH'
            bos = True if label == 'HH' and last_high is not None else bos
            choch = True if label == 'LH' and last_high is not None else choch
            last_high = row['high']
        elif row['swing_low']:
            label = 'HL' if last_low is None or row['low'] > last_low else 'LL'
            bos = True if label == 'LL' and last_low is not None else bos
            choch = True if label == 'HL' and last_low is not None else choch
            last_low = row['low']
        labels.append(label)

    swings['label'] = labels
    last_labels = swings['label'].tail(4).tolist()
    if len(last_labels) < 3:
        trend_status = "No Trend"
    elif last_labels[-3:] == ['HH', 'HL', 'HH'] or last_labels[-3:] == ['HL', 'HH', 'HL']:
        trend_status = 'Uptrend'
    elif last_labels[-3:] == ['LL', 'LH', 'LL'] or last_labels[-3:] == ['LH', 'LL', 'LH']:
        trend_status = 'Downtrend'
    else:
        trend_status = 'Trend Broken'

    if choch and not bos:
        trend_status = 'Change of Character'
    elif bos and not choch:
        trend_status = trend_status + ' (BoS)'

    return trend_status

def analyze_trends(symbols, timeframes):
    results = []
    for tf in timeframes:
        for idx, symbol in enumerate(symbols):
            st.info(f"Scanning {symbol} on {tf} ({idx+1}/{len(symbols)})")
            df = fetch_ohlcv(symbol, tf)
            if df is None or len(df) < 20:
                continue
            df = detect_swing_points(df)
            trend = classify_trend(df)
            results.append({'Symbol': symbol, 'Timeframe': tf, 'Trend': trend})
            time.sleep(0.3)
    return pd.DataFrame(results)

# === STREAMLIT UI ===
st.set_page_config(layout="wide")
st.title("📈 Bitget Price Action Trend Screener")

selected_timeframes = st.multiselect("Select Timeframes to Scan", TIMEFRAMES, default=['1h', '4h', '1d'])
st.write("This tool scans Bitget USDT Perpetual markets using pure price action swing structure to identify Uptrends, Downtrends, and Changes of Character.")

if st.button("Run Screener"):
    with st.spinner("Scanning Bitget markets... Please wait..."):
        markets = BITGET.load_markets()
        symbols = [s for s in markets if '/USDT:USDT' in s and markets[s]['type'] == 'swap']

        result_df = analyze_trends(symbols, selected_timeframes)

        if not result_df.empty:
            uptrend_df = result_df[result_df['Trend'].str.contains('Uptrend')]
            downtrend_df = result_df[result_df['Trend'].str.contains('Downtrend')]
            choch_df = result_df[result_df['Trend'].str.contains('Change of Character')]
            broken_df = result_df[result_df['Trend'].str.contains('Trend Broken')]
            no_trend_df = result_df[result_df['Trend'] == 'No Trend']

            if not uptrend_df.empty:
                st.markdown("### 🟢 Uptrend")
                st.dataframe(uptrend_df, use_container_width=True)

            if not downtrend_df.empty:
                st.markdown("### 🔴 Downtrend")
                st.dataframe(downtrend_df, use_container_width=True)

            if not choch_df.empty:
                st.markdown("### ⚠️ Change of Character")
                st.dataframe(choch_df, use_container_width=True)

            if not broken_df.empty:
                st.markdown("### ⚫ Trend Broken")
                st.dataframe(broken_df, use_container_width=True)

            if not no_trend_df.empty:
                st.markdown("### ⚪ No Trend")
                st.dataframe(no_trend_df, use_container_width=True)

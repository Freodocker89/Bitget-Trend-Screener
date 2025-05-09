import streamlit as st
import pandas as pd
import ccxt
import time

# === CONFIG ===
TIMEFRAMES = ['1m', '3m', '5m', '10m', '15m', '20m', '30m', '1h', '2h', '4h', '8h', '10h', '16h', '1d', '1w']
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

    for i in range(len(swings)):
        row = swings.iloc[i]
        if row['swing_high']:
            label = 'HH' if last_high is None or row['high'] > last_high else 'LH'
            last_high = row['high']
        elif row['swing_low']:
            label = 'HL' if last_low is None or row['low'] > last_low else 'LL'
            last_low = row['low']
        labels.append(label)

    swings['label'] = labels
    last_labels = swings['label'].tail(4).tolist()
    if len(last_labels) < 3:
        return "No Trend"
    if last_labels[-3:] == ['HH', 'HL', 'HH'] or last_labels[-3:] == ['HL', 'HH', 'HL']:
        return 'Uptrend'
    elif last_labels[-3:] == ['LL', 'LH', 'LL'] or last_labels[-3:] == ['LH', 'LL', 'LH']:
        return 'Downtrend'
    else:
        return 'Trend Broken'

def analyze_trends(symbols, timeframes):
    results = []
    for tf in timeframes:
        for symbol in symbols:
            df = fetch_ohlcv(symbol, tf)
            if df is None or len(df) < 20:
                continue
            df = detect_swing_points(df)
            trend = classify_trend(df)
            results.append({'Symbol': symbol, 'Timeframe': tf, 'Trend': trend})
            time.sleep(0.3)  # Avoid rate limits
    return pd.DataFrame(results)

# === STREAMLIT UI ===
st.set_page_config(layout="wide")
st.title("📊 Bitget Futures Trend Screener (Price Action)")

selected_timeframes = st.multiselect("Select Timeframes to Scan", TIMEFRAMES, default=['1h', '4h', '1d'])
st.write("This tool shows clean Uptrends and Downtrends only. Any broken structures are filtered out.")

if st.button("Run Screener"):
    with st.spinner("Scanning markets... This may take a minute..."):
        markets = BITGET.load_markets()
        symbols = [s for s in markets if '/USDT:USDT' in s and markets[s]['type'] == 'swap']

        trend_df = analyze_trends(symbols, selected_timeframes)

        uptrends = trend_df[trend_df['Trend'] == 'Uptrend']
        downtrends = trend_df[trend_df['Trend'] == 'Downtrend']

        st.subheader("📈 Uptrending Assets")
        st.dataframe(uptrends, use_container_width=True)

        st.subheader("📉 Downtrending Assets")
        st.dataframe(downtrends, use_container_width=True)

        st.success("Screener complete!")

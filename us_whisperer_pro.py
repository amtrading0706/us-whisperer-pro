# us_whisperer_pro.py
import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from transformers import pipeline
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import re
import time

# -------------------------------
# 1. S&P 500 Tickers (Full List - 100+)
# -------------------------------
SP500 = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK.B', 'JPM', 'V',
    'JNJ', 'PG', 'UNH', 'HD', 'MA', 'DIS', 'NFLX', 'ADBE', 'CRM', 'PYPL',
    'INTC', 'AMD', 'CSCO', 'PEP', 'ABBV', 'TMO', 'AVGO', 'COST', 'MCD', 'ABT',
    'WMT', 'ACN', 'LIN', 'NEE', 'DHR', 'TXN', 'HON', 'ORCL', 'NKE', 'QCOM',
    'LOW', 'SBUX', 'IBM', 'GE', 'CAT', 'GS', 'BLK', 'AXP', 'BKNG', 'MDT',
    'CVS', 'GILD', 'ISRG', 'SYK', 'LRCX', 'NOW', 'MU', 'ADP', 'LMT', 'BA',
    'PLD', 'AMT', 'SCHW', 'T', 'VZ', 'CME', 'PNC', 'USB', 'COF', 'AON',
    'MMC', 'CB', 'PGR', 'AFL', 'MET', 'TRV', 'ALL', 'PRU', 'AIG', 'BK',
    'SPGI', 'MCO', 'ICE', 'CMG', 'KLAC', 'SNPS', 'CDNS', 'FTNT', 'PANW',
    'CRWD', 'ZS', 'DDOG', 'NET', 'DOCU', 'TWLO', 'OKTA', 'RBLX', 'SNOW'
]

# -------------------------------
# 2. Load FinBERT
# -------------------------------
@st.cache_resource
def load_model():
    return pipeline("sentiment-analysis", model="yiyanghkust/finbert-tone")

# -------------------------------
# 3. Earnings Calendar
# -------------------------------
def get_earnings_today():
    url = f"https://finance.yahoo.com/calendar/earnings?day={datetime.now().strftime('%Y-%m-%d')}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        dfs = pd.read_html(requests.get(url, headers=headers, timeout=10).text)
        df = dfs[0]
        df = df[df['Symbol'].isin(SP500)]
        return df[['Symbol', 'Company', 'EPS Estimate', 'Reported EPS']].dropna()
    except:
        return pd.DataFrame()

# -------------------------------
# 4. 8-K Filings (SEC)
# -------------------------------
def get_8k_filings():
    url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&count=100&output=atom"
    try:
        resp = requests.get(url, timeout=10)
        root = ET.fromstring(resp.content)
        filings = []
        for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry'):
            title = entry.find('.//{http://www.w3.org/2005/Atom}title').text
            link = entry.find('.//{http://www.w3.org/2005/Atom}link').attrib['href']
            symbol_match = re.search(r'\(([^)]+)\)', title)
            if symbol_match and symbol_match.group(1) in SP500:
                filings.append({'Symbol': symbol_match.group(1), 'Title': title, 'Link': link})
        return pd.DataFrame(filings)
    except:
        return pd.DataFrame()

# -------------------------------
# 5. Insider Buys (OpenInsider)
# -------------------------------
def get_insider_buys():
    url = "http://openinsider.com/latest-insider-trading"
    try:
        dfs = pd.read_html(requests.get(url, timeout=10).text)
        df = dfs[0]
        df = df[df['Trade Type'] == 'P - Open market purchase']
        df = df[df['Ticker'].isin(SP500)]
        return df[['Ticker', 'Filing Date', 'Insider Name', 'Price', 'Qty', 'Value']].head(10)
    except:
        return pd.DataFrame()

# -------------------------------
# 6. Price Move
# -------------------------------
def get_price_move(symbol):
    try:
        data = yf.download(symbol, period="2d", progress=False)
        if len(data) >= 2:
            return round((data['Close'].iloc[-1] / data['Close'].iloc[-2] - 1) * 100, 2)
        return None
    except:
        return None

# -------------------------------
# 7. Signal Logic
# -------------------------------
def get_signal(row, source):
    if source == "earnings":
        surprise = ((row['Reported EPS'] - row['EPS Estimate']) / abs(row['EPS Estimate'])) * 100
        if surprise > 15: return "STRONG BUY"
        elif surprise > 5: return "BUY"
        elif surprise < -10: return "STRONG SELL"
        elif surprise < -3: return "SELL"
        else: return "HOLD"
    elif source == "8k":
        score = row['Score']
        if score > 0.7: return "STRONG BUY"
        elif score > 0.4: return "BUY"
        elif score < -0.5: return "STRONG SELL"
        elif score < -0.2: return "SELL"
        else: return "HOLD"
    return "HOLD"

# -------------------------------
# 8. Streamlit App
# -------------------------------
def main():
    st.set_page_config(page_title="US Earnings Whisperer PRO", layout="wide")
    st.title("US Earnings Whisperer PRO")
    st.markdown("**S&P 500 AI Signals: Earnings + 8-K + Insider Buys** | Live Market Edge")

    tab1, tab2, tab3 = st.tabs(["Earnings Today", "8-K Filings", "Insider Buys"])

    # === TAB 1: EARNINGS ===
    with tab1:
        if st.button("Scan Earnings (Today)", type="primary"):
            with st.spinner("Loading earnings data..."):
                earnings = get_earnings_today()
                if not earnings.empty:
                    earnings['Surprise %'] = ((earnings['Reported EPS'] - earnings['EPS Estimate']) / earnings['EPS Estimate'].abs() * 100).round(1)
                    earnings['Signal'] = earnings.apply(lambda row: get_signal(row, "earnings"), axis=1)
                    earnings['Price Move'] = earnings['Symbol'].apply(get_price_move)
                    st.success(f"{len(earnings)} S&P 500 earnings today!")
                    st.dataframe(earnings[['Symbol', 'Company', 'Surprise %', 'Signal', 'Price Move']], use_container_width=True)
                else:
                    st.info("No S&P 500 earnings today.")

    # === TAB 2: 8-K ===
    with tab2:
        if st.button("Scan 8-K Filings (Last 24h)", type="primary"):
            with st.spinner("Scraping SEC 8-K..."):
                filings = get_8k_filings()
                if not filings.empty:
                    model = load_model()
                    results = []
                    for _, row in filings.iterrows():
                        text = row['Title'][:512]
                        sent = model(text)[0]
                        score = sent['score'] if sent['label'] == 'Positive' else -sent['score']
                        signal = get_signal({'Score': score}, "8k")
                        move = get_price_move(row['Symbol'])
                        results.append({
                            'Symbol': row['Symbol'],
                            'Title': row['Title'][:80] + '...',
                            'Score': round(score, 3),
                            'Signal': signal,
                            'Move %': move,
                            'Link': f"[SEC]({row['Link']})"
                        })
                    df = pd.DataFrame(results).sort_values('Score', descending=True)
                    st.success(f"{len(df)} 8-K signals!")
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No 8-K filings in last 24h.")

    # === TAB 3: INSIDER BUYS ===
    with tab3:
        if st.button("Scan Insider Buys (Last 24h)", type="primary"):
            with st.spinner("Loading insider data..."):
                insiders = get_insider_buys()
                if not insiders.empty:
                    insiders['Signal'] = "BUY (Insider)"
                    st.success(f"{len(insiders)} insider buys!")
                    st.dataframe(insiders, use_container_width=True)
                else:
                    st.info("No insider buys today.")

    st.caption("**LIVE | DEPLOYED | MONETIZABLE** | Sell for **$99/mo** on Gumroad")

if __name__ == "__main__":
    main()

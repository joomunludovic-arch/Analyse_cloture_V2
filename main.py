import os
import pandas as pd
import numpy as np
from datetime import datetime
import requests
from flask import Flask

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=data)

def generate_fake_data(ticker, days=60):
    np.random.seed(hash(ticker) % 123456)
    base_price = np.random.uniform(80, 150)
    dates = pd.date_range(end=datetime.today(), periods=days)
    close = base_price + np.cumsum(np.random.randn(days))
    open_ = close - np.random.uniform(0.5, 2.0, days)
    volume = np.random.randint(100_000, 1_000_000, days)
    return pd.DataFrame({
        'Date': dates,
        'Ticker': ticker,
        'Open': open_,
        'Close': close,
        'Volume': volume
    })

def calculate_ichimoku(df):
    df['Tenkan_sen'] = df['Close'].rolling(window=9).mean()
    df['Kijun_sen'] = df['Close'].rolling(window=26).mean()
    return df

@app.route('/')
def run_analysis():
    try:
        tickers = ['AAPL', 'TSLA', 'NFLX']
        all_signals = []

        for ticker in tickers:
            df = generate_fake_data(ticker)
            df = df.sort_values(by='Date')
            df['Volatility'] = df['Close'].rolling(window=10).std()
            vol_mean = df['Volatility'].mean()
            vol_std = df['Volatility'].std()
            df['Z_score'] = (df['Volatility'] - vol_mean) / vol_std
            df = calculate_ichimoku(df)

            df['Signal'] = np.where(
                (df['Z_score'] > 2) & (df['Close'] > df['Tenkan_sen']) & (df['Close'] > df['Kijun_sen']),
                "📈 Signal haussier",
                np.where(
                    (df['Z_score'] > 2) & (df['Close'] < df['Tenkan_sen']) & (df['Close'] < df['Kijun_sen']),
                    "📉 Signal baissier",
                    ""
                )
            )

            signals = df[df['Signal'] != ""][['Date', 'Ticker', 'Close', 'Z_score', 'Signal']].tail(3)
            all_signals.append(signals)

        final_alerts = pd.concat(all_signals)
        if not final_alerts.empty:
            messages = []
            for _, row in final_alerts.iterrows():
                msg = (
                    f"📌 {row['Ticker']} - {row['Date'].strftime('%Y-%m-%d')}\n"
                    f"💰 {row['Close']:.2f} | Z={row['Z_score']:.2f}\n"
                    f"{row['Signal']}"
                )
                messages.append(msg)
            send_telegram_message("📊 Signaux détectés :\n\n" + "\n\n".join(messages))
        else:
            send_telegram_message("✅ Aucune anomalie détectée aujourd’hui.")
        return "✅ Analyse exécutée avec succès"
    except Exception as e:
        send_telegram_message(f"❌ Erreur : {str(e)}")
        return f"❌ Erreur dans le script : {str(e)}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
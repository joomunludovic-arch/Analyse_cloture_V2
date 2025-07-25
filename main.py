import os
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import requests
from flask import Flask
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Flask app
app = Flask(__name__)

# Telegram credentials
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Google Sheets scope
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(
    "/etc/secrets/credentials.json", scope
)

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"Erreur envoi Telegram : {e}")

def get_tickers_from_sheets():
    client = gspread.authorize(creds)
    sheet = client.open_by_key("1-hPKh5yJq6F-eboLbsG8sLxwdesI9LPH2L08emI7i6g")
    data = sheet.sheet1.col_values(2)[1:]  # Colonne B (indexée à 2), sans le header
    return [ticker.strip().upper() for ticker in data if ticker.strip()]

def calculate_ichimoku(df):
    df['Tenkan_sen'] = df['Close'].rolling(window=9).mean()
    df['Kijun_sen'] = df['Close'].rolling(window=26).mean()
    return df

@app.route('/')
def run_analysis():
    try:
        tickers = get_tickers_from_sheets()
        all_signals = []

        for ticker in tickers:
            df = yf.download(ticker, period="3mo", interval="1d", progress=False)
            if df.empty:
                continue
            df.reset_index(inplace=True)
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

            signals = df[df['Signal'] != ""][['Date', 'Close', 'Z_score', 'Signal']].tail(1)
            if not signals.empty:
                signals["Ticker"] = ticker
                all_signals.append(signals)

        if all_signals:
            result = pd.concat(all_signals)
            messages = []
            for _, row in result.iterrows():
                messages.append(
                    f"📌 {row['Ticker']} - {row['Date'].strftime('%Y-%m-%d')}\n"
                    f"💰 {row['Close']:.2f} | Z={row['Z_score']:.2f}\n"
                    f"{row['Signal']}"
                )
            send_telegram_message("📊 Signaux détectés :\n\n" + "\n\n".join(messages))
        else:
            send_telegram_message("✅ Aucune anomalie détectée aujourd’hui.")
        return "✅ Analyse exécutée avec succès"
    except Exception as e:
        send_telegram_message(f"❌ Erreur dans le script : {str(e)}")
        return f"❌ Erreur : {str(e)}"

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8000)
import os
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import requests
from flask import Flask
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# Chargement des variables d'environnement
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
GOOGLE_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, data=data)

def get_tickers_from_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDS, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1-hPKh5yJq6F-eboLbsG8sLxwdesI9LPH2L08emI7i6g/edit").sheet1
    tickers = sheet.col_values(2)[1:]
    return tickers

def calculate_ichimoku(df):
    df['Tenkan_sen'] = df['Close'].rolling(window=9).mean()
    df['Kijun_sen'] = df['Close'].rolling(window=26).mean()
    return df

@app.route('/')
def run_analysis():
    try:
        tickers = get_tickers_from_google_sheets()
        all_signals = []

        for ticker in tickers:
            df = yf.download(ticker, period="3mo")
            df.reset_index(inplace=True)
            df = df.sort_values(by='Date')
            df['Volatility'] = df['Close'].rolling(window=10).std()
            vol_mean = df['Volatility'].mean()
            vol_std = df['Volatility'].std()
            df['Z_score'] = (df['Volatility'] - vol_mean) / vol_std
            df = calculate_ichimoku(df)

            df['Signal'] = np.where(
                (df['Z_score'] > 2) & (df['Close'] > df['Tenkan_sen']) & (df['Close'] > df['Kijun_sen']),
                "ð Signal haussier",
                np.where(
                    (df['Z_score'] > 2) & (df['Close'] < df['Tenkan_sen']) & (df['Close'] < df['Kijun_sen']),
                    "ð Signal baissier",
                    ""
                )
            )

            signals = df[df['Signal'] != ""][['Date', 'Close', 'Z_score', 'Signal']].tail(3)
            signals['Ticker'] = ticker
            all_signals.append(signals)

        final_alerts = pd.concat(all_signals)
        if not final_alerts.empty:
            messages = []
            for _, row in final_alerts.iterrows():
                msg = (
                    f"ð {row['Ticker']} - {row['Date'].strftime('%Y-%m-%d')}
"
                    f"ð° {row['Close']:.2f} | Z={row['Z_score']:.2f}
"
                    f"{row['Signal']}"
                )
                messages.append(msg)
            send_telegram_message("ð Signaux dÃ©tectÃ©s :

" + "

".join(messages))
        else:
            send_telegram_message("â Aucune anomalie dÃ©tectÃ©e aujourdâhui.")
        return "â Analyse exÃ©cutÃ©e avec succÃ¨s"
    except Exception as e:
        send_telegram_message(f"â Erreur : {str(e)}")
        return f"â Erreur dans le script : {str(e)}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)

import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

# Configurações
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BINANCE_API_URL = "https://api.binance.com/api/v3"
SIGNAL_DELAY = timedelta(minutes=15)
RISCO_PERCENTUAL = 0.02

sinais_enviados = {}

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem})

def buscar_pares_usdt():
    try:
        response = requests.get(f"{BINANCE_API_URL}/ticker/price").json()
        return [x["symbol"] for x in response if x["symbol"].endswith("USDT")]
    except Exception as e:
        enviar_telegram(f"Erro ao buscar pares: {e}")
        return []

def obter_dados(par, intervalo="1h"):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={par}&interval={intervalo}&limit=100"
        data = requests.get(url).json()
        df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close", "volume", *range(6)])
        df["close"] = pd.to_numeric(df["close"])
        return df
    except Exception as e:
        print(f"Erro ao buscar dados do par {par}: {e}")
        return None

def analisar():
    pares = buscar_pares_usdt()
    for par in pares:
        df = obter_dados(par)
        if df is None:
            continue

        rsi = RSIIndicator(df["close"]).rsi().iloc[-1]
        if rsi < 30 or rsi > 70:
            mensagem = f"Sinal detectado para {par} - RSI: {rsi:.2f}"
            enviar_telegram(mensagem)

# Bot loop
while True:
    analisar()
    time.sleep(60)
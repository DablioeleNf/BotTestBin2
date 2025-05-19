import requests
import pandas as pd
import time
from datetime import datetime, timedelta
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

# Configurações do Telegram
TELEGRAM_TOKEN = "SEU_TELEGRAM_TOKEN"  # Substitua pelo seu token do bot
TELEGRAM_CHAT_ID = "SEU_TELEGRAM_CHAT_ID"  # Substitua pelo ID do seu chat

# Configurações do bot
BINANCE_API_URL = "https://api.binance.com/api/v3"
SIGNAL_DELAY = timedelta(minutes=15)  # Tempo de espera entre sinais do mesmo par
RISCO_PERCENTUAL = 0.02  # 2% de risco por operação

sinais_enviados = {}  # Armazena o último envio de sinais para cada par

def enviar_telegram(mensagem):
    """
    Envia mensagens para o Telegram.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        response = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": mensagem})
        if response.status_code != 200:
            print(f"Erro ao enviar mensagem no Telegram: {response.text}")
    except Exception as e:
        print(f"Erro ao conectar com Telegram: {e}")

def buscar_pares_usdt():
    """
    Busca todos os pares de negociação disponíveis em USDT.
    """
    try:
        response = requests.get(f"{BINANCE_API_URL}/ticker/price").json()
        return [x["symbol"] for x in response if x["symbol"].endswith("USDT")]
    except Exception as e:
        enviar_telegram(f"Erro ao buscar pares na Binance: {e}")
        return []

def obter_dados(par, intervalo="1h"):
    """
    Obtém os dados de preços históricos para um par de negociação.
    """
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={par}&interval={intervalo}&limit=100"
        data = requests.get(url).json()
        df = pd.DataFrame(data, columns=[
            "time", "open", "high", "low", "close", "volume", *range(6)
        ])
        df["close"] = pd.to_numeric(df["close"])
        return df
    except Exception as e:
        print(f"Erro ao buscar dados do par {par}: {e}")
        return None

def analisar():
    """
    Realiza análise técnica para identificar sinais de compra/venda.
    """
    pares = buscar_pares_usdt()
    if not pares:
        return

    for par in pares:
        agora = datetime.utcnow()
        if par in sinais_enviados and agora - sinais_enviados[par] < SIGNAL_DELAY:
            continue  # Ignorar pares já analisados recentemente

        df = obter_dados(par)
        if df is None:
            continue

        # Análise Técnica
        rsi = RSIIndicator(df["close"]).rsi().iloc[-1]
        close = df["close"].iloc[-1]

        if rsi < 30:
            tipo = "Compra"
            mensagem = f"""✅ Sinal de Compra Detectado!
📊 Par: {par}
💵 Preço Atual: {close}
📈 RSI: {rsi:.2f} (Sobrevendido)
            """
            enviar_telegram(mensagem)
            sinais_enviados[par] = agora

        elif rsi > 70:
            tipo = "Venda"
            mensagem = f"""❌ Sinal de Venda Detectado!
📊 Par: {par}
💵 Preço Atual: {close}
📉 RSI: {rsi:.2f} (Sobrecomprado)
            """
            enviar_telegram(mensagem)
            sinais_enviados[par] = agora

# Bot loop
enviar_telegram("🤖 Bot de sinais iniciado com sucesso!")
while True:
    analisar()
    time.sleep(60)  # Aguarda 60 segundos antes de rodar a análise novamente
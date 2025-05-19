import requests
import pandas as pd
import time
import ta
from datetime import datetime, timedelta
from ta.trend import ADXIndicator

# Configurações do bot
TOKEN = "SEU_TOKEN_TELEGRAM"
CHAT_ID = "SEU_CHAT_ID_TELEGRAM"
CSV_FILE = "sinais_registrados.csv"
RISCO_PERCENTUAL = 0.02  # 2% de risco
TEMPO_ESPERA = timedelta(minutes=10)  # Espera entre sinais do mesmo par

sinais_enviados = {}

# Função para enviar mensagem ao Telegram
def enviar_telegram(mensagem):
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": mensagem}
        )
        if response.status_code != 200:
            print(f"⚠️ Erro ao enviar mensagem ao Telegram: {response.json()}")
    except Exception as e:
        print(f"⚠️ Erro ao enviar mensagem ao Telegram: {e}")

# Função para buscar pares de futuros USDT na Binance
def buscar_pares_futuros_usdt():
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    try:
        response = requests.get(url, timeout=20)
        if response.status_code != 200:
            print(f"⚠️ Erro na API da Binance. Código HTTP: {response.status_code}")
            enviar_telegram(f"❌ Erro na API Binance. Código HTTP: {response.status_code}")
            return []

        data = response.json()
        if "symbols" not in data:
            print("⚠️ Resposta da API Binance inválida. Campo 'symbols' não encontrado.")
            enviar_telegram("❌ Resposta da API Binance inválida. Campo 'symbols' não encontrado.")
            return []

        pares = [s["symbol"] for s in data["symbols"] if s["symbol"].endswith("USDT") and s["contractType"] == "PERPETUAL"]
        if not pares:
            print("⚠️ Nenhum par PERPETUAL USDT encontrado.")
            enviar_telegram("❌ Nenhum par PERPETUAL USDT encontrado na Binance.")
        return pares

    except requests.exceptions.RequestException as e:
        print(f"⚠️ Erro de conexão com a API Binance: {e}")
        enviar_telegram(f"❌ Erro de conexão com a API Binance: {e}")
        return []

    except Exception as e:
        print(f"⚠️ Erro inesperado ao buscar pares: {e}")
        enviar_telegram(f"❌ Erro inesperado ao buscar pares: {e}")
        return []

# Função para obter dados do par específico
def obter_dados(par, intervalo="1h", limite=200):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={par}&interval={intervalo}&limit={limite}"
    try:
        r = requests.get(url, timeout=20).json()
        if isinstance(r, list):
            df = pd.DataFrame(r, columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "num_trades",
                "taker_buy_base", "taker_buy_quote", "ignore"
            ])
            df["close"] = df["close"].astype(float)
            df["open"] = df["open"].astype(float)
            df["high"] = df["high"].astype(float)
            df["low"] = df["low"].astype(float)
            df["volume"] = df["volume"].astype(float)
            return df
    except Exception as e:
        print(f"⚠️ Erro ao obter dados do par {par}: {e}")
        return None

# Função para calcular score baseado em indicadores
def calcular_score(df1h):
    score = 0
    criterios = []
    tipo = "Indefinido"

    # RSI
    rsi = ta.momentum.RSIIndicator(df1h["close"]).rsi().iloc[-1]
    if rsi > 70:
        score += 1
        criterios.append("RSI sobrecomprado")
        tipo = "Venda"
    elif rsi < 30:
        score += 1
        criterios.append("RSI sobrevendido")
        tipo = "Compra"

    # ADX
    adx = ADXIndicator(df1h["high"], df1h["low"], df1h["close"]).adx().iloc[-1]
    if adx > 25:
        score += 1
        criterios.append("Tendência forte detectada (ADX)")

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(df1h["close"])
    close = df1h["close"].iloc[-1]
    if close < bb.bollinger_lband().iloc[-1]:
        score += 1
        criterios.append("Bollinger abaixo da banda inferior")
    elif close > bb.bollinger_hband().iloc[-1]:
        score += 1
        criterios.append("Bollinger acima da banda superior")

    return score, criterios, tipo

# Função para análise de sinais
def analisar():
    pares = buscar_pares_futuros_usdt()
    if not pares:
        enviar_telegram("❌ Erro ao buscar pares futuros na Binance.")
        return

    for par in pares:
        agora = datetime.utcnow()
        if par in sinais_enviados and agora - sinais_enviados[par] < TEMPO_ESPERA:
            continue  # Pular pares que receberam sinal recentemente

        df1h = obter_dados(par, "1h")
        if df1h is None:
            continue

        score, criterios, tipo = calcular_score(df1h)
        if score >= 4:
            close = df1h["close"].iloc[-1]
            suporte = min(df1h["low"].tail(20))
            resistencia = max(df1h["high"].tail(20))

            preco_entrada = round(close, 2)
            stop_loss = round(preco_entrada * (1 - RISCO_PERCENTUAL if tipo == "Compra" else 1 + RISCO_PERCENTUAL), 2)
            tp1 = round(preco_entrada * (1 + RISCO_PERCENTUAL if tipo == "Compra" else 1 - RISCO_PERCENTUAL), 2)
            tp2 = round(preco_entrada * (1 + 2 * RISCO_PERCENTUAL if tipo == "Compra" else 1 - 2 * RISCO_PERCENTUAL), 2)
            tp3 = round(preco_entrada * (1 + 3 * RISCO_PERCENTUAL if tipo == "Compra" else 1 - 3 * RISCO_PERCENTUAL), 2)

            msg = f"""✅ Sinal forte detectado!
📊 Par: {par}
📈 Tipo de sinal: {tipo}
💵 Preço atual: {close}
🎯 Preço de entrada: {preco_entrada}
📈 Take Profit 1: {tp1}
📈 Take Profit 2: {tp2}
📈 Take Profit 3: {tp3}
❌ Stop Loss: {stop_loss}
🧠 Critérios:"""
            for crit in criterios:
                msg += f"\n• {crit}"
            enviar_telegram(msg)
            sinais_enviados[par] = agora

# Início do bot
enviar_telegram("🤖 Bot de sinais cripto iniciado com sucesso!")
while True:
    analisar()
    time.sleep(60)
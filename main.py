import requests
import pandas as pd
import time
import ta
from datetime import datetime, timedelta
from ta.trend import ADXIndicator
from ta.volatility import BollingerBands
from ta.momentum import RSIIndicator

# Configurações do bot
TOKEN = "SEU_TOKEN_TELEGRAM"
CHAT_ID = "SEU_CHAT_ID_TELEGRAM"
RISCO_PERCENTUAL = 0.02  # 2% de risco por operação
TEMPO_ESPERA = timedelta(minutes=10)  # Espera entre sinais do mesmo par

# Dicionário para rastrear sinais enviados
sinais_enviados = {}

# Envia mensagem no Telegram
def enviar_telegram(mensagem):
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": mensagem}
        )
        response.raise_for_status()
    except Exception as e:
        print(f"Erro Telegram: {e}")

# Mensagem inicial para confirmar que o bot iniciou
enviar_telegram("🤖 Bot de sinais iniciado com sucesso! Agora monitorando pares de criptomoedas.")

# Busca todos os pares futuros com USDT na Binance
def buscar_pares_futuros_usdt():
    try:
        url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
        response = requests.get(url, timeout=10).json()
        return [s["symbol"] for s in response["symbols"] if s["symbol"].endswith("USDT") and s["contractType"] == "PERPETUAL"]
    except Exception as e:
        print(f"Erro ao buscar pares: {e}")
        return []

# Obtém os dados de velas do par específico
def obter_dados(par, intervalo="1h", limite=200):
    try:
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={par}&interval={intervalo}&limit={limite}"
        response = requests.get(url, timeout=10).json()
        if isinstance(response, list):
            df = pd.DataFrame(response, columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "num_trades",
                "taker_buy_base", "taker_buy_quote", "ignore"
            ])
            df["close"] = df["close"].astype(float)
            df["open"] = df["open"].astype(float)
            df["high"] = df["high"].astype(float)
            df["low"] = df["low"].astype(float)
            return df
    except Exception as e:
        print(f"Erro ao obter dados do par {par}: {e}")
    return None

# Análise dinâmica com score ajustável
def calcular_score(df):
    score = 0
    criterios = []
    tipo = "Indefinido"

    # RSI
    rsi = RSIIndicator(df["close"]).rsi().iloc[-1]
    if rsi > 70:
        score += 1
        criterios.append("RSI sobrecomprado")
        tipo = "Venda"
    elif rsi < 30:
        score += 1
        criterios.append("RSI sobrevendido")
        tipo = "Compra"

    # ADX
    adx = ADXIndicator(df["high"], df["low"], df["close"]).adx().iloc[-1]
    if adx > 25:
        score += 1
        criterios.append("Tendência forte detectada (ADX)")

    # Bollinger Bands
    bb = BollingerBands(df["close"])
    close = df["close"].iloc[-1]
    if close < bb.bollinger_lband().iloc[-1]:
        score += 1
        criterios.append("Preço abaixo da banda inferior")
    elif close > bb.bollinger_hband().iloc[-1]:
        score += 1
        criterios.append("Preço acima da banda superior")

    # Dinâmica: Ajusta o score mínimo necessário com base no ADX
    score_minimo = 2 if adx < 25 else 3

    return score, criterios, tipo, score_minimo

# Função principal para analisar os sinais
def analisar():
    pares = buscar_pares_futuros_usdt()
    if not pares:
        enviar_telegram("❌ Erro ao buscar pares futuros na Binance.")
        return

    for par in pares:
        agora = datetime.utcnow()
        if par in sinais_enviados and agora - sinais_enviados[par] < TEMPO_ESPERA:
            continue

        df = obter_dados(par)
        if df is None:
            continue

        score, criterios, tipo, score_minimo = calcular_score(df)
        if score >= score_minimo:
            close = df["close"].iloc[-1]
            suporte = df["low"].tail(20).min()
            resistencia = df["high"].tail(20).max()

            preco_entrada = close
            stop_loss = round(preco_entrada * (1 - RISCO_PERCENTUAL), 2)
            tp1 = round(preco_entrada * (1 + RISCO_PERCENTUAL), 2)
            tp2 = round(preco_entrada * (1 + 2 * RISCO_PERCENTUAL), 2)
            tp3 = round(preco_entrada * (1 + 3 * RISCO_PERCENTUAL), 2)

            mensagem = f"""✅ Sinal detectado!
📊 Par: {par}
📈 Score: {score}/{score_minimo}
💵 Preço Atual: {close}
🔹 Preço de Entrada: {preco_entrada}
🔸 Take Profit 1: {tp1}
🔸 Take Profit 2: {tp2}
🔸 Take Profit 3: {tp3}
❌ Stop Loss: {stop_loss}
📋 Critérios utilizados:"""
            for crit in criterios:
                mensagem += f"\n- {crit}"
            enviar_telegram(mensagem)

            sinais_enviados[par] = agora

# Início do bot
while True:
    analisar()
    time.sleep(60)
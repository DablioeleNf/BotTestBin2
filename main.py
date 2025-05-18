import requests
import pandas as pd
import time
import ta
from datetime import datetime
from ta.trend import ADXIndicator, PSARIndicator

# Configurações do bot
TOKEN = "8088057144:AAED-qGi9sXtQ42LK8L1MwwTqZghAE21I3U"
CHAT_ID = "719387436"
CSV_FILE = "sinais_registrados.csv"

def enviar_telegram(mensagem):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": mensagem}
        )
    except Exception as e:
        print(f"Erro Telegram: {e}")

def buscar_pares_futuros_usdt():
    try:
        url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
        r = requests.get(url, timeout=10).json()
        return [s["symbol"] for s in r["symbols"] if s["symbol"].endswith("USDT") and s["contractType"] == "PERPETUAL"]
    except Exception as e:
        print(f"Erro ao buscar pares: {e}")
        return []

def obter_dados(par, intervalo="1h", limite=200):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={par}&interval={intervalo}&limit={limite}"
    try:
        r = requests.get(url, timeout=10).json()
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
        print(f"Erro ao obter dados do par {par}: {e}")
        return None

def detectar_formacoes(df):
    ult = df.iloc[-1]
    corpo = abs(ult["open"] - ult["close"])
    sombra_inf = ult["low"] - min(ult["open"], ult["close"])
    if corpo < sombra_inf and sombra_inf > corpo * 2:
        return True
    return False

def calcular_score(df1h, df5m, df15m, df30m):
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

    # SAR Parabólico
    psar = PSARIndicator(df1h["high"], df1h["low"], df1h["close"]).psar().iloc[-1]
    if df1h["close"].iloc[-1] > psar:
        criterios.append("SAR tendência de alta")
    else:
        criterios.append("SAR tendência de baixa")

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(df1h["close"])
    close = df1h["close"].iloc[-1]
    if close < bb.bollinger_lband().iloc[-1]:
        score += 1
        criterios.append("Bollinger abaixo da banda inferior")
    elif close > bb.bollinger_hband().iloc[-1]:
        score += 1
        criterios.append("Bollinger acima da banda superior")

    # Suporte e Resistência
    suporte = min(df1h["close"].tail(20))
    resistencia = max(df1h["close"].tail(20))
    margem = 0.02  # Alterado de 1% para 2%
    if abs(close - suporte) / close < margem:
        score += 1
        criterios.append("Suporte próximo")
    elif abs(close - resistencia) / close < margem:
        score += 1
        criterios.append("Resistência próxima")

    # Formações gráficas
    if detectar_formacoes(df5m):
        score += 1
        criterios.append("Formação gráfica detectada")

    return score, criterios, tipo

def analisar():
    pares = buscar_pares_futuros_usdt()
    if not pares:
        enviar_telegram("❌ Erro ao buscar pares futuros na Binance.")
        return

    melhor_score = 0
    melhor_par = None
    melhor_criterios = []
    melhor_tipo = "Indefinido"
    melhor_preco = 0.0

    for par in pares:
        df1h = obter_dados(par, "1h")
        df5m = obter_dados(par, "5m")
        df15m = obter_dados(par, "15m")
        df30m = obter_dados(par, "30m")
        if df1h is None or df5m is None or df15m is None or df30m is None:
            continue

        score, criterios, tipo = calcular_score(df1h, df5m, df15m, df30m)
        preco = df1h["close"].iloc[-1]

        if score > melhor_score:
            melhor_score = score
            melhor_par = par
            melhor_criterios = criterios
            melhor_tipo = tipo
            melhor_preco = preco

    if melhor_score >= 4:  # Ajustado para detectar sinais com score >= 4
        enviar_telegram(f"Sinal encontrado no par {melhor_par} com score {melhor_score}!")
    else:
        enviar_telegram("⚠️ Nenhum sinal forte e confiável identificado.")

# === INÍCIO DO BOT ===
enviar_telegram("🤖 Bot de sinais cripto 24h (Futuros USDT) atualizado e iniciado com sucesso!")
while True:
    analisar()
    time.sleep(60)
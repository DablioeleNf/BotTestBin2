import requests
import pandas as pd
import time
import ta
from datetime import datetime
from ta.trend import ADXIndicator, PSARIndicator
from ta.volatility import AverageTrueRange
from ta.momentum import RSIIndicator

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

# === Melhoria 1: Identificação de Contexto de Mercado ===
def identificar_contexto(df):
    atr = AverageTrueRange(df["high"], df["low"], df["close"]).average_true_range().iloc[-1]
    adx = ADXIndicator(df["high"], df["low"], df["close"]).adx().iloc[-1]

    if adx > 25:
        return "Tendência", atr
    elif adx < 20:
        return "Consolidação", atr
    else:
        return "Indefinido", atr

# === Melhoria 2: Detecção de Divergências ===
def detectar_divergencia(df):
    rsi = RSIIndicator(df["close"]).rsi()
    precos = df["close"]

    if (precos.iloc[-2] > precos.iloc[-1]) and (rsi.iloc[-2] < rsi.iloc[-1]):
        return "Divergência de alta detectada (RSI)"
    elif (precos.iloc[-2] < precos.iloc[-1]) and (rsi.iloc[-2] > rsi.iloc[-1]):
        return "Divergência de baixa detectada (RSI)"
    return None

def calcular_score(df1h, df5m, df15m, df30m):
    score = 0
    criterios = []
    tipo = "Indefinido"

    # === Contexto do Mercado ===
    contexto, atr = identificar_contexto(df1h)
    criterios.append(f"Contexto de mercado: {contexto} (ATR: {atr:.2f})")

    # === RSI ===
    rsi = ta.momentum.RSIIndicator(df1h["close"]).rsi().iloc[-1]
    if rsi > 70:
        score += 1
        criterios.append("RSI sobrecomprado")
        tipo = "Venda"
    elif rsi < 30:
        score += 1
        criterios.append("RSI sobrevendido")
        tipo = "Compra"

    # === Divergência ===
    divergencia = detectar_divergencia(df1h)
    if divergencia:
        score += 1
        criterios.append(divergencia)

    # === Outros indicadores (Mantidos como antes) ===
    adx = ADXIndicator(df1h["high"], df1h["low"], df1h["close"]).adx().iloc[-1]
    if adx > 25:
        score += 1
        criterios.append("Tendência forte detectada (ADX)")

    psar = PSARIndicator(df1h["high"], df1h["low"], df1h["close"]).psar().iloc[-1]
    if df1h["close"].iloc[-1] > psar:
        criterios.append("SAR tendência de alta")
    else:
        criterios.append("SAR tendência de baixa")

    return score, criterios, tipo

def analisar():
    pares = buscar_pares_futuros_usdt()
    if not pares:
        enviar_telegram("❌ Erro ao buscar pares futuros na Binance.")
        return

    for par in pares:
        df1h = obter_dados(par, "1h")
        df5m = obter_dados(par, "5m")
        df15m = obter_dados(par, "15m")
        df30m = obter_dados(par, "30m")
        if df1h is None or df5m is None or df15m is None or df30m is None:
            continue

        score, criterios, tipo = calcular_score(df1h, df5m, df15m, df30m)
        if score >= 4:  # Critério para sinal forte
            preco = df1h["close"].iloc[-1]
            registrar_sinal(par, score, criterios, tipo)
            hora = datetime.utcnow().strftime("%H:%M:%S UTC")
            msg = f"""✅ Sinal forte detectado!
🕒 Horário: {hora}
📊 Par: {par}
📈 Score: {score}/6
📌 Tipo de sinal: {tipo}
💵 Preço atual: {preco}
🧠 Critérios:"""
            for crit in criterios:
                msg += f"\n• {crit}"
            enviar_telegram(msg)

# === INÍCIO DO BOT ===
enviar_telegram("🤖 Bot de sinais cripto atualizado e iniciado com melhorias!")
while True:
    analisar()
    time.sleep(60)
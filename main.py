import requests
import pandas as pd
import time
from datetime import datetime
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator, PSARIndicator
from ta.volatility import BollingerBands

# Configurações do bot
TOKEN = "SEU_TOKEN"
CHAT_ID = "SEU_CHAT_ID"
CSV_FILE = "sinais_registrados.csv"

# Função para envio de mensagens no Telegram
def enviar_telegram(mensagem):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": mensagem}
        )
    except Exception as e:
        print(f"Erro ao enviar mensagem no Telegram: {e}")

# Função para calcular o CCI manualmente
def calcular_cci(high, low, close, window=20):
    tp = (high + low + close) / 3  # Preço típico
    sma = tp.rolling(window=window).mean()  # Média móvel simples
    mad = tp.rolling(window=window).apply(lambda x: (x - x.mean()).abs().mean())  # Média de desvio absoluto
    cci = (tp - sma) / (0.015 * mad)
    return cci

# Buscar pares de futuros USDT
def buscar_pares_futuros_usdt():
    try:
        url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
        r = requests.get(url, timeout=10).json()
        return [s["symbol"] for s in r["symbols"] if s["symbol"].endswith("USDT") and s["contractType"] == "PERPETUAL"]
    except Exception as e:
        print(f"Erro ao buscar pares: {e}")
        return []

# Obter dados históricos
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

# Calcular score do par
def calcular_score(df1h, df5m, df15m, df30m):
    score = 0
    criterios = []
    tipo = "Indefinido"

    # RSI
    rsi = RSIIndicator(df1h["close"]).rsi().iloc[-1]
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
    bb = BollingerBands(df1h["close"])
    close = df1h["close"].iloc[-1]
    if close < bb.bollinger_lband().iloc[-1]:
        score += 1
        criterios.append("Bollinger abaixo da banda inferior")
    elif close > bb.bollinger_hband().iloc[-1]:
        score += 1
        criterios.append("Bollinger acima da banda superior")

    # CCI
    cci = calcular_cci(df1h["high"], df1h["low"], df1h["close"]).iloc[-1]
    if cci > 100:
        score += 1
        criterios.append("CCI sobrecomprado")
    elif cci < -100:
        score += 1
        criterios.append("CCI sobrevendido")

    return score, criterios, tipo

# Registrar sinais
def registrar_sinal(par, score, criterios, tipo):
    agora = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"{agora},{par},{score},{tipo},{'|'.join(criterios)}\n"
    with open(CSV_FILE, "a") as f:
        f.write(linha)

# Analisar pares
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
enviar_telegram("🤖 Bot de sinais cripto 24h (Futuros USDT) atualizado e iniciado com sucesso!")
while True:
    analisar()
    time.sleep(60)
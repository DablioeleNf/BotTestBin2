import requests
import pandas as pd
import time
import ta
from datetime import datetime, timedelta
from ta.trend import ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

# Configurações do bot
TOKEN = "SEU_TOKEN_TELEGRAM"
CHAT_ID = "SEU_CHAT_ID_TELEGRAM"
RISCO_PERCENTUAL = 0.02  # 2% de risco
TEMPO_ESPERA = timedelta(minutes=10)  # Espera entre sinais do mesmo par

sinais_enviados = {}

def enviar_telegram(mensagem):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
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
    di_plus = ADXIndicator(df["high"], df["low"], df["close"]).adx_pos().iloc[-1]
    di_minus = ADXIndicator(df["high"], df["low"], df["close"]).adx_neg().iloc[-1]
    if adx > 25:
        score += 1
        criterios.append("Tendência forte (ADX)")
        if di_plus > di_minus:
            tipo = "Compra"
        else:
            tipo = "Venda"

    # Bollinger Bands
    bb = BollingerBands(df["close"])
    close = df["close"].iloc[-1]
    if close < bb.bollinger_lband().iloc[-1]:
        score += 1
        criterios.append("Bollinger abaixo da banda inferior")
    elif close > bb.bollinger_hband().iloc[-1]:
        score += 1
        criterios.append("Bollinger acima da banda superior")

    # Volume
    volume = df["volume"].iloc[-1]
    media_volume = df["volume"].mean()
    if volume > 1.5 * media_volume:
        score += 1
        criterios.append("Volume acima da média")

    return score, criterios, tipo

def calcular_preco_entrada(close, suporte, resistencia, tipo, margem=0.002):
    if tipo == "Compra":
        preco_entrada = max(close, suporte * (1 + margem))
    elif tipo == "Venda":
        preco_entrada = min(close, resistencia * (1 - margem))
    else:
        preco_entrada = close
    return round(preco_entrada, 2)

def calcular_stop_loss(preco_entrada, tipo, risco=RISCO_PERCENTUAL):
    if tipo == "Compra":
        stop_loss = preco_entrada * (1 - risco)
    elif tipo == "Venda":
        stop_loss = preco_entrada * (1 + risco)
    else:
        stop_loss = preco_entrada
    return round(stop_loss, 2)

def calcular_take_profits(preco_entrada, tipo, risco=RISCO_PERCENTUAL):
    if tipo == "Compra":
        tp1 = round(preco_entrada * (1 + risco), 2)
        tp2 = round(preco_entrada * (1 + 2 * risco), 2)
        tp3 = round(preco_entrada * (1 + 3 * risco), 2)
    elif tipo == "Venda":
        tp1 = round(preco_entrada * (1 - risco), 2)
        tp2 = round(preco_entrada * (1 - 2 * risco), 2)
        tp3 = round(preco_entrada * (1 - 3 * risco), 2)
    else:
        tp1, tp2, tp3 = preco_entrada, preco_entrada, preco_entrada
    return tp1, tp2, tp3

def analisar():
    pares = buscar_pares_futuros_usdt()
    if not pares:
        enviar_telegram("❌ Erro ao buscar pares futuros na Binance.")
        return

    for par in pares:
        agora = datetime.utcnow()
        if par in sinais_enviados and agora - sinais_enviados[par] < TEMPO_ESPERA:
            continue  # Pular pares que receberam sinal recentemente

        df = obter_dados(par, "1h")
        if df is None:
            continue

        score, criterios, tipo = calcular_score(df)
        if score >= 4:
            close = df["close"].iloc[-1]
            suporte = min(df["low"].tail(20))
            resistencia = max(df["high"].tail(20))

            preco_entrada = calcular_preco_entrada(close, suporte, resistencia, tipo)
            stop_loss = calcular_stop_loss(preco_entrada, tipo)
            tp1, tp2, tp3 = calcular_take_profits(preco_entrada, tipo)
            alvo_final = tp3

            hora = agora.strftime("%H:%M:%S UTC")
            msg = f"""✅ *Sinal forte detectado!*
🕒 *Horário:* {hora}
📊 *Par:* `{par}`
📈 *Score:* `{score}/6`
📌 *Tipo de sinal:* `{tipo}`
💵 *Preço atual:* `{close:.2f}`
🎯 *Preço de entrada:* `{preco_entrada}`
🎯 *Take Profit 1:* `{tp1}`
🎯 *Take Profit 2:* `{tp2}`
🎯 *Take Profit 3:* `{tp3}`
🎯 *Alvo final:* `{alvo_final}`
❌ *Stop Loss:* `{stop_loss}`
🧠 *Critérios:*"""
            for crit in criterios:
                msg += f"\n• {crit}"

            enviar_telegram(msg)
            sinais_enviados[par] = agora

# === INÍCIO DO BOT ===
enviar_telegram("🤖 *Bot de sinais cripto iniciado!*")
while True:
    analisar()
    time.sleep(60)
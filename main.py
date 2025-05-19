import requests
import pandas as pd
import time
import ta
from datetime import datetime, timedelta
from ta.trend import ADXIndicator, EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

# Configurações do bot
TOKEN = "SEU_TOKEN_TELEGRAM"  # Substitua pelo seu token
CHAT_ID = "SEU_CHAT_ID_TELEGRAM"  # Substitua pelo ID do seu chat
SALDO_TOTAL = 1000.0  # Saldo total em dólares (simulado)
RISCO_PERCENTUAL = 0.02  # Percentual de risco por operação (2%)
TEMPO_ESPERA = timedelta(minutes=10)  # Espera entre sinais do mesmo par

sinais_enviados = {}

# Função para enviar mensagens ao Telegram
def enviar_telegram(mensagem):
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
        )
        if response.status_code == 200:
            print("✅ Mensagem enviada ao Telegram.")
        else:
            print(f"⚠️ Erro ao enviar mensagem. Status code: {response.status_code}")
            print(response.json())
    except Exception as e:
        print(f"Erro Telegram: {e}")

# Buscar pares futuros USDT na Binance
def buscar_pares_futuros_usdt():
    try:
        url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
        r = requests.get(url, timeout=10).json()
        return [s["symbol"] for s in r["symbols"] if s["symbol"].endswith("USDT") and s["contractType"] == "PERPETUAL"]
    except Exception as e:
        print(f"Erro ao buscar pares: {e}")
        return []

# Obter dados do par de moedas
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

# Analisar sinais usando indicadores técnicos
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

    # EMA (Média Móvel Exponencial)
    ema_short = EMAIndicator(df["close"], window=9).ema_indicator().iloc[-1]
    ema_long = EMAIndicator(df["close"], window=21).ema_indicator().iloc[-1]
    if ema_short > ema_long:
        score += 1
        criterios.append("Tendência de alta confirmada (EMA)")
        tipo = "Compra"
    elif ema_short < ema_long:
        score += 1
        criterios.append("Tendência de baixa confirmada (EMA)")
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

# Analisar pares para gerar sinais
def analisar():
    pares = buscar_pares_futuros_usdt()
    if not pares:
        enviar_telegram("❌ Erro ao buscar pares futuros na Binance.")
        return

    for par in pares:
        agora = datetime.utcnow()
        if par in sinais_enviados and agora - sinais_enviados[par] < TEMPO_ESPERA:
            continue

        df = obter_dados(par, "1h")
        if df is None:
            continue

        score, criterios, tipo = calcular_score(df)
        if score >= 4:
            close = df["close"].iloc[-1]
            hora = agora.strftime("%H:%M:%S UTC")
            msg = f"""✅ *Sinal detectado!*
🕒 *Horário:* {hora}
📊 *Par:* `{par}`
📈 *Score:* `{score}/6`
📌 *Tipo de sinal:* `{tipo}`
💵 *Preço atual:* `{close}`
🧠 *Critérios:*"""
            for crit in criterios:
                msg += f"\n• {crit}"

            enviar_telegram(msg)
            sinais_enviados[par] = agora

# === INÍCIO DO BOT ===
enviar_telegram("🤖 *Bot de sinais cripto atualizado e iniciado!*")
while True:
    analisar()
    time.sleep(60)
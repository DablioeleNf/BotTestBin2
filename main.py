import requests
import pandas as pd
import time
import ta
from datetime import datetime, timedelta
from ta.trend import ADXIndicator, PSARIndicator

# Configurações do bot
TOKEN = "8088057144:AAED-qGi9sXtQ42LK8L1MwwTqZghAE21I3U"
CHAT_ID = "719387436"
CSV_FILE = "sinais_registrados.csv"

# Controle para evitar spam por par+timeframe
ultimo_envio = {}

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

def calcular_score(df):
    score = 0
    criterios = []
    tipo = "Indefinido"

    # RSI
    rsi = ta.momentum.RSIIndicator(df["close"]).rsi().iloc[-1]
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

    # SAR Parabólico
    psar = PSARIndicator(df["high"], df["low"], df["close"]).psar().iloc[-1]
    if df["close"].iloc[-1] > psar:
        criterios.append("SAR tendência de alta")
    else:
        criterios.append("SAR tendência de baixa")

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(df["close"])
    close = df["close"].iloc[-1]
    if close < bb.bollinger_lband().iloc[-1]:
        score += 1
        criterios.append("Bollinger abaixo da banda inferior")
    elif close > bb.bollinger_hband().iloc[-1]:
        score += 1
        criterios.append("Bollinger acima da banda superior")

    # Suporte e Resistência
    suporte = min(df["close"].tail(20))
    resistencia = max(df["close"].tail(20))
    margem = 0.02  # 2% de margem
    if abs(close - suporte) / close < margem:
        score += 1
        criterios.append("Suporte próximo")
    elif abs(close - resistencia) / close < margem:
        score += 1
        criterios.append("Resistência próxima")

    return score, criterios, tipo

def registrar_sinal(par, score, criterios, tipo, timeframe):
    agora = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"{agora},{par},{score},{tipo},{timeframe},{'|'.join(criterios)}\n"
    with open(CSV_FILE, "a") as f:
        f.write(linha)

def analisar():
    pares = buscar_pares_futuros_usdt()
    if not pares:
        enviar_telegram("❌ Erro ao buscar pares futuros na Binance.")
        return

    timeframes = ["15m", "30m", "1h"]
    agora = datetime.utcnow()

    for par in pares:
        for tf in timeframes:
            key = f"{par}_{tf}"
            # Evita spam do par+timeframe em 10 min
            if key in ultimo_envio and agora - ultimo_envio[key] < timedelta(minutes=10):
                continue

            df = obter_dados(par, tf)
            if df is None:
                continue

            score, criterios, tipo = calcular_score(df)
            if score >= 4:
                preco_atual = df["close"].iloc[-1]
                ema20 = ta.trend.EMAIndicator(df["close"], window=20).ema_indicator().iloc[-1]
                preco_entrada = ema20

                margem_sl = 0.015
                margem_tp1 = 0.015
                margem_tp2 = 0.03
                margem_tp3 = 0.05
                margem_tp4 = 0.08

                if tipo == "Compra":
                    stop_loss = preco_entrada * (1 - margem_sl)
                    tp1 = preco_entrada * (1 + margem_tp1)
                    tp2 = preco_entrada * (1 + margem_tp2)
                    tp3 = preco_entrada * (1 + margem_tp3)
                    tp4 = preco_entrada * (1 + margem_tp4)
                elif tipo == "Venda":
                    stop_loss = preco_entrada * (1 + margem_sl)
                    tp1 = preco_entrada * (1 - margem_tp1)
                    tp2 = preco_entrada * (1 - margem_tp2)
                    tp3 = preco_entrada * (1 - margem_tp3)
                    tp4 = preco_entrada * (1 - margem_tp4)
                else:
                    continue

                duracao = f"Entrada no timeframe {tf}, curto prazo (até 24h)"

                registrar_sinal(par, score, criterios, tipo, tf)
                ultimo_envio[key] = agora

                hora = agora.strftime("%H:%M:%S UTC")
                msg = f"""✅ Sinal forte detectado!
🕒 Horário: {hora}
📊 Par: {par}
⏰ Timeframe: {tf}
📈 Score: {score}/6
📌 Tipo de sinal: {tipo}
💰 Preço Atual: {preco_atual:.4f}
🎯 Preço de Entrada (EMA20 {tf}): {preco_entrada:.4f}
⛔ Stop Loss: {stop_loss:.4f}
🎯 Take Profit 1: {tp1:.4f}
🎯 Take Profit 2: {tp2:.4f}
🎯 Take Profit 3: {tp3:.4f}
🎯 Alvo Final (TP4): {tp4:.4f}
⏳ Duração estimada: {duracao}
🧠 Critérios:"""
                for crit in criterios:
                    msg += f"\n• {crit}"
                enviar_telegram(msg)

# === INÍCIO DO BOT ===
enviar_telegram("🤖 Bot de sinais cripto 24h (Futuros USDT) iniciado com múltiplos timeframes!")
while True:
    analisar()
    time.sleep(60)
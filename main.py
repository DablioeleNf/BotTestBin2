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
    margem = 0.02  # 2% de margem
    if abs(close - suporte) / close < margem:
        score += 1
        criterios.append("Suporte próximo")
    elif abs(close - resistencia) / close < margem:
        score += 1
        criterios.append("Resistência próxima")

    return score, criterios, tipo, suporte, resistencia

def gerar_precos_entrada_stop_tp(tipo, preco_atual, suporte, resistencia):
    # Define preço de entrada, stop loss e TPs baseados em tipo e níveis de suporte/resistência
    if tipo == "Compra":
        preco_entrada = preco_atual
        stop_loss = suporte * 0.995  # Stop loss ligeiramente abaixo do suporte
        range_tp = resistencia - preco_entrada
        if range_tp <= 0:
            return None, None, None, None, None
        tp1 = preco_entrada + 0.3 * range_tp
        tp2 = preco_entrada + 0.6 * range_tp
        tp3 = preco_entrada + 1.0 * range_tp
    elif tipo == "Venda":
        preco_entrada = preco_atual
        stop_loss = resistencia * 1.005  # Stop loss ligeiramente acima da resistência
        range_tp = preco_entrada - suporte
        if range_tp <= 0:
            return None, None, None, None, None
        tp1 = preco_entrada - 0.3 * range_tp
        tp2 = preco_entrada - 0.6 * range_tp
        tp3 = preco_entrada - 1.0 * range_tp
    else:
        return None, None, None, None, None

    return preco_entrada, stop_loss, tp1, tp2, tp3

def estimar_duracao_entrada():
    # Pode ser aprimorada com análise de volatilidade ou volume, aqui é um placeholder
    return "1-4 horas"

def registrar_sinal(par, score, criterios, tipo, preco_entrada, stop_loss, tp1, tp2, tp3):
    agora = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"{agora},{par},{score},{tipo},{preco_entrada},{stop_loss},{tp1},{tp2},{tp3},{'|'.join(criterios)}\n"
    with open(CSV_FILE, "a") as f:
        f.write(linha)

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

        score, criterios, tipo, suporte, resistencia = calcular_score(df1h, df5m, df15m, df30m)
        if score >= 4:  # Critério para sinal forte
            preco_entrada, stop_loss, tp1, tp2, tp3 = gerar_precos_entrada_stop_tp(tipo, df1h["close"].iloc[-1], suporte, resistencia)
            if None in (preco_entrada, stop_loss, tp1, tp2, tp3):
                continue

            duracao = estimar_duracao_entrada()
            registrar_sinal(par, score, criterios, tipo, preco_entrada, stop_loss, tp1, tp2, tp3)
            hora = datetime.utcnow().strftime("%H:%M:%S UTC")

            msg = f"""✅ Sinal forte detectado!
🕒 Horário: {hora}
📊 Par: {par}
📈 Score: {score:.2f}
📌 Tipo de sinal: {tipo}
💵 Preço de entrada: {preco_entrada:.4f}
⛔ Stop Loss: {stop_loss:.4f}
🎯 Take Profit 1: {tp1:.4f}
🎯 Take Profit 2: {tp2:.4f}
🎯 Take Profit 3: {tp3:.4f}
⏳ Duração estimada: {duracao}
🧠 Critérios:"""
            for crit in criterios:
                msg += f"\n• {crit}"
            enviar_telegram(msg)

# === INÍCIO DO BOT ===
enviar_telegram("🤖 Bot de sinais cripto 24h (Futuros USDT) atualizado e iniciado com sucesso!")
while True:
    analisar()
    time.sleep(60)
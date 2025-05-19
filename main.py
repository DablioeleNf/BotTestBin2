import requests
import pandas as pd
import time
import ta
from datetime import datetime
from ta.trend import ADXIndicator, PSARIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
import logging

# Configurações do bot
TOKEN = "8088057144:AAED-qGi9sXtQ42LK8L1MwwTqZghAE21I3U"
CHAT_ID = "719387436"
CSV_FILE = "sinais_registrados.csv"
LOG_FILE = "bot_logs.log"

# Configuração de logging
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

def enviar_telegram(mensagem):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": mensagem},
            timeout=10
        )
    except Exception as e:
        logging.error(f"Erro Telegram: {e}")

def buscar_pares_futuros_usdt():
    try:
        url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
        r = requests.get(url, timeout=10).json()
        return [s["symbol"] for s in r["symbols"] if s["symbol"].endswith("USDT") and s["contractType"] == "PERPETUAL"]
    except Exception as e:
        logging.error(f"Erro ao buscar pares: {e}")
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
        logging.error(f"Erro ao obter dados do par {par}: {e}")
        return None

def calcular_score(df1h, df5m, df15m, df30m):
    score = 0
    criterios = []
    tipo = "Indefinido"
    close = df1h["close"].iloc[-1]

    # RSI
    rsi = RSIIndicator(df1h["close"]).rsi().iloc[-1]
    if rsi > 70:
        score += 0.3
        criterios.append("RSI sobrecomprado")
        tipo = "Venda"
    elif rsi < 30:
        score += 0.3
        criterios.append("RSI sobrevendido")
        tipo = "Compra"

    # ADX
    adx = ADXIndicator(df1h["high"], df1h["low"], df1h["close"]).adx().iloc[-1]
    if adx > 25:
        score += 0.4
        criterios.append("Tendência forte detectada (ADX)")

    # SAR Parabólico
    psar = PSARIndicator(df1h["high"], df1h["low"], df1h["close"]).psar().iloc[-1]
    if close > psar:
        criterios.append("SAR tendência de alta")
    else:
        criterios.append("SAR tendência de baixa")

    # Bollinger Bands
    bb = BollingerBands(df1h["close"])
    if close < bb.bollinger_lband().iloc[-1]:
        score += 0.2
        criterios.append("Bollinger abaixo da banda inferior")
    elif close > bb.bollinger_hband().iloc[-1]:
        score += 0.2
        criterios.append("Bollinger acima da banda superior")

    # MACD
    macd = MACD(df1h["close"]).macd_diff().iloc[-1]
    if macd > 0:
        score += 0.3
        criterios.append("MACD indicando alta")
    elif macd < 0:
        score += 0.3
        criterios.append("MACD indicando baixa")

    # Suporte e Resistência
    suporte = min(df1h["close"].tail(20))
    resistencia = max(df1h["close"].tail(20))
    margem = 0.02
    if abs(close - suporte) / close < margem:
        score += 0.2
        criterios.append("Suporte próximo")
    elif abs(close - resistencia) / close < margem:
        score += 0.2
        criterios.append("Resistência próxima")

    return score, criterios, tipo, suporte, resistencia

def calcular_risco_reward(preco_entrada, stop_loss, alvo):
    risco = abs(preco_entrada - stop_loss)
    recompensa = abs(alvo - preco_entrada)
    if risco == 0:
        return 0
    return recompensa / risco

def gerar_precos_entrada_stop_tp(tipo, close, suporte, resistencia):
    margem_sl = 0.01  # 1% para stop loss
    margem_tp = 0.03  # 3% entre tps

    if tipo == "Compra":
        preco_entrada = close
        stop_loss = suporte * (1 - margem_sl)
        alvo = resistencia
        # 3 TPs escalonados entre entrada e alvo
        tp1 = preco_entrada + (alvo - preco_entrada) * 0.33
        tp2 = preco_entrada + (alvo - preco_entrada) * 0.66
        tp3 = alvo
    elif tipo == "Venda":
        preco_entrada = close
        stop_loss = resistencia * (1 + margem_sl)
        alvo = suporte
        # 3 TPs escalonados entre entrada e alvo (descendo)
        tp1 = preco_entrada - (preco_entrada - alvo) * 0.33
        tp2 = preco_entrada - (preco_entrada - alvo) * 0.66
        tp3 = alvo
    else:
        return None, None, None, None, None

    return preco_entrada, stop_loss, tp1, tp2, tp3

def estimar_duracao_entrada():
    # Estimativa simples: operação no timeframe 1h pode durar até 1 dia (24h)
    return "Até 24 horas (timeframe 1h)"

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
        if score >= 1.0:  # Critério para sinal forte
            preco_entrada, stop_loss, tp1, tp2, tp3 = gerar_precos_entrada_stop_tp(tipo, df1h["close"].iloc[-1], suporte, resistencia)
            if None in (preco_entrada, stop_loss, tp1, tp2, tp3):
                continue

            duracao = estimar_duracao_entrada()
            registrar_sinal(par, score, criterios, tipo, preco_entrada, stop_loss, tp1, tp2, tp3)
            hora = datetime.utcnow().strftime("%H:%M:%S UTC")

            msg = f"""✅ Sinal forte detectado!
🕒 Horário: {hora}
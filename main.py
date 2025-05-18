import requests
import pandas as pd
import time
import ta
from datetime import datetime
from ta.trend import MACD
from ta.volatility import AverageTrueRange

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

def calcular_score(df1h, df5m, df4h):
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

    # MACD
    macd = MACD(df1h["close"]).macd_diff().iloc[-1]
    if macd > 0:
        score += 1
        criterios.append("MACD positivo (tendência de alta)")
    else:
        criterios.append("MACD negativo (tendência de baixa)")

    # ATR (volatilidade dinâmica)
    atr = AverageTrueRange(df1h["high"], df1h["low"], df1h["close"]).average_true_range().iloc[-1]
    criterios.append(f"ATR (volatilidade): {atr:.4f}")

    # Volume
    volume_medio = df1h["volume"].mean()
    if df1h["volume"].iloc[-1] > volume_medio:
        score += 1
        criterios.append("Volume acima da média")
    else:
        criterios.append("Volume abaixo da média")

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(df1h["close"])
    close = df1h["close"].iloc[-1]
    if close < bb.bollinger_lband().iloc[-1]:
        score += 1
        criterios.append("Bollinger abaixo da banda inferior")
    elif close > bb.bollinger_hband().iloc[-1]:
        score += 1
        criterios.append("Bollinger acima da banda superior")

    # Confirmação no timeframe de 4h
    rsi_4h = ta.momentum.RSIIndicator(df4h["close"]).rsi().iloc[-1]
    if (tipo == "Compra" and rsi_4h < 50) or (tipo == "Venda" and rsi_4h > 50):
        score += 1
        criterios.append(f"Tendência consistente no gráfico de 4h ({tipo})")

    return score, criterios, tipo, atr

def registrar_sinal(par, score, criterios, tipo, confiavel):
    agora = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"{agora},{par},{score},{tipo},{'|'.join(criterios)},{'Sim' if confiavel else 'Não'}\n"
    with open(CSV_FILE, "a") as f:
        f.write(linha)

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
    melhor_atr = 0.0

    for par in pares:
        df1h = obter_dados(par, "1h")
        df5m = obter_dados(par, "5m")
        df4h = obter_dados(par, "4h")
        if df1h is None or df5m is None or df4h is None:
            continue

        score, criterios, tipo, atr = calcular_score(df1h, df5m, df4h)
        preco = df1h["close"].iloc[-1]
        registrar_sinal(par, score, criterios, tipo, score >= 5)

        if score > melhor_score:
            melhor_score = score
            melhor_par = par
            melhor_criterios = criterios
            melhor_tipo = tipo
            melhor_preco = preco
            melhor_atr = atr

    if melhor_score >= 5 and melhor_tipo in ["Compra", "Venda"]:
        entrada = melhor_preco
        tp1 = round(entrada + (melhor_atr * 1.5) if melhor_tipo == "Compra" else entrada - (melhor_atr * 1.5), 4)
        tp2 = round(entrada + (melhor_atr * 2.0) if melhor_tipo == "Compra" else entrada - (melhor_atr * 2.0), 4)
        sl = round(entrada - (melhor_atr * 1.5) if melhor_tipo == "Compra" else entrada + (melhor_atr * 1.5), 4)
        hora = datetime.utcnow().strftime("%H:%M:%S UTC")

        msg = f"""✅ Sinal forte detectado!
🕒 Horário: {hora}
📊 Par: {melhor_par}
📈 Score: {melhor_score}/6
📌 Tipo de sinal: {melhor_tipo}
💵 Entrada: {entrada}
🎯 TP1: {tp1}
🎯 TP2: {tp2}
❌ Stop Loss: {sl}
🧠 Critérios:"""
        for crit in melhor_criterios:
            msg += f"\n• {crit}"
        enviar_telegram(msg)
    else:
        enviar_telegram("⚠️ Nenhum sinal forte e confiável identificado.")

# === INÍCIO DO BOT ===
enviar_telegram("🤖 Bot de sinais cripto atualizado iniciado com sucesso!")
while True:
    analisar()
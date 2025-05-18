import requests
import pandas as pd
import time
import ta
from datetime import datetime

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

def calcular_score(df1h, df5m):
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

    # EMA
    ema = ta.trend.EMAIndicator(df1h["close"], window=21).ema_indicator().iloc[-1]
    if df1h["close"].iloc[-1] > ema:
        score += 1
        criterios.append("EMA tendência de alta")
    else:
        criterios.append("EMA tendência de baixa")

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
    if abs(close - suporte) / close < 0.01:
        score += 1
        criterios.append("Suporte próximo")
    elif abs(close - resistencia) / close < 0.01:
        score += 1
        criterios.append("Resistência próxima")

    # Formações gráficas
    if detectar_formacoes(df5m):
        score += 1
        criterios.append("Formação gráfica detectada")

    return score, criterios, tipo

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

    for par in pares:
        df1h = obter_dados(par, "1h")
        df5m = obter_dados(par, "5m")
        if df1h is None or df5m is None:
            continue

        score, criterios, tipo = calcular_score(df1h, df5m)
        preco = df1h["close"].iloc[-1]
        registrar_sinal(par, score, criterios, tipo, score >= 5)

        if score > melhor_score:
            melhor_score = score
            melhor_par = par
            melhor_criterios = criterios
            melhor_tipo = tipo
            melhor_preco = preco

    if melhor_score >= 5 and melhor_tipo in ["Compra", "Venda"]:
        entrada = melhor_preco
        tp1 = round(entrada * (1.01 if melhor_tipo == "Compra" else 0.99), 4)
        tp2 = round(entrada * (1.02 if melhor_tipo == "Compra" else 0.98), 4)
        tp3 = round(entrada * (1.03 if melhor_tipo == "Compra" else 0.97), 4)
        sl = round(entrada * (0.985 if melhor_tipo == "Compra" else 1.015), 4)
        hora = datetime.utcnow().strftime("%H:%M:%S UTC")

        msg = f"""✅ Sinal forte detectado!
🕒 Horário: {hora}
📊 Par: {melhor_par}
📈 Score: {melhor_score}/6
📌 Tipo de sinal: {melhor_tipo}
💵 Entrada: {entrada}
🎯 TP1 (50%): {tp1}
🎯 TP2 (30%): {tp2}
🎯 TP3 (20%): {tp3}
❌ Stop Loss: {sl}
🧠 Critérios:"""
        for crit in melhor_criterios:
            msg += f"\n• {crit}"
        enviar_telegram(msg)
    else:
        enviar_telegram("⚠️ Nenhum sinal forte e confiável identificado.")

# === INÍCIO DO BOT ===
enviar_telegram("🤖 Bot de sinais cripto 24h (Futuros USDT) iniciado com sucesso!")
while True:
    analisar()
    time.sleep(20 * 60)  # Executa a cada 20 minutos

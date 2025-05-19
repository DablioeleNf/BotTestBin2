import requests
import pandas as pd
import time
import ta
from datetime import datetime, timedelta

# Configurações do bot
TOKEN = "8088057144:AAED-qGi9sXtQ42LK8L1MwwTqZghAE21I3U"
CHAT_ID = "719387436"
CSV_FILE = "sinais_registrados.csv"
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

def calcular_suporte_resistencia(df):
    """Calcula suporte e resistência usando as máximas e mínimas recentes."""
    suporte = df["low"].rolling(window=20).min().iloc[-1]
    resistencia = df["high"].rolling(window=20).max().iloc[-1]
    return suporte, resistencia

def calcular_score(df):
    score = 0
    criterios = []
    tipo = "Indefinido"

    # MACD
    macd = ta.trend.MACD(df["close"]).macd_diff().iloc[-1]
    if macd > 0:
        score += 1
        criterios.append("MACD sinal positivo")
        tipo = "Compra"
    elif macd < 0:
        score += 1
        criterios.append("MACD sinal negativo")
        tipo = "Venda"

    # ATR
    atr = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"]).average_true_range().iloc[-1]

    # Suporte e Resistência
    suporte, resistencia = calcular_suporte_resistencia(df)
    preco_atual = df["close"].iloc[-1]
    if preco_atual < suporte * 1.02:
        score += 1
        criterios.append("Preço próximo ao suporte")
    elif preco_atual > resistencia * 0.98:
        score += 1
        criterios.append("Preço próximo à resistência")

    return score, criterios, tipo, suporte, resistencia, atr

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
            if key in ultimo_envio and agora - ultimo_envio[key] < timedelta(minutes=10):
                continue

            df = obter_dados(par, tf)
            if df is None:
                continue

            score, criterios, tipo, suporte, resistencia, atr = calcular_score(df)
            if score >= 4:
                preco_atual = df["close"].iloc[-1]

                margem_sl = atr
                margem_tp1 = atr * 1.5
                margem_tp2 = atr * 3
                margem_tp3 = atr * 5

                if tipo == "Compra":
                    stop_loss = preco_atual - margem_sl
                    tp1 = preco_atual + margem_tp1
                    tp2 = preco_atual + margem_tp2
                    tp3 = preco_atual + margem_tp3
                elif tipo == "Venda":
                    stop_loss = preco_atual + margem_sl
                    tp1 = preco_atual - margem_tp1
                    tp2 = preco_atual - margem_tp2
                    tp3 = preco_atual - margem_tp3
                else:
                    continue

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
🎯 Suporte: {suporte:.4f}
🎯 Resistência: {resistencia:.4f}
⛔ Stop Loss: {stop_loss:.4f}
🎯 Take Profit 1: {tp1:.4f}
🎯 Take Profit 2: {tp2:.4f}
🎯 Take Profit 3: {tp3:.4f}
🧠 Critérios:"""
                for crit in criterios:
                    msg += f"\n• {crit}"
                enviar_telegram(msg)

# === INÍCIO DO BOT ===
enviar_telegram("🤖 Bot de sinais cripto atualizado com novos indicadores e suporte/resistência dinâmicos!")
while True:
    analisar()
    time.sleep(60)
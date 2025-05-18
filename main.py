import requests
import pandas as pd
import time
from datetime import datetime, timedelta
from ta.trend import ADXIndicator, PSARIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

# Configurações do bot
TOKEN = "8088057144:AAED-qGi9sXtQ42LK8L1MwwTqZghAE21I3U"
CHAT_ID = "719387436"
CSV_FILE = "sinais_registrados.csv"
TEMPO_MINIMO = 10  # Tempo mínimo em minutos entre sinais do mesmo par

# Endpoints das exchanges
ENDPOINTS = {
    "binance": "https://fapi.binance.com",
    "bybit": "https://api.bybit.com"
}

# Dicionário para controlar o tempo do último sinal enviado para cada par
ultimo_sinal = {}

def enviar_telegram(mensagem):
    """Envia uma mensagem para o Telegram."""
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": mensagem}
        )
    except Exception as e:
        print(f"Erro Telegram: {e}")

def buscar_pares(exchange):
    """Busca os pares USDT disponíveis em cada exchange."""
    try:
        if exchange == "binance":
            url = f"{ENDPOINTS['binance']}/fapi/v1/exchangeInfo"
            r = requests.get(url, timeout=10).json()
            return [s["symbol"] for s in r["symbols"] if s["symbol"].endswith("USDT")]
        elif exchange == "bybit":
            url = f"{ENDPOINTS['bybit']}/v5/market/symbols"
            r = requests.get(url, timeout=10).json()
            return [s["symbol"] for s in r["result"]["list"] if s["symbol"].endswith("USDT")]
    except Exception as e:
        print(f"Erro ao buscar pares na {exchange}: {e}")
        return []

def obter_dados(exchange, par, intervalo="1h", limite=200):
    """Obtém os dados de candle para o par especificado."""
    try:
        if exchange == "binance":
            url = f"{ENDPOINTS['binance']}/fapi/v1/klines?symbol={par}&interval={intervalo}&limit={limite}"
        elif exchange == "bybit":
            intervalo_bybit = {"1h": 60, "5m": 5, "15m": 15, "30m": 30}[intervalo]
            url = f"{ENDPOINTS['bybit']}/v5/market/kline?symbol={par}&interval={intervalo_bybit}&limit={limite}"
        
        r = requests.get(url, timeout=10).json()
        data = r if isinstance(r, list) else r.get("result", {}).get("list", [])
        if data:
            df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["close"] = df["close"].astype(float)
            df["open"] = df["open"].astype(float)
            df["high"] = df["high"].astype(float)
            df["low"] = df["low"].astype(float)
            df["volume"] = df["volume"].astype(float)
            return df
    except Exception as e:
        print(f"Erro ao obter dados do par {par} na {exchange}: {e}")
        return None

def calcular_score(df1h):
    """Calcula o score com base em indicadores técnicos."""
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

    return score, criterios, tipo

def registrar_sinal(exchange, par, score, criterios, tipo):
    """Registra os sinais no arquivo CSV."""
    agora = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"{agora},{exchange},{par},{score},{tipo},{'|'.join(criterios)}\n"
    with open(CSV_FILE, "a") as f:
        f.write(linha)

def analisar():
    """Analisa os pares nas exchanges e gera sinais."""
    for exchange in ["binance", "bybit"]:
        pares = buscar_pares(exchange)
        if not pares:
            enviar_telegram(f"❌ Erro ao buscar pares na {exchange.capitalize()}.")
            continue

        for par in pares:
            agora = datetime.utcnow()
            if par in ultimo_sinal and agora - ultimo_sinal[par] < timedelta(minutes=TEMPO_MINIMO):
                continue

            df1h = obter_dados(exchange, par, "1h")
            if df1h is None:
                continue

            score, criterios, tipo = calcular_score(df1h)
            if score >= 4:  # Critério para sinal forte
                preco = df1h["close"].iloc[-1]
                registrar_sinal(exchange, par, score, criterios, tipo)
                hora = agora.strftime("%H:%M:%S UTC")
                msg = f"""✅ Sinal forte detectado!
🕒 Horário: {hora}
📊 Exchange: {exchange.capitalize()}
📊 Par: {par}
📈 Score: {score}/6
📌 Tipo de sinal: {tipo}
💵 Preço atual: {preco}
🧠 Critérios:"""
                for crit in criterios:
                    msg += f"\n• {crit}"
                enviar_telegram(msg)
                ultimo_sinal[par] = agora

# === INÍCIO DO BOT ===
enviar_telegram("🤖 Bot de sinais cripto 24h (Binance e Bybit) atualizado e iniciado com sucesso!")
while True:
    analisar()
    time.sleep(60)
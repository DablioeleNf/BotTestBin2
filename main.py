import os
import time
import logging
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from ta.trend import ADXIndicator, PSARIndicator
from ta.volatility import BollingerBands
from ta.momentum import RSIIndicator

# === Carrega variáveis do arquivo .env ===
load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CSV_FILE = "sinais_registrados.csv"
INTERVALO_ANALISE = int(os.getenv("INTERVALO_ANALISE", 300))  # Padrão: 5 minutos

# === Configuração de Logs ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def enviar_telegram(mensagem):
    """Envia mensagens para o Telegram"""
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": mensagem}
        )
        logging.info("Mensagem enviada com sucesso!")
    except Exception as e:
        logging.error(f"Erro ao enviar mensagem no Telegram: {e}")

def buscar_pares_futuros_usdt():
    """Busca os pares de Futuros USDT na Binance"""
    try:
        url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
        r = requests.get(url, timeout=10).json()
        return [s["symbol"] for s in r["symbols"] if s["symbol"].endswith("USDT") and s["contractType"] == "PERPETUAL"]
    except Exception as e:
        logging.error(f"Erro ao buscar pares: {e}")
        return []

def obter_dados(par, intervalo="1h", limite=200):
    """Obtém os dados históricos de um par específico"""
    try:
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={par}&interval={intervalo}&limit={limite}"
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

def calcular_score(df1h):
    """Calcula o score de um par baseado em indicadores técnicos"""
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

    return score, criterios, tipo

def registrar_sinal(par, score, criterios, tipo):
    """Registra os sinais em um arquivo CSV"""
    agora = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"{agora},{par},{score},{tipo},{'|'.join(criterios)}\n"
    with open(CSV_FILE, "a") as f:
        f.write(linha)

def limpar_csv(dias=30):
    """Limpa registros antigos do CSV"""
    if not os.path.exists(CSV_FILE):
        return

    df = pd.read_csv(CSV_FILE, names=["timestamp", "par", "score", "tipo", "criterios"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    limite = datetime.utcnow() - pd.Timedelta(days=dias)
    df = df[df["timestamp"] > limite]
    df.to_csv(CSV_FILE, index=False, header=False)

def analisar():
    """Analisa os pares e envia sinais fortes para o Telegram"""
    pares = buscar_pares_futuros_usdt()
    if not pares:
        enviar_telegram("❌ Erro ao buscar pares futuros na Binance.")
        return

    for par in pares:
        df1h = obter_dados(par, "1h")
        if df1h is None:
            continue

        score, criterios, tipo = calcular_score(df1h)
        if score >= 3:  # Critério para sinal forte
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

        time.sleep(5)  # Pausa entre os pares

# === INÍCIO DO BOT ===
if __name__ == "__main__":
    enviar_telegram("🤖 Bot de sinais cripto 24h iniciado com sucesso!")
    while True:
        limpar_csv()  # Limpa registros antigos
        analisar()
        time.sleep(INTERVALO_ANALISE)
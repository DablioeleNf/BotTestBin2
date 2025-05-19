import asyncio
import aiohttp
import pandas as pd
import ta
from datetime import datetime
from ta.trend import ADXIndicator, PSARIndicator
from ta.volatility import BollingerBands
from ta.momentum import RSIIndicator

# Configurações do bot
TOKEN = "8088057144:AAED-qGi9sXtQ42LK8L1MwwTqZghAE21I3U"
CHAT_ID = "719387436"
CSV_FILE = "sinais_registrados.csv"

# Função para enviar mensagem pelo Telegram
async def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(url, data={"chat_id": CHAT_ID, "text": mensagem})
    except Exception as e:
        print(f"Erro ao enviar mensagem para o Telegram: {e}")

# Função para buscar pares futuros USDT na Binance
async def buscar_pares_futuros_usdt():
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                data = await response.json()
                return [s["symbol"] for s in data["symbols"] if s["symbol"].endswith("USDT") and s["contractType"] == "PERPETUAL"]
    except Exception as e:
        print(f"Erro ao buscar pares: {e}")
        return []

# Função para obter dados do par
async def obter_dados(par, intervalo="1h", limite=200):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={par}&interval={intervalo}&limit={limite}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                data = await response.json()
                if isinstance(data, list):
                    df = pd.DataFrame(data, columns=[
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

# Função para calcular score
def calcular_score(df1h, df5m, df15m, df30m):
    score = 0
    criterios = []
    tipo = "Indefinido"
    close = df1h["close"].iloc[-1]

    # RSI Multi-timeframe
    rsi1h = RSIIndicator(df1h["close"]).rsi().iloc[-1]
    rsi5m = RSIIndicator(df5m["close"]).rsi().iloc[-1]
    if rsi1h < 30 and rsi5m < 30:
        score += 1
        criterios.append("RSI multi-timeframe indicando sobrevendido")
        tipo = "Compra"
    elif rsi1h > 70 and rsi5m > 70:
        score += 1
        criterios.append("RSI multi-timeframe indicando sobrecomprado")
        tipo = "Venda"

    # Bollinger Bands
    bb = BollingerBands(df1h["close"])
    if close < bb.bollinger_lband().iloc[-1]:
        score += 1
        criterios.append("Preço abaixo da banda inferior (Bollinger)")
    elif close > bb.bollinger_hband().iloc[-1]:
        score += 1
        criterios.append("Preço acima da banda superior (Bollinger)")

    # Suporte e resistência
    suporte = min(df1h["close"].tail(20))
    resistencia = max(df1h["close"].tail(20))
    margem = 0.02
    if abs(close - suporte) / close < margem:
        score += 1
        criterios.append("Preço próximo ao suporte")
    elif abs(close - resistencia) / close < margem:
        score += 1
        criterios.append("Preço próximo à resistência")

    return score, criterios, tipo

# Função para registrar sinais
def registrar_sinal(par, score, criterios, tipo):
    agora = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"{agora},{par},{score},{tipo},{'|'.join(criterios)}\n"
    with open(CSV_FILE, "a") as f:
        f.write(linha)

# Função principal de análise
async def analisar():
    pares = await buscar_pares_futuros_usdt()
    if not pares:
        await enviar_telegram("❌ Erro ao buscar pares futuros na Binance.")
        return

    tasks = []
    for par in pares:
        tasks.append(obter_dados(par, "1h"))
        tasks.append(obter_dados(par, "5m"))
        tasks.append(obter_dados(par, "15m"))
        tasks.append(obter_dados(par, "30m"))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for i, par in enumerate(pares):
        df1h, df5m, df15m, df30m = results[i * 4:i * 4 + 4]
        if None in (df1h, df5m, df15m, df30m):
            continue

        score, criterios, tipo = calcular_score(df1h, df5m, df15m, df30m)
        if score >= 3:
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
            await enviar_telegram(msg)

# Loop principal
async def main():
    await enviar_telegram("🤖 Bot de sinais cripto atualizado e iniciado com sucesso!")
    while True:
        await analisar()
        await asyncio.sleep(60)

# Executa o bot
if __name__ == "__main__":
    asyncio.run(main())
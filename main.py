import os
import aiohttp
import asyncio
import pandas as pd
import ta
from datetime import datetime
from ta.trend import ADXIndicator, PSARIndicator

# Configurações do bot
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CSV_FILE = "sinais_registrados.csv"

if not TOKEN or not CHAT_ID:
    raise ValueError("As variáveis de ambiente TOKEN e CHAT_ID devem estar configuradas.")

async def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data={"chat_id": CHAT_ID, "text": mensagem}) as response:
                if response.status != 200:
                    print(f"Erro ao enviar mensagem: {await response.text()}")
    except Exception as e:
        print(f"Erro Telegram: {e}")

async def buscar_pares_futuros_usdt():
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                return [s["symbol"] for s in data["symbols"] if s["symbol"].endswith("USDT") and s["contractType"] == "PERPETUAL"]
    except Exception as e:
        print(f"Erro ao buscar pares: {e}")
        return []

async def obter_dados(par, intervalo="1h", limite=200):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={par}&interval={intervalo}&limit={limite}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
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

def calcular_score(df1h):
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

    return score, criterios, tipo

def registrar_sinal(par, score, criterios, tipo):
    agora = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"{agora},{par},{score},{tipo},{'|'.join(criterios)}\n"
    with open(CSV_FILE, "a") as f:
        f.write(linha)

async def analisar():
    pares = await buscar_pares_futuros_usdt()
    if not pares:
        await enviar_telegram("❌ Erro ao buscar pares futuros na Binance.")
        return

    for par in pares:
        df1h = await obter_dados(par, "1h")
        if df1h is None:
            continue

        score, criterios, tipo = calcular_score(df1h)
        if score >= 4:  # Critério para sinal forte
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

async def main():
    await enviar_telegram("🤖 Bot de sinais cripto 24h (Futuros USDT) atualizado e iniciado com sucesso!")
    while True:
        await analisar()
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
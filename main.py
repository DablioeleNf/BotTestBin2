import requests
import time
from datetime import datetime

# Configurações globais
WAIT_TIME = 600  # Tempo de espera em segundos (10 minutos)
last_signals = {}  # Dicionário para rastrear últimos sinais enviados por par

def fetch_binance_symbols():
    """
    Busca os pares disponíveis na Binance.
    """
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return [symbol['symbol'] for symbol in data.get('symbols', [])]
        else:
            print(f"Erro ao buscar pares na Binance: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"Erro de conexão com Binance: {e}")
        return []

def analyze_pair(pair):
    """
    Realiza uma análise técnica simples para o par fornecido.
    """
    # Simulação de análise técnica
    analysis = {
        "entry_price": 100.0,
        "take_profits": [105.0, 110.0, 115.0],
        "stop_loss": 95.0,
        "timestamp": datetime.now().isoformat()
    }
    return analysis

def send_signal(pair, analysis):
    """
    Envia um sinal baseado na análise técnica.
    """
    global last_signals

    # Verificar se já foi enviado sinal recentemente
    current_time = time.time()
    if pair in last_signals and current_time - last_signals[pair] < WAIT_TIME:
        print(f"Sinal para {pair} ignorado. Último sinal enviado há menos de {WAIT_TIME} segundos.")
        return

    # Enviar sinal (simulação de envio)
    print(f"Enviando sinal para {pair}...")
    print(f"Entrada: {analysis['entry_price']}")
    print(f"TPs: {analysis['take_profits']}")
    print(f"SL: {analysis['stop_loss']}")
    print(f"Análise gerada em: {analysis['timestamp']}")

    # Atualizar o tempo do último sinal
    last_signals[pair] = current_time

def main():
    while True:
        print("Buscando pares na Binance...")
        binance_symbols = fetch_binance_symbols()
        print(f"Pares encontrados na Binance: {len(binance_symbols)}")

        if binance_symbols:
            for pair in binance_symbols[:5]:  # Limitar para análise inicial de 5 pares
                analysis = analyze_pair(pair)
                send_signal(pair, analysis)
        else:
            print("Nenhum par encontrado para análise.")

        print(f"Aguardando {WAIT_TIME // 60} minutos para a próxima execução...")
        time.sleep(WAIT_TIME)

if __name__ == "__main__":
    main()
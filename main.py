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

        score, criterios, tipo = calcular_score(df1h, df5m, df15m, df30m)
        if score >= 4:  # Critério para sinal forte
            preco_atual = df1h["close"].iloc[-1]  # Preço atual do par no timeframe 1h

            # Define preços de entrada, stop loss e take profits (exemplo simples)
            preco_entrada = preco_atual
            margem_sl = 0.015  # 1.5% stop loss
            margem_tp1 = 0.015  # 1.5% TP1
            margem_tp2 = 0.03   # 3% TP2
            margem_tp3 = 0.05   # 5% TP3

            if tipo == "Compra":
                stop_loss = preco_entrada * (1 - margem_sl)
                tp1 = preco_entrada * (1 + margem_tp1)
                tp2 = preco_entrada * (1 + margem_tp2)
                tp3 = preco_entrada * (1 + margem_tp3)
            elif tipo == "Venda":
                stop_loss = preco_entrada * (1 + margem_sl)
                tp1 = preco_entrada * (1 - margem_tp1)
                tp2 = preco_entrada * (1 - margem_tp2)
                tp3 = preco_entrada * (1 - margem_tp3)
            else:
                # Se tipo indefinido, pula esse par
                continue

            duracao = "Curto prazo (até 24h)"  # Pode ajustar ou calcular dinamicamente se quiser

            registrar_sinal(par, score, criterios, tipo)  # Salva no CSV

            hora = datetime.utcnow().strftime("%H:%M:%S UTC")
            msg = f"""✅ Sinal forte detectado!
🕒 Horário: {hora}
📊 Par: {par}
📈 Score: {score}/6
📌 Tipo de sinal: {tipo}
💵 Preço atual (Entrada): {preco_entrada:.4f}
⛔ Stop Loss: {stop_loss:.4f}
🎯 Take Profit 1 (Alvo 1): {tp1:.4f}
🎯 Take Profit 2 (Alvo 2): {tp2:.4f}
🎯 Take Profit 3 (Alvo final): {tp3:.4f}
⏳ Duração estimada: {duracao}
🧠 Critérios:"""
            for crit in criterios:
                msg += f"\n• {crit}"
            enviar_telegram(msg)
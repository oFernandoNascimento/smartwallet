# Arquivo: src/ai_engine.py
import streamlit as st
import google.generativeai as genai
import re
import json
import logging
from datetime import datetime
import pytz

# Configuração de Log
logging.basicConfig(level=logging.INFO)
FUSO_BR = pytz.timezone('America/Sao_Paulo')

class AIManager:
    """
    Cérebro da IA: Gerencia Texto, Áudio, Conversão de Moedas e Coach.
    VERSÃO ESTÁVEL (Gemini 1.5): Usa os modelos oficiais de produção.
    """
    
    @staticmethod
    def configure():
        try:
            genai.configure(api_key=st.secrets["GEMINI_KEY"])
        except Exception as e:
            logging.error(f"Erro Config IA: {e}")

    @staticmethod
    def _clean_json(text):
        """Limpa a resposta da IA para extrair apenas o JSON."""
        if not text: return None
        # Remove markdown e blocos de código
        text = re.sub(r'```json', '', text, flags=re.IGNORECASE)
        text = re.sub(r'```', '', text).strip()
        
        # Busca o JSON com regex se houver lixo em volta (ex: "Aqui está o JSON: { ... }")
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try: return json.loads(match.group(0))
            except: pass
            
        # Tenta parse direto se o regex falhar
        try: return json.loads(text)
        except: return None

    @staticmethod
    def process_nlp(text, mkt, categories):
        return AIManager._core_process(text, mkt, categories, is_audio=False)

    @staticmethod
    def process_audio_nlp(audio_file, mkt, categories):
        try:
            audio_bytes = audio_file.read()
            return AIManager._core_process(audio_bytes, mkt, categories, is_audio=True)
        except Exception as e:
            return {"error": f"Erro leitura áudio: {e}"}

    @staticmethod
    def _core_process(input_data, mkt, categories, is_audio):
        cat_str = ", ".join(categories)
        
        prompt = f"""
        ACT AS: Financial Assistant & Currency Converter.
        CONTEXT: User is in Brazil. Output Currency: BRL (R$).
        DATE: {datetime.now(FUSO_BR).strftime('%Y-%m-%d')}.
        
        # RATES (1 Unit = X BRL):
        USD: {mkt.get('USD', 5.0)} | EUR: {mkt.get('EUR', 6.0)} | BTC: {mkt.get('BTC', 500000)}
        
        # INSTRUCTIONS:
        1. Identify currency. IF foreign, CONVERT to BRL using rates.
        2. Categorize based on: [{cat_str}].
           - "Bitcoin/Cripto/Ações" -> "Investimentos".
        3. OUTPUT JSON ONLY.
        
        # JSON FORMAT:
        {{
            "amount": float,         // Value in BRL
            "category": "string",    // From list
            "date": "YYYY-MM-DD",    // Today
            "description": "string", // Desc + original currency if converted
            "type": "string"         // 'Receita' OR 'Despesa'
        }}
        """
        
        # LISTA DE MODELOS OFICIAIS (ORDEM DE PRIORIDADE)
        # Removido 'gemini-pro' (antigo) e '2.0-flash-exp' (instável)
        models = ['gemini-1.5-flash', 'gemini-1.5-pro']
        
        last_error = ""
        
        for model_name in models:
            try:
                model = genai.GenerativeModel(model_name)
                
                if is_audio:
                    response = model.generate_content([prompt, {"mime_type": "audio/wav", "data": input_data}])
                else:
                    response = model.generate_content(prompt)
                
                data = AIManager._clean_json(response.text)
                
                if data:
                    # Higienização final dos dados
                    t = str(data.get('type', '')).lower()
                    if t in ['expense', 'outcome', 'gasto', 'saída']: data['type'] = 'Despesa'
                    elif t in ['income', 'entry', 'ganho', 'entrada', 'receita']: data['type'] = 'Receita'
                    else: data['type'] = data.get('type', 'Despesa').capitalize()
                    
                    try: data['amount'] = float(data['amount'])
                    except: data['amount'] = 0.0
                    
                    return data
            except Exception as e:
                last_error = str(e)
                logging.warning(f"Modelo {model_name} falhou. Tentando próximo...")
                continue # Tenta o próximo modelo
                
        return {"error": f"IA indisponível. Erro técnico: {last_error}"}

    @staticmethod
    def coach_financeiro(df, renda_total, mkt):
        if df.empty: return "Sem dados."
        prompt = f"""
        ACT AS: Personal Financial Coach (PT-BR).
        DATA: Income R$ {renda_total}, Transactions: {df.head(40).to_string()}
        GOAL: Analyze spending, suggest savings, give 1 investment tip.
        FORMAT: Markdown, Portuguese.
        """
        try:
            # O modelo 1.5 Flash é excelente para textos longos (Coach)
            return genai.GenerativeModel('gemini-1.5-flash').generate_content(prompt).text
        except: return "Coach offline."
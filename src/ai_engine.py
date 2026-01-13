# Arquivo: src/ai_engine.py
import streamlit as st
import google.generativeai as genai
import re
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
import pytz

# Configuração de Log
logging.basicConfig(level=logging.INFO)
FUSO_BR = pytz.timezone('America/Sao_Paulo')

class AIManager:
    """
    Cérebro da IA: Gerencia Texto, Áudio, Conversão de Moedas e Coach.
    """
    
    @staticmethod
    def configure():
        try:
            if "GEMINI_KEY" in st.secrets:
                genai.configure(api_key=st.secrets["GEMINI_KEY"])
            else:
                logging.warning("GEMINI_KEY não encontrada nos secrets.")
        except Exception as e:
            logging.error(f"Erro Config IA: {e}")

    @staticmethod
    def _clean_json(text: str) -> Optional[Dict]:
        """Limpa a resposta da IA para extrair apenas o JSON."""
        if not text: return None
        text = re.sub(r'```json', '', text, flags=re.IGNORECASE)
        text = re.sub(r'```', '', text).strip()
        
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try: return json.loads(match.group(0))
            except: pass
            
        try: return json.loads(text)
        except: return None

    @staticmethod
    def _try_local_rules(text: str) -> Optional[Dict]:
        """Classificador local via Regex."""
        try:
            text_lower = text.lower()
            
            # Se tiver moeda estrangeira, DELEGA para o Gemini converter
            if re.search(r'(dolar|dólar|usd|euro|eur|libra|gbp|bitcoin|btc)', text_lower):
                return None 

            amount = 0.0
            valor_match = re.search(r'(\d+[\.,]?\d*)', text)
            if valor_match:
                val_str = valor_match.group(1).replace(',', '.')
                try: amount = float(val_str)
                except: pass

            if amount <= 0: return None

            tipo = "Despesa"
            if re.search(r'(recebi|ganhei|pix|entrada|salário|depósito)', text_lower):
                tipo = "Receita"
            elif re.search(r'(gastei|paguei|compra|saída|uber|ifood)', text_lower):
                tipo = "Despesa"
            
            cat = "Outros"
            if "uber" in text_lower or "combustível" in text_lower or "ônibus" in text_lower: cat = "Transporte"
            elif "ifood" in text_lower or "restaurante" in text_lower or "mercado" in text_lower: cat = "Alimentação"
            elif "aluguel" in text_lower or "luz" in text_lower or "internet" in text_lower: cat = "Moradia"
            elif "curso" in text_lower or "faculdade" in text_lower: cat = "Educação"
            
            return {
                "amount": amount,
                "category": cat,
                "date": datetime.now(FUSO_BR).strftime('%Y-%m-%d %H:%M:%S'),
                "description": text.title(),
                "type": tipo,
                "source": "Local/Regex"
            }
        except Exception:
            return None

    @staticmethod
    def process_nlp(text: str, mkt: Dict, categories: List[str]) -> Dict:
        return AIManager._core_process(text, mkt, categories, is_audio=False)

    @staticmethod
    def process_audio_nlp(audio_file, mkt: Dict, categories: List[str]) -> Dict:
        try:
            audio_bytes = audio_file.read()
            return AIManager._core_process(audio_bytes, mkt, categories, is_audio=True)
        except Exception as e:
            return {"error": f"Erro leitura áudio: {e}"}

    @staticmethod
    def _core_process(input_data: Any, mkt: Dict, categories: List[str], is_audio: bool) -> Dict:
        # 1. Regex Local (apenas se for texto simples)
        if not is_audio and isinstance(input_data, str):
            local_result = AIManager._try_local_rules(input_data)
            if local_result:
                return local_result

        # 2. IA do Google (Gemini)
        cat_str = ", ".join(categories)
        
        # [BUG FIX] Agora incluímos explicitamente o USER INPUT no prompt de texto
        user_content = ""
        if not is_audio:
            user_content = f'USER INPUT: "{input_data}"'

        prompt = f"""
        ACT AS: Financial Assistant. CONTEXT: Brazil (BRL). DATE_TIME: {datetime.now(FUSO_BR).strftime('%Y-%m-%d %H:%M:%S')}.
        RATES: USD={mkt.get('USD', 5.0)}, BTC={mkt.get('BTC', 500000)}.
        TASK: Convert currency if needed. Classify in: [{cat_str}].
        
        {user_content}
        
        OUTPUT JSON ONLY: {{
            "amount": float, 
            "category": "str", 
            "date": "YYYY-MM-DD HH:MM:SS",
            "description": "str", 
            "type": "Receita/Despesa"
        }}
        """
        
        # Lista limpa: Apenas modelos que sabemos que funcionam ou são backups novos
        models = ['gemini-2.0-flash-exp', 'gemini-1.5-flash-8b']
        
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
                    t = str(data.get('type', '')).lower()
                    if t in ['expense', 'outcome', 'gasto', 'saída']: data['type'] = 'Despesa'
                    elif t in ['income', 'entry', 'ganho', 'entrada', 'receita']: data['type'] = 'Receita'
                    else: data['type'] = data.get('type', 'Despesa').capitalize()
                    
                    try: data['amount'] = float(data['amount'])
                    except: data['amount'] = 0.0
                    
                    return data
            except Exception as e:
                last_error = str(e)
                continue 
                
        return {"error": f"IA indisponível. Erro: {last_error}"}

    @staticmethod
    def coach_financeiro(df, renda_total, mkt):
        if df.empty: return "Sem dados suficientes para análise."
        
        prompt = f"""
        Atue como um Coach Financeiro Pessoal Sênior.
        Dados do Cliente: Renda Mensal R$ {renda_total:.2f}.
        Histórico Recente: 
        {df.head(40).to_string()}
        
        Missão: Analise os gastos, sugira onde economizar e dê 1 dica de investimento conservador.
        Responda em Português, direto e motivador. Use Markdown.
        """
        
        models = ['gemini-2.0-flash-exp', 'gemini-1.5-flash-8b']
        last_error = ""
        
        for model_name in models:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                if response and response.text:
                    return response.text
            except Exception as e:
                last_error = str(e)
                continue
                
        return f"Coach offline. Erro: {last_error}"
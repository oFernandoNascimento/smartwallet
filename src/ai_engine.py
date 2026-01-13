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
    Agora com arquitetura Híbrida: Tenta Regex Local -> Fallback para Gemini AI.
    """
    
    @staticmethod
    def configure():
        try:
            # Implementação de verificação de chave antes de iniciar
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
        # Tratamento de erro: remove markdown de código se a IA mandar
        text = re.sub(r'```json', '', text, flags=re.IGNORECASE)
        text = re.sub(r'```', '', text).strip()
        
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try: return json.loads(match.group(0))
            except: pass
            
        try: return json.loads(text)
        except: return None

    # --- IMPLEMENTAÇÃO DE CLASSIFICADOR LOCAL (REGEX) ---
    # Responde ao feedback sobre não usar LLM para tarefas triviais.
    @staticmethod
    def _try_local_rules(text: str) -> Optional[Dict]:
        """
        Tenta classificar usando regras determinísticas (Regex) antes de chamar a IA.
        Mais rápido, privado e sem custo.
        """
        try:
            text_lower = text.lower()
            amount = 0.0
            
            # 1. Extração de Valor via Regex (R$ XX,XX ou XX.XX)
            # Busca padrões numéricos comuns no texto
            valor_match = re.search(r'(\d+[\.,]?\d*)', text)
            if valor_match:
                val_str = valor_match.group(1).replace(',', '.')
                try: amount = float(val_str)
                except: pass

            if amount <= 0: return None # Se não achou valor, delega pra IA

            # 2. Classificação Simples de Tipo
            tipo = "Despesa" # Default conservador
            if re.search(r'(recebi|ganhei|pix|entrada|salário|depósito)', text_lower):
                tipo = "Receita"
            elif re.search(r'(gastei|paguei|compra|saída|uber|ifood)', text_lower):
                tipo = "Despesa"
            
            # 3. Tentativa de Categorização por Palavras-Chave
            cat = "Outros"
            if "uber" in text_lower or "combustível" in text_lower or "ônibus" in text_lower: cat = "Transporte"
            elif "ifood" in text_lower or "restaurante" in text_lower or "mercado" in text_lower: cat = "Alimentação"
            elif "aluguel" in text_lower or "luz" in text_lower or "internet" in text_lower: cat = "Moradia"
            elif "curso" in text_lower or "faculdade" in text_lower: cat = "Educação"
            
            # Se conseguiu extrair valor e inferir algo, retorna o objeto pronto
            # Evita chamar a API do Google (Custo Zero)
            return {
                "amount": amount,
                "category": cat,
                "date": datetime.now(FUSO_BR).strftime('%Y-%m-%d'),
                "description": text.title(),
                "type": tipo,
                "source": "Local/Regex" # Flag para debug
            }
        except Exception as e:
            logging.error(f"Erro no parser local: {e}")
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
        # Pipeline Híbrido:
        # 1. Se for texto, tenta o Regex Local primeiro (Baseline).
        if not is_audio and isinstance(input_data, str):
            local_result = AIManager._try_local_rules(input_data)
            if local_result:
                logging.info("Processado via Regex Local (Baseline)")
                return local_result

        # 2. Se falhar ou for áudio, chama a Heavy Artillery (LLM)
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
                continue 
                
        return {"error": f"IA indisponível. Erro técnico: {last_error}"}

    @staticmethod
    def coach_financeiro(df, renda_total, mkt):
        if df.empty: return "Sem dados."
        # Mantendo 100% da lógica original, apenas encapsulando erros
        try:
            prompt = f"""
            ACT AS: Personal Financial Coach (PT-BR).
            DATA: Income R$ {renda_total}, Transactions: {df.head(40).to_string()}
            GOAL: Analyze spending, suggest savings, give 1 investment tip.
            FORMAT: Markdown, Portuguese.
            """
            return genai.GenerativeModel('gemini-1.5-flash').generate_content(prompt).text
        except Exception as e:
            return f"Coach offline temporariamente: {e}"
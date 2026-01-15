import streamlit as st
import google.generativeai as genai
import re
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
import pytz
import pandas as pd
from src.utils import KnowledgeBaseLoader

# Configuração de Log e Fuso Horário
logging.basicConfig(level=logging.INFO)
FUSO_BR = pytz.timezone('America/Sao_Paulo')

class AIManager:
    """
    Controlador da Lógica de IA.
    Responsável por:
    1. Processamento de Linguagem Natural (Texto e Áudio) para transações.
    2. Chat RAG (Retrieval-Augmented Generation) com base de conhecimento.
    3. Análise financeira avançada (Coach).
    """
    
    KNOWLEDGE_SOURCE = "assets"  
    
    @staticmethod
    def configure():
        """Configura a API do Google Gemini."""
        try:
            if "GEMINI_KEY" in st.secrets:
                genai.configure(api_key=st.secrets["GEMINI_KEY"])
            else:
                logging.warning("GEMINI_KEY não encontrada nos secrets.")
        except Exception as e:
            logging.error(f"Erro na configuração da IA: {e}")

    @staticmethod
    def _clean_json(text: str) -> Optional[Dict]:
        """Extrai e converte o JSON da resposta textual da IA."""
        if not text: return None
        # Remove blocos de código markdown se houver
        text = re.sub(r'```json', '', text, flags=re.IGNORECASE)
        text = re.sub(r'```', '', text).strip()
        
        # Tenta encontrar o padrão JSON
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try: return json.loads(match.group(0))
            except: pass
        try: return json.loads(text)
        except: return None

    @staticmethod
    def _sanitize_output(text: str) -> str:
        """
        Sanitiza a saída de texto para o Streamlit.
        Remove formatação Markdown de código (backticks) e escapa símbolos LaTeX ($)
        para garantir renderização de texto plano limpo.
        """
        if not text: return ""
        text = text.replace("`", "")  # Remove backticks
        text = text.replace("$", "\$") # Escapa cifrão para evitar LaTeX
        return text

    @staticmethod
    def _format_history_for_learning(df: pd.DataFrame) -> str:
        """Formata o histórico recente para Few-Shot Learning no prompt."""
        if df is None or df.empty: return "Histórico vazio."
        examples = df.head(5)[['description', 'category', 'type', 'amount']].to_dict(orient='records')
        history_text = "=== EXEMPLOS DO PASSADO ===\n"
        for ex in examples:
            history_text += f"- '{ex['description']}' -> Cat: {ex['category']}, Tipo: {ex['type']}\n"
        return history_text

    @staticmethod
    def _try_local_rules(text: str) -> Optional[Dict]:
        """Tenta classificar a transação usando Regex local antes de chamar a IA."""
        try:
            text_lower = text.lower()
            # Se houver termos complexos de investimento, delega para a IA
            termos_complexos = r'(dolar|dólar|usd|euro|eur|libra|gbp|bitcoin|btc|cdb|cdi|selic|fii|dividendos|rendimento|investi|aplic|guard|resgat|tesouro)'
            if re.search(termos_complexos, text_lower): return None 

            amount = 0.0
            valor_match = re.search(r'(\d+[\.,]?\d*)', text)
            if valor_match:
                val_str = valor_match.group(1).replace(',', '.')
                try: amount = float(val_str)
                except: pass

            if amount <= 0: return None
            
            tipo = "Despesa"
            if re.search(r'(recebi|ganhei|pix|entrada|salário|depósito)', text_lower): tipo = "Receita"
            elif re.search(r'(gastei|paguei|compra|saída|uber|ifood)', text_lower): tipo = "Despesa"
            
            cat = "Outros"
            if "uber" in text_lower or "combustível" in text_lower or "ônibus" in text_lower: cat = "Transporte"
            elif "ifood" in text_lower or "restaurante" in text_lower or "mercado" in text_lower: cat = "Alimentação"
            elif "aluguel" in text_lower or "luz" in text_lower or "internet" in text_lower: cat = "Moradia"
            elif "curso" in text_lower or "faculdade" in text_lower: cat = "Educação"
            
            if cat == "Outros" and tipo == "Despesa": return None

            return {
                "amount": amount,
                "category": cat,
                "date": datetime.now(FUSO_BR).strftime('%Y-%m-%d %H:%M:%S'),
                "description": text.title(),
                "type": tipo,
                "source": "Local/Regex"
            }
        except Exception: return None

    @staticmethod
    def process_nlp(text: str, mkt: Dict, categories: List[str], history_df: pd.DataFrame = None) -> Dict:
        """Processa entrada de texto para extrair dados da transação."""
        return AIManager._core_process(text, mkt, categories, history_df, is_audio=False)

    @staticmethod
    def process_audio_nlp(audio_file, mkt: Dict, categories: List[str], history_df: pd.DataFrame = None) -> Dict:
        """Processa entrada de áudio para extrair dados da transação."""
        try:
            audio_bytes = audio_file.read()
            return AIManager._core_process(audio_bytes, mkt, categories, history_df, is_audio=True)
        except Exception as e:
            return {"error": f"Erro leitura áudio: {e}"}

    @staticmethod
    def _core_process(input_data: Any, mkt: Dict, categories: List[str], history_df: pd.DataFrame, is_audio: bool) -> Dict:
        """Núcleo de processamento da IA para classificação de transações."""
        knowledge_text = KnowledgeBaseLoader.load_knowledge(AIManager.KNOWLEDGE_SOURCE)
        
        # Tenta regras locais para texto simples
        if not is_audio and isinstance(input_data, str) and not knowledge_text:
            local_result = AIManager._try_local_rules(input_data)
            if local_result: return local_result

        learning_context = AIManager._format_history_for_learning(history_df)
        user_content = ""
        if not is_audio: user_content = f'USER INPUT: "{input_data}"'

        prompt = f"""
        ACT AS: Senior Financial Analyst.
        CONTEXT: Brazil (BRL). DATE: {datetime.now(FUSO_BR).strftime('%Y-%m-%d %H:%M:%S')}.
        RATES: USD={mkt.get('USD', 5.0)}, BTC={mkt.get('BTC', 500000)}.
        === KNOWLEDGE BASE ===
        {knowledge_text}
        === USER HISTORY ===
        {learning_context}
        
        RULES FOR CLASSIFICATION:
        1. "Investi", "Aportei", "Comprei CDB/Ação", "Guardei" -> Type="Despesa" (Money leaves checking account).
        2. "Tenho X", "Saldo é X", "Resgatei", "Tirei do investimento" -> Type="Receita" (Money enters or is just balance).
        3. Priority: Knowledge Base > User History > Default Rules.
        
        Output strictly JSON.
        {user_content}
        OUTPUT JSON:
        {{ "amount": float, "category": "str", "date": "YYYY-MM-DD HH:MM:SS", "description": "str", "type": "Receita/Despesa" }}
        """
        
        models = ['gemini-2.0-flash-exp', 'gemini-1.5-flash', 'gemini-pro']
        for model_name in models:
            try:
                model = genai.GenerativeModel(model_name)
                if is_audio: response = model.generate_content([prompt, {"mime_type": "audio/wav", "data": input_data}])
                else: response = model.generate_content(prompt)
                data = AIManager._clean_json(response.text)
                if data:
                    t = str(data.get('type', '')).lower()
                    if t in ['expense', 'outcome', 'gasto', 'saída']: data['type'] = 'Despesa'
                    elif t in ['income', 'entry', 'ganho', 'entrada', 'receita']: data['type'] = 'Receita'
                    else: data['type'] = data.get('type', 'Despesa').capitalize()
                    try: data['amount'] = float(data['amount'])
                    except: data['amount'] = 0.0
                    return data
            except: continue 
        return {"error": "IA indisponível."}

    @staticmethod
    def chat_with_docs(user_question: str, df: pd.DataFrame = None) -> str:
        """
        Chat RAG: Responde perguntas com base na documentação e no contexto financeiro do usuário.
        Diferencia Salário Mensal de Patrimônio Acumulado.
        """
        try:
            knowledge = KnowledgeBaseLoader.load_knowledge(AIManager.KNOWLEDGE_SOURCE)
            
            resumo_financeiro = "Sem dados."
            if df is not None and not df.empty:
                # 1. Identificação de Salário (Recorrência)
                mask_salario = (df['category'].str.contains('Salário', case=False, na=False)) & (df['type'] == 'Receita')
                df_salario = df[mask_salario].sort_values('date', ascending=False)
                salario_estimado = df_salario.iloc[0]['amount'] if not df_salario.empty else 0.0

                # 2. Identificação de Patrimônio (Investimentos)
                keywords = ['cdi', 'cdb', 'lci', 'lca', 'tesouro', 'poupanca', 'nubank', 'caixinha', 'invest', 'btc', 'cripto', 'ouro', 'dolar', 'fii', 'ações']
                pattern = '|'.join(keywords)
                mask_invest = ((df['category'].str.contains('Invest', case=False, na=False)) | (df['description'].str.contains(pattern, case=False, na=False)))
                df_invest = df[mask_invest]
                
                # Cálculo simples de patrimônio (soma de fluxos de investimento)
                total_investido_aportes = df_invest[df_invest['type'] == 'Despesa']['amount'].sum()
                total_investido_saldos = df_invest[df_invest['type'] == 'Receita']['amount'].sum()
                total_patrimonio = total_investido_aportes + total_investido_saldos
                
                # 3. Total de Despesas
                total_gastos = df[df['type'] == 'Despesa']['amount'].sum()
                
                resumo_financeiro = f"""
                === RAIO-X FINANCEIRO ===
                - RENDA MENSAL (SALÁRIO RECORRENTE): R$ {salario_estimado:.2f}
                - PATRIMÔNIO ACUMULADO (INVESTIMENTOS): R$ {total_patrimonio:.2f}
                - GASTOS TOTAIS REGISTRADOS: R$ {total_gastos:.2f}
                ========================
                """

            prompt = f"""
            ATUE COMO: Mentor Financeiro Sênior do SmartWallet.
            
            DADOS DO USUÁRIO:
            {resumo_financeiro}
            
            SABEDORIA TÉCNICA:
            {knowledge}
            
            PERGUNTA: "{user_question}"
            
            DIRETRIZES:
            1. **PROIBIDO USAR FORMATO DE CÓDIGO** (Não use crases `).
            2. **PROIBIDO USAR LATEX** (Não use $ para formatar fórmulas, use R$ apenas como texto).
            3. Escreva valores e dinheiro como texto normal ou Negrito. Ex: "R$ 1.500,00" ou "**R$ 1.500,00**".
            4. Diferencie Renda Mensal de Patrimônio Acumulado.
            5. Não cite nomes de arquivos.
            """
            
            models = ['gemini-2.0-flash-exp', 'gemini-1.5-flash', 'gemini-pro']
            for model_name in models:
                try:
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(prompt)
                    if response and response.text:
                        return AIManager._sanitize_output(response.text)
                except: continue
            
            return "Não foi possível conectar a nenhum modelo de IA no momento."
            
        except Exception as e:
            return f"Erro no Chat: {str(e)}"

    @staticmethod
    def coach_financeiro(df, renda_total, mkt):
        """Gera uma análise completa do perfil financeiro."""
        knowledge_text = KnowledgeBaseLoader.load_knowledge(AIManager.KNOWLEDGE_SOURCE)
        if df.empty: return "Sem dados suficientes."
        
        prompt = f"""
        Atue como Consultor Financeiro Sênior.
        SABEDORIA TÉCNICA: {knowledge_text}
        
        DADOS CLIENTE: Renda Total Entradas: {renda_total:.2f}.
        HISTÓRICO: {df.head(40).to_string()}
        
        MISSÃO: Analise gastos e dê dicas.
        
        DIRETRIZES:
        1. NÃO USE CRASES (`).
        2. NÃO USE FORMULA LATEX.
        3. Use **Negrito** para valores.
        4. Texto limpo.
        """
        
        models = ['gemini-2.0-flash-exp', 'gemini-1.5-flash', 'gemini-pro']
        for model_name in models:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                if response and response.text:
                    return AIManager._sanitize_output(response.text)
            except: continue
        return "Coach offline."
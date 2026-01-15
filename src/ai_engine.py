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
    Motor de Inteligência Artificial do SmartWallet.
    
    Responsabilidades:
    - Processamento de Linguagem Natural (NLP) Híbrido: Regex Local + LLM (Gemini).
    - Classificação automática de transações financeiras.
    - Chat RAG (Retrieval-Augmented Generation) com base de conhecimento técnica.
    - Consultoria Financeira (Coach) baseada em histórico de dados.
    """
    
    KNOWLEDGE_SOURCE = "assets"  
    
    @staticmethod
    def configure():
        """Inicializa a configuração da API do Google Gemini (Generative AI)."""
        try:
            if "GEMINI_KEY" in st.secrets:
                genai.configure(api_key=st.secrets["GEMINI_KEY"])
            else:
                logging.warning("SmartWallet: GEMINI_KEY não encontrada nos secrets.")
        except Exception as e:
            logging.error(f"Erro na configuração da IA: {e}")

    @staticmethod
    def _clean_json(text: str) -> Optional[Dict]:
        """
        Parser robusto para extrair JSON de respostas textuais da IA.
        Remove blocos Markdown (```json) e tenta corrigir formatações inválidas.
        """
        if not text: return None
        # Limpeza de markdown
        text = re.sub(r'```json', '', text, flags=re.IGNORECASE)
        text = re.sub(r'```', '', text).strip()
        
        # Tentativa de extração via Regex se houver texto ao redor
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try: return json.loads(match.group(0))
            except: pass
        
        # Tentativa direta
        try: return json.loads(text)
        except: return None

    @staticmethod
    def _sanitize_output(text: str) -> str:
        """
        Sanitiza strings de saída para exibição segura no frontend (Streamlit).
        Previne injeção de LaTeX indesejado ($) e remove backticks.
        """
        if not text: return ""
        text = text.replace("`", "")
        text = text.replace("$", "\$") 
        return text

    @staticmethod
    def _format_history_for_learning(df: pd.DataFrame) -> str:
        """
        Prepara o histórico de transações para 'Few-Shot Learning'.
        Permite que a IA aprenda o estilo de categorização do usuário.
        """
        if df is None or df.empty: return "Histórico vazio."
        # Seleciona os 5 exemplos mais recentes para contexto
        examples = df.head(5)[['description', 'category', 'type', 'amount']].to_dict(orient='records')
        history_text = "=== HISTÓRICO RECENTE DO USUÁRIO (Contexto) ===\n"
        for ex in examples:
            history_text += f"- Descrição: '{ex['description']}' | Categoria: {ex['category']} | Tipo: {ex['type']}\n"
        return history_text

    @staticmethod
    def _try_local_rules(text: str) -> Optional[Dict]:
        """
        Motor de Regras Locais (Regex).
        Processa transações comuns instantaneamente sem custo de API.
        Garante que termos como 'Padaria' e 'Farmácia' sejam categorizados corretamente.
        """
        try:
            text_lower = text.lower()
            
            # Se a transação envolver investimento ou câmbio, delega para a IA (LLM)
            termos_complexos = r'(dolar|dólar|usd|euro|eur|libra|gbp|bitcoin|btc|cdb|cdi|selic|fii|dividendos|rendimento|investi|aplic|guard|resgat|tesouro)'
            if re.search(termos_complexos, text_lower): return None 

            # Extração de valor via Regex
            amount = 0.0
            valor_match = re.search(r'(\d+[\.,]?\d*)', text)
            if valor_match:
                val_str = valor_match.group(1).replace(',', '.')
                try: amount = float(val_str)
                except: pass

            if amount <= 0: return None
            
            # Determinação do Tipo (Receita vs Despesa)
            tipo = "Despesa"
            if re.search(r'(recebi|ganhei|pix|entrada|salário|depósito)', text_lower): tipo = "Receita"
            elif re.search(r'(gastei|paguei|compra|saída|uber|ifood)', text_lower): tipo = "Despesa"
            
            # Mapeamento Determinístico de Categorias
            cat = "Outros"
            
            # Regras de Negócio Hardcoded
            if "uber" in text_lower or "combustível" in text_lower or "ônibus" in text_lower or "posto" in text_lower: cat = "Transporte"
            elif "ifood" in text_lower or "restaurante" in text_lower or "mercado" in text_lower or "padaria" in text_lower or "lanche" in text_lower: cat = "Alimentação"
            elif "aluguel" in text_lower or "luz" in text_lower or "internet" in text_lower or "condomínio" in text_lower: cat = "Moradia"
            elif "curso" in text_lower or "faculdade" in text_lower or "livro" in text_lower: cat = "Educação"
            elif "farmácia" in text_lower or "médico" in text_lower or "remédio" in text_lower or "hospital" in text_lower or "dentista" in text_lower: cat = "Saúde"
            
            # Se não conseguiu categorizar, retorna None para a IA tentar
            if cat == "Outros" and tipo == "Despesa": return None

            return {
                "amount": amount,
                "category": cat,
                "date": datetime.now(FUSO_BR).strftime('%Y-%m-%d %H:%M:%S'),
                "description": text.title(), # Mantém a descrição literal (ex: "Gastei Na Padaria")
                "type": tipo,
                "source": "Local/Regex"
            }
        except Exception: return None

    @staticmethod
    def process_nlp(text: str, mkt: Dict, categories: List[str], history_df: pd.DataFrame = None) -> Dict:
        """Entrada pública para processamento de texto."""
        return AIManager._core_process(text, mkt, categories, history_df, is_audio=False)

    @staticmethod
    def process_audio_nlp(audio_file, mkt: Dict, categories: List[str], history_df: pd.DataFrame = None) -> Dict:
        """Entrada pública para processamento de áudio."""
        try:
            audio_bytes = audio_file.read()
            return AIManager._core_process(audio_bytes, mkt, categories, history_df, is_audio=True)
        except Exception as e:
            return {"error": f"Erro leitura áudio: {e}"}

    @staticmethod
    def _core_process(input_data: Any, mkt: Dict, categories: List[str], history_df: pd.DataFrame, is_audio: bool) -> Dict:
        """
        Núcleo de processamento da IA.
        Decide entre usar Regras Locais ou chamar a API do Gemini.
        """
        knowledge_text = KnowledgeBaseLoader.load_knowledge(AIManager.KNOWLEDGE_SOURCE)
        
        # 1. Tenta Regras Locais (Prioridade para velocidade e custo)
        if not is_audio and isinstance(input_data, str):
            local_result = AIManager._try_local_rules(input_data)
            if local_result: return local_result

        # 2. Prepara Contexto para o LLM
        learning_context = AIManager._format_history_for_learning(history_df)
        user_content = ""
        if not is_audio: user_content = f'USER INPUT: "{input_data}"'

        # Lista de categorias permitidas para guiar a IA
        cats_str = ", ".join(categories)

        # Prompt Engenheirado
        prompt = f"""
        ACT AS: Senior Financial Analyst AI.
        CONTEXT: Brazil (BRL). DATE: {datetime.now(FUSO_BR).strftime('%Y-%m-%d %H:%M:%S')}.
        RATES: USD={mkt.get('USD', 5.0)}, BTC={mkt.get('BTC', 500000)}.
        
        === ALLOWED CATEGORIES ===
        [{cats_str}]
        
        === KNOWLEDGE BASE (Reference Only) ===
        {knowledge_text}
        
        === USER HISTORY (Style Guide) ===
        {learning_context}
        
        TASK:
        Analyze the input and extract structured financial data.
        
        RULES:
        1. **DESCRIPTION**: Must be LITERAL and descriptive. Examples:
           - Input: "Gastei 20 na padaria" -> Description: "Gasto na Padaria" (Do NOT simply use "Alimentação" here).
           - Input: "Uber pro trabalho" -> Description: "Uber pro Trabalho".
        
        2. **CATEGORY**: Must be ONE of the [ALLOWED CATEGORIES].
           - "Padaria", "Restaurante", "Mercado" -> Category: "Alimentação".
           - "Farmácia", "Médico", "Remédio" -> Category: "Saúde".
           - "Uber", "Posto", "Gasolina" -> Category: "Transporte".
           - DO NOT INVENT NEW CATEGORIES.
        
        3. **TYPE**: "Receita" (Income) or "Despesa" (Expense).
           - Investment flows ("Aportei", "Investi") count as "Despesa" (Output cash flow).
           - Withdrawals ("Resgatei", "Saldo") count as "Receita".

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
                    # Validação final da Categoria
                    cat_ia = data.get('category', 'Outros')
                    if cat_ia not in categories:
                        # Tenta encontrar a categoria mais próxima ou usa Outros
                        data['category'] = 'Outros' 
                        for c in categories:
                            if c.lower() in cat_ia.lower() or cat_ia.lower() in c.lower():
                                data['category'] = c
                                break

                    # Normalização do Tipo
                    t = str(data.get('type', '')).lower()
                    if t in ['expense', 'outcome', 'gasto', 'saída']: data['type'] = 'Despesa'
                    elif t in ['income', 'entry', 'ganho', 'entrada', 'receita']: data['type'] = 'Receita'
                    else: data['type'] = data.get('type', 'Despesa').capitalize()
                    
                    try: data['amount'] = float(data['amount'])
                    except: data['amount'] = 0.0
                    
                    return data
            except: continue 
        return {"error": "IA indisponível. Tente novamente."}

    @staticmethod
    def chat_with_docs(user_question: str, df: pd.DataFrame = None) -> str:
        """
        Chat RAG: Responde perguntas financeiras usando a base de conhecimento (PDFs).
        Diferencia fluxos de caixa (Salário) de estoques (Patrimônio).
        """
        try:
            knowledge = KnowledgeBaseLoader.load_knowledge(AIManager.KNOWLEDGE_SOURCE)
            
            resumo_financeiro = "Sem dados financeiros."
            if df is not None and not df.empty:
                # Lógica para estimar Salário (Renda Recorrente)
                mask_salario = (df['category'].str.contains('Salário', case=False, na=False)) & (df['type'] == 'Receita')
                df_salario = df[mask_salario].sort_values('date', ascending=False)
                salario_estimado = df_salario.iloc[0]['amount'] if not df_salario.empty else 0.0

                # Lógica para estimar Patrimônio (Investimentos)
                keywords = ['cdi', 'cdb', 'lci', 'lca', 'tesouro', 'poupanca', 'nubank', 'caixinha', 'invest', 'btc', 'cripto']
                pattern = '|'.join(keywords)
                mask_invest = ((df['category'].str.contains('Invest', case=False, na=False)) | (df['description'].str.contains(pattern, case=False, na=False)))
                df_invest = df[mask_invest]
                
                total_aportes = df_invest[df_invest['type'] == 'Despesa']['amount'].sum()
                total_resgates = df_invest[df_invest['type'] == 'Receita']['amount'].sum()
                total_patrimonio = total_aportes + total_resgates # Simplificação para Saldo
                
                total_gastos = df[df['type'] == 'Despesa']['amount'].sum()
                
                resumo_financeiro = f"""
                === RAIO-X DO USUÁRIO ===
                - RENDA MENSAL ESTIMADA: R$ {salario_estimado:.2f}
                - PATRIMÔNIO ACUMULADO: R$ {total_patrimonio:.2f}
                - TOTAL GASTOS (Período): R$ {total_gastos:.2f}
                """

            prompt = f"""
            ACT AS: Mentor Financeiro Pessoal (SmartWallet).
            
            USER DATA:
            {resumo_financeiro}
            
            KNOWLEDGE BASE (Técnica):
            {knowledge}
            
            USER QUESTION: "{user_question}"
            
            GUIDELINES:
            1. Seja direto, empático e técnico.
            2. Use a Knowledge Base para fundamentar respostas.
            3. NÃO use blocos de código ou LaTeX. Use negrito para valores (R$ 100,00).
            """
            
            models = ['gemini-2.0-flash-exp', 'gemini-1.5-flash', 'gemini-pro']
            for model_name in models:
                try:
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(prompt)
                    if response and response.text:
                        return AIManager._sanitize_output(response.text)
                except: continue
            
            return "O Chat Inteligente está temporariamente indisponível."
            
        except Exception as e:
            return f"Erro interno no Chat: {str(e)}"

    @staticmethod
    def coach_financeiro(df, renda_total, mkt):
        """
        Coach Financeiro: Analisa o extrato e gera insights proativos.
        """
        knowledge_text = KnowledgeBaseLoader.load_knowledge(AIManager.KNOWLEDGE_SOURCE)
        if df.empty: return "Dados insuficientes para análise do Coach."
        
        prompt = f"""
        ATUE COMO: Consultor Financeiro de Elite.
        BASE DE CONHECIMENTO: {knowledge_text}
        
        PERFIL DO CLIENTE:
        - Renda Total (Entradas): R$ {renda_total:.2f}
        - Últimas Transações:
        {df.head(40).to_string()}
        
        MISSÃO:
        Analise os padrões de gasto, identifique gargalos e sugira melhorias baseadas na teoria financeira (ex: Regra 50/30/20).
        Seja curto e use tópicos.
        
        DIRETRIZES:
        - Sem Markdown de código.
        - Sem LaTeX.
        """
        
        models = ['gemini-2.0-flash-exp', 'gemini-1.5-flash', 'gemini-pro']
        for model_name in models:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                if response and response.text:
                    return AIManager._sanitize_output(response.text)
            except: continue
        return "Coach offline no momento."

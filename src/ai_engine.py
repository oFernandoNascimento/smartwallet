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
    - [NOVO] ETL Inteligente para arquivos Bancários (OFX e PDF).
    """
    
    KNOWLEDGE_SOURCE = "assets"  
    
    @staticmethod
    def configure():
        """Inicializa a configuração da API do Google Gemini (Generative AI)."""
        try:
            # Tenta pegar a chave dos secrets do Streamlit ou ambiente
            api_key = st.secrets.get("GEMINI_KEY") or st.secrets.get("GOOGLE_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
            else:
                logging.warning("SmartWallet: Chave de API do Gemini não encontrada.")
        except Exception as e:
            logging.error(f"Erro na configuração da IA: {e}")

    @staticmethod
    def _clean_json(text: str) -> Optional[Dict]:
        """Parser robusto para extrair JSON de respostas textuais da IA."""
        if not text: return None
        # Remove blocos de código markdown se existirem
        text = re.sub(r'```json', '', text, flags=re.IGNORECASE)
        text = re.sub(r'```', '', text).strip()
        
        # Tenta encontrar o JSON dentro do texto (caso a IA fale antes)
        match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
        if match:
            text_to_parse = match.group(0)
        else:
            text_to_parse = text

        try: 
            return json.loads(text_to_parse)
        except: 
            logging.warning(f"Falha ao fazer parse do JSON: {text[:50]}...")
            return None

    @staticmethod
    def _sanitize_output(text: str) -> str:
        """Sanitiza strings de saída para exibição segura no frontend."""
        if not text: return ""
        text = text.replace("`", "")
        text = text.replace("$", "\$") 
        return text

    @staticmethod
    def _format_history_for_learning(df: pd.DataFrame) -> str:
        """Prepara o histórico de transações para 'Few-Shot Learning'."""
        if df is None or df.empty: return "Histórico vazio."
        # Pega os 5 exemplos mais recentes para dar contexto à IA
        examples = df.head(5)[['description', 'category', 'type', 'amount']].to_dict(orient='records')
        history_text = "=== HISTÓRICO RECENTE DO USUÁRIO (Contexto) ===\n"
        for ex in examples:
            history_text += f"- Descrição: '{ex['description']}' | Categoria: {ex['category']} | Tipo: {ex['type']}\n"
        return history_text

    @staticmethod
    def _try_local_rules(text: str) -> Optional[Dict]:
        """Motor de Regras Locais (Regex) para classificação rápida sem custo de IA."""
        try:
            text_lower = text.lower()
            # Ignora termos complexos que exigem IA (investimentos, câmbio)
            termos_complexos = r'(dolar|dólar|usd|euro|eur|libra|gbp|bitcoin|btc|cdb|cdi|selic|fii|dividendos|rendimento|investi|aplic|guard|resgat|tesouro)'
            if re.search(termos_complexos, text_lower): return None 

            amount = 0.0
            # Tenta extrair valor numérico (ex: 50,00 ou 50.00)
            valor_match = re.search(r'(\d+[\.,]?\d*)', text)
            if valor_match:
                val_str = valor_match.group(1).replace(',', '.')
                try: amount = float(val_str)
                except: pass

            if amount <= 0: return None
            
            # Classificação Simples de Tipo
            tipo = "Despesa"
            if re.search(r'(recebi|ganhei|pix|entrada|salário|depósito)', text_lower): tipo = "Receita"
            elif re.search(r'(gastei|paguei|compra|saída|uber|ifood)', text_lower): tipo = "Despesa"
            
            # Classificação Simples de Categoria
            cat = "Outros"
            if "uber" in text_lower or "combustível" in text_lower or "ônibus" in text_lower or "posto" in text_lower: cat = "Transporte"
            elif "ifood" in text_lower or "restaurante" in text_lower or "mercado" in text_lower or "padaria" in text_lower or "lanche" in text_lower: cat = "Alimentação"
            elif "aluguel" in text_lower or "luz" in text_lower or "internet" in text_lower or "condomínio" in text_lower: cat = "Moradia"
            elif "curso" in text_lower or "faculdade" in text_lower or "livro" in text_lower: cat = "Educação"
            elif "farmácia" in text_lower or "médico" in text_lower or "remédio" in text_lower or "hospital" in text_lower or "dentista" in text_lower: cat = "Saúde"
            
            # Se não conseguiu categorizar nem definir tipo com certeza, deixa para a IA
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
        """Entrada pública para processamento de texto."""
        return AIManager._core_process(text, mkt, categories, history_df, is_audio=False)

    @staticmethod
    def process_audio_nlp(audio_file, mkt: Dict, categories: List[str], history_df: pd.DataFrame = None) -> Dict:
        """Entrada pública para processamento de áudio."""
        try:
            # Lê os bytes do arquivo de áudio para envio
            audio_bytes = audio_file.read()
            return AIManager._core_process(audio_bytes, mkt, categories, history_df, is_audio=True)
        except Exception as e:
            return {"error": f"Erro leitura áudio: {e}"}

    @staticmethod
    def _core_process(input_data: Any, mkt: Dict, categories: List[str], history_df: pd.DataFrame, is_audio: bool) -> Dict:
        """Núcleo de processamento da IA com regras rígidas de categorização."""
        # Carrega contexto da base de conhecimento (opcional para NLP simples, mas útil para contexto)
        # knowledge_text = KnowledgeBaseLoader.load_knowledge(AIManager.KNOWLEDGE_SOURCE) 
        
        # Tenta regras locais primeiro para economizar tokens (apenas texto)
        if not is_audio and isinstance(input_data, str):
            local_result = AIManager._try_local_rules(input_data)
            if local_result: return local_result

        learning_context = AIManager._format_history_for_learning(history_df)
        user_content = ""
        if not is_audio: user_content = f'USER INPUT: "{input_data}"'

        cats_str = ", ".join(categories)

        prompt = f"""
        ACT AS: Senior Financial Analyst AI.
        CONTEXT: Brazil (BRL). DATE: {datetime.now(FUSO_BR).strftime('%Y-%m-%d %H:%M:%S')}.
        RATES: USD={mkt.get('USD', 5.0)}, BTC={mkt.get('BTC', 500000)}.
        
        === ALLOWED CATEGORIES ===
        [{cats_str}]
        
        === USER HISTORY (Style Guide) ===
        {learning_context}
        
        TASK:
        Analyze the input and extract structured financial data.
        
        RULES:
        1. DESCRIPTION: Must be LITERAL (e.g., "Gastei 20 na padaria" -> "Gasto na Padaria").
        2. CATEGORY: Must be strictly ONE of the [ALLOWED CATEGORIES].
           - "Padaria" -> "Alimentação". "Uber" -> "Transporte".
        3. TYPE: "Receita" or "Despesa".
        
        Output strictly JSON.
        {user_content}
        OUTPUT JSON:
        {{ "amount": float, "category": "str", "date": "YYYY-MM-DD HH:MM:SS", "description": "str", "type": "Receita/Despesa" }}
        """
        
        # Lista de modelos para fallback
        models = ['gemini-1.5-flash', 'gemini-2.0-flash-exp', 'gemini-1.5-pro-latest'] 
        for model_name in models:
            try:
                model = genai.GenerativeModel(model_name)
                if is_audio: response = model.generate_content([prompt, {"mime_type": "audio/wav", "data": input_data}])
                else: response = model.generate_content(prompt)
                
                data = AIManager._clean_json(response.text)
                
                if data:
                    # Normalização de Categoria (Garante que existe na lista do usuário)
                    cat_ia = data.get('category', 'Outros')
                    if cat_ia not in categories:
                        data['category'] = 'Outros' 
                        for c in categories:
                            if c.lower() in cat_ia.lower() or cat_ia.lower() in c.lower():
                                data['category'] = c
                                break

                    # Normalização de Tipo (Traduz para Português)
                    t = str(data.get('type', '')).lower()
                    if t in ['expense', 'outcome', 'gasto', 'saída', 'debit']: data['type'] = 'Despesa'
                    elif t in ['income', 'entry', 'ganho', 'entrada', 'receita', 'credit']: data['type'] = 'Receita'
                    else: data['type'] = data.get('type', 'Despesa').capitalize()
                    
                    try: data['amount'] = float(data['amount'])
                    except: data['amount'] = 0.0
                    
                    return data
            except: continue 
        return {"error": "IA indisponível. Tente novamente."}

    @staticmethod
    def chat_with_docs(user_question: str, df: pd.DataFrame = None) -> str:
        """
        Chat RAG Inteligente.
        Blindado contra vazamento de nomes de arquivos e respostas genéricas.
        Calcula dados reais antes de enviar ao modelo.
        """
        try:
            knowledge = KnowledgeBaseLoader.load_knowledge(AIManager.KNOWLEDGE_SOURCE)
            
            resumo_financeiro = "O usuário ainda não tem transações registradas."
            if df is not None and not df.empty:
                # Cálculos de Inteligência para Contexto
                gastos = df[df['type']=='Despesa']['amount'].sum()
                receitas = df[df['type']=='Receita']['amount'].sum()
                saldo = receitas - gastos
                
                # Identifica Salário Base (Última entrada marcada como Salário)
                mask_salario = df['category'].str.contains('Salário', case=False, na=False) & (df['type'] == 'Receita')
                df_sal = df[mask_salario].sort_values('date', ascending=False)
                salario_base = df_sal.iloc[0]['amount'] if not df_sal.empty else 0.0
                
                # Top categorias
                top_cats = df[df['type']=='Despesa'].groupby('category')['amount'].sum().sort_values(ascending=False).head(3)
                top_cats_str = ", ".join([f"{c}: R$ {v:.2f}" for c, v in top_cats.items()])
                
                resumo_financeiro = f"""
                === CONTEXTO ATUAL DO USUÁRIO (Dados Reais) ===
                - Saldo Atual (Caixa): R$ {saldo:.2f}
                - Total Gasto (Período): R$ {gastos:.2f}
                - Salário Base Identificado: R$ {salario_base:.2f} (Use este valor para cálculos de % como 50/30/20)
                - Top Categorias de Gasto: {top_cats_str}
                - Últimas 3 transações:
                {df.head(3)[['date', 'description', 'amount', 'category']].to_string(index=False)}
                """

            prompt = f"""
            ATUE COMO: Consultor Financeiro de Elite (Private Banking).
            
            SABEDORIA INTERNA (KNOWLEDGE BASE):
            {knowledge}
            
            DADOS DO CLIENTE:
            {resumo_financeiro}
            
            PERGUNTA DO USUÁRIO: "{user_question}"
            
            REGRAS OBRIGATÓRIAS (STRICT RULES):
            1. **DIFERENCIE RENDA**: Entenda que "Entradas Totais" podem incluir resgates. Use "Salário Base" para cálculos de orçamento mensal.
            2. **SIGILO TOTAL DA FONTE**: NUNCA mencione "apostila", "PDF", "texto fornecido". Internalize o conhecimento.
            3. **PERSONALIZAÇÃO**: Use os DADOS DO CLIENTE para dar exemplos.
            4. **TOM DE VOZ**: Profissional, direto, empático e prático.
            
            Responda em Markdown limpo.
            """
            
            models = ['gemini-1.5-flash', 'gemini-2.0-flash-exp', 'gemini-1.5-pro-latest']
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
    def coach_financeiro(df, renda_total_bruta, mkt):
        """
        Coach Financeiro Avançado (Auditor).
        Diferencia Salário Real de Entradas Totais (Resgates/Transferências).
        """
        knowledge_text = KnowledgeBaseLoader.load_knowledge(AIManager.KNOWLEDGE_SOURCE)
        if df.empty: return "Preciso de mais dados para gerar uma análise robusta."
        
        # 1. Isolamento do Salário Real (para cálculos de orçamento)
        mask_salario = (df['category'].str.contains('Salário', case=False, na=False)) & (df['type'] == 'Receita')
        df_salario = df[mask_salario].sort_values('date', ascending=False)
        
        salario_real = df_salario.iloc[0]['amount'] if not df_salario.empty else 0.0
        msg_salario = f"R$ {salario_real:.2f}" if salario_real > 0 else "Não identificado (Considere as Entradas Totais com cautela)"

        # 2. Dados de Despesas
        despesas = df[df['type'] == 'Despesa']
        total_despesas = despesas['amount'].sum()
        
        cats = despesas.groupby('category')['amount'].sum().sort_values(ascending=False)
        top_cat_nome = cats.index[0] if not cats.empty else "Nenhuma"
        top_cat_valor = cats.iloc[0] if not cats.empty else 0.0
        
        frequencia = despesas['description'].value_counts().head(3)
        item_frequente = frequencia.index[0] if not frequencia.empty else "Nenhum"
        
        prompt = f"""
        ATUE COMO: Um Auditor Financeiro Sênior e Consultor de Investimentos.
        
        BASE DE CONHECIMENTO TÉCNICO (Referência interna):
        {knowledge_text}
        
        PERFIL FINANCEIRO DO CLIENTE (DADOS REAIS):
        - Entradas Totais (Inclui resgates/pix): R$ {renda_total_bruta:.2f}
        - SALÁRIO MENSAL (Base para Regra 50/30/20): {msg_salario}  <-- IMPORTANTE: Use este valor para calcular % de gastos.
        - Despesa Total: R$ {total_despesas:.2f}
        - Maior Ralo de Dinheiro: Categoria '{top_cat_nome}' (R$ {top_cat_valor:.2f})
        - Gasto mais frequente: '{item_frequente}'
        - Cotação Atual: Dólar R$ {mkt.get('USD', 5.0):.2f}, Bitcoin R$ {mkt.get('BTC', 0):.2f}
        
        AMOSTRA DE TRANSAÇÕES (Detalhes):
        {df.head(20)[['date', 'description', 'amount', 'category']].to_string(index=False)}
        
        SUA MISSÃO (Relatório de Choque de Realidade):
        1. **DIAGNÓSTICO REALISTA:** Compare os gastos com o SALÁRIO MENSAL (se identificado), não com as entradas totais.
        2. **PADRÕES:** Aponte vícios específicos (ex: iFood, Uber).
        3. **PLANO DE AÇÃO:** Dê 3 passos concretos. Use valores monetários.
        4. **INVESTIMENTO:** Sugira alocação baseada no que sobra do SALÁRIO.
        
        REGRAS DE OURO:
        - **JAMAIS** mencione fontes (apostilas, pdfs).
        - Use formatação Markdown.
        """
        
        models = ['gemini-1.5-flash', 'gemini-2.0-flash-exp']
        for model_name in models:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                if response and response.text:
                    return AIManager._sanitize_output(response.text)
            except: continue
        return "Coach offline no momento."

    # =========================================================================
    #  NOVAS FUNCIONALIDADES (OFX & PDF) - Adicionadas sem remover nada
    # =========================================================================

    @staticmethod
    def enrich_transactions(transactions_list: List[Dict], user_categories: List[str]) -> List[Dict]:
        """
        [NOVO] Processamento Inteligente de OFX.
        Recebe transações brutas e usa IA para:
        1. Diferenciar Receita vs Despesa (crucial para OFX que vem tudo misturado).
        2. Categorizar com base na lista do usuário.
        3. Limpar descrições criptografadas de banco.
        """
        try:
            # Seleciona modelo rápido e eficiente para lotes
            model = genai.GenerativeModel('gemini-1.5-flash')
            cats_str = ", ".join(user_categories)
            
            # Limita a 30 transações por lote para garantir precisão e não estourar tokens
            data_str = json.dumps(transactions_list[:30], default=str)

            prompt = f"""
            ATUE COMO: Auditor de Extratos Bancários.
            CONTEXTO: Analise este JSON de transações bancárias (OFX).
            
            CATEGORIAS VÁLIDAS: [{cats_str}]
            
            REGRAS OBRIGATÓRIAS (CRÍTICO):
            1. **TIPO (Receita vs Despesa)**:
               - Valor negativo (< 0) -> "Despesa".
               - Valor positivo (> 0) E descrição contém "Depósito", "Pix Recebido", "Salário", "Resgate" -> "Receita".
               - Valor positivo (> 0) mas descrição é "Estorno" -> "Receita".
               - ATENÇÃO: Bancos as vezes mandam tudo positivo com sinalizador 'D' ou 'C'. 
               - Se descrição tiver "Compra", "Pgto", "Saque", "Debit" -> "Despesa".
               
            2. **CATEGORIZAÇÃO**:
               - Use a lista fornecida. Se não encaixar, use "Outros".
               
            3. **DESCRIÇÃO**:
               - Limpe códigos inúteis (Ex: "COMPRA ELO 1234 PADARIA" -> "Padaria").
            
            ENTRADA:
            {data_str}

            SAÍDA ESPERADA (Apenas JSON puro):
            [
                {{ "date": "YYYY-MM-DD", "description": "Nome Limpo", "amount": 100.50, "type": "Despesa", "category": "Alimentação" }}
            ]
            """
            
            response = model.generate_content(prompt)
            # Usa o parser robusto já existente na classe
            clean_list = AIManager._clean_json(response.text)
            
            if isinstance(clean_list, list):
                return clean_list
            return transactions_list # Retorna original se falhar

        except Exception as e:
            logging.error(f"Erro no enriquecimento OFX: {e}")
            return transactions_list

    @staticmethod
    def extract_transactions_from_text(raw_text: str) -> List[Dict]:
        """
        [NOVO] Extração de Transações de PDF (Texto Não Estruturado).
        Transforma o "copia e cola" de um PDF em JSON estruturado.
        """
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"""
            ATUE COMO: Extrator de Dados Financeiros (ETL).
            TAREFA: Converter texto bruto de extrato bancário (PDF) em JSON.
            
            TEXTO BRUTO:
            {raw_text[:30000]} 

            REGRAS DE EXTRAÇÃO:
            1. Ignore cabeçalhos, saldos parciais e rodapés. Foque nas TRANSAÇÕES.
            2. Identifique DATA, DESCRIÇÃO, VALOR.
            3. **TIPO**: 
               - Se tiver sinal de menos (-) ou coluna DÉBITO -> "Despesa".
               - Se for CRÉDITO, DEPÓSITO, SALÁRIO -> "Receita".
            4. **VALOR**: Retorne sempre positivo (float absolute). O tipo define o sinal.
            
            SAÍDA (JSON List):
            [
                {{ "date": "YYYY-MM-DD", "description": "Resumo", "amount": 50.00, "type": "Despesa" }}
            ]
            """
            
            response = model.generate_content(prompt)
            extracted_data = AIManager._clean_json(response.text)
            
            if isinstance(extracted_data, list):
                return extracted_data
            return []

        except Exception as e:
            logging.error(f"Erro na extração de PDF: {e}")
            return []
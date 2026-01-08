"""
SmartWallet Portfolio
Sistema de Gestão Financeira Inteligente com Processamento de Linguagem Natural (NLP).
Desenvolvido como projeto de portfólio para demonstração de habilidades técnicas em Python, Streamlit e integração com LLMs.

Author: Fernando Teixeira do Nascimento
Date: 08/01/2026
Version: 1.0.0
"""

import streamlit as st
import google.generativeai as genai
import pandas as pd
import sqlite3
import plotly.express as px
import requests
import json
import re
import time
from datetime import datetime

# --- CONFIGURAÇÃO DO AMBIENTE E LAYOUT ---
st.set_page_config(
    page_title="SmartWallet | Gestão Financeira",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- GERENCIAMENTO DE CREDENCIAIS E SEGURANÇA ---
def configure_api():
    """
    Configura a conexão com a API de LLM utilizando variáveis de ambiente seguras.
    Requer o arquivo .streamlit/secrets.toml configurado.
    """
    try:
        # Tenta recuperar a chave dos segredos do ambiente (Melhor Prática de Segurança)
        api_key = st.secrets.get("GEMINI_KEY")
        if not api_key:
            raise ValueError("Chave de API não detectada nos segredos do ambiente.")
        genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"Erro de Configuração de Ambiente: {e}")
        st.stop()

configure_api()

# --- ESTILIZAÇÃO CSS (INTERFACE MODERNA) ---
st.markdown("""
    <style>
    /* Animações de Feedback Visual (Market Data) */
    @keyframes blink-up {
        0% { background-color: #0E1117; border-color: #444; }
        50% { background-color: rgba(76, 175, 80, 0.15); border-color: #4CAF50; transform: scale(1.01); }
        100% { background-color: #0E1117; border-color: #444; }
    }
    @keyframes blink-down {
        0% { background-color: #0E1117; border-color: #444; }
        50% { background-color: rgba(244, 67, 54, 0.15); border-color: #F44336; transform: scale(1.01); }
        100% { background-color: #0E1117; border-color: #444; }
    }

    /* Componentes de UI */
    .market-card { 
        background-color: #0E1117; 
        border: 1px solid #333; 
        border-radius: 8px; 
        padding: 12px; 
        text-align: center;
        transition: border-color 0.3s ease;
    }
    .anim-up { animation: blink-up 1.2s ease-out; }
    .anim-down { animation: blink-down 1.2s ease-out; }
    
    .label-coin { font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 4px; }
    .value-coin { font-size: 20px; font-weight: 600; font-family: 'Roboto Mono', monospace; }
    .trend-up { color: #4CAF50; }
    .trend-down { color: #F44336; }
    .trend-flat { color: #E0E0E0; }
    
    /* Ajustes Gerais */
    div[data-testid="stMetricValue"] { font-size: 24px; }
    </style>
""", unsafe_allow_html=True)

# --- CAMADA DE PERSISTÊNCIA (DAO) ---
class TransactionDAO:
    """Data Access Object para manipulação segura e transacional do SQLite."""
    
    def __init__(self, db_path='smartwallet.db'):
        self.db_path = db_path
        self._init_schema()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_schema(self):
        """Inicializa o esquema do banco de dados com tratamento de exceção."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT,
                    description TEXT,
                    type TEXT
                )
            ''')
            conn.commit()
        except sqlite3.Error as e:
            st.error(f"Erro crítico de I/O no banco de dados: {e}")
        finally:
            if conn: conn.close()

    def insert_transaction(self, date, amount, category, description, type_):
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transactions (date, amount, category, description, type) 
                VALUES (?, ?, ?, ?, ?)''', (date, amount, category, description, type_))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            if conn: conn.close()

    def fetch_all(self):
        conn = None
        try:
            conn = self._get_connection()
            return pd.read_sql_query("SELECT * FROM transactions ORDER BY date DESC, id DESC", conn)
        except Exception:
            return pd.DataFrame()
        finally:
            if conn: conn.close()

# Instância Global do Gerenciador de Banco de Dados
db_manager = TransactionDAO()

# --- SERVIÇO DE DADOS DE MERCADO ---
def fetch_market_data():
    """
    Obtém cotações em tempo real via API pública.
    Inclui timeout para evitar latência na interface.
    """
    try:
        response = requests.get("https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,GBP-BRL,BTC-BRL", timeout=2)
        response.raise_for_status()
        data = response.json()
        return {
            "USD": float(data['USDBRL']['bid']),
            "EUR": float(data['EURBRL']['bid']),
            "GBP": float(data['GBPBRL']['bid']),
            "BTC": float(data['BTCBRL']['bid']),
            "status": "online"
        }
    except Exception:
        # Fallback values em caso de indisponibilidade da API
        return {"USD": 0.0, "EUR": 0.0, "GBP": 0.0, "BTC": 0.0, "status": "offline"}

# --- PROCESSAMENTO DE LINGUAGEM NATURAL (NLP) ---
def process_natural_language_input(text, market_data):
    """
    Pipeline de processamento de texto livre utilizando modelo generativo.
    Implementa estratégia de fallback de modelos para alta disponibilidade.
    """
    prompt = f"""
    Role: Financial Data Parser.
    Context Date: {datetime.now().strftime('%Y-%m-%d')}
    User Input: "{text}"
    Reference Rates: USD={market_data['USD']}, EUR={market_data['EUR']}
    
    Task:
    1. Identify transaction type ('Receita' or 'Despesa').
    2. Convert foreign currencies to BRL using reference rates.
    3. Format description in formal Portuguese (Capitalized).
    4. If conversion occurs, append "(Orig: CURRENCY VALUE)" to description.
    
    Output Format (JSON Only):
    {{ "amount": float, "category": "string", "date": "YYYY-MM-DD", "description": "string", "type": "Receita" or "Despesa" }}
    """
    
    # Ordem de prioridade de modelos (Performance > Compatibilidade)
    models = ['gemini-2.5-flash', 'gemini-pro', 'gemini-1.5-flash']
    
    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            
            # Sanitização da resposta JSON (Remoção de Markdown)
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            match = re.search(r'\{.*\}', clean_text, re.DOTALL)
            
            if match:
                payload = json.loads(match.group(0))
                # Validação de integridade do payload
                if all(k in payload for k in ('amount', 'category', 'type')):
                    return payload
        except Exception:
            continue # Failover silencioso para o próximo modelo
            
    return {"error": "Não foi possível processar a solicitação no momento."}

def generate_financial_report(df):
    """Gera análise qualitativa executiva baseada no histórico de transações."""
    if df.empty: return "Dados insuficientes para análise."
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""
        Analyst Role: Senior Financial Advisor.
        Data Context: \n{df.to_string()}\n
        
        Objective: Provide a formal, rational, and actionable financial assessment using Portuguese.
        Structure:
        1. Diagnóstico de Saúde Financeira.
        2. Identificação de Gargalos.
        3. Plano de Ação (3 pontos estratégicos).
        """
        return model.generate_content(prompt).text
    except Exception:
        return "Serviço de análise indisponível temporariamente."

# --- COMPONENTES DE UI (Auto-Update) ---
@st.fragment(run_every=10)
def render_market_ticker():
    """Renderiza o cabeçalho de cotações com atualização automática via Fragmentos."""
    
    # Persistência de estado para cálculo de tendência
    if 'market_cache' not in st.session_state:
        st.session_state['market_cache'] = fetch_market_data()
    
    previous_data = st.session_state['market_cache']
    current_data = fetch_market_data()
    st.session_state['market_cache'] = current_data
    
    # Layout do Cabeçalho
    c_header, c_meta = st.columns([3, 1])
    with c_header:
        st.title(f"📊 SmartWallet | {datetime.now().strftime('%d/%m/%Y')}")
    with c_meta:
        status_color = "🟢" if current_data['status'] == "online" else "🔴"
        st.caption(f"{status_color} Data Feed: {current_data['status'].upper()} | {datetime.now().strftime('%H:%M:%S')}")

    # Grid de Cotações
    cols = st.columns(4)
    assets = [("USD", "Dólar Comercial"), ("EUR", "Euro"), ("GBP", "Libra Esterlina"), ("BTC", "Bitcoin")]

    for idx, (symbol, label) in enumerate(assets):
        curr_val = current_data.get(symbol, 0)
        prev_val = previous_data.get(symbol, 0)
        
        # Lógica de Animação CSS baseada na variação de preço
        anim_class = ""
        trend_class = "trend-flat"
        icon = ""
        
        if curr_val > prev_val:
            anim_class = "anim-up"
            trend_class = "trend-up"
            icon = "▲"
        elif curr_val < prev_val:
            anim_class = "anim-down"
            trend_class = "trend-down"
            icon = "▼"
            
        with cols[idx]:
            st.markdown(f"""
            <div class="market-card {anim_class}">
                <div class="label-coin">{label} ({symbol})</div>
                <div class="value-coin {trend_class}">R$ {curr_val:,.2f} {icon}</div>
            </div>
            """, unsafe_allow_html=True)

# --- EXECUÇÃO PRINCIPAL ---
def main():
    render_market_ticker()
    st.divider()

    # Contexto de Dados Atual (Snapshot)
    current_market = st.session_state.get('market_cache', fetch_market_data())

    # Navegação Principal
    tabs = st.tabs(["🤖 Input Inteligente", "✍️ Registro Manual", "📈 Analytics", "📑 Extrato", "🧠 Consultoria"])

    # 1. INPUT NLP
    with tabs[0]:
        st.markdown("#### Registro via Linguagem Natural")
        with st.form("nlp_form", clear_on_submit=True):
            user_input = st.text_input("Descreva a transação:", placeholder="Ex: Recebi 4500 de salário ou Gastei 120 no restaurante")
            submitted = st.form_submit_button("Processar Registro")
        
        if submitted and user_input:
            with st.spinner("Processando..."):
                result = process_natural_language_input(user_input, current_market)
                if "error" in result:
                    st.error(result["error"])
                else:
                    saved = db_manager.insert_transaction(
                        result['date'], result['amount'], result['category'], result['description'], result['type']
                    )
                    if saved:
                        msg_type = "Receita" if result['type'] == 'Receita' else "Despesa"
                        st.success(f"{msg_type} registrada: R$ {result['amount']:.2f} ({result['description']})")

    # 2. INPUT MANUAL
    with tabs[1]:
        st.markdown("#### Registro Estruturado")
        col_type, col_val = st.columns([1, 2])
        trans_type = col_type.radio("Tipo:", ["Receita", "Despesa"], horizontal=True)
        
        categories = ["Salário", "Investimentos", "Outros"] if trans_type == "Receita" else \
                     ["Alimentação", "Moradia", "Transporte", "Lazer", "Educação", "Saúde", "Serviços", "Outros"]
        
        amount = col_val.number_input("Valor (BRL)", min_value=0.0, step=10.0, format="%.2f")
        category = st.selectbox("Categoria", categories)
        desc = st.text_input("Descrição", placeholder="Detalhes opcionais")
        
        if st.button("Salvar Registro"):
            if amount > 0:
                db_manager.insert_transaction(datetime.now(), amount, category, desc or category, trans_type)
                st.success("Registro salvo com sucesso.")
            else:
                st.warning("O valor deve ser positivo.")

    # 3. ANALYTICS (DASHBOARD)
    with tabs[2]:
        df = db_manager.fetch_all()
        if not df.empty:
            income = df[df['type'] == 'Receita']['amount'].sum()
            expense = df[df['type'] == 'Despesa']['amount'].sum()
            balance = income - expense
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Entradas Totais", f"R$ {income:,.2f}")
            c2.metric("Saídas Totais", f"R$ {expense:,.2f}")
            c3.metric("Saldo Líquido", f"R$ {balance:,.2f}", delta="Positivo" if balance >= 0 else "Negativo")
            
            st.divider()
            
            st.subheader("Análise de Despesas por Categoria")
            expense_data = df[df['type'] == 'Despesa'].groupby("category")['amount'].sum().reset_index()
            
            if not expense_data.empty:
                fig = px.pie(expense_data, values='amount', names='category', 
                             color_discrete_sequence=px.colors.qualitative.Prism,
                             hole=0.4)
                fig.update_traces(textposition='outside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sem dados de despesa para visualização.")
        else:
            st.warning("Aguardando dados para gerar visualizações.")

    # 4. EXTRATO (GRID)
    with tabs[3]:
        df = db_manager.fetch_all()
        if not df.empty:
            display_df = df.rename(columns={
                'date': 'Data', 'amount': 'Valor', 'category': 'Categoria', 
                'description': 'Descrição', 'type': 'Tipo'
            })[['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor']]
            
            def apply_style(styler):
                styler.set_properties(**{'text-align': 'center', 'border': '1px solid #333'})
                styler.set_table_styles([{'selector': 'th', 'props': [('background-color', '#262730'), ('color', 'white')]}])
                styler.apply(lambda x: ['background-color: rgba(76, 175, 80, 0.2); color: #fff' if x['Tipo'] == 'Receita' 
                                      else 'background-color: rgba(244, 67, 54, 0.2); color: #fff' for _ in x], axis=1)
                styler.format({'Valor': 'R$ {:,.2f}'})
                return styler

            st.dataframe(apply_style(display_df.style), use_container_width=True, hide_index=True)
            
            if st.button("Reiniciar Banco de Dados"):
                try:
                    import os
                    if os.path.exists("smartwallet.db"): os.remove("smartwallet.db")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao reiniciar: {e}")

    # 5. CONSULTORIA
    with tabs[4]:
        st.markdown("#### Consultoria Financeira Avançada")
        if st.button("Solicitar Diagnóstico"):
            df = db_manager.fetch_all()
            if not df.empty:
                with st.spinner("Gerando análise..."):
                    report = generate_financial_report(df)
                    st.markdown("---")
                    st.markdown(report)
            else:
                st.warning("É necessário histórico financeiro para esta análise.")

if __name__ == "__main__":
    main()

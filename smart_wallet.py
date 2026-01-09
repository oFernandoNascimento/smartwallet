"""
SmartWallet Portfolio
Sistema de Gestão Financeira Inteligente com Processamento de Linguagem Natural (NLP).
Desenvolvido como projeto de portfólio para demonstração de habilidades técnicas em Python, Streamlit e integração com LLMs.

Author: Fernando Teixeira do Nascimento
Date: 08/01/2026
Version: 2.2.0 (SQLite Persistence Edition)
"""

import streamlit as st
import google.generativeai as genai
import pandas as pd
import plotly.express as px
import requests
import json
import re
import time
import pytz
import sqlite3  # Novo import para o Banco de Dados
from datetime import datetime

# --- CONFIGURAÇÃO GLOBAL DE FUSO HORÁRIO ---
fuso_br = pytz.timezone('America/Sao_Paulo')

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
            # Fallback opcional ou erro
            # genai.configure(api_key="SUA_KEY_AQUI") # Apenas para teste local sem secrets
            pass 
        else:
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

# --- CAMADA DE PERSISTÊNCIA (SQLITE3) ---
class TransactionDAO:
    """
    Gerenciador de dados persistente usando SQLite.
    Substitui o armazenamento em sessão para salvar dados permanentemente em arquivo.
    """
    
    def __init__(self, db_name="smartwallet.db"):
        self.db_name = db_name
        self.init_db()

    def get_connection(self):
        """Estabelece conexão com o banco de dados"""
        return sqlite3.connect(self.db_name, check_same_thread=False)

    def init_db(self):
        """Cria a tabela de transações se ela não existir"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT,
                        date TEXT,
                        amount REAL,
                        category TEXT,
                        description TEXT,
                        type TEXT
                    )
                """)
                conn.commit()
        except Exception as e:
            st.error(f"Erro ao inicializar banco de dados: {e}")

    def insert_transaction(self, user_id, date, amount, category, description, type_):
        """Insere uma nova transação vinculada a um usuário (wallet_id)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO transactions (user_id, date, amount, category, description, type)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, str(date), float(amount), category, description, type_))
                conn.commit()
            return True
        except Exception:
            return False

    def fetch_all(self, user_id):
        """Busca todas as transações de um usuário específico"""
        try:
            with self.get_connection() as conn:
                # Carrega dados filtrando pelo user_id
                df = pd.read_sql_query(
                    "SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC, id DESC", 
                    conn, 
                    params=(user_id,)
                )
            
            # Se o dataframe estiver vazio, retorna estrutura vazia com as colunas corretas
            if df.empty:
                return pd.DataFrame(columns=['id', 'user_id', 'date', 'amount', 'category', 'description', 'type'])
            
            return df
        except Exception:
            return pd.DataFrame(columns=['id', 'user_id', 'date', 'amount', 'category', 'description', 'type'])
            
    def clear_data(self, user_id):
        """Remove apenas os dados do usuário atual"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM transactions WHERE user_id = ?", (user_id,))
                conn.commit()
            return True
        except Exception:
            return False

# Instância Global do Gerenciador de Banco de Dados
db_manager = TransactionDAO()

# --- SERVIÇO DE DADOS DE MERCADO ---
def fetch_market_data():
    """
    Obtém cotações utilizando Frankfurter (Moedas Fiat) e AwesomeAPI (Bitcoin).
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 1. Valores de segurança (Fallback)
    market_data = {
        "USD": 5.39,
        "EUR": 6.28,
        "GBP": 7.24,
        "BTC": 490775.00,
        "status": "offline" 
    }
    
    try:
        # 2. Busca Dados Fiat (Frankfurter API)
        resp_usd = requests.get("https://api.frankfurter.app/latest?from=USD&to=BRL", headers=headers, timeout=2)
        if resp_usd.status_code == 200:
            market_data["USD"] = float(resp_usd.json()['rates']['BRL'])
            market_data["status"] = "online"

        resp_eur = requests.get("https://api.frankfurter.app/latest?from=EUR&to=BRL", headers=headers, timeout=2)
        if resp_eur.status_code == 200:
            market_data["EUR"] = float(resp_eur.json()['rates']['BRL'])

        resp_gbp = requests.get("https://api.frankfurter.app/latest?from=GBP&to=BRL", headers=headers, timeout=2)
        if resp_gbp.status_code == 200:
            market_data["GBP"] = float(resp_gbp.json()['rates']['BRL'])

        # 3. Busca Bitcoin via AwesomeAPI
        resp_btc = requests.get("https://economia.awesomeapi.com.br/last/BTC-BRL", headers=headers, timeout=2)
        if resp_btc.status_code == 200:
            btc_val = resp_btc.json()['BTCBRL']['bid']
            market_data["BTC"] = float(btc_val)

    except Exception as e:
        pass
        
    return market_data

# --- PROCESSAMENTO DE LINGUAGEM NATURAL (NLP) ---
def process_natural_language_input(text, market_data):
    """
    Pipeline de processamento de texto livre utilizando modelo generativo.
    """
    prompt = f"""
    Role: Financial Data Parser.
    Context Date: {datetime.now(fuso_br).strftime('%Y-%m-%d')}
    User Input: "{text}"
    Reference Rates: USD={market_data['USD']}, EUR={market_data['EUR']}, GBP={market_data['GBP']}, BTC={market_data['BTC']}
    
    Task:
    1. Identify transaction type ('Receita' or 'Despesa').
    2. Convert foreign currencies to BRL using reference rates.
    3. Format description in formal Portuguese (Capitalized).
    4. If conversion occurs, append "(Orig: CURRENCY VALUE)" to description.
    5. CRITICAL: If the user is BUYING an asset (Bitcoin, Stock, Dollar for holding), calculate the quantity = (Amount_BRL / Rate) and append "(Qty: X.XXXX ASSET)" to the description.
       Example: "Comprei 1500 reais de Bitcoin" -> Description: "Aquisição de Bitcoin (Qty: 0.003056 BTC)".
       Mark category as "Investimentos".
    
    Output Format (JSON Only):
    {{ "amount": float, "category": "string", "date": "YYYY-MM-DD", "description": "string", "type": "Receita" or "Despesa" }}
    """
    
    models = ['gemini-2.5-flash', 'gemini-pro', 'gemini-1.5-flash']
    
    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            
            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            match = re.search(r'\{.*\}', clean_text, re.DOTALL)
            
            if match:
                payload = json.loads(match.group(0))
                if all(k in payload for k in ('amount', 'category', 'type')):
                    return payload
        except Exception:
            continue
            
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
    
    if 'market_cache' not in st.session_state:
        st.session_state['market_cache'] = fetch_market_data()
    
    previous_data = st.session_state['market_cache']
    current_data = fetch_market_data()
    st.session_state['market_cache'] = current_data
    
    c_header, c_meta = st.columns([3, 1])
    with c_header:
        st.title(f"📊 SmartWallet | {datetime.now(fuso_br).strftime('%d/%m/%Y')}")
    with c_meta:
        status_color = "🟢" if current_data['status'] == "online" else "🔴"
        st.caption(f"{status_color} Data Feed: {current_data['status'].upper()} | {datetime.now(fuso_br).strftime('%H:%M:%S')}")

    cols = st.columns(4)
    assets = [("USD", "Dólar Comercial"), ("EUR", "Euro"), ("GBP", "Libra Esterlina"), ("BTC", "Bitcoin")]

    for idx, (symbol, label) in enumerate(assets):
        curr_val = current_data.get(symbol, 0)
        prev_val = previous_data.get(symbol, 0)
        
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
    
    # --- BARRA LATERAL PARA LOGIN / IDENTIFICAÇÃO ---
    with st.sidebar:
        st.header("🔐 Acesso")
        # Define um ID padrão para não quebrar na primeira execução
        wallet_id = st.text_input("ID do Usuário / Carteira", value="Demonstracao", help="Digite seu nome ou ID para carregar seus dados salvos.")
        st.info(f"Conectado como: {wallet_id}")
        st.divider()

    st.divider()

    current_market = st.session_state.get('market_cache', fetch_market_data())

    # Abas Principais
    tabs = st.tabs(["🤖 Input Inteligente", "✍️ Registro Manual", "📈 Analytics", "💰 Investimentos", "📑 Extrato", "🧠 Consultoria"])

    # 1. INPUT NLP
    with tabs[0]:
        st.markdown("#### 🗣️ Diga para a IA o que você gastou ou recebeu")
        with st.form("nlp_form", clear_on_submit=True):
            user_input = st.text_input(
                "Descreva sua movimentação:", 
                placeholder="Ex: Gastei 20 na farmácia, Recebi 1500 de salário ou Comprei 1500 reais em Bitcoin"
            )
            submitted = st.form_submit_button("Processar via Inteligência Artificial")
        
        if submitted and user_input:
            with st.spinner("A IA está analisando sua transação..."):
                result = process_natural_language_input(user_input, current_market)
                if "error" in result:
                    st.error(result["error"])
                else:
                    # Passa o wallet_id para salvar no usuário correto
                    saved = db_manager.insert_transaction(
                        wallet_id, result['date'], result['amount'], result['category'], result['description'], result['type']
                    )
                    if saved:
                        msg_type = "Receita" if result['type'] == 'Receita' else "Despesa"
                        st.success(f"{msg_type} identificada: R$ {result['amount']:.2f} ({result['description']})")

    # 2. INPUT MANUAL
    with tabs[1]:
        st.markdown("#### Registro Estruturado")
        col_type, col_val = st.columns([1, 2])
        trans_type = col_type.radio("Tipo:", ["Receita", "Despesa"], horizontal=True)
        
        categories = ["Salário", "Investimentos", "Outros"] if trans_type == "Receita" else \
                     ["Alimentação", "Moradia", "Transporte", "Lazer", "Educação", "Saúde", "Investimentos", "Serviços", "Outros"]
        
        amount = col_val.number_input("Valor (BRL)", min_value=0.0, step=10.0, format="%.2f")
        category = st.selectbox("Categoria", categories)
        desc = st.text_input("Descrição", placeholder="Detalhes opcionais")
        
        if st.button("Salvar Registro"):
            if amount > 0:
                # Passa o wallet_id
                db_manager.insert_transaction(wallet_id, datetime.now(fuso_br), amount, category, desc or category, trans_type)
                st.success("Registro salvo com sucesso.")
            else:
                st.warning("O valor deve ser positivo.")

    # 3. ANALYTICS (DASHBOARD)
    with tabs[2]:
        # Busca dados apenas do usuário logado
        df = db_manager.fetch_all(wallet_id)
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

    # 4. INVESTIMENTOS
    with tabs[3]:
        st.subheader("Carteira de Investimentos")
        df = db_manager.fetch_all(wallet_id)
        
        if not df.empty:
            invest_df = df[df['category'].isin(['Investimentos', 'Investimento'])]
            
            if not invest_df.empty:
                total_invested = invest_df['amount'].sum()
                st.metric("Total Investido", f"R$ {total_invested:,.2f}")
                
                grouped_invest = invest_df.groupby('description')['amount'].sum().reset_index().sort_values(by='amount', ascending=False)
                grouped_invest.columns = ['Ativo / Descrição', 'Valor Total (R$)']
                
                st.table(grouped_invest.style.format({'Valor Total (R$)': 'R$ {:,.2f}'}))
            else:
                st.info("Nenhum registro classificado como 'Investimentos' encontrado.")
        else:
            st.warning("Sem dados.")

    # 5. EXTRATO (GRID)
    with tabs[4]:
        df = db_manager.fetch_all(wallet_id)
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
            
            if st.button("Limpar Dados desta Carteira"):
                try:
                    db_manager.clear_data(wallet_id)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao reiniciar: {e}")

    # 6. CONSULTORIA
    with tabs[5]:
        st.markdown("#### Consultoria Financeira Avançada")
        if st.button("Solicitar Diagnóstico"):
            df = db_manager.fetch_all(wallet_id)
            if not df.empty:
                with st.spinner("Gerando análise..."):
                    report = generate_financial_report(df)
                    st.markdown("---")
                    st.markdown(report)
            else:
                st.warning("É necessário histórico financeiro para esta análise.")
    
    # --- RODAPÉ DE COPYRIGHT ---
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666; font-size: 12px; margin-top: 20px;'>
            © 2026 SmartWallet Portfolio. Developed by Fernando Teixeira do Nascimento. All rights reserved.
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()

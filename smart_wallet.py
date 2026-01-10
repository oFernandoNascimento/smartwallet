"""
SmartWallet Portfolio
Sistema de Gestão Financeira Inteligente com Processamento de Linguagem Natural (NLP).
Desenvolvido como projeto de portfólio para demonstração de habilidades técnicas em Python, Streamlit e integração com LLMs.

Author: Fernando Teixeira do Nascimento
Date: 10/01/2026
Version: 4.2.2 (Fix NameError Bug & Excel)
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
import hashlib
import psycopg2 # Conector PostgreSQL
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
    """
    try:
        api_key = st.secrets.get("GEMINI_KEY")
        if not api_key:
            pass 
        else:
            genai.configure(api_key=api_key)
            
        # Verificação extra para o Banco de Dados
        if not st.secrets.get("DATABASE_URL"):
            st.warning("⚠️ Atenção: 'DATABASE_URL' não encontrada. O banco na nuvem não funcionará.")
            
    except Exception as e:
        st.error(f"Erro de Configuração de Ambiente: {e}")
        st.stop()

configure_api()

# --- ESTILIZAÇÃO CSS (INTERFACE MODERNA & LOGIN) ---
st.markdown("""
    <style>
    /* =========================================
       ESTILOS DA TELA DE LOGIN
       ========================================= */
    .login-container {
        background-color: #1E1E1E;
        padding: 40px;
        border-radius: 15px;
        border: 1px solid #333;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        text-align: center;
        margin-bottom: 20px;
    }
    .login-header {
        font-size: 28px;
        font-weight: bold;
        color: #4CAF50;
        margin-bottom: 10px;
        font-family: 'Roboto', sans-serif;
    }
    .login-sub {
        font-size: 14px;
        color: #aaa;
        margin-bottom: 30px;
    }
    
    /* =========================================
       ESTILOS ORIGINAIS DO APP
       ========================================= */
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
    
    div[data-testid="stMetricValue"] { font-size: 24px; }
    </style>
""", unsafe_allow_html=True)

# --- CAMADA DE PERSISTÊNCIA (POSTGRESQL - NUVEM) ---
class CloudTransactionDAO:
    """
    Gerenciador de Banco de Dados Híbrido:
    1. Gerencia Usuários (Criptografia SHA-256)
    2. Gerencia Transações Financeiras (Na Nuvem/Supabase)
    """
    
    def __init__(self):
        self.init_db()

    def get_connection(self):
        """Estabelece conexão com o Supabase via URL"""
        return psycopg2.connect(st.secrets["DATABASE_URL"])

    def _hash_password(self, password):
        """Cria hash da senha para segurança"""
        return hashlib.sha256(password.encode()).hexdigest()

    def init_db(self):
        """Inicializa as tabelas de Usuários e Transações"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    
                    # Tabela de Usuários
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            username TEXT PRIMARY KEY,
                            password_hash TEXT NOT NULL,
                            created_at TEXT
                        );
                    """)
                    
                    # Tabela de Transações
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS transactions (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT,
                            date TEXT,
                            amount REAL,
                            category TEXT,
                            description TEXT,
                            type TEXT,
                            FOREIGN KEY(user_id) REFERENCES users(username)
                        );
                    """)
                    conn.commit()
        except Exception as e:
            st.error(f"Erro Crítico de Banco de Dados: {e}")

    # --- MÉTODOS DE AUTENTICAÇÃO ---
    def create_user(self, username, password):
        if not username or not password:
            return False, "Usuário e senha são obrigatórios."
            
        pwd_hash = self._hash_password(password)
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO users (username, password_hash, created_at) VALUES (%s, %s, %s)",
                        (username, pwd_hash, str(datetime.now()))
                    )
                    conn.commit()
            return True, "Conta criada com sucesso! Faça login."
        except psycopg2.IntegrityError:
            return False, "Este nome de usuário já está em uso."
        except Exception as e:
            return False, f"Erro ao criar conta: {e}"

    def verify_login(self, username, password):
        pwd_hash = self._hash_password(password)
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT username FROM users WHERE username = %s AND password_hash = %s", 
                        (username, pwd_hash)
                    )
                    user = cursor.fetchone()
                return user is not None
        except Exception:
            return False

    # --- MÉTODOS FINANCEIROS ---
    def insert_transaction(self, user_id, date, amount, category, description, type_):
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO transactions (user_id, date, amount, category, description, type)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (user_id, str(date), float(amount), category, description, type_))
                    conn.commit()
            return True
        except Exception:
            return False

    def fetch_all(self, user_id):
        try:
            with self.get_connection() as conn:
                df = pd.read_sql_query(
                    "SELECT * FROM transactions WHERE user_id = %s ORDER BY date DESC, id DESC", 
                    conn, 
                    params=(user_id,)
                )
            if df.empty:
                return pd.DataFrame(columns=['id', 'user_id', 'date', 'amount', 'category', 'description', 'type'])
            return df
        except Exception:
            return pd.DataFrame(columns=['id', 'user_id', 'date', 'amount', 'category', 'description', 'type'])
            
    def clear_data(self, user_id):
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM transactions WHERE user_id = %s", (user_id,))
                    conn.commit()
            return True
        except Exception:
            return False

# Instância Global
db_manager = CloudTransactionDAO()

# --- SERVIÇO DE DADOS DE MERCADO ---
def fetch_market_data():
    headers = {"User-Agent": "Mozilla/5.0"}
    market_data = {
        "USD": 5.39, "EUR": 6.28, "GBP": 7.24, "BTC": 490775.00, "status": "offline" 
    }
    try:
        resp_usd = requests.get("https://api.frankfurter.app/latest?from=USD&to=BRL", headers=headers, timeout=2)
        if resp_usd.status_code == 200:
            market_data["USD"] = float(resp_usd.json()['rates']['BRL'])
            market_data["status"] = "online"
        
        # Warm-up calls
        requests.get("https://api.frankfurter.app/latest?from=EUR&to=BRL", headers=headers, timeout=1)
        requests.get("https://api.frankfurter.app/latest?from=GBP&to=BRL", headers=headers, timeout=1)
        
        resp_btc = requests.get("https://economia.awesomeapi.com.br/last/BTC-BRL", headers=headers, timeout=2)
        if resp_btc.status_code == 200:
            btc_val = resp_btc.json()['BTCBRL']['bid']
            market_data["BTC"] = float(btc_val)
    except Exception:
        pass
    return market_data

# --- PROCESSAMENTO DE LINGUAGEM NATURAL (NLP) ---
def process_natural_language_input(text, market_data):
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
    5. Calculate asset quantity if buying assets.
    
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
    if df.empty: return "Dados insuficientes para análise."
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""
        Analyst Role: Senior Financial Advisor.
        Data Context: \n{df.to_string()}\n
        Objective: Provide a formal financial assessment in Portuguese.
        Structure: 1. Diagnóstico, 2. Gargalos, 3. Plano de Ação.
        """
        return model.generate_content(prompt).text
    except Exception:
        return "Serviço de análise indisponível temporariamente."

# --- COMPONENTES DE UI (TICKER) ---
@st.fragment(run_every=10)
def render_market_ticker():
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
        st.caption(f"{status_color} Feed: {current_data['status'].upper()} | ☁️ Nuvem Conectada")

    cols = st.columns(4)
    assets = [("USD", "Dólar"), ("EUR", "Euro"), ("GBP", "Libra"), ("BTC", "Bitcoin")]

    for idx, (symbol, label) in enumerate(assets):
        curr_val = current_data.get(symbol, 0)
        prev_val = previous_data.get(symbol, 0)
        
        anim_class = "anim-up" if curr_val > prev_val else "anim-down" if curr_val < prev_val else ""
        trend_class = "trend-up" if curr_val > prev_val else "trend-down" if curr_val < prev_val else "trend-flat"
        icon = "▲" if curr_val > prev_val else "▼" if curr_val < prev_val else ""
            
        with cols[idx]:
            st.markdown(f"""
            <div class="market-card {anim_class}">
                <div class="label-coin">{label} ({symbol})</div>
                <div class="value-coin {trend_class}">R$ {curr_val:,.2f} {icon}</div>
            </div>
            """, unsafe_allow_html=True)

# --- FUNÇÃO DE CONTROLE DE LOGIN (MANTIDA) ---
def login_flow():
    """
    Gerencia a interface de Login/Registro.
    """
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['username'] = None

    if st.session_state['logged_in']:
        return st.session_state['username']

    # --- TELA DE LOGIN ---
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div class="login-container">
            <div class="login-header">🔐 SmartWallet Cloud</div>
            <div class="login-sub">Gerenciamento financeiro seguro e na Nuvem</div>
        </div>
        """, unsafe_allow_html=True)

        tab_login, tab_register = st.tabs(["🔑 Entrar na Conta", "📝 Criar Nova Conta"])

        # ABA: LOGIN
        with tab_login:
            with st.form("login_form", clear_on_submit=True):
                user_login = st.text_input("Usuário", placeholder="Seu nome de usuário", key="access_code_secure")
                pass_login = st.text_input("Senha", type="password", placeholder="Sua senha secreta", key="pass_code_secure")
                submit_login = st.form_submit_button("Acessar Painel", type="primary", use_container_width=True)

                if submit_login:
                    if db_manager.verify_login(user_login, pass_login):
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = user_login
                        st.toast(f"Bem-vindo de volta, {user_login}!", icon="🎉")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Usuário ou senha incorretos.")

        # ABA: REGISTRO
        with tab_register:
            with st.form("register_form", clear_on_submit=True):
                st.info("Crie um usuário único para proteger seus dados na nuvem.")
                new_user = st.text_input("Escolha um Usuário", placeholder="Ex: fernando.silva", key="new_registry_secure")
                new_pass = st.text_input("Escolha uma Senha", type="password", key="new_registry_pass_secure")
                new_pass_confirm = st.text_input("Confirme a Senha", type="password", key="new_registry_pass_conf_secure")
                submit_register = st.form_submit_button("Criar Conta", use_container_width=True)

                if submit_register:
                    if new_pass != new_pass_confirm:
                        st.error("As senhas não coincidem.")
                    elif len(new_pass) < 4:
                        st.warning("A senha deve ter pelo menos 4 caracteres.")
                    else:
                        success, message = db_manager.create_user(new_user, new_pass)
                        if success:
                            st.success(message)
                        else:
                            st.error(message)

    st.stop()

# --- EXECUÇÃO PRINCIPAL (APP) ---
def main():
    # 1. Verifica autenticação
    current_user = login_flow()

    # 2. Barra lateral
    with st.sidebar:
        st.header("👤 Perfil")
        st.success(f"Usuário: **{current_user}**")
        if st.button("Sair / Logout", type="secondary"):
            st.session_state['logged_in'] = False
            st.session_state['username'] = None
            st.rerun()
        st.divider()
        st.info("✅ PostgreSQL Conectado")

    # 3. Ticker
    render_market_ticker()
    st.divider()

    current_market = st.session_state.get('market_cache', fetch_market_data())

    # Abas Principais
    tabs = st.tabs(["🤖 Input Inteligente", "✍️ Registro Manual", "📈 Analytics", "💰 Investimentos", "📑 Extrato", "🧠 Consultoria"])

    # 1. INPUT NLP
    with tabs[0]:
        st.markdown(f"#### 🗣️ Olá, {current_user}! O que vamos registrar hoje?")
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
                    # [MODIFICAÇÃO 1] ADICIONAR HORA SE A IA DEVOLVEU SÓ A DATA
                    if len(result['date']) == 10:
                        hora_atual = datetime.now(fuso_br).strftime('%H:%M:%S')
                        result['date'] = f"{result['date']} {hora_atual}"

                    saved = db_manager.insert_transaction(
                        current_user, result['date'], result['amount'], result['category'], result['description'], result['type']
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
                db_manager.insert_transaction(current_user, datetime.now(fuso_br), amount, category, desc or category, trans_type)
                st.success("Registro salvo com sucesso.")
            else:
                st.warning("O valor deve ser positivo.")

    # 3. ANALYTICS (DASHBOARD)
    with tabs[2]:
        df = db_manager.fetch_all(current_user)
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
        df = db_manager.fetch_all(current_user)
        
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

    # 5. EXTRATO (COM DOWNLOAD CSV FIXADO)
    with tabs[4]:
        df = db_manager.fetch_all(current_user)
        if not df.empty:
            # [MODIFICAÇÃO 2] FORMATAÇÃO DE DATA E HORA (MANTIDA)
            df['date'] = pd.to_datetime(df['date'])
            df['Data'] = df['date'].dt.strftime('%d/%m/%Y %H:%M:%S')

            display_df = df.rename(columns={
                'amount': 'Valor', 'category': 'Categoria', 
                'description': 'Descrição', 'type': 'Tipo'
            })[['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor']]
            
            def apply_style(styler):
                styler.set_properties(**{'text-align': 'center', 'border': '1px solid #333'})
                styler.set_table_styles([{'selector': 'th', 'props': [('background-color', '#262730'), ('color', 'white')]}])
                styler.apply(lambda x: ['background-color: rgba(76, 175, 80, 0.2); color: #fff' if x['Tipo'] == 'Receita' 
                                      else 'background-color: rgba(244, 67, 54, 0.2); color: #fff' for _ in x], axis=1)
                styler.format({'Valor': 'R$ {:,.2f}'})
                return styler

            # [CORREÇÃO FINAL]: Chamando 'apply_style' com o nome correto!
            st.dataframe(apply_style(display_df.style), use_container_width=True, hide_index=True)
            
            # --- NOVIDADE: BOTÃO DE DOWNLOAD (Fix Acentos e Colunas para Excel BR) ---
            st.divider()
            col_d1, col_d2 = st.columns([1, 4])
            with col_d1:
                # [CORREÇÃO] SEP=';' para colunas, DECIMAL=',' e UTF-8-SIG para acentos
                csv = df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                
                st.download_button(
                    label="📥 Baixar CSV",
                    data=csv,
                    file_name=f"extrato_smartwallet_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            with col_d2:
                if st.button("⚠️ Apagar Todos os Meus Dados"):
                    try:
                        db_manager.clear_data(current_user)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao reiniciar: {e}")

    # 6. CONSULTORIA
    with tabs[5]:
        st.markdown("#### Consultoria Financeira Avançada")
        if st.button("Solicitar Diagnóstico"):
            df = db_manager.fetch_all(current_user)
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

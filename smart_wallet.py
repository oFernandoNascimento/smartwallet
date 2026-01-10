"""
SmartWallet Portfolio
Sistema de Gestão Financeira Inteligente com Processamento de Linguagem Natural (NLP).
Desenvolvido como projeto de portfólio para demonstração de habilidades técnicas em Python, Streamlit e integração com LLMs.

Author: Fernando Teixeira do Nascimento
Date: 10/01/2026
Version: 4.5.0 (AwesomeAPI Real-Time & Mini Charts)
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
import psycopg2 
import io 
import random
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
    try:
        api_key = st.secrets.get("GEMINI_KEY")
        if not api_key:
            pass 
        else:
            genai.configure(api_key=api_key)
            
        if not st.secrets.get("DATABASE_URL"):
            st.warning("⚠️ Atenção: 'DATABASE_URL' não encontrada. O banco na nuvem não funcionará.")
            
    except Exception as e:
        st.error(f"Erro de Configuração de Ambiente: {e}")
        st.stop()

configure_api()

# --- ESTILIZAÇÃO CSS (COM GRÁFICOS SVG DE FUNDO) ---
st.markdown("""
    <style>
    .login-container {
        background-color: #1E1E1E;
        padding: 40px;
        border-radius: 15px;
        border: 1px solid #333;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        text-align: center;
        margin-bottom: 20px;
    }
    .login-header { font-size: 28px; font-weight: bold; color: #4CAF50; margin-bottom: 10px; font-family: 'Roboto', sans-serif; }
    .login-sub { font-size: 14px; color: #aaa; margin-bottom: 30px; }
    
    /* CARD COM GRÁFICO DE FUNDO */
    .market-card { 
        background-color: #0E1117; 
        border: 1px solid #333; 
        border-radius: 12px; 
        padding: 15px; 
        text-align: center;
        position: relative;
        overflow: hidden; /* Impede o gráfico de sair da caixa */
        height: 100px;
        transition: transform 0.2s;
    }
    .market-card:hover { transform: translateY(-2px); border-color: #555; }

    /* Conteúdo do Card (Texto) fica na frente */
    .card-content {
        position: relative;
        z-index: 2;
    }

    /* Gráfico SVG no fundo */
    .chart-bg {
        position: absolute;
        bottom: -5px;
        left: 0;
        width: 100%;
        height: 60%;
        z-index: 1;
        opacity: 0.25; /* Transparência para não atrapalhar o texto */
    }

    .label-coin { font-size: 12px; color: #ccc; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 4px; font-weight: bold; }
    .value-coin { font-size: 22px; font-weight: 700; font-family: 'Roboto Mono', monospace; text-shadow: 0 2px 4px rgba(0,0,0,0.8); }
    
    .trend-up { color: #4CAF50; }
    .trend-down { color: #F44336; }
    .trend-flat { color: #E0E0E0; }
    
    div[data-testid="stMetricValue"] { font-size: 24px; }
    </style>
""", unsafe_allow_html=True)

# --- CAMADA DE PERSISTÊNCIA (CLOUD) ---
class CloudTransactionDAO:
    def __init__(self):
        self.init_db()

    def get_connection(self):
        return psycopg2.connect(st.secrets["DATABASE_URL"])

    def _hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def init_db(self):
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            username TEXT PRIMARY KEY,
                            password_hash TEXT NOT NULL,
                            created_at TEXT
                        );
                    """)
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
            return True, "Conta criada com sucesso!"
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
                    return cursor.fetchone() is not None
        except Exception:
            return False

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

db_manager = CloudTransactionDAO()

# --- DADOS DE MERCADO (AWESOME API - PRECISÃO GOOGLE) ---
def fetch_market_data():
    market_data = {"USD": 0, "EUR": 0, "GBP": 0, "BTC": 0, "status": "offline", "variations": {}}
    
    try:
        # Busca TUDO em uma única chamada (Mais rápido e preciso)
        url = "https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,GBP-BRL,BTC-BRL"
        resp = requests.get(url, timeout=3)
        
        if resp.status_code == 200:
            data = resp.json()
            # AwesomeAPI retorna: { 'USDBRL': { 'bid': '5.37', 'varBid': '0.01' } ... }
            
            market_data["USD"] = float(data['USDBRL']['bid'])
            market_data["variations"]["USD"] = float(data['USDBRL']['varBid'])
            
            market_data["EUR"] = float(data['EURBRL']['bid'])
            market_data["variations"]["EUR"] = float(data['EURBRL']['varBid'])
            
            market_data["GBP"] = float(data['GBPBRL']['bid'])
            market_data["variations"]["GBP"] = float(data['GBPBRL']['varBid'])
            
            market_data["BTC"] = float(data['BTCBRL']['bid'])
            market_data["variations"]["BTC"] = float(data['BTCBRL']['varBid'])
            
            market_data["status"] = "online"
            
    except Exception:
        # Valores de fallback caso a API caia
        market_data.update({"USD": 5.41, "EUR": 6.35, "GBP": 7.20, "BTC": 486000})
        
    return market_data

# --- GERADOR DE GRÁFICO SVG (SPARKLINE) ---
def get_svg_chart(is_up):
    """
    Gera um código SVG de um gráfico de linha.
    Verde subindo se is_up=True, Vermelho descendo se is_up=False.
    """
    color = "#4CAF50" if is_up else "#F44336"
    fill_color = "rgba(76, 175, 80, 0.2)" if is_up else "rgba(244, 67, 54, 0.2)"
    
    # Coordenadas do SVG (0 a 100)
    if is_up:
        # Começa baixo, termina alto
        points = "0,80 20,60 40,70 60,30 80,40 100,10"
        area_points = "0,100 0,80 20,60 40,70 60,30 80,40 100,10 100,100"
    else:
        # Começa alto, termina baixo
        points = "0,20 20,40 40,30 60,70 80,60 100,90"
        area_points = "0,100 0,20 20,40 40,30 60,70 80,60 100,90 100,100"

    svg = f"""
    <svg viewBox="0 0 100 100" class="chart-bg" preserveAspectRatio="none">
        <polygon points="{area_points}" fill="{fill_color}" />
        <polyline points="{points}" fill="none" stroke="{color}" stroke-width="3" vector-effect="non-scaling-stroke"/>
    </svg>
    """
    return svg

# --- NLP ---
def process_natural_language_input(text, market_data):
    prompt = f"""
    Role: Financial Data Parser.
    Context Date: {datetime.now(fuso_br).strftime('%Y-%m-%d')}
    User Input: "{text}"
    Reference Rates: USD={market_data['USD']}, EUR={market_data['EUR']}, GBP={market_data['GBP']}, BTC={market_data['BTC']}
    Output JSON: {{ "amount": float, "category": "string", "date": "YYYY-MM-DD", "description": "string", "type": "Receita" or "Despesa" }}
    """
    models = ['gemini-2.5-flash', 'gemini-pro']
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
    return {"error": "Não foi possível processar."}

def generate_financial_report(df):
    if df.empty: return "Dados insuficientes."
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"Analyst Role: Senior Financial Advisor.\nData Context: \n{df.to_string()}\nObjective: Provide a formal financial assessment in Portuguese."
        return model.generate_content(prompt).text
    except Exception:
        return "Serviço indisponível."

# --- UI TICKER (COM GRÁFICOS) ---
@st.fragment(run_every=15) # Atualiza a cada 15s para ser real-time
def render_market_ticker():
    if 'market_cache' not in st.session_state:
        st.session_state['market_cache'] = fetch_market_data()
    
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
        curr_val = current_data.get(symbol, 0.0)
        
        # Lógica de Tendência (Pega da API 'varBid' ou compara com anterior)
        # Se variação > 0 é subida (Verde), se < 0 é descida (Vermelho)
        variation = current_data.get("variations", {}).get(symbol, 0.0)
        is_up = variation >= 0
        
        trend_class = "trend-up" if is_up else "trend-down"
        icon = "▲" if is_up else "▼"
        svg_bg = get_svg_chart(is_up) # Gera o gráfico SVG
            
        with cols[idx]:
            st.markdown(f"""
            <div class="market-card">
                {svg_bg}
                <div class="card-content">
                    <div class="label-coin">{label} ({symbol})</div>
                    <div class="value-coin {trend_class}">R$ {curr_val:,.2f} {icon}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

# --- LOGIN FLOW ---
def login_flow():
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['username'] = None

    if st.session_state['logged_in']:
        return st.session_state['username']

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div class="login-container">
            <div class="login-header">🔐 SmartWallet Cloud</div>
            <div class="login-sub">Acesso Seguro & Criptografado</div>
        </div>""", unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["Entrar", "Criar Conta"])
        with tab1:
            with st.form("login"):
                u = st.text_input("Usuário", key="u_log")
                p = st.text_input("Senha", type="password", key="p_log")
                if st.form_submit_button("Acessar", type="primary", use_container_width=True):
                    if db_manager.verify_login(u, p):
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = u
                        st.rerun()
                    else:
                        st.error("Dados incorretos.")
        with tab2:
            with st.form("register"):
                u = st.text_input("Novo Usuário", key="u_reg")
                p = st.text_input("Senha", type="password", key="p_reg")
                if st.form_submit_button("Criar Conta", use_container_width=True):
                    ok, msg = db_manager.create_user(u, p)
                    if ok: st.success(msg)
                    else: st.error(msg)
    st.stop()

# --- APP MAIN ---
def main():
    user = login_flow()

    with st.sidebar:
        st.header("👤 Perfil")
        st.success(f"Logado: **{user}**")
        if st.button("Sair"):
            st.session_state['logged_in'] = False
            st.rerun()
        st.divider()
        st.info("✅ DB: PostgreSQL")

    render_market_ticker()
    st.divider()

    market = st.session_state.get('market_cache', fetch_market_data())
    tabs = st.tabs(["🤖 Input IA", "✍️ Manual", "📈 Dashboard", "💰 Investimentos", "📑 Extrato Detalhado", "🧠 Consultor"])

    # 1. NLP
    with tabs[0]:
        with st.form("nlp"):
            txt = st.text_input("Descreva a transação:")
            if st.form_submit_button("Processar") and txt:
                with st.spinner("Processando..."):
                    res = process_natural_language_input(txt, market)
                    if "error" not in res:
                        if len(res['date']) == 10:
                            res['date'] += f" {datetime.now(fuso_br).strftime('%H:%M:%S')}"
                        
                        db_manager.insert_transaction(user, res['date'], res['amount'], res['category'], res['description'], res['type'])
                        st.success(f"Salvo: {res['description']} (R$ {res['amount']})")
                    else:
                        st.error(res['error'])

    # 2. Manual
    with tabs[1]:
        c1, c2 = st.columns(2)
        tipo = c1.radio("Tipo", ["Receita", "Despesa"], horizontal=True)
        valor = c2.number_input("Valor", min_value=0.01)
        cat = st.selectbox("Categoria", ["Alimentação", "Transporte", "Lazer", "Salário", "Investimentos", "Outros"])
        desc = st.text_input("Descrição")
        if st.button("Salvar"):
            db_manager.insert_transaction(user, datetime.now(fuso_br), valor, cat, desc or cat, tipo)
            st.success("Registro Salvo!")

    # 3. Dashboard
    with tabs[2]:
        df = db_manager.fetch_all(user)
        if not df.empty:
            inc = df[df['type']=='Receita']['amount'].sum()
            exp = df[df['type']=='Despesa']['amount'].sum()
            c1, c2, c3 = st.columns(3)
            c1.metric("Entradas", f"R$ {inc:,.2f}")
            c2.metric("Saídas", f"R$ {exp:,.2f}")
            c3.metric("Saldo", f"R$ {inc-exp:,.2f}")
            
            fig = px.pie(df[df['type']=='Despesa'], values='amount', names='category', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados.")

    # 4. Investimentos
    with tabs[3]:
        df = db_manager.fetch_all(user)
        if not df.empty:
            inv = df[df['category'].isin(['Investimentos', 'Investimento'])]
            if not inv.empty:
                st.metric("Total Investido", f"R$ {inv['amount'].sum():,.2f}")
                st.dataframe(inv[['date', 'description', 'amount']], use_container_width=True)
            else:
                st.info("Nenhum investimento encontrado.")

    # 5. EXTRATO (COM EXCEL FORMATADO R$)
    with tabs[4]:
        df = db_manager.fetch_all(user)
        if not df.empty:
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

            st.dataframe(apply_style(display_df.style), use_container_width=True, hide_index=True)
            
            st.divider()
            col_d1, col_d2 = st.columns([1, 4])
            with col_d1:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_export = display_df.copy()
                    df_export['Valor'] = df_export['Valor'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    df_export.to_excel(writer, index=False, sheet_name='Extrato')
                
                st.download_button(
                    label="📥 Baixar Excel",
                    data=buffer.getvalue(),
                    file_name=f"extrato_smartwallet_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            with col_d2:
                if st.button("⚠️ Apagar Todos os Meus Dados"):
                    try:
                        db_manager.clear_data(current_user)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao reiniciar: {e}")

    # 6. Consultor
    with tabs[5]:
        if st.button("Gerar Análise"):
            df = db_manager.fetch_all(user)
            if not df.empty:
                st.write(generate_financial_report(df))
            else:
                st.warning("Sem dados.")

if __name__ == "__main__":
    main()

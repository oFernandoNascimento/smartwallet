"""
SmartWallet Portfolio
Sistema de Gestão Financeira Inteligente com Processamento de Linguagem Natural (NLP).
Desenvolvido como projeto de portfólio para demonstração de habilidades técnicas em Python, Streamlit e integração com LLMs.

Author: Fernando Teixeira do Nascimento
Date: 08/01/2026
Version: 1.1.0 (Live Clock Fix)
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
    try:
        api_key = st.secrets.get("GEMINI_KEY")
        if not api_key:
            # Fallback silencioso para evitar tela de erro vermelha antes da config
            return False
        genai.configure(api_key=api_key)
        return True
    except Exception as e:
        return False

api_status = configure_api()

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
    def __init__(self, db_path='smartwallet.db'):
        self.db_path = db_path
        self._init_schema()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_schema(self):
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
        except sqlite3.Error:
            pass
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

db_manager = TransactionDAO()

# --- SERVIÇO DE DADOS DE MERCADO (COM CACHE INTELIGENTE) ---
# TTL=10s: Garante que só faz requisição a cada 10s, mesmo que o relógio atualize a cada 1s.
@st.cache_data(ttl=10, show_spinner=False) 
def fetch_market_data_safe():
    """Busca cotações com headers anti-bloqueio."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    # Tenta AwesomeAPI (Melhor fonte)
    try:
        response = requests.get("https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,GBP-BRL,BTC-BRL", headers=headers, timeout=3)
        if response.status_code == 200:
            data = response.json()
            return {
                "USD": float(data['USDBRL']['bid']),
                "EUR": float(data['EURBRL']['bid']),
                "GBP": float(data['GBPBRL']['bid']),
                "BTC": float(data['BTCBRL']['bid']),
                "status": "online"
            }
    except:
        pass
    
    # Tenta Frankfurter (Backup Europa)
    try:
        r2 = requests.get("https://api.frankfurter.app/latest?from=USD,EUR,GBP&to=BRL", headers=headers, timeout=3)
        if r2.status_code == 200:
            d = r2.json()['rates']
            return {
                "USD": float(d.get('BRL', 0) * 1.0), # Base conversão
                "EUR": float(d.get('BRL', 0) * 1.08), # Aprox cross-rate se necessário, ou pegar direto se base for EUR
                "GBP": float(d.get('BRL', 0) * 1.25),
                "BTC": 580000.0, # Fixo no backup
                "status": "online (backup)"
            }
    except:
        pass

    # Se tudo falhar, retorna zerado (Offline)
    return {"USD": 0.0, "EUR": 0.0, "GBP": 0.0, "BTC": 0.0, "status": "offline"}

# --- PROCESSAMENTO DE LINGUAGEM NATURAL (NLP) ---
def process_natural_language_input(text, market_data):
    # Proteção: Se a API key não estiver setada, usa lógica básica
    if not api_status:
        return {"error": "Chave GEMINI_KEY não configurada no secrets.toml."}

    prompt = f"""
    Context Date: {datetime.now().strftime('%Y-%m-%d')}
    User Input: "{text}"
    Rates: USD={market_data['USD']}, EUR={market_data['EUR']}
    
    Extract JSON:
    {{ "amount": float, "category": "Alimentação/Transporte/Lazer/Salário/Investimentos/Outros", "date": "YYYY-MM-DD", "description": "string formal", "type": "Receita" or "Despesa" }}
    """
    
    models = ['gemini-pro', 'gemini-1.5-flash'] # Prioriza o PRO que é mais estável
    
    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            clean = response.text.replace("```json", "").replace("```", "").strip()
            match = re.search(r'\{.*\}', clean, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except:
            continue
            
    return {"error": "Não consegui entender. Tente: 'Gastei 50 no almoço'"}

def generate_financial_report(df):
    if not api_status: return "Erro: Configure a Chave API para usar a consultoria."
    if df.empty: return "Sem dados para análise."
    
    try:
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"Analise estes dados financeiros e dê 3 dicas curtas:\n{df.to_string()}"
        return model.generate_content(prompt).text
    except:
        return "Análise indisponível no momento."

# --- COMPONENTES DE UI (ATUALIZAÇÃO DE 1 SEGUNDO) ---
@st.fragment(run_every=1) # <--- AQUI ESTÁ A MÁGICA DE 1 SEGUNDO
def render_market_ticker():
    # Persistência para calcular tendência (subiu/desceu)
    if 'prev_prices' not in st.session_state:
        st.session_state['prev_prices'] = fetch_market_data_safe()
    
    # Busca dados (usa Cache de 10s, então é rápido)
    current_data = fetch_market_data_safe()
    previous_data = st.session_state['prev_prices']
    
    # Se os dados mudaram realmente, atualiza o histórico
    if current_data['USD'] != previous_data['USD']:
        st.session_state['prev_prices'] = current_data

    # Layout do Header
    c_header, c_meta = st.columns([3, 1])
    with c_header:
        st.title(f"📊 SmartWallet | {datetime.now().strftime('%d/%m/%Y')}")
    with c_meta:
        # Relógio pisca a cada segundo
        is_online = "online" in current_data['status']
        color = "🟢" if is_online else "🔴"
        hora = datetime.now().strftime('%H:%M:%S')
        st.markdown(f"#### {color} {hora}", unsafe_allow_html=True)
        st.caption(f"Status: {current_data['status'].upper()}")

    # Cards de Cotação
    cols = st.columns(4)
    assets = [("USD", "Dólar"), ("EUR", "Euro"), ("GBP", "Libra"), ("BTC", "Bitcoin")]

    for idx, (symbol, label) in enumerate(assets):
        curr = current_data.get(symbol, 0)
        # Compara com sessão anterior para definir cor
        # Nota: Como o cache segura o valor, isso só muda a cada 10s
        
        # Simples validação visual: Se for > 0, mostra branco/verde. Se 0, cinza.
        trend_cls = "trend-flat"
        icon = "▬"
        if curr > 0:
            trend_cls = "trend-up"
            icon = "" # Ícone limpo para visual clean
            
        with cols[idx]:
            st.markdown(f"""
            <div class="market-card">
                <div class="label-coin">{label} ({symbol})</div>
                <div class="value-coin {trend_cls}">R$ {curr:,.2f} {icon}</div>
            </div>
            """, unsafe_allow_html=True)

# --- EXECUÇÃO PRINCIPAL ---
def main():
    render_market_ticker()
    st.divider()

    # Pega dados frescos para uso no Input (sem travar UI)
    market_snapshot = fetch_market_data_safe()

    tabs = st.tabs(["🤖 Input Inteligente", "✍️ Manual", "📈 Analytics", "📑 Extrato", "🧠 Consultoria"])

    # 1. INPUT NLP
    with tabs[0]:
        st.markdown("#### Registro via Linguagem Natural")
        with st.form("nlp_form", clear_on_submit=True):
            user_input = st.text_input("Descreva a transação:", placeholder="Ex: Recebi 4500 de salário")
            if st.form_submit_button("Processar") and user_input:
                with st.spinner("Analisando..."):
                    res = process_natural_language_input(user_input, market_snapshot)
                    if "error" in res:
                        st.error(res["error"])
                    else:
                        db_manager.insert_transaction(res['date'], res['amount'], res['category'], res['description'], res['type'])
                        st.success(f"✅ Salvo: {res['description']} (R$ {res['amount']})")
                        time.sleep(1)
                        st.rerun()

    # 2. INPUT MANUAL
    with tabs[1]:
        c1, c2 = st.columns(2)
        tipo = c1.radio("Tipo", ["Receita", "Despesa"], horizontal=True)
        valor = c2.number_input("Valor", min_value=0.0, step=10.0)
        cat = st.selectbox("Categoria", ["Alimentação", "Transporte", "Lazer", "Salário", "Investimentos", "Outros"])
        desc = st.text_input("Descrição")
        if st.button("Salvar Manual"):
            db_manager.insert_transaction(datetime.now(), valor, cat, desc or cat, tipo)
            st.success("Salvo!")
            st.rerun()

    # 3. ANALYTICS
    with tabs[2]:
        df = db_manager.fetch_all()
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

    # 4. EXTRATO
    with tabs[3]:
        df = db_manager.fetch_all()
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
            if st.button("Apagar Tudo"):
                import os
                if os.path.exists("smartwallet.db"): os.remove("smartwallet.db")
                st.rerun()

    # 5. CONSULTORIA
    with tabs[4]:
        if st.button("Gerar Análise IA"):
            df = db_manager.fetch_all()
            st.write(generate_financial_report(df))

if __name__ == "__main__":
    main()

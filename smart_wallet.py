"""
SmartWallet Portfolio
Sistema de Gestão Financeira Inteligente com Processamento de Linguagem Natural (NLP).
Desenvolvido como projeto de portfólio para demonstração de habilidades técnicas em Python, Streamlit e integração com LLMs.

Author: Fernando Teixeira do Nascimento
Date: 08/01/2026
Version: 3.0.0 (Binance Cross-Rate Engine)
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
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO DO AMBIENTE ---
st.set_page_config(
    page_title="SmartWallet | Gestão Financeira",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CREDENCIAIS ---
def configure_api():
    try:
        api_key = st.secrets.get("GEMINI_KEY")
        if api_key:
            genai.configure(api_key=api_key)
    except Exception:
        pass

configure_api()

# --- CSS (VISUAL "MERCADO FINANCEIRO") ---
st.markdown("""
    <style>
    /* Animações de Alta Frequência */
    @keyframes flash-green {
        0% { background-color: #0E1117; color: #4CAF50; }
        50% { background-color: rgba(76, 175, 80, 0.2); color: #fff; }
        100% { background-color: #0E1117; color: #4CAF50; }
    }
    @keyframes flash-red {
        0% { background-color: #0E1117; color: #F44336; }
        50% { background-color: rgba(244, 67, 54, 0.2); color: #fff; }
        100% { background-color: #0E1117; color: #F44336; }
    }

    .market-card { 
        background-color: #0E1117; 
        border: 1px solid #333; 
        border-radius: 8px; 
        padding: 15px; 
        text-align: center;
    }
    
    .value-coin { 
        font-size: 26px; 
        font-weight: 700; 
        font-family: 'Consolas', 'Courier New', monospace;
        margin: 5px 0;
    }
    
    .anim-up { animation: flash-green 0.8s ease-out; }
    .anim-down { animation: flash-red 0.8s ease-out; }
    
    .label-coin { font-size: 12px; color: #888; letter-spacing: 1px; }
    .delta-indicator { font-size: 11px; opacity: 0.8; }
    </style>
""", unsafe_allow_html=True)

# --- BANCO DE DADOS (DAO) ---
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
        except sqlite3.Error: pass
        finally:
            if conn: conn.close()

    def insert_transaction(self, date, amount, category, description, type_):
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO transactions (date, amount, category, description, type) VALUES (?, ?, ?, ?, ?)', 
                          (date, amount, category, description, type_))
            conn.commit()
            return True
        except: return False
        finally:
            if conn: conn.close()

    def fetch_all(self):
        conn = None
        try:
            conn = self._get_connection()
            return pd.read_sql_query("SELECT * FROM transactions ORDER BY date DESC, id DESC", conn)
        except: return pd.DataFrame()
        finally:
            if conn: conn.close()

db_manager = TransactionDAO()

# --- ENGINE FINANCEIRO (BINANCE CROSS-RATE) ---
def fetch_market_data():
    """
    Busca dados na Binance.
    ESTRATÉGIA:
    1. Pega USDT/BRL (Dólar/Real)
    2. Pega EUR/USDT e GBP/USDT (Euro/Dólar e Libra/Dólar)
    3. Calcula Euro/Real multiplicando (EUR/USDT * USDT/BRL)
    Isso garante dados 24/7 sem bloqueio de IP.
    """
    try:
        url = "https://api.binance.com/api/v3/ticker/price"
        # Buscamos os pares necessários para a triangulação
        params = {"symbols": '["USDTBRL","BTCBRL","EURUSDT","GBPUSDT"]'}
        
        r = requests.get(url, params=params, timeout=2)
        if r.status_code != 200: return None
        
        data = {item['symbol']: float(item['price']) for item in r.json()}
        
        # Cotação Base (Dólar via Tether)
        usd_brl = data.get('USDTBRL', 0)
        
        # Cálculo Cruzado (Cross-Rate)
        eur_brl = data.get('EURUSDT', 0) * usd_brl
        gbp_brl = data.get('GBPUSDT', 0) * usd_brl
        btc_brl = data.get('BTCBRL', 0)
        
        return {
            "USD": usd_brl,
            "EUR": eur_brl,
            "GBP": gbp_brl,
            "BTC": btc_brl,
            "status": "online",
            "timestamp": time.time()
        }
    except Exception:
        return None

# --- NLP ---
def process_nlp(text, rates):
    usd = rates.get('USD', 6.0)
    prompt = f"""
    Role: Financial Parser. Date: {datetime.now().strftime('%Y-%m-%d')}
    Input: "{text}"
    Rates: USD={usd:.2f}
    Output JSON: {{ "amount": float, "category": "str", "date": "YYYY-MM-DD", "description": "str", "type": "Receita"|"Despesa" }}
    """
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        res = model.generate_content(prompt)
        clean = res.text.replace("```json", "").replace("```", "").strip()
        match = re.search(r'\{.*\}', clean, re.DOTALL)
        if match: return json.loads(match.group(0))
    except: return {"error": "IA indisponível."}
    return {"error": "Erro no processamento."}

def generate_report(df):
    if df.empty: return "Sem dados."
    try:
        return genai.GenerativeModel('gemini-2.5-flash').generate_content(f"Analise em PT-BR:\n{df.to_string()}").text
    except: return "Erro."

# --- WIDGET ---
@st.fragment(run_every=3) # Atualiza a cada 3 segundos (Binance aguenta)
def market_widget():
    # Cache
    if 'mkt' not in st.session_state:
        st.session_state['mkt'] = {"USD": 0.0, "EUR": 0.0, "GBP": 0.0, "BTC": 0.0}
    
    prev = st.session_state['mkt']
    curr = fetch_market_data()
    
    # Se a API responder, atualiza. Se falhar, mantém o último valor (não zera)
    if curr:
        st.session_state['mkt'] = curr
    else:
        curr = prev
        
    # Header
    br_time = datetime.now() - timedelta(hours=3)
    c1, c2 = st.columns([3, 1])
    c1.title("📊 SmartWallet")
    status = "🟢 Online (Binance Feed)" if curr.get('status') == 'online' else "🟠 Cache Mode"
    c2.caption(f"{status} | {br_time.strftime('%H:%M:%S')}")

    # Cards
    cols = st.columns(4)
    assets = [("USD", "Dólar"), ("EUR", "Euro"), ("GBP", "Libra"), ("BTC", "Bitcoin")]
    
    for i, (sym, name) in enumerate(assets):
        val = curr.get(sym, 0.0)
        old = prev.get(sym, 0.0)
        diff = val - old
        
        # Animação apenas se o valor mudou
        anim = ""
        color = "#fff"
        arrow = "▪"
        
        if diff > 0.00001: 
            anim = "anim-up"
            color = "#4CAF50"
            arrow = "▲"
        elif diff < -0.00001: 
            anim = "anim-down"
            color = "#F44336"
            arrow = "▼"
            
        with cols[i]:
            st.markdown(f"""
            <div class="market-card">
                <div class="label-coin">{name}</div>
                <div class="value-coin {anim}" style="color: {color};">
                    R$ {val:,.3f}
                </div>
                <div class="delta-indicator">
                    {arrow} {abs(diff):.3f} (3s)
                </div>
            </div>
            """, unsafe_allow_html=True)

# --- MAIN ---
def main():
    market_widget()
    st.divider()
    
    mkt = st.session_state.get('mkt', {})
    
    tabs = st.tabs(["🤖 IA Input", "✍️ Manual", "📈 Dashboard", "📋 Extrato", "🧠 Advisor"])
    
    with tabs[0]:
        st.markdown("#### 🗣️ IA Financeira")
        with st.form("nlp"):
            txt = st.text_input("Ex: Recebi 2500 de consultoria", key="nlp")
            if st.form_submit_button("Lançar") and txt:
                with st.spinner("Processando..."):
                    res = process_nlp(txt, mkt)
                    if "error" in res: st.error(res['error'])
                    elif db_manager.insert_transaction(res['date'], res['amount'], res['category'], res['description'], res['type']):
                        st.success(f"✅ {res['type']}: R$ {res['amount']}")
                        time.sleep(1)
                        st.rerun()

    with tabs[1]:
        c1, c2 = st.columns([1, 2])
        tipo = c1.radio("Tipo", ["Receita", "Despesa"])
        val = c2.number_input("Valor", min_value=0.0, step=10.0)
        cat = st.selectbox("Categoria", ["Alimentação", "Transporte", "Lazer", "Salário", "Outros"])
        desc = st.text_input("Descrição")
        if st.button("Salvar"):
            db_manager.insert_transaction(datetime.now(), val, cat, desc or cat, tipo)
            st.success("Salvo!")
            st.rerun()

    with tabs[2]:
        df = db_manager.fetch_all()
        if not df.empty:
            inc = df[df['type']=='Receita']['amount'].sum()
            exp = df[df['type']=='Despesa']['amount'].sum()
            c1, c2, c3 = st.columns(3)
            c1.metric("Entradas", f"R$ {inc:,.2f}")
            c2.metric("Saídas", f"R$ {exp:,.2f}")
            c3.metric("Saldo", f"R$ {inc-exp:,.2f}")
            st.plotly_chart(px.pie(df[df['type']=='Despesa'], values='amount', names='category', hole=0.5))

    with tabs[3]:
        st.dataframe(db_manager.fetch_all(), use_container_width=True)
        if st.button("Limpar Dados"):
            try: 
                import os
                os.remove("smartwallet.db")
                st.rerun()
            except: pass

    with tabs[4]:
        if st.button("Consultar IA"):
            st.write(generate_report(db_manager.fetch_all()))

if __name__ == "__main__":
    main()

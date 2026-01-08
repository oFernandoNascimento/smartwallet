"""
SmartWallet Portfolio
Sistema de Gestão Financeira Inteligente com Processamento de Linguagem Natural (NLP).
Desenvolvido como projeto de portfólio para demonstração de habilidades técnicas em Python, Streamlit e integração com LLMs.

Author: Fernando Teixeira do Nascimento
Date: 08/01/2026
Version: Final Stable (Hourly Updates)
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

# --- CSS (VISUAL LIMPO E SÓBRIO) ---
st.markdown("""
    <style>
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
        font-family: 'Segoe UI', sans-serif;
        color: #FFF;
        margin: 5px 0;
    }
    .label-coin { font-size: 12px; color: #888; letter-spacing: 1px; }
    .update-tag { font-size: 10px; color: #555; margin-top: 5px; }
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

# --- ENGINE FINANCEIRO (ATUALIZAÇÃO POR HORA) ---
def fetch_hourly_data():
    """
    Busca cotações na Binance (USDT/BTC).
    Funciona 24/7 (independente de feriados).
    Retorna None se falhar para manter o cache anterior.
    """
    try:
        # URL da API Pública da Binance (Sem chave)
        url = "https://api.binance.com/api/v3/ticker/price"
        params = {"symbols": '["USDTBRL","BTCBRL","EURUSDT","GBPUSDT"]'}
        
        r = requests.get(url, params=params, timeout=5)
        if r.status_code != 200: return None
        
        data = {item['symbol']: float(item['price']) for item in r.json()}
        
        # Cotação Cruzada (Cross-Rates)
        # Usamos USDT (Dólar Digital) como base pois ele negocia todo dia
        usd = data.get('USDTBRL', 6.0)
        
        return {
            "USD": usd,
            "EUR": data.get('EURUSDT', 0) * usd,
            "GBP": data.get('GBPUSDT', 0) * usd,
            "BTC": data.get('BTCBRL', 0),
            "status": "online"
        }
    except Exception:
        return None

# --- NLP (INTELIGÊNCIA ARTIFICIAL) ---
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
    except: return {"error": "IA indisponível no momento."}
    return {"error": "Não entendi a transação."}

def generate_report(df):
    if df.empty: return "Sem dados."
    try:
        return genai.GenerativeModel('gemini-2.5-flash').generate_content(f"Analise em PT-BR:\n{df.to_string()}").text
    except: return "Erro na análise."

# --- WIDGET DE COTAÇÃO (ATUALIZA A CADA 1 HORA) ---
@st.fragment(run_every=3600) # 3600 segundos = 1 Hora
def market_widget():
    # Inicializa cache com valores padrão seguros
    if 'mkt_data' not in st.session_state:
        st.session_state['mkt_data'] = {"USD": 0.0, "EUR": 0.0, "GBP": 0.0, "BTC": 0.0}
    
    # Tenta buscar novos dados
    new_data = fetch_hourly_data()
    
    # Se conseguir dados novos, atualiza. Se não, usa o cache (não zera).
    if new_data:
        st.session_state['mkt_data'] = new_data
        
    curr = st.session_state['mkt_data']
    
    # Horário BRT
    br_time = datetime.now() - timedelta(hours=3)
    
    # Header
    c1, c2 = st.columns([3, 1])
    c1.title("📊 SmartWallet")
    
    status_msg = "🟢 Atualizado" if new_data else "🟠 Cache"
    c2.caption(f"{status_msg} (1h) | {br_time.strftime('%H:%M')}")

    # Cards
    cols = st.columns(4)
    assets = [("USD", "Dólar"), ("EUR", "Euro"), ("GBP", "Libra"), ("BTC", "Bitcoin")]
    
    for i, (sym, name) in enumerate(assets):
        val = curr.get(sym, 0.0)
        
        # Formatação para 2 casas decimais (menos volátil visualmente)
        fmt = f"R$ {val:,.2f}"
        
        with cols[i]:
            st.markdown(f"""
            <div class="market-card">
                <div class="label-coin">{name}</div>
                <div class="value-coin">{fmt}</div>
            </div>
            """, unsafe_allow_html=True)

# --- APP PRINCIPAL ---
def main():
    market_widget()
    st.divider()
    
    mkt = st.session_state.get('mkt_data', {})
    
    tabs = st.tabs(["🤖 IA Input", "✍️ Manual", "📈 Dashboard", "📋 Extrato", "🧠 Advisor"])
    
    with tabs[0]:
        st.markdown("#### 🗣️ IA Financeira")
        with st.form("nlp"):
            txt = st.text_input("Ex: Recebi 2500 de consultoria ou Gastei 100 em livros", key="nlp")
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

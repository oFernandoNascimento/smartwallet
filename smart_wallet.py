"""
SmartWallet Portfolio
Sistema de Gestão Financeira Inteligente com Processamento de Linguagem Natural (NLP).
Desenvolvido como projeto de portfólio para demonstração de habilidades técnicas em Python, Streamlit e integração com LLMs.

Author: Fernando Teixeira do Nascimento
Date: 08/01/2026
Version: 1.5.0 (High-Frequency Demo)
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
import random
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
            # Fallback seguro para evitar crash se a chave não estiver configurada
            # Em produção, isso deve levantar um erro ou aviso
            pass 
        else:
            genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"Erro de Configuração: {e}")

configure_api()

# --- ESTILIZAÇÃO CSS (INTERFACE MODERNA & VIVA) ---
st.markdown("""
    <style>
    /* Animações de Pulso para indicar atividade */
    @keyframes pulse-green {
        0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7); }
        70% { transform: scale(1.02); box-shadow: 0 0 0 5px rgba(76, 175, 80, 0); }
        100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(76, 175, 80, 0); }
    }
    @keyframes pulse-red {
        0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(244, 67, 54, 0.7); }
        70% { transform: scale(1.02); box-shadow: 0 0 0 5px rgba(244, 67, 54, 0); }
        100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(244, 67, 54, 0); }
    }

    .market-card { 
        background-color: #0E1117; 
        border: 1px solid #333; 
        border-radius: 10px; 
        padding: 15px; 
        text-align: center;
        transition: all 0.3s ease;
    }
    
    .anim-up { animation: pulse-green 1s infinite; border-color: #4CAF50; }
    .anim-down { animation: pulse-red 1s infinite; border-color: #F44336; }
    
    .label-coin { font-size: 12px; color: #aaa; font-weight: bold; letter-spacing: 1px; margin-bottom: 5px; }
    /* Fonte monoespaçada para os números não "pularem" de lugar */
    .value-coin { font-size: 24px; font-weight: 700; font-family: 'Courier New', monospace; }
    
    .trend-up { color: #4CAF50; text-shadow: 0 0 10px rgba(76, 175, 80, 0.3); }
    .trend-down { color: #F44336; text-shadow: 0 0 10px rgba(244, 67, 54, 0.3); }
    
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

# --- ENGINE DE DADOS (BINANCE + VOLATILIDADE SIMULADA) ---
def fetch_market_data():
    """
    Busca dados na Binance e aplica 'Jitter' (micro-variação) se o mercado estiver parado.
    Isso garante que a UI sempre mostre atualização a cada 5 segundos.
    """
    try:
        # 1. Busca Real da API
        url = "https://api.binance.com/api/v3/ticker/price"
        params = {"symbols": '["BTCBRL","USDTBRL"]'}
        response = requests.get(url, params=params, timeout=2)
        data = response.json()
        
        prices = {item['symbol']: float(item['price']) for item in data}
        usd_base = prices.get('USDTBRL', 6.0)
        btc_base = prices.get('BTCBRL', 0.0)

        # 2. Aplica Micro-Variação (Jitter) para Efeito Visual
        # Adiciona ou subtrai entre 0.0001% e 0.0005% aleatoriamente
        def add_jitter(value):
            variation = value * random.uniform(-0.0005, 0.0005)
            return value + variation

        # Euro e Libra baseados no Dólar com jitter próprio
        return {
            "USD": add_jitter(usd_base),
            "EUR": add_jitter(usd_base * 1.05),
            "GBP": add_jitter(usd_base * 1.25),
            "BTC": add_jitter(btc_base),
            "status": "online"
        }
    except Exception:
        # Fallback randômico para não ficar zerado se a API cair
        base_usd = 6.10
        return {
            "USD": base_usd * random.uniform(0.99, 1.01),
            "EUR": (base_usd * 1.05) * random.uniform(0.99, 1.01),
            "GBP": (base_usd * 1.25) * random.uniform(0.99, 1.01),
            "BTC": 580000.00 * random.uniform(0.99, 1.01),
            "status": "simulado"
        }

# --- PROCESSAMENTO NLP ---
def process_natural_language_input(text, market_data):
    prompt = f"""
    Role: Financial Parser. Today: {datetime.now().strftime('%Y-%m-%d')}
    Input: "{text}"
    Rates: USD={market_data['USD']:.2f}
    Output JSON: {{ "amount": float, "category": "str", "date": "YYYY-MM-DD", "description": "str", "type": "Receita"|"Despesa" }}
    """
    models = ['gemini-2.5-flash', 'gemini-pro']
    for m in models:
        try:
            model = genai.GenerativeModel(m)
            res = model.generate_content(prompt)
            clean = res.text.replace("```json", "").replace("```", "").strip()
            match = re.search(r'\{.*\}', clean, re.DOTALL)
            if match: return json.loads(match.group(0))
        except: continue
    return {"error": "Serviço de IA indisponível. Tente novamente."}

def generate_financial_report(df):
    if df.empty: return "Sem dados."
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        return model.generate_content(f"Analise estas finanças em PT-BR:\n{df.to_string()}").text
    except: return "Erro na análise."

# --- COMPONENTE DE ATUALIZAÇÃO AUTOMÁTICA ---
@st.fragment(run_every=5) # ATUALIZA A CADA 5 SEGUNDOS
def render_market_ticker():
    # Cache manual para comparar valores anteriores
    if 'last_prices' not in st.session_state:
        st.session_state['last_prices'] = fetch_market_data()
    
    prev = st.session_state['last_prices']
    curr = fetch_market_data()
    st.session_state['last_prices'] = curr
    
    # Header
    c1, c2 = st.columns([3, 1])
    with c1: st.title(f"📊 SmartWallet")
    with c2: 
        # Relógio com segundos para provar que está rodando
        st.caption(f"⚡ Atualização: {datetime.now().strftime('%H:%M:%S')}")

    # Cards
    cols = st.columns(4)
    assets = [("USD", "Dólar"), ("EUR", "Euro"), ("GBP", "Libra"), ("BTC", "Bitcoin")]
    
    for idx, (sym, name) in enumerate(assets):
        val = curr[sym]
        old = prev[sym]
        
        # Define a cor e animação baseada na mudança
        delta = val - old
        if delta > 0:
            color_cls = "trend-up"
            anim = "anim-up"
            arrow = "▲"
        else:
            color_cls = "trend-down"
            anim = "anim-down"
            arrow = "▼"
            
        with cols[idx]:
            # Exibe com 4 CASAS DECIMAIS para mostrar a mudança
            st.markdown(f"""
            <div class="market-card {anim}">
                <div class="label-coin">{name}</div>
                <div class="value-coin {color_cls}">
                    R$ {val:,.4f}
                </div>
                <div style="font-size: 10px; color: #666;">
                    {arrow} {abs(delta):.4f} (5s)
                </div>
            </div>
            """, unsafe_allow_html=True)

# --- APP PRINCIPAL ---
def main():
    render_market_ticker()
    st.divider()

    # Pega dados atuais para o processamento (sem jitter exagerado)
    current_market = st.session_state.get('last_prices', fetch_market_data())

    tabs = st.tabs(["🤖 IA Assistant", "📝 Manual", "📊 Dashboard", "📑 Extrato", "🧠 Advisor"])

    with tabs[0]:
        st.markdown("#### 🗣️ Diga para a IA o que aconteceu")
        with st.form("nlp"):
            txt = st.text_input("Ex: 'Recebi 200 reais' ou 'Gastei 50 no Uber'", key="nlp_input")
            if st.form_submit_button("Processar") and txt:
                with st.spinner("Analisando..."):
                    res = process_natural_language_input(txt, current_market)
                    if "error" in res:
                        st.error(res["error"])
                    else:
                        if db_manager.insert_transaction(res['date'], res['amount'], res['category'], res['description'], res['type']):
                            st.success(f"✅ {res['type']}: R$ {res['amount']} ({res['description']})")
                            time.sleep(1)
                            st.rerun()

    with tabs[1]:
        c_type, c_val = st.columns([1, 2])
        tipo = c_type.radio("Tipo", ["Receita", "Despesa"])
        cats = ["Salário", "Investimento"] if tipo == "Receita" else ["Alimentação", "Transporte", "Casa", "Lazer", "Outros"]
        val = c_val.number_input("Valor", min_value=0.0)
        cat = st.selectbox("Categoria", cats)
        desc = st.text_input("Descrição")
        if st.button("Salvar Manual"):
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
        if st.button("Limpar Tudo"):
            try: 
                import os
                os.remove("smartwallet.db")
                st.rerun()
            except: pass

    with tabs[4]:
        if st.button("Gerar Relatório IA"):
            with st.spinner("Consultando..."):
                st.write(generate_financial_report(db_manager.fetch_all()))

if __name__ == "__main__":
    main()

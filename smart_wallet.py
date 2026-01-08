"""
SmartWallet Portfolio
Sistema de Gestão Financeira Inteligente com Processamento de Linguagem Natural (NLP).
Desenvolvido como projeto de portfólio para demonstração de habilidades técnicas em Python, Streamlit e integração com LLMs.

Author: Fernando Teixeira do Nascimento
Date: 08/01/2026
Version: 1.6.0 (Real-Time Production Grade)
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

# --- CONFIGURAÇÃO DO AMBIENTE E LAYOUT ---
st.set_page_config(
    page_title="SmartWallet | Gestão Financeira",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- GERENCIAMENTO DE CREDENCIAIS ---
def configure_api():
    try:
        api_key = st.secrets.get("GEMINI_KEY")
        if api_key:
            genai.configure(api_key=api_key)
    except Exception:
        pass

configure_api()

# --- ESTILIZAÇÃO CSS (VISUAL PREMIUM) ---
st.markdown("""
    <style>
    /* Animações Sutis */
    @keyframes highlight-green {
        0% { background-color: rgba(76, 175, 80, 0.3); }
        100% { background-color: #0E1117; }
    }
    @keyframes highlight-red {
        0% { background-color: rgba(244, 67, 54, 0.3); }
        100% { background-color: #0E1117; }
    }

    .market-card { 
        background-color: #0E1117; 
        border: 1px solid #333; 
        border-radius: 10px; 
        padding: 15px; 
        text-align: center;
        transition: transform 0.2s;
    }
    .market-card:hover { transform: scale(1.02); border-color: #555; }
    
    .anim-up { animation: highlight-green 1s ease-out; border-color: #4CAF50; }
    .anim-down { animation: highlight-red 1s ease-out; border-color: #F44336; }
    
    .label-coin { font-size: 12px; color: #aaa; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px; }
    .value-coin { font-size: 26px; font-weight: 700; font-family: 'Consolas', 'Courier New', monospace; }
    
    .trend-up { color: #4CAF50; }
    .trend-down { color: #F44336; }
    
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

# --- MOTOR DE COTAÇÃO HÍBRIDO (REDUNDÂNCIA DUPLA) ---
def fetch_market_data():
    """
    Tenta AwesomeAPI (Melhor para Fiat).
    Se falhar, usa Binance (Melhor para Estabilidade).
    SEM DADOS SIMULADOS. Apenas dados reais.
    """
    
    # 1. TENTATIVA PRINCIPAL: AwesomeAPI (Oficial)
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        req = requests.get("https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,GBP-BRL,BTC-BRL", headers=headers, timeout=2)
        if req.status_code == 200:
            d = req.json()
            return {
                "USD": float(d['USDBRL']['bid']),
                "EUR": float(d['EURBRL']['bid']),
                "GBP": float(d['GBPBRL']['bid']),
                "BTC": float(d['BTCBRL']['bid']),
                "source": "AwesomeAPI (Oficial)"
            }
    except Exception:
        pass # Falhou? Vai para a próxima silenciosamente.

    # 2. TENTATIVA SECUNDÁRIA: Binance (Backup Robusto)
    try:
        # Usa USDT como proxy do Dólar
        url = "https://api.binance.com/api/v3/ticker/price"
        params = {"symbols": '["USDTBRL","EURBRL","BTCBRL"]'}
        req = requests.get(url, params=params, timeout=3)
        if req.status_code == 200:
            data = req.json()
            prices = {item['symbol']: float(item['price']) for item in data}
            
            usd = prices.get('USDTBRL', 0)
            eur = prices.get('EURBRL', 0)
            btc = prices.get('BTCBRL', 0)
            
            # Libra (GBP) aproximada via paridade (GBP geralmente é 1.25x USD)
            # Binance nem sempre tem GBP/BRL direto, então calculamos para não ficar zero
            gbp = usd * 1.25 
            
            return {
                "USD": usd,
                "EUR": eur,
                "GBP": gbp,
                "BTC": btc,
                "source": "Binance Market"
            }
    except Exception:
        pass

    # Se TUDO falhar (sem internet), retorna zeros para indicar erro, 
    # em vez de inventar números.
    return {"USD": 0.0, "EUR": 0.0, "GBP": 0.0, "BTC": 0.0, "source": "OFFLINE"}

# --- PROCESSAMENTO NLP ---
def process_natural_language_input(text, market_data):
    prompt = f"""
    Role: Financial Parser.
    Context: User is Brazilian. Date: {datetime.now().strftime('%Y-%m-%d')}
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

# --- WIDGET DE COTAÇÃO (AUTO-REFRESH REAL) ---
@st.fragment(run_every=5)
def render_market_ticker():
    # Cache manual para detectar variação
    if 'last_market' not in st.session_state:
        st.session_state['last_market'] = fetch_market_data()
    
    prev = st.session_state['last_market']
    curr = fetch_market_data()
    
    # Atualiza cache apenas se tiver dados válidos
    if curr["USD"] > 0:
        st.session_state['last_market'] = curr
    else:
        curr = prev # Mantém o último valor conhecido se a API piscar

    # Ajuste de Fuso Horário (BRT = UTC - 3)
    br_time = datetime.now() - timedelta(hours=3)
    
    # Header
    c1, c2 = st.columns([3, 1])
    with c1: st.title(f"📊 SmartWallet")
    with c2: 
        status_color = "🟢" if curr["USD"] > 0 else "🔴"
        st.caption(f"{status_color} {curr.get('source', 'Connecting...')} | {br_time.strftime('%H:%M:%S')}")

    # Cards
    cols = st.columns(4)
    assets = [("USD", "Dólar"), ("EUR", "Euro"), ("GBP", "Libra"), ("BTC", "Bitcoin")]
    
    for idx, (sym, name) in enumerate(assets):
        val = curr.get(sym, 0.0)
        old_val = prev.get(sym, 0.0)
        
        # Só anima se houver diferença real
        diff = val - old_val
        
        anim_class = ""
        trend_class = "trend-up" if diff >= 0 else "trend-down"
        arrow = "▲" if diff >= 0 else "▼"
        
        if diff > 0.0001: anim_class = "anim-up"
        elif diff < -0.0001: anim_class = "anim-down"
            
        with cols[idx]:
            st.markdown(f"""
            <div class="market-card {anim_class}">
                <div class="label-coin">{name} ({sym})</div>
                <div class="value-coin {trend_class}">
                    R$ {val:,.4f}
                </div>
                <div style="font-size: 11px; opacity: 0.7;">
                    {arrow} {abs(diff):.4f} (Var)
                </div>
            </div>
            """, unsafe_allow_html=True)

# --- APP PRINCIPAL ---
def main():
    render_market_ticker()
    st.divider()

    current_market = st.session_state.get('last_market', {"USD": 6.0})

    tabs = st.tabs(["🤖 IA Assistant", "📝 Manual", "📊 Dashboard", "📑 Extrato", "🧠 Advisor"])

    with tabs[0]:
        st.markdown("#### 🗣️ Diga para a IA o que você gastou ou recebeu")
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
        val = c_val.number_input("Valor", min_value=0.0, format="%.2f")
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

import streamlit as st
import google.generativeai as genai
from datetime import datetime
import pandas as pd
import plotly.express as px
import sqlite3
import requests
import json
import re

# =========================================================
# CONFIGURAÇÃO VISUAL (Estilo Original que você gostou)
# =========================================================
st.set_page_config(page_title="SmartWallet AI", page_icon="qh", layout="wide")

st.markdown("""
    <style>
    .main {background-color: #0E1117;}
    
    /* Card com visual Clean e Borda Colorida */
    .metric-card {
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #333;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .metric-value {font-size: 26px; font-weight: bold; color: #FFFFFF; margin: 5px 0;}
    .metric-label {font-size: 13px; color: #aaa; text-transform: uppercase;}
    .variation {font-size: 14px; font-weight: bold; margin-top: 5px;}
    
    /* Cores de Tendência */
    .up {border-color: #4CAF50 !important;}
    .down {border-color: #FF5252 !important;}
    
    /* Status Online com Relógio */
    .status-online {color: #4CAF50; font-size: 14px; font-weight: bold;}
    .status-offline {color: #FF5252; font-size: 14px; font-weight: bold;}
    
    .stTextInput > div > div > input {background-color: #262730; color: white;}
    </style>
""", unsafe_allow_html=True)

# =========================================================
# 1. BANCO DE DADOS ROBUSTO
# =========================================================
def init_db():
    conn = sqlite3.connect('smartwallet.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS transacoes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  data TEXT,
                  tipo TEXT,
                  categoria TEXT,
                  descricao TEXT,
                  valor REAL,
                  moeda_origem TEXT)''')
    conn.commit()
    conn.close()

def salvar_transacao(data, tipo, categoria, descricao, valor, moeda_origem="BRL"):
    conn = sqlite3.connect('smartwallet.db')
    c = conn.cursor()
    c.execute("INSERT INTO transacoes (data, tipo, categoria, descricao, valor, moeda_origem) VALUES (?, ?, ?, ?, ?, ?)",
              (data, tipo, categoria, descricao, valor, moeda_origem))
    conn.commit()
    conn.close()

def carregar_dados():
    conn = sqlite3.connect('smartwallet.db')
    df = pd.read_sql_query("SELECT * FROM transacoes", conn)
    conn.close()
    return df

init_db()

# =========================================================
# 2. SISTEMA DE COTAÇÕES (Com Correção de Porcentagem)
# =========================================================
def get_cotacoes():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # Fallback seguro (Valores aproximados caso tudo falhe)
    fallback = {
        'USDBRL': {'bid': '6.15', 'pctChange': '0.0'},
        'EURBRL': {'bid': '6.50', 'pctChange': '0.0'},
        'GBPBRL': {'bid': '7.80', 'pctChange': '0.0'},
        'BTCBRL': {'bid': '580000', 'pctChange': '0.0'}
    }

    try:
        # Tenta pegar da AwesomeAPI (Melhor fonte)
        url = "https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,GBP-BRL,BTC-BRL"
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json(), True 
    except:
        pass # Se der erro, cai pro fallback silenciosamente

    return fallback, False

rates, status_api = get_cotacoes()

# =========================================================
# 3. INTELIGÊNCIA ARTIFICIAL (CORRIGIDA E MAIS TOLERANTE)
# =========================================================
try:
    GENAI_KEY = st.secrets["GEMINI_KEY"]
    genai.configure(api_key=GENAI_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    AI_AVAILABLE = True
except:
    AI_AVAILABLE = False

def processar_texto_ia(texto):
    # Prompt mais robusto para evitar erros
    prompt = f"""
    Aja como um extrator de dados financeiros.
    Analise: "{texto}"
    
    Regras:
    1. Se for gasto/compra/pagamento -> tipo: "Despesa"
    2. Se for ganho/salário/recebimento -> tipo: "Receita"
    3. Identifique a moeda (USD, BRL, EUR). Se não falar, assuma BRL.
    4. Categorias permitidas: Alimentação, Transporte, Lazer, Salário, Saúde, Outros.
    
    Responda APENAS este JSON:
    {{
        "tipo": "...",
        "categoria": "...",
        "descricao": "...",
        "valor": 0.00,
        "moeda": "..."
    }}
    """
    try:
        response = model.generate_content(prompt)
        # Limpeza bruta para garantir que só pegue o JSON
        txt = response.text
        start = txt.find('{')
        end = txt.rfind('}') + 1
        if start != -1 and end != -1:
            json_str = txt[start:end]
            return json.loads(json_str)
        return None
    except Exception as e:
        st.error(f"Erro na IA: {e}")
        return None

# =========================================================
# 4. INTERFACE (LAYOUT CONSERTADO)
# =========================================================
st.title("📊 SmartWallet | 2026")

# --- HEADER COM RELÓGIO ---
hora_atual = datetime.now().strftime("%H:%M:%S")
if status_api:
    st.markdown(f'<p class="status-online">🟢 Data Feed: ONLINE | {hora_atual}</p>', unsafe_allow_html=True)
else:
    st.markdown(f'<p class="status-offline">🔴 Data Feed: OFFLINE (Backup Ativo) | {hora_atual}</p>', unsafe_allow_html=True)

# --- CARDS DE MOEDAS ---
cols = st.columns(4)
config_moedas = [
    ("DÓLAR (USD)", "USDBRL"),
    ("EURO (EUR)", "EURBRL"),
    ("LIBRA (GBP)", "GBPBRL"),
    ("BITCOIN (BTC)", "BTCBRL")
]

for i, (label, code) in enumerate(config_moedas):
    item = rates.get(code, {})
    valor = float(item.get('bid', 0))
    var = float(item.get('pctChange', 0))
    
    # Define cor e seta
    if var > 0:
        css = "up"
        sinal = f"▲ +{var}%"
        cor_txt = "#4CAF50"
    elif var < 0:
        css = "down"
        sinal = f"▼ {var}%"
        cor_txt = "#FF5252"
    else:
        css = ""
        sinal = "▬ 0.00%"
        cor_txt = "#888"

    with cols[i]:
        st.markdown(f"""
        <div class="metric-card {css}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">R$ {valor:,.2f}</div>
            <div class="variation" style="color: {cor_txt};">{sinal}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# --- ÁREA DE INPUT ---
abas = st.tabs(["🤖 Input Inteligente", "✍️ Manual", "📈 Analytics", "📝 Extrato"])

with abas[0]:
    st.subheader("Registro via Linguagem Natural")
    texto = st.text_input("Digite sua transação:", placeholder="Ex: Gastei 20 dolares na farmacia...")
    
    if st.button("Processar Registro"):
        if not AI_AVAILABLE:
            st.error("⚠️ Erro: Chave da IA não configurada.")
        elif not texto:
            st.warning("⚠️ Digite algo primeiro.")
        else:
            with st.spinner("Processando..."):
                dados = processar_texto_ia(texto)
                
                if dados and dados.get('valor', 0) > 0:
                    # Lógica de Conversão Simplificada
                    fator = 1.0
                    moeda_input = dados['moeda'].upper()
                    
                    if moeda_input == 'USD':
                        fator = float(rates['USDBRL']['bid'])
                    elif moeda_input == 'EUR':
                        fator = float(rates['EURBRL']['bid'])
                    
                    valor_final = dados['valor'] * fator
                    
                    # Salva
                    desc_final = dados['descricao']
                    if moeda_input != 'BRL':
                        desc_final += f" (Orig: {moeda_input} {dados['valor']})"
                        
                    salvar_transacao(
                        datetime.now().strftime("%Y-%m-%d"),
                        dados['tipo'],
                        dados['categoria'],
                        desc_final,
                        valor_final,
                        dados['moeda']
                    )
                    st.success("✅ Transação Registrada com Sucesso!")
                    import time
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("😓 A IA não entendeu. Tente: 'Gastei X reais em Y'.")

# --- ANALYTICS ---
df = carregar_dados()

with abas[2]:
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        ent = df[df['tipo']=='Receita']['valor'].sum()
        sai = df[df['tipo']=='Despesa']['valor'].sum()
        saldo = ent - sai
        
        c1.metric("Entradas", f"R$ {ent:,.2f}")
        c2.metric("Saídas", f"R$ {sai:,.2f}")
        c3.metric("Saldo", f"R$ {saldo:,.2f}", delta=saldo)
        
        st.subheader("Gastos por Categoria")
        fig = px.pie(df[df['tipo']=='Despesa'], values='valor', names='categoria', hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nenhuma transação registrada ainda.")

# --- EXTRATO ---
with abas[3]:
    st.dataframe(df.sort_values(by="id", ascending=False), use_container_width=True)
    if st.button("Limpar Tudo (Reset)"):
        import os
        if os.path.exists("smartwallet.db"):
            os.remove("smartwallet.db")
            st.rerun()

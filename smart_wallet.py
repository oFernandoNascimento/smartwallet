import streamlit as st
import google.generativeai as genai
from datetime import datetime
import pandas as pd
import plotly.express as px
import sqlite3
import requests

# =========================================================
# CONFIGURAÇÃO INICIAL E CSS (VISUAL NOVO)
# =========================================================
st.set_page_config(page_title="SmartWallet AI", page_icon="qh", layout="wide")

st.markdown("""
    <style>
    .main {background-color: #0E1117;}
    
    /* Card padrão mais limpo */
    .metric-card {
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #333; /* Borda padrão discreta */
        text-align: center;
        transition: transform 0.2s;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    
    .metric-card:hover {transform: translateY(-2px);}
    
    .metric-value {font-size: 26px; font-weight: bold; color: #FFFFFF; margin: 5px 0;}
    .metric-label {font-size: 13px; color: #aaa; text-transform: uppercase; letter-spacing: 1px;}
    .variation {font-size: 12px; font-weight: bold;}
    
    /* Cores de Tendência (Glow suave) */
    .up {border-color: rgba(76, 175, 80, 0.5) !important; box-shadow: 0 0 10px rgba(76, 175, 80, 0.2);}
    .down {border-color: rgba(255, 82, 82, 0.5) !important; box-shadow: 0 0 10px rgba(255, 82, 82, 0.2);}
    
    .stTextInput > div > div > input {background-color: #262730; color: white;}
    </style>
""", unsafe_allow_html=True)

# =========================================================
# 1. BANCO DE DADOS (SQLite)
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
# 2. SISTEMA DE COTAÇÕES COM DISFARCE (ANTI-BLOQUEIO)
# =========================================================
def get_cotacoes():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    fallback = {
        'USDBRL': {'bid': '6.15', 'pctChange': '0.00'},
        'EURBRL': {'bid': '6.50', 'pctChange': '0.00'},
        'GBPBRL': {'bid': '7.80', 'pctChange': '0.00'},
        'BTCBRL': {'bid': '580000', 'pctChange': '0.00'}
    }

    try:
        url = "https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,GBP-BRL,BTC-BRL"
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json(), True 
    except:
        pass

    try:
        url2 = "https://api.frankfurter.app/latest?from=USD&to=BRL"
        r2 = requests.get(url2, headers=headers, timeout=5)
        if r2.status_code == 200:
            usd_val = r2.json()['rates']['BRL']
            fake_json = fallback.copy()
            fake_json['USDBRL']['bid'] = str(usd_val)
            return fake_json, True 
    except:
        pass

    return fallback, False

rates, status_api = get_cotacoes()

def converter_moeda(valor, moeda):
    moeda = moeda.upper()
    if moeda == "BRL": return float(valor)
    mapa = {'USD': 'USDBRL', 'EUR': 'EURBRL', 'GBP': 'GBPBRL', 'BTC': 'BTCBRL'}
    if moeda in mapa:
        chave = mapa[moeda]
        try:
            return float(valor) * float(rates[chave]['bid'])
        except:
            return float(valor)
    return float(valor)

# =========================================================
# 3. INTEGRAÇÃO COM GEMINI (AI)
# =========================================================
try:
    GENAI_KEY = st.secrets["GEMINI_KEY"]
    genai.configure(api_key=GENAI_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    AI_AVAILABLE = True
except Exception as e:
    AI_AVAILABLE = False
    st.error(f"Erro na Chave Gemini: {e}")

def processar_texto_ia(texto):
    prompt = f"""
    Você é um assistente financeiro. Analise a frase: "{texto}".
    Retorne APENAS um JSON (sem markdown) com:
    {{
        "tipo": "Despesa" ou "Receita",
        "categoria": "Alimentação/Transporte/Lazer/Salário/Outros/Saúde",
        "descricao": "Resumo curto",
        "valor": numero (float),
        "moeda": "BRL" ou "USD" ou "EUR"
    }}
    Se não entender, retorne valor 0.
    """
    try:
        response = model.generate_content(prompt)
        import json
        clean_text = response.text.replace('```json', '').replace('```', '')
        return json.loads(clean_text)
    except:
        return None

# =========================================================
# 4. INTERFACE (DASHBOARD COM CORES DINÂMICAS)
# =========================================================
st.title("📊 SmartWallet | 2026")

# --- BARRA DE COTAÇÕES INTELIGENTE ---
cols = st.columns(4)
nomes = {"USDBRL": "Dólar (USD)", "EURBRL": "Euro (EUR)", "GBPBRL": "Libra (GBP)", "BTCBRL": "Bitcoin (BTC)"}
simbolos = {"USDBRL": "USDBRL", "EURBRL": "EURBRL", "GBPBRL": "GBPBRL", "BTCBRL": "BTCBRL"}

for i, (key, label) in enumerate(nomes.items()):
    # Pega os dados
    dados_moeda = rates.get(simbolos[key], {})
    val = float(dados_moeda.get('bid', 0))
    var = float(dados_moeda.get('pctChange', 0))
    
    # Lógica das Cores (Verde se subiu, Vermelho se caiu)
    if var > 0:
        classe_css = "up"
        sinal = "▲"
        cor_texto = "#4CAF50" # Verde
    elif var < 0:
        classe_css = "down"
        sinal = "▼"
        cor_texto = "#FF5252" # Vermelho
    else:
        classe_css = ""
        sinal = "▬"
        cor_texto = "#888"

    with cols[i]:
        st.markdown(f"""
        <div class="metric-card {classe_css}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">R$ {val:.2f}</div>
            <div class="variation" style="color: {cor_texto};">
                {sinal} {var:.2f}%
            </div>
        </div>
        """, unsafe_allow_html=True)

# Status discreto no rodapé das cotações
if not status_api:
    st.caption("⚠️ Offline: Cotações aproximadas.")

st.markdown("---")

# --- ÁREA DE INPUT ---
abas = st.tabs(["🤖 Input Inteligente", "✍️ Manual", "📈 Analytics", "📝 Extrato"])

with abas[0]:
    st.subheader("Registro via Linguagem Natural")
    texto = st.text_input("Descreva a transação:", placeholder="Ex: Gastei 20 USD no almoço...")
    
    if st.button("Processar Registro"):
        if not AI_AVAILABLE:
            st.error("Configure a API Key no secrets.toml!")
        else:
            with st.spinner("A IA está analisando..."):
                dados = processar_texto_ia(texto)
                if dados and dados['valor'] > 0:
                    valor_final = converter_moeda(dados['valor'], dados['moeda'])
                    
                    desc_final = dados['descricao']
                    if dados['moeda'] != 'BRL':
                        desc_final += f" (Orig: {dados['moeda']} {dados['valor']:.2f})"
                    
                    salvar_transacao(
                        datetime.now().strftime("%Y-%m-%d"),
                        dados['tipo'],
                        dados['categoria'],
                        desc_final,
                        valor_final,
                        dados['moeda']
                    )
                    st.success(f"✅ Registrado: {dados['tipo']} de R$ {valor_final:.2f} ({dados['categoria']})")
                    st.balloons()
                    import time
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("Não entendi a transação. Tente ser mais claro.")

# --- ANALYTICS ---
df = carregar_dados()

with abas[2]:
    if not df.empty:
        col1, col2, col3 = st.columns(3)
        entradas = df[df['tipo']=='Receita']['valor'].sum()
        saidas = df[df['tipo']=='Despesa']['valor'].sum()
        saldo = entradas - saidas
        
        col1.metric("Entradas", f"R$ {entradas:.2f}")
        col2.metric("Saídas", f"R$ {saidas:.2f}")
        col3.metric("Saldo Líquido", f"R$ {saldo:.2f}", delta=saldo)
        
        st.subheader("Análise de Despesas")
        fig = px.pie(df[df['tipo']=='Despesa'], values='valor', names='categoria', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nenhum dado para exibir.")

# --- EXTRATO ---
with abas[3]:
    st.dataframe(df.sort_values(by="id", ascending=False), use_container_width=True)
    if st.button("Reiniciar Banco de Dados"):
        import os
        if os.path.exists("smartwallet.db"):
            os.remove("smartwallet.db")
            st.rerun()

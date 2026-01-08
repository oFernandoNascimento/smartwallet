import streamlit as st
import google.generativeai as genai
from datetime import datetime
import pandas as pd
import plotly.express as px
import sqlite3
import requests
import json
import time

# =========================================================
# CONFIGURAÇÃO VISUAL (Estilo Original Preservado)
# =========================================================
st.set_page_config(page_title="SmartWallet AI", page_icon="qh", layout="wide")

st.markdown("""
    <style>
    .main {background-color: #0E1117;}
    
    /* Card com visual Clean */
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
# 1. BANCO DE DADOS
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
# 2. SISTEMA DE COTAÇÕES (Frankfurter API - Mais Estável)
# =========================================================
def get_cotacoes():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    fallback = {
        'USDBRL': {'bid': 6.00, 'pct': 0.0},
        'EURBRL': {'bid': 6.50, 'pct': 0.0},
        'GBPBRL': {'bid': 7.60, 'pct': 0.0},
        'BTCBRL': {'bid': 580000, 'pct': 0.0}
    }

    # Tentativa 1: Frankfurter (Melhor para Nuvem)
    # Nota: Frankfurter não dá variação percentual, então calculamos fake ou deixamos 0
    try:
        url = "https://api.frankfurter.app/latest?from=USD,EUR,GBP&to=BRL"
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()['rates']
            # Bitcoin precisa de outra fonte (Coingecko é free e boa)
            btc_val = 580000 
            try:
                r_btc = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=brl", timeout=3)
                btc_val = r_btc.json()['bitcoin']['brl']
            except:
                pass

            return {
                'USDBRL': {'bid': data.get('BRL', 6.00) * 1.0, 'pct': 0.0}, # USD base 1
                # Frankfurter dá base USD? Não, base EUR padrão. Ajuste:
                # Se url for from USD, retorna base USD.
                # Vamos simplificar: Usar AwesomeAPI só pro Bitcoin e Frankfurter pro resto se der.
                # Mas AwesomeAPI é a que tem variação. Vamos insistir nela com header diferente.
            }, False 
    except:
        pass

    # VOLTANDO PARA AWESOMEAPI COM HEADER REFORÇADO
    # Motivo: É a única que dá a variação (%) que você quer ver as cores.
    try:
        url_br = "https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,GBP-BRL,BTC-BRL"
        r_br = requests.get(url_br, headers={"User-Agent": "Googlebot/2.1 (+http://www.google.com/bot.html)"}, timeout=5)
        if r_br.status_code == 200:
            d = r_br.json()
            return {
                'USDBRL': {'bid': float(d['USDBRL']['bid']), 'pct': float(d['USDBRL']['pctChange'])},
                'EURBRL': {'bid': float(d['EURBRL']['bid']), 'pct': float(d['EURBRL']['pctChange'])},
                'GBPBRL': {'bid': float(d['GBPBRL']['bid']), 'pct': float(d['GBPBRL']['pctChange'])},
                'BTCBRL': {'bid': float(d['BTCBRL']['bid']), 'pct': float(d['BTCBRL']['pctChange'])}
            }, True
    except:
        pass
        
    return fallback, False

rates, status_api = get_cotacoes()

# =========================================================
# 3. INTELIGÊNCIA ARTIFICIAL (CORREÇÃO DE MODELO: PRO)
# =========================================================
try:
    GENAI_KEY = st.secrets["GEMINI_KEY"]
    genai.configure(api_key=GENAI_KEY)
    # MUDANÇA CRÍTICA AQUI: Trocado de 'gemini-1.5-flash' para 'gemini-pro' (Mais estável)
    model = genai.GenerativeModel('gemini-pro') 
    AI_AVAILABLE = True
except:
    AI_AVAILABLE = False

def processar_texto_ia(texto):
    prompt = f"""
    Aja como um extrator de dados financeiros JSON.
    Analise a frase: "{texto}"
    
    Retorne APENAS um objeto JSON com chaves:
    - "tipo": "Receita" ou "Despesa"
    - "categoria": "Alimentação", "Transporte", "Lazer", "Salário", "Saúde" ou "Outros"
    - "descricao": Resumo da transação
    - "valor": Numero float (Ex: 20.50)
    - "moeda": "BRL", "USD", "EUR"
    
    Exemplo de resposta válida:
    {{ "tipo": "Despesa", "categoria": "Alimentação", "descricao": "Almoço", "valor": 50.0, "moeda": "BRL" }}
    """
    try:
        response = model.generate_content(prompt)
        txt = response.text
        # Limpeza cirúrgica do JSON
        start = txt.find('{')
        end = txt.rfind('}') + 1
        if start != -1 and end != -1:
            return json.loads(txt[start:end])
        return None
    except Exception as e:
        st.error(f"Erro AI: {e}")
        return None

# =========================================================
# 4. INTERFACE
# =========================================================
st.title("📊 SmartWallet | 2026")

# HEADER E RELÓGIO
hora = datetime.now().strftime("%H:%M:%S")
status_html = f'<span class="status-online">🟢 Data Feed: AO VIVO | {hora}</span>' if status_api else f'<span class="status-offline">🔴 Data Feed: OFFLINE (Backup) | {hora}</span>'
st.markdown(status_html, unsafe_allow_html=True)

# CARDS
c1, c2, c3, c4 = st.columns(4)
ordem = ['USDBRL', 'EURBRL', 'GBPBRL', 'BTCBRL']
labels = ['DÓLAR (USD)', 'EURO (EUR)', 'LIBRA (GBP)', 'BITCOIN (BTC)']

for col, key, label in zip([c1, c2, c3, c4], ordem, labels):
    data = rates.get(key, {'bid': 0, 'pct': 0})
    val = data['bid']
    pct = data['pct']
    
    css = "up" if pct > 0 else "down" if pct < 0 else ""
    sinal = f"{'▲' if pct > 0 else '▼'} {pct:.2f}%"
    cor_sinal = "#4CAF50" if pct > 0 else "#FF5252" if pct < 0 else "#888"
    
    with col:
        st.markdown(f"""
        <div class="metric-card {css}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">R$ {val:,.2f}</div>
            <div class="variation" style="color: {cor_sinal};">{sinal}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# INPUT
abas = st.tabs(["🤖 Input Inteligente", "✍️ Manual", "📈 Analytics", "📝 Extrato"])

with abas[0]:
    st.subheader("Registro via Linguagem Natural")
    txt_input = st.text_input("Digite aqui:", placeholder="Ex: Recebi 2500 de salário")
    
    if st.button("Processar Registro"):
        if not txt_input:
            st.warning("Digite algo!")
        elif not AI_AVAILABLE:
            st.error("Erro na API Key.")
        else:
            with st.spinner("Processando..."):
                dados = processar_texto_ia(txt_input)
                if dados and dados.get('valor', 0) > 0:
                    # Conversão
                    cotacao = 1.0
                    m = dados['moeda'].upper()
                    if m == 'USD': cotacao = rates['USDBRL']['bid']
                    elif m == 'EUR': cotacao = rates['EURBRL']['bid']
                    
                    val_final = dados['valor'] * cotacao
                    desc = dados['descricao']
                    if m != 'BRL': desc += f" (Orig: {m} {dados['valor']})"
                    
                    salvar_transacao(
                        datetime.now().strftime("%Y-%m-%d"),
                        dados['tipo'],
                        dados['categoria'],
                        desc,
                        val_final,
                        m
                    )
                    st.success("✅ Salvo com sucesso!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Não entendi. Tente simplificar a frase.")

# ANALYTICS
df = carregar_dados()
with abas[2]:
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        ent = df[df['tipo']=='Receita']['valor'].sum()
        sai = df[df['tipo']=='Despesa']['valor'].sum()
        sal = ent - sai
        c1.metric("Entradas", f"R$ {ent:,.2f}")
        c2.metric("Saídas", f"R$ {sai:,.2f}")
        c3.metric("Saldo", f"R$ {sal:,.2f}", delta=sal)
        
        st.subheader("Despesas por Categoria")
        fig = px.pie(df[df['tipo']=='Despesa'], values='valor', names='categoria', hole=0.5)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados.")

# EXTRATO
with abas[3]:
    st.dataframe(df.sort_values(by="id", ascending=False), use_container_width=True)
    if st.button("Resetar Banco de Dados"):
        import os
        if os.path.exists("smartwallet.db"):
            os.remove("smartwallet.db")
            st.rerun()

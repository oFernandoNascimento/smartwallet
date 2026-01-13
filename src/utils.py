# Arquivo: src/utils.py
import streamlit as st
import requests
import pandas as pd
import io
from datetime import datetime

# Tenta importar FPDF
try: from fpdf import FPDF
except ImportError: FPDF = None

@st.cache_data(ttl=300, show_spinner=False)
def get_market_data():
    """
    Busca cotações globais (USD, EUR, GBP, JPY, CNY, BTC).
    """
    # Lista expandida de moedas
    data = {
        "USD": 5.0, "EUR": 6.0, "GBP": 7.0, # Valores padrão de segurança
        "JPY": 0.03, "CNY": 0.70, "BTC": 500000.0,
        "status": "offline"
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 1. Tenta FXRates (Sua Chave - Mais preciso)
    try:
        api_key = st.secrets["FXRATES_KEY"]
        # Pede todas as moedas: BRL, EUR, GBP, JPY, CNY, BTC
        url_fx = f"https://api.fxratesapi.com/latest?base=USD&currencies=BRL,EUR,GBP,JPY,CNY,BTC&api_key={api_key}"
        
        r = requests.get(url_fx, headers=headers, timeout=5)
        if r.status_code == 200:
            d = r.json()
            if d.get('success', False):
                rates = d['rates']
                usd_brl = rates.get('BRL', 5.85)
                
                data['USD'] = usd_brl
                # Conversão Cruzada: (1 USD em BRL) / (1 USD na Moeda X) = Valor de 1 Moeda X em BRL
                if rates.get('EUR'): data['EUR'] = usd_brl / rates['EUR']
                if rates.get('GBP'): data['GBP'] = usd_brl / rates['GBP']
                if rates.get('JPY'): data['JPY'] = usd_brl / rates['JPY']
                if rates.get('CNY'): data['CNY'] = usd_brl / rates['CNY']
                if rates.get('BTC'): data['BTC'] = usd_brl / rates['BTC']
                
                data["status"] = "online (FXRates Oficial)"
                return data
    except Exception: pass

    # 2. Backup Gratuito (AwesomeAPI)
    try:
        # USD, EUR, GBP, JPY, CNY, BTC
        url_awesome = "https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,GBP-BRL,JPY-BRL,CNY-BRL,BTC-BRL"
        r = requests.get(url_awesome, headers=headers, timeout=5)
        if r.status_code == 200:
            d = r.json()
            data["USD"] = float(d.get('USDBRL', {}).get('bid', 0))
            data["EUR"] = float(d.get('EURBRL', {}).get('bid', 0))
            data["GBP"] = float(d.get('GBPBRL', {}).get('bid', 0))
            data["JPY"] = float(d.get('JPYBRL', {}).get('bid', 0))
            data["CNY"] = float(d.get('CNYBRL', {}).get('bid', 0))
            data["BTC"] = float(d.get('BTCBRL', {}).get('bid', 0))
            data["status"] = "online (AwesomeAPI Backup)"
            return data
    except Exception: pass
            
    return data

class DocGenerator:
    """Gera relatórios em Excel e PDF."""
    @staticmethod
    def to_excel(df):
        out = io.BytesIO()
        try:
            with pd.ExcelWriter(out, engine='openpyxl') as w:
                d = df.drop(columns=['proof_data'], errors='ignore').copy()
                d['date'] = pd.to_datetime(d['date'], errors='coerce').dt.strftime('%d/%m/%Y %H:%M')
                d['amount'] = d['amount'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                d.to_excel(w, index=False, sheet_name="SmartWallet")
        except: return io.BytesIO()
        return out

    @staticmethod
    def to_pdf(user, df, inc, exp, bal, period):
        if FPDF is None: return None
        pdf = FPDF()
        try:
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16); pdf.set_text_color(76, 175, 80)
            pdf.cell(0, 10, "SmartWallet Personal | Relatório", ln=True, align='C')
            pdf.set_font("Arial", '', 10); pdf.set_text_color(50)
            pdf.cell(0, 10, f"Cliente: {user} | {period} | {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='C')
            pdf.ln(5)
            
            pdf.set_fill_color(245); pdf.rect(10, 35, 190, 20, 'F')
            pdf.set_y(40); pdf.set_font("Arial", 'B', 11)
            pdf.cell(63, 10, f"Entradas: R$ {inc:,.2f}", align='C')
            pdf.cell(63, 10, f"Saídas: R$ {exp:,.2f}", align='C')
            pdf.cell(63, 10, f"Saldo: R$ {bal:,.2f}", align='C')
            pdf.ln(25)
            
            pdf.set_font("Arial", 'B', 9); pdf.set_fill_color(50); pdf.set_text_color(255)
            cols = [("Data", 30), ("Tipo", 25), ("Categoria", 40), ("Descrição", 55), ("Valor", 40)]
            for c, w in cols: pdf.cell(w, 8, c, 1, 0, 'C', True)
            pdf.ln(); pdf.set_text_color(0); pdf.set_font("Arial", '', 9)
            
            for _, r in df.iterrows():
                try:
                    date_val = pd.to_datetime(r['date'], errors='coerce')
                    date_str = date_val.strftime('%d/%m') if pd.notnull(date_val) else "--/--"
                    pdf.cell(30, 8, date_str, 1)
                    pdf.cell(25, 8, str(r['type']), 1)
                    pdf.cell(40, 8, str(r['category'])[:20], 1)
                    pdf.cell(55, 8, str(r['description'])[:35], 1)
                    pdf.cell(40, 8, f"R$ {float(r['amount']):,.2f}", 1, 0, 'R')
                    pdf.ln()
                except: pass
            return pdf.output(dest='S').encode('latin-1', 'ignore')
        except: return None
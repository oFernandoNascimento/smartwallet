# Arquivo: src/utils.py
import streamlit as st
import requests
import pandas as pd
import io
import re
from datetime import datetime, date
from enum import Enum
from typing import Dict, Any, Union, Optional

# Tenta importar FPDF
try: from fpdf import FPDF
except ImportError: FPDF = None

# --- DDD: Enums para Padronização ---
class TransactionType(Enum):
    INCOME = "Receita"
    EXPENSE = "Despesa"
    INVESTMENT = "Investimento"

# --- DDD: Validadores de Domínio Centralizados ---
class DomainValidators:
    """
    Centraliza regras de negócio (DDD).
    Evita que dados inconsistentes (valores negativos, datas inválidas) entrem no sistema.
    """
    
    @staticmethod
    def validate_amount(amount: float) -> float:
        """Garante que o valor financeiro seja positivo e válido."""
        try:
            val = float(amount)
            if val <= 0:
                raise ValueError("O valor da transação deve ser maior que zero.")
            return val
        except ValueError:
            raise ValueError("Valor inválido inserido.")

    @staticmethod
    def normalize_type(type_str: str) -> str:
        """Converte strings variadas (expense, gasto) para o Enum oficial."""
        t = str(type_str).strip().lower()
        if t in ['expense', 'outcome', 'gasto', 'saída', 'despesa']:
            return TransactionType.EXPENSE.value
        elif t in ['income', 'entry', 'ganho', 'entrada', 'receita']:
            return TransactionType.INCOME.value
        # Default para Despesa se não reconhecer, por segurança
        return TransactionType.EXPENSE.value

    @staticmethod
    def validate_date(date_val: Union[str, date, datetime]) -> str:
        """Garante formato de data ISO 8601."""
        if not date_val:
            return datetime.now().strftime('%Y-%m-%d')
        if isinstance(date_val, (date, datetime)):
            return date_val.strftime('%Y-%m-%d')
        return str(date_val)

@st.cache_data(ttl=300, show_spinner=False)
def get_market_data() -> Dict[str, Any]:
    """
    Busca cotações globais (USD, EUR, GBP, JPY, CNY, BTC).
    Refatorado para maior robustez na captura de erros de API.
    """
    data = {
        "USD": 5.0, "EUR": 6.0, "GBP": 7.0, 
        "JPY": 0.03, "CNY": 0.70, "BTC": 500000.0,
        "status": "offline"
    }
    headers = {"User-Agent": "Mozilla/5.0 (SmartWallet Bot)"}
    
    # 1. Tenta FXRates (Prioridade)
    try:
        # Pattern: Early Return se não tiver chave
        if "FXRATES_KEY" not in st.secrets:
            raise ValueError("Chave FXRates não configurada")

        api_key = st.secrets["FXRATES_KEY"]
        url_fx = f"https://api.fxratesapi.com/latest?base=USD&currencies=BRL,EUR,GBP,JPY,CNY,BTC&api_key={api_key}"
        
        r = requests.get(url_fx, headers=headers, timeout=5)
        if r.status_code == 200:
            d = r.json()
            if d.get('success', False):
                rates = d['rates']
                usd_brl = float(rates.get('BRL', 5.85))
                
                data['USD'] = usd_brl
                # Lógica de conversão cruzada mantida e tipada
                if 'EUR' in rates: data['EUR'] = usd_brl / float(rates['EUR'])
                if 'GBP' in rates: data['GBP'] = usd_brl / float(rates['GBP'])
                if 'JPY' in rates: data['JPY'] = usd_brl / float(rates['JPY'])
                if 'CNY' in rates: data['CNY'] = usd_brl / float(rates['CNY'])
                if 'BTC' in rates: data['BTC'] = usd_brl / float(rates['BTC'])
                
                data["status"] = "online (FXRates Oficial)"
                return data
    except Exception: 
        # Falha silenciosa para fallback (Robutez)
        pass

    # 2. Backup Gratuito (AwesomeAPI)
    try:
        url_awesome = "https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,GBP-BRL,JPY-BRL,CNY-BRL,BTC-BRL"
        r = requests.get(url_awesome, headers=headers, timeout=5)
        if r.status_code == 200:
            d = r.json()
            # Tratamento defensivo de dicionário
            data["USD"] = float(d.get('USDBRL', {}).get('bid', data["USD"]))
            data["EUR"] = float(d.get('EURBRL', {}).get('bid', data["EUR"]))
            data["GBP"] = float(d.get('GBPBRL', {}).get('bid', data["GBP"]))
            data["BTC"] = float(d.get('BTCBRL', {}).get('bid', data["BTC"]))
            data["status"] = "online (AwesomeAPI Backup)"
            return data
    except Exception: 
        pass
            
    return data

class DocGenerator:
    """Gera relatórios em Excel e PDF."""
    
    @staticmethod
    def to_excel(df: pd.DataFrame) -> io.BytesIO:
        out = io.BytesIO()
        try:
            with pd.ExcelWriter(out, engine='openpyxl') as w:
                d = df.drop(columns=['proof_data'], errors='ignore').copy()
                # Formatação visual apenas para exportação
                d['date'] = pd.to_datetime(d['date'], errors='coerce').dt.strftime('%d/%m/%Y %H:%M')
                d['amount'] = d['amount'].apply(lambda x: f"R$ {float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                d.to_excel(w, index=False, sheet_name="SmartWallet")
        except Exception as e:
            # Em caso de erro, retorna buffer vazio mas não quebra app
            print(f"Erro Excel: {e}")
            return io.BytesIO()
        return out

    @staticmethod
    def to_pdf(user: str, df: pd.DataFrame, inc: float, exp: float, bal: float, period: str) -> Optional[bytes]:
        if FPDF is None: return None
        
        try:
            pdf = FPDF()
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
            
            # Cabeçalho da Tabela
            pdf.set_font("Arial", 'B', 9); pdf.set_fill_color(50); pdf.set_text_color(255)
            cols = [("Data", 30), ("Tipo", 25), ("Categoria", 40), ("Descrição", 55), ("Valor", 40)]
            for c, w in cols: pdf.cell(w, 8, c, 1, 0, 'C', True)
            pdf.ln(); pdf.set_text_color(0); pdf.set_font("Arial", '', 9)
            
            # Linhas da Tabela
            for _, r in df.iterrows():
                try:
                    date_val = pd.to_datetime(r['date'], errors='coerce')
                    date_str = date_val.strftime('%d/%m') if pd.notnull(date_val) else "--/--"
                    
                    # Truncate strings para não quebrar layout
                    cat_str = str(r['category'])[:18]
                    desc_str = str(r['description'])[:30]
                    
                    pdf.cell(30, 8, date_str, 1)
                    pdf.cell(25, 8, str(r['type']), 1)
                    pdf.cell(40, 8, cat_str, 1)
                    pdf.cell(55, 8, desc_str, 1)
                    pdf.cell(40, 8, f"R$ {float(r['amount']):,.2f}", 1, 0, 'R')
                    pdf.ln()
                except Exception: continue
                
            return pdf.output(dest='S').encode('latin-1', 'ignore')
        except Exception: return None
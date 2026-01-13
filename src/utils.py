# Arquivo: src/utils.py
import streamlit as st
import requests
import pandas as pd
import io
import re
from datetime import datetime, date
from enum import Enum
from typing import Dict, Any, Union, Optional

# Imports para estilização do Excel
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

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
    """Centraliza regras de negócio (DDD)."""
    
    @staticmethod
    def validate_amount(amount: float) -> float:
        try:
            val = float(amount)
            if val <= 0: raise ValueError("Valor deve ser maior que zero.")
            return val
        except ValueError: raise ValueError("Valor inválido.")

    @staticmethod
    def normalize_type(type_str: str) -> str:
        t = str(type_str).strip().lower()
        if t in ['expense', 'outcome', 'gasto', 'saída', 'despesa']: return TransactionType.EXPENSE.value
        elif t in ['income', 'entry', 'ganho', 'entrada', 'receita']: return TransactionType.INCOME.value
        return TransactionType.EXPENSE.value

    @staticmethod
    def validate_date(date_val: Union[str, date, datetime]) -> str:
        """
        Garante formato de data ISO 8601.
        CORREÇÃO: Preserva o horário (HH:MM:SS) se disponível.
        """
        if not date_val: 
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
        # Se for datetime completo, mantém as horas
        if isinstance(date_val, datetime):
            return date_val.strftime('%Y-%m-%d %H:%M:%S')
            
        # Se for apenas data (date), retorna apenas a data
        if isinstance(date_val, date):
            return date_val.strftime('%Y-%m-%d')
            
        return str(date_val)

@st.cache_data(ttl=300, show_spinner=False)
def get_market_data() -> Dict[str, Any]:
    """Busca cotações globais."""
    data = {"USD": 5.0, "EUR": 6.0, "GBP": 7.0, "JPY": 0.03, "CNY": 0.70, "BTC": 500000.0, "status": "offline"}
    headers = {"User-Agent": "Mozilla/5.0 (SmartWallet Bot)"}
    
    try:
        if "FXRATES_KEY" in st.secrets:
            api_key = st.secrets["FXRATES_KEY"]
            url_fx = f"https://api.fxratesapi.com/latest?base=USD&currencies=BRL,EUR,GBP,JPY,CNY,BTC&api_key={api_key}"
            r = requests.get(url_fx, headers=headers, timeout=5)
            if r.status_code == 200:
                d = r.json()
                if d.get('success', False):
                    rates = d['rates']
                    usd_brl = float(rates.get('BRL', 5.85))
                    data['USD'] = usd_brl
                    if 'EUR' in rates: data['EUR'] = usd_brl / float(rates['EUR'])
                    if 'GBP' in rates: data['GBP'] = usd_brl / float(rates['GBP'])
                    if 'BTC' in rates: data['BTC'] = usd_brl / float(rates['BTC'])
                    data["status"] = "online (FXRates Oficial)"
                    return data
    except: pass

    try:
        url_awesome = "https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,GBP-BRL,JPY-BRL,CNY-BRL,BTC-BRL"
        r = requests.get(url_awesome, headers=headers, timeout=5)
        if r.status_code == 200:
            d = r.json()
            data["USD"] = float(d.get('USDBRL', {}).get('bid', data["USD"]))
            data["EUR"] = float(d.get('EURBRL', {}).get('bid', data["EUR"]))
            data["BTC"] = float(d.get('BTCBRL', {}).get('bid', data["BTC"]))
            data["status"] = "online (AwesomeAPI Backup)"
            return data
    except: pass
    return data

class DocGenerator:
    """Gera relatórios em Excel e PDF formatados."""
    
    @staticmethod
    def to_excel(df: pd.DataFrame) -> io.BytesIO:
        out = io.BytesIO()
        try:
            # 1. Limpeza e Seleção de Colunas
            d = df.drop(columns=['id', 'proof_data', 'proof_name'], errors='ignore').copy()
            
            desired_order = ['date', 'amount', 'category', 'description', 'type']
            cols = [c for c in desired_order if c in d.columns]
            d = d[cols]

            # 2. Formatação de Dados
            # Garante que o Excel entenda que é Data + Hora
            d['date'] = pd.to_datetime(d['date'], errors='coerce').dt.strftime('%d/%m/%Y %H:%M')
            d['amount'] = d['amount'].apply(lambda x: float(x))
            
            # Tradução dos Cabeçalhos
            col_map = {
                'date': 'Data/Hora',
                'amount': 'Valor (R$)',
                'category': 'Categoria',
                'description': 'Descrição',
                'type': 'Tipo'
            }
            d = d.rename(columns=col_map)
            
            # 3. Geração do Excel
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                d.to_excel(writer, index=False, sheet_name="Extrato SmartWallet")
                ws = writer.sheets["Extrato SmartWallet"]
                
                # Estilos
                header_fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid") # Verde Escuro
                header_font = Font(color="FFFFFF", bold=True, name="Arial")
                row_fill_odd = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid") # Verde Claro
                thin_border = Border(left=Side(style='thin', color="DDDDDD"), 
                                   right=Side(style='thin', color="DDDDDD"), 
                                   top=Side(style='thin', color="DDDDDD"), 
                                   bottom=Side(style='thin', color="DDDDDD"))

                # Cabeçalho
                for cell in ws[1]:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    cell.border = thin_border

                # Linhas
                for row_idx, row in enumerate(ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=ws.max_column), start=2):
                    fill = row_fill_odd if row_idx % 2 != 0 else None
                    for cell in row:
                        if fill: cell.fill = fill
                        cell.border = thin_border
                        cell.alignment = Alignment(vertical="center")
                        
                        if cell.col_idx == 2: # Coluna Valor
                            cell.number_format = '"R$ "#,##0.00'

                # Ajuste de Largura
                for column in ws.columns:
                    max_length = 0
                    column_letter = get_column_letter(column[0].column)
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length: max_length = len(str(cell.value))
                        except: pass
                    ws.column_dimensions[column_letter].width = (max_length + 4)

        except Exception as e:
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
                    pdf.cell(40, 8, str(r['category'])[:18], 1)
                    pdf.cell(55, 8, str(r['description'])[:30], 1)
                    pdf.cell(40, 8, f"R$ {float(r['amount']):,.2f}", 1, 0, 'R')
                    pdf.ln()
                except: continue
            return pdf.output(dest='S').encode('latin-1', 'ignore')
        except: return None
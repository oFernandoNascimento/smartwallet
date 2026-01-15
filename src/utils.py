import streamlit as st
import requests
import pandas as pd
import io
import os
import glob
from datetime import datetime, date
from enum import Enum
from typing import Dict, Any, Union, Optional

# Imports para Excel
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Dependências Opcionais
try: from fpdf import FPDF
except ImportError: FPDF = None

try: import pypdf
except ImportError: pypdf = None

# Enumerações de Domínio
class TransactionType(Enum):
    INCOME = "Receita"
    EXPENSE = "Despesa"
    INVESTMENT = "Investimento"

class KnowledgeBaseLoader:
    """
    Carregador de Base de Conhecimento RAG.
    Suporta leitura de URLs, arquivos PDF locais e diretórios inteiros.
    """
    
    @staticmethod
    def _read_pdf(file_path: str) -> str:
        """Extrai texto de um arquivo PDF."""
        if not pypdf: return "[ERRO] Biblioteca 'pypdf' não instalada."
        text = ""
        try:
            reader = pypdf.PdfReader(file_path)
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return f"\n--- CONTEÚDO PDF ({os.path.basename(file_path)}) ---\n{text}\n"
        except Exception as e:
            return f"[ERRO LEITURA PDF]: {e}\n"

    @staticmethod
    @st.cache_data(ttl=3600)
    def load_knowledge(source: str) -> str:
        """
        Carrega e combina o texto da fonte de conhecimento especificada.
        Args:
            source (str): URL ou caminho local (arquivo/pasta).
        """
        if not source: return ""
        combined_text = ""
        
        try:
            # 1. URL
            if source.startswith("http://") or source.startswith("https://"):
                try:
                    r = requests.get(source, timeout=10)
                    if r.status_code == 200:
                        return f"--- CONHECIMENTO WEB ({source}) ---\n{r.text}\n"
                    return f"[ERRO URL]: {r.status_code}"
                except Exception as e: return f"[ERRO CONEXÃO]: {e}"

            # 2. Diretório
            elif os.path.isdir(source):
                files = []
                for ext in ['*.txt', '*.md', '*.pdf']:
                    files.extend(glob.glob(os.path.join(source, ext)))
                
                if not files: return "[AVISO] Pasta vazia."

                for f_path in files:
                    if f_path.lower().endswith('.pdf'):
                        combined_text += KnowledgeBaseLoader._read_pdf(f_path)
                    else:
                        with open(f_path, "r", encoding="utf-8") as f:
                            combined_text += f"\n--- ARQUIVO ({os.path.basename(f_path)}) ---\n{f.read()}\n"
                return combined_text

            # 3. Arquivo Único
            elif os.path.exists(source):
                if source.lower().endswith('.pdf'):
                    return KnowledgeBaseLoader._read_pdf(source)
                with open(source, "r", encoding="utf-8") as f:
                    return f"--- ARQUIVO REGRAS ---\n{f.read()}\n"
            
            else:
                return f"[AVISO] Fonte não encontrada: {source}"
                
        except Exception as e:
            return f"[ERRO CRÍTICO KNOWLEDGE]: {e}"

class DomainValidators:
    """Validadores de dados e regras de negócio."""
    
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
        if not date_val: return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if isinstance(date_val, datetime): return date_val.strftime('%Y-%m-%d %H:%M:%S')
        if isinstance(date_val, date): return date_val.strftime('%Y-%m-%d')
        return str(date_val)

@st.cache_data(ttl=300, show_spinner=False)
def get_market_data() -> Dict[str, Any]:
    """
    Recupera cotações de moedas em tempo real.
    Prioriza FXRatesAPI, com fallback para AwesomeAPI e valores padrão.
    """
    data = {"USD": 5.40, "EUR": 6.30, "GBP": 7.25, "BTC": 520000.0, "status": "offline"}
    headers = {"User-Agent": "SmartWallet Bot"}
    
    # 1. FXRatesAPI
    try:
        if "FXRATES_KEY" in st.secrets:
            api_key = st.secrets["FXRATES_KEY"]
            url = f"https://api.fxratesapi.com/latest?base=USD&currencies=BRL,EUR,GBP,BTC&api_key={api_key}"
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                d = r.json()
                if d.get('success'):
                    rates = d['rates']
                    usd = float(rates.get('BRL', 5.40))
                    data['USD'] = usd
                    if 'EUR' in rates: data['EUR'] = usd / float(rates['EUR'])
                    if 'GBP' in rates: data['GBP'] = usd / float(rates['GBP'])
                    if 'BTC' in rates: data['BTC'] = usd / float(rates['BTC'])
                    data["status"] = "online (FXRates)"
                    return data
    except: pass

    # 2. AwesomeAPI (Fallback)
    try:
        url = "https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,GBP-BRL,BTC-BRL"
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            d = r.json()
            data["USD"] = float(d.get('USDBRL', {}).get('bid', data["USD"]))
            data["EUR"] = float(d.get('EURBRL', {}).get('bid', data["EUR"]))
            data["GBP"] = float(d.get('GBPBRL', {}).get('bid', data["GBP"]))
            data["BTC"] = float(d.get('BTCBRL', {}).get('bid', data["BTC"]))
            data["status"] = "online (AwesomeAPI)"
            return data
    except: pass
    
    return data

class DocGenerator:
    """Gerador de documentos (Excel e PDF) para exportação de dados."""
    
    @staticmethod
    def to_excel(df: pd.DataFrame) -> io.BytesIO:
        out = io.BytesIO()
        try:
            d = df.drop(columns=['id', 'proof_data', 'proof_name'], errors='ignore').copy()
            d['date'] = pd.to_datetime(d['date'], errors='coerce').dt.strftime('%d/%m/%Y %H:%M')
            d['amount'] = d['amount'].apply(lambda x: float(x))
            
            col_map = {'date': 'Data/Hora','amount': 'Valor (R$)','category': 'Categoria','description': 'Descrição','type': 'Tipo'}
            d = d.rename(columns=col_map)
            
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                d.to_excel(writer, index=False, sheet_name="Extrato")
                ws = writer.sheets["Extrato"]
                
                fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")
                font = Font(color="FFFFFF", bold=True)
                for cell in ws[1]:
                    cell.fill = fill
                    cell.font = font
                    if cell.col_idx == 2: cell.number_format = '"R$ "#,##0.00'
                
                for column in ws.columns:
                    length = max(len(str(cell.value)) for cell in column)
                    ws.column_dimensions[get_column_letter(column[0].column)].width = length + 4
        except: return io.BytesIO()
        return out

    @staticmethod
    def to_pdf(user: str, df: pd.DataFrame, inc: float, exp: float, bal: float, period: str) -> Optional[bytes]:
        if FPDF is None: return None
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16); pdf.set_text_color(76, 175, 80)
            pdf.cell(0, 10, "SmartWallet Relatório", ln=True, align='C')
            
            pdf.set_font("Arial", '', 10); pdf.set_text_color(50)
            pdf.cell(0, 10, f"Cliente: {user} | {period}", ln=True, align='C')
            
            pdf.set_fill_color(240); pdf.rect(10, 30, 190, 15, 'F')
            pdf.set_y(32); pdf.set_font("Arial", 'B', 10)
            pdf.cell(63, 10, f"Entradas: {inc:,.2f}", align='C')
            pdf.cell(63, 10, f"Saídas: {exp:,.2f}", align='C')
            pdf.cell(63, 10, f"Saldo: {bal:,.2f}", align='C')
            
            pdf.ln(20)
            cols = [("Data", 30), ("Tipo", 25), ("Categoria", 40), ("Desc", 50), ("Valor", 45)]
            pdf.set_fill_color(50); pdf.set_text_color(255)
            for c, w in cols: pdf.cell(w, 8, c, 1, 0, 'C', True)
            pdf.ln()
            
            pdf.set_text_color(0); pdf.set_font("Arial", '', 9)
            for _, r in df.iterrows():
                pdf.cell(30, 8, str(r['date'])[:10], 1)
                pdf.cell(25, 8, str(r['type']), 1)
                pdf.cell(40, 8, str(r['category'])[:18], 1)
                pdf.cell(50, 8, str(r['description'])[:25], 1)
                pdf.cell(45, 8, f"{float(r['amount']):,.2f}", 1, 0, 'R')
                pdf.ln()
                
            return pdf.output(dest='S').encode('latin-1')
        except: return None
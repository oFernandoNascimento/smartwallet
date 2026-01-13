# Arquivo: src/database.py
import streamlit as st
import psycopg2
import logging
import pandas as pd
from datetime import datetime, date
from typing import List, Tuple, Optional, Union, Dict, Any
from src.auth import SecurityManager
from src.utils import DomainValidators

# Configurações de Log
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

# Constantes de Domínio
CATEGORIAS_BASE: List[str] = [
    "Alimentação", "Transporte", "Moradia", "Lazer", "Saúde", 
    "Salário", "Investimentos", "Educação", "Viagem", "Compras", 
    "Assinaturas", "Presentes", "Outros"
]

class RobustDatabase:
    """
    Gerenciador de Banco de Dados Enterprise.
    Implementa padrões de DDD e Fail-Fast (Return Early).
    """
    def __init__(self):
        self.init_tables()

    def get_conn(self):
        """Pattern: Singleton Connection Cache."""
        @st.cache_resource(ttl=3600)
        def _get_cached_connection():
            # Guard Clause: Verifica conexão antes de tentar conectar
            if "DATABASE_URL" not in st.secrets:
                raise ConnectionError("DATABASE_URL not found in secrets.")
            return psycopg2.connect(st.secrets["DATABASE_URL"])
        return _get_cached_connection()

    def init_tables(self) -> None:
        """Inicializa esquema do banco com tratamento de migrações."""
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    # Tabelas Core
                    cur.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT, created_at TEXT)")
                    cur.execute("""CREATE TABLE IF NOT EXISTS transactions (
                        id SERIAL PRIMARY KEY, user_id TEXT, date TEXT, amount REAL, category TEXT, description TEXT, type TEXT,
                        FOREIGN KEY(user_id) REFERENCES users(username))""")
                    cur.execute("""CREATE TABLE IF NOT EXISTS budgets (
                        id SERIAL PRIMARY KEY, user_id TEXT, category TEXT, limit_amount REAL,
                        FOREIGN KEY(user_id) REFERENCES users(username))""")
                    cur.execute("""CREATE TABLE IF NOT EXISTS recurring (
                        id SERIAL PRIMARY KEY, user_id TEXT, category TEXT, amount REAL, description TEXT, type TEXT, day_of_month INT, last_processed TEXT,
                        FOREIGN KEY(user_id) REFERENCES users(username))""")
                    cur.execute("""CREATE TABLE IF NOT EXISTS custom_categories (
                        id SERIAL PRIMARY KEY, user_id TEXT, name TEXT,
                        FOREIGN KEY(user_id) REFERENCES users(username))""")
                    
                    # Migração Defensiva (Idempotente)
                    try:
                        cur.execute("ALTER TABLE transactions ADD COLUMN proof_data BYTEA")
                        cur.execute("ALTER TABLE transactions ADD COLUMN proof_name TEXT")
                    except psycopg2.errors.DuplicateColumn:
                        conn.rollback() # Ignora se já existir
                    except Exception:
                        conn.rollback()

                    conn.commit()
        except Exception as e:
            logging.critical(f"Database Initialization Failed: {e}")

    # --- Auth Methods (APLICANDO RETURN EARLY / FAIL FAST) ---
    def register(self, user: str, pwd: str) -> Tuple[bool, str]:
        # [FAIL FAST 1] Validação de Inputs Vazios
        # Se falhar aqui, a função morre imediatamente. O código não avança.
        if not user or not pwd: 
            return False, "Usuário e senha são obrigatórios."
        
        # [FAIL FAST 2] Validação de Força da Senha
        if not SecurityManager.is_strong_password(pwd):
            return False, "Senha fraca! Requer: 8 chars, letras e números."
            
        # [HAPPY PATH] Se chegou aqui, está tudo certo para tentar salvar.
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    # Verifica existência prévia
                    cur.execute("SELECT 1 FROM users WHERE username = %s", (user,))
                    if cur.fetchone():
                        return False, "Usuário já cadastrado."

                    # Inserção Segura
                    cur.execute("INSERT INTO users VALUES (%s, %s, %s)", 
                               (user, SecurityManager.hash_pwd(pwd), str(datetime.now())))
                    conn.commit()
            return True, "Usuário criado com sucesso."
        except Exception as e:
            logging.error(f"Registration Error: {e}")
            return False, "Erro interno no servidor."

    def login(self, user: str, pwd: str) -> bool:
        # Guard Clause simples
        if not user or not pwd: return False
        
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT username FROM users WHERE username=%s AND password_hash=%s", 
                               (user, SecurityManager.hash_pwd(pwd)))
                    return cur.fetchone() is not None
        except Exception as e:
            logging.error(f"Login Error: {e}")
            return False

    # --- Categories ---
    def get_categories(self, uid: str) -> List[str]:
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT name FROM custom_categories WHERE user_id=%s", (uid,))
                    custom = [row[0] for row in cur.fetchall()]
            return sorted(list(set(CATEGORIAS_BASE + custom)))
        except Exception:
            return sorted(CATEGORIAS_BASE)

    def add_category(self, uid: str, name: str) -> bool:
        # Guard Clause: Nome inválido
        if not name or name in CATEGORIAS_BASE: return False
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM custom_categories WHERE user_id=%s AND name=%s", (uid, name))
                    if cur.fetchone(): return False
                    
                    cur.execute("INSERT INTO custom_categories (user_id, name) VALUES (%s, %s)", (uid, name))
                    conn.commit()
            return True
        except Exception: return False

    def delete_category(self, uid: str, name: str) -> bool:
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM custom_categories WHERE user_id=%s AND name=%s", (uid, name))
                    conn.commit()
            return True
        except Exception: return False

    # --- Transactions (APLICANDO DDD VALIDATION) ---
    def add_transaction(self, uid: str, date_val: Any, amt: float, cat: str, desc: str, type_: str, 
                       proof_file=None, proof_name: str=None) -> bool:
        try:
            # [DDD] Validação de Regras de Negócio CENTRALIZADA
            # Aqui garantimos que o dinheiro não é negativo e a data é válida.
            # Se falhar, o DomainValidators lança erro e para a execução (Fail Fast).
            clean_amt = DomainValidators.validate_amount(amt)
            clean_date = DomainValidators.validate_date(date_val)
            clean_type = DomainValidators.normalize_type(type_)
            
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    proof_bytes = proof_file.getvalue() if proof_file else None
                    
                    cur.execute("""INSERT INTO transactions 
                        (user_id, date, amount, category, description, type, proof_data, proof_name) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (uid, clean_date, clean_amt, cat, desc, clean_type, 
                         psycopg2.Binary(proof_bytes) if proof_bytes else None, proof_name))
                    conn.commit()
            return True
        except ValueError as ve:
            # Captura erros de validação de negócio (ex: valor negativo)
            logging.warning(f"Business Logic Validation Failed: {ve}")
            return False
        except Exception as e:
            logging.error(f"Transaction Insert Error: {e}")
            return False

    def remove_transaction(self, tid: int, uid: str) -> bool:
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM transactions WHERE id=%s AND user_id=%s", (tid, uid))
                    conn.commit()
            return True
        except Exception: return False

    def get_totals(self, uid: str, start_date=None, end_date=None) -> Tuple[float, float]:
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    q = "SELECT type, SUM(amount) FROM transactions WHERE user_id = %s"
                    p = [uid]
                    if start_date and end_date:
                        q += " AND date >= %s AND date <= %s"
                        p.extend([str(start_date), str(end_date)])
                    q += " GROUP BY type"
                    cur.execute(q, tuple(p))
                    
                    results = cur.fetchall()
                    receita = 0.0
                    despesa = 0.0
                    
                    for tipo, valor in results:
                        # Usa o validador para normalizar (DDD) antes de somar
                        norm_type = DomainValidators.normalize_type(tipo)
                        if norm_type == "Receita":
                            receita += valor
                        else:
                            despesa += valor
                            
                    return receita, despesa
        except Exception as e: 
            logging.error(f"Error fetching totals: {e}")
            return 0.0, 0.0

    def fetch_all(self, uid: str, limit: int=None, start_date=None, end_date=None) -> pd.DataFrame:
        try:
            with self.get_conn() as conn:
                q = """SELECT id, date, amount, category, description, type, proof_name, proof_data 
                       FROM transactions WHERE user_id = %s"""
                p = [uid]
                
                if start_date and end_date:
                    q += " AND date >= %s AND date <= %s"
                    p.extend([str(start_date), str(end_date)])
                
                q += " ORDER BY date DESC, id DESC"
                
                if limit:
                    q += " LIMIT %s"
                    p.append(limit)
                
                df = pd.read_sql_query(q, conn, params=p)
                return df
        except Exception:
            return pd.DataFrame(columns=['id', 'date', 'amount', 'category', 'description', 'type'])

    def nuke_data(self, uid: str) -> bool:
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM transactions WHERE user_id=%s", (uid,))
                    cur.execute("DELETE FROM budgets WHERE user_id=%s", (uid,))
                    cur.execute("DELETE FROM recurring WHERE user_id=%s", (uid,))
                    conn.commit()
            return True
        except Exception: return False

    # --- Budgets & Recurring ---
    def set_meta(self, uid: str, cat: str, lim: float) -> bool:
        try:
            # [Fail Fast] Validação direta: Meta negativa não existe
            if float(lim) < 0: return False
            
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM budgets WHERE user_id=%s AND category=%s", (uid, cat))
                    if cur.fetchone():
                        cur.execute("UPDATE budgets SET limit_amount=%s WHERE user_id=%s AND category=%s", (float(lim), uid, cat))
                    else:
                        cur.execute("INSERT INTO budgets (user_id, category, limit_amount) VALUES (%s, %s, %s)", (uid, cat, float(lim)))
                    conn.commit()
            return True
        except Exception: return False

    def delete_meta(self, uid: str, cat: str) -> bool:
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM budgets WHERE user_id=%s AND category=%s", (uid, cat))
                    conn.commit()
            return True
        except Exception: return False

    def get_metas(self, uid: str) -> pd.DataFrame:
        try:
            with self.get_conn() as conn:
                return pd.read_sql_query("SELECT category, limit_amount FROM budgets WHERE user_id=%s", conn, params=(uid,))
        except Exception: return pd.DataFrame()

    def add_recurring(self, uid: str, cat: str, amt: float, desc: str, type_: str, day: int) -> bool:
        try:
            # [DDD + Fail Fast] Validações antes de tocar no banco
            clean_amt = DomainValidators.validate_amount(amt)
            clean_type = DomainValidators.normalize_type(type_)
            if not (1 <= int(day) <= 31): return False

            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""INSERT INTO recurring 
                        (user_id, category, amount, description, type, day_of_month, last_processed) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (uid, cat, clean_amt, desc, clean_type, int(day), ''))
                    conn.commit()
            return True
        except Exception: return False

    def process_recurring_items(self, uid: str, fuso_br=None) -> int:
        """Processa contas fixas mensais de forma idempotente."""
        try:
            import pytz
            local_tz = fuso_br if fuso_br else pytz.timezone('America/Sao_Paulo')
            today = datetime.now(local_tz).date()
            current_month_str = today.strftime('%Y-%m')
            
            count = 0
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, category, amount, description, type, day_of_month, last_processed FROM recurring WHERE user_id=%s", (uid,))
                    items = cur.fetchall()
                    
                    for item in items:
                        rid, cat, amt, desc, type_, day, last_proc = item
                        
                        # Idempotência: Se já rodou neste mês, pula (Early Return dentro do loop)
                        if last_proc == current_month_str:
                            continue
                            
                        if today.day >= day:
                            # Reutiliza add_transaction para garantir validações
                            self.add_transaction(uid, today, amt, cat, f"{desc} (Recorrente)", type_)
                            
                            cur.execute("UPDATE recurring SET last_processed=%s WHERE id=%s", (current_month_str, rid))
                            count += 1
                    conn.commit()
            return count
        except Exception as e:
            logging.error(f"Recurring Process Error: {e}")
            return 0
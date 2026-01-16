import streamlit as st
import logging
import pandas as pd
import threading
import traceback
from datetime import datetime
from typing import List, Tuple, Any
from src.auth import SecurityManager
from src.utils import DomainValidators

# Configurações de Log
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(filename)s:%(lineno)d] - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

CATEGORIAS_BASE: List[str] = [
    "Alimentação", "Transporte", "Moradia", "Lazer", "Saúde", 
    "Salário", "Investimentos", "Educação", "Viagem", "Compras", 
    "Assinaturas", "Presentes", "Outros"
]

class RobustDatabase:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RobustDatabase, cls).__new__(cls)
                cls._instance.initialized = False
                cls._instance.logger = logging.getLogger("RobustDatabase")
        return cls._instance
    
    def __init__(self):
        if not self.initialized:
            self.init_tables()
            self.initialized = True

    def get_conn(self) -> Any:
        @st.cache_resource(ttl=3600)
        def _get_cached_connection() -> Any:
            # 1. Tenta Supabase (Postgres)
            if "DATABASE_URL" in st.secrets:
                try:
                    import psycopg2
                    conn = psycopg2.connect(st.secrets["DATABASE_URL"])
                    self.logger.info("Conectado ao Supabase (Postgres).")
                    return conn
                except Exception as e:
                    self.logger.warning(f"Falha Supabase: {e}. Usando SQLite.")
            
            # 2. Fallback SQLite
            import sqlite3
            conn = sqlite3.connect('smartwallet.db', check_same_thread=False)
            try: conn.execute("PRAGMA journal_mode=WAL;")
            except: pass
            return conn
            
        return _get_cached_connection()

    def init_tables(self) -> None:
        """Cria as tabelas com commit IMEDIATO para evitar rollback em erro de migração."""
        self.logger.info("Verificando tabelas...")
        conn = self.get_conn()
        
        # Detecta se é Postgres (Supabase) ou SQLite
        is_postgres = 'psycopg2' in str(type(conn))
        blob_type = "BYTEA" if is_postgres else "BLOB"
        id_type = "SERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY"
        
        try:
            with conn.cursor() as cur:
                # 1. Criação das Tabelas (Core)
                cur.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT, created_at TEXT)")
                
                # Transactions (Já com as colunas certas para evitar erro de ALTER)
                cur.execute(f"""CREATE TABLE IF NOT EXISTS transactions (
                    id {id_type}, 
                    user_id TEXT, 
                    date TEXT, 
                    amount REAL, 
                    category TEXT, 
                    description TEXT, 
                    type TEXT,
                    proof_data {blob_type},
                    proof_name TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(username))""")
                
                cur.execute(f"""CREATE TABLE IF NOT EXISTS budgets (
                    id {id_type}, user_id TEXT, category TEXT, limit_amount REAL,
                    FOREIGN KEY(user_id) REFERENCES users(username))""")
                
                cur.execute(f"""CREATE TABLE IF NOT EXISTS recurring (
                    id {id_type}, user_id TEXT, category TEXT, amount REAL, description TEXT, type TEXT, day_of_month INT, last_processed TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(username))""")
                
                cur.execute(f"""CREATE TABLE IF NOT EXISTS custom_categories (
                    id {id_type}, user_id TEXT, name TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(username))""")
                
                conn.commit() # <--- SALVA AQUI! (O Segredo)
                self.logger.info("Tabelas criadas/verificadas com sucesso.")

                # 2. Índices
                try:
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_trans_user_date ON transactions(user_id, date);")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_trans_category ON transactions(category);")
                    conn.commit()
                except Exception as idx_err:
                    self.logger.warning(f"Erro menor criando índices: {idx_err}")

        except Exception as e:
            self.logger.critical(f"Erro fatal criando tabelas: {e}")
            conn.rollback()

    # --- Autenticação ---
    def register(self, user: str, pwd: str) -> Tuple[bool, str]:
        if not user or not pwd: return False, "Campos vazios."
        if not SecurityManager.is_strong_password(pwd): return False, "Senha fraca."
        try:
            conn = self.get_conn()
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM users WHERE username = %s", (user,))
                if cur.fetchone(): return False, "Usuário existe."
                cur.execute("INSERT INTO users (username, password_hash, created_at) VALUES (%s, %s, %s)", 
                           (user, SecurityManager.hash_pwd(pwd), str(datetime.now())))
                conn.commit()
            return True, "Sucesso."
        except Exception as e:
            self.logger.error(f"Erro ao registrar: {e}")
            return False, "Erro interno."

    def login(self, user: str, pwd: str) -> bool:
        try:
            conn = self.get_conn()
            with conn.cursor() as cur:
                cur.execute("SELECT username FROM users WHERE username=%s AND password_hash=%s", 
                           (user, SecurityManager.hash_pwd(pwd)))
                return cur.fetchone() is not None
        except Exception as e:
            self.logger.error(f"Erro login: {e}")
            return False

    # --- Métodos de Negócio (Simplificados para Brevidade - Mantenha os seus se já funcionam, ou use estes) ---
    def add_transaction(self, uid: str, date_val: Any, amt: float, cat: str, desc: str, type_: str, proof_file=None, proof_name: str=None) -> bool:
        try:
            clean_amt = DomainValidators.validate_amount(amt)
            clean_date = DomainValidators.validate_date(date_val)
            clean_type = DomainValidators.normalize_type(type_)
            
            conn = self.get_conn()
            proof_bytes = proof_file.getvalue() if proof_file else None
            
            # Adaptação BLOB
            p_data = proof_bytes
            if 'psycopg2' in str(type(conn)) and proof_bytes:
                import psycopg2
                p_data = psycopg2.Binary(proof_bytes)

            with conn.cursor() as cur:
                cur.execute("""INSERT INTO transactions 
                    (user_id, date, amount, category, description, type, proof_data, proof_name) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (uid, clean_date, clean_amt, cat, desc, clean_type, p_data, proof_name))
                conn.commit()
            st.cache_data.clear()
            return True
        except Exception as e:
            self.logger.error(f"Erro add_transaction: {e}")
            return False

    def get_categories(self, uid: str) -> List[str]:
        try:
            conn = self.get_conn()
            with conn.cursor() as cur:
                cur.execute("SELECT name FROM custom_categories WHERE user_id=%s", (uid,))
                custom = [row[0] for row in cur.fetchall()]
            return sorted(list(set(CATEGORIAS_BASE + custom)))
        except: return sorted(CATEGORIAS_BASE)

    def add_category(self, uid: str, name: str) -> bool:
        if name in CATEGORIAS_BASE: return False
        try:
            conn = self.get_conn()
            with conn.cursor() as cur:
                cur.execute("INSERT INTO custom_categories (user_id, name) VALUES (%s, %s)", (uid, name))
                conn.commit()
            st.cache_data.clear()
            return True
        except: return False

    def delete_category(self, uid: str, name: str) -> bool:
        try:
            conn = self.get_conn()
            with conn.cursor() as cur:
                cur.execute("DELETE FROM custom_categories WHERE user_id=%s AND name=%s", (uid, name))
                conn.commit()
            st.cache_data.clear()
            return True
        except: return False

    def remove_transaction(self, tid: int, uid: str) -> bool:
        try:
            conn = self.get_conn()
            with conn.cursor() as cur:
                cur.execute("DELETE FROM transactions WHERE id=%s AND user_id=%s", (tid, uid))
                conn.commit()
            st.cache_data.clear()
            return True
        except: return False

    def get_totals(self, uid: str, start_date=None, end_date=None) -> Tuple[float, float]:
        try:
            conn = self.get_conn()
            with conn.cursor() as cur:
                q = "SELECT type, SUM(amount) FROM transactions WHERE user_id = %s"
                p = [uid]
                if start_date and end_date:
                    q += " AND date >= %s AND date <= %s"
                    p.extend([str(start_date), str(end_date)])
                q += " GROUP BY type"
                cur.execute(q, tuple(p))
                res = cur.fetchall()
                rec = sum(v for t, v in res if DomainValidators.normalize_type(t) == "Receita")
                desp = sum(v for t, v in res if DomainValidators.normalize_type(t) != "Receita")
                return rec, desp
        except: return 0.0, 0.0

    def fetch_all(self, uid: str, limit: int=None, start_date=None, end_date=None) -> pd.DataFrame:
        try:
            conn = self.get_conn()
            q = "SELECT id, date, amount, category, description, type, proof_name FROM transactions WHERE user_id = %s"
            p = [uid]
            if start_date and end_date:
                q += " AND date >= %s AND date <= %s"
                p.extend([str(start_date), str(end_date)])
            q += " ORDER BY date DESC"
            if limit: q += f" LIMIT {limit}"
            return pd.read_sql_query(q, conn, params=p)
        except: return pd.DataFrame(columns=['id', 'date', 'amount', 'category', 'description', 'type'])

    def nuke_data(self, uid: str) -> bool:
        try:
            conn = self.get_conn()
            with conn.cursor() as cur:
                for t in ["transactions", "budgets", "recurring", "custom_categories"]:
                    cur.execute(f"DELETE FROM {t} WHERE user_id=%s", (uid,))
                conn.commit()
            st.cache_data.clear()
            return True
        except: return False

    def set_meta(self, uid: str, cat: str, lim: float) -> bool:
        try:
            conn = self.get_conn()
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM budgets WHERE user_id=%s AND category=%s", (uid, cat))
                if cur.fetchone():
                    cur.execute("UPDATE budgets SET limit_amount=%s WHERE user_id=%s AND category=%s", (lim, uid, cat))
                else:
                    cur.execute("INSERT INTO budgets (user_id, category, limit_amount) VALUES (%s, %s, %s)", (uid, cat, lim))
                conn.commit()
            st.cache_data.clear()
            return True
        except: return False

    def delete_meta(self, uid: str, cat: str) -> bool:
        try:
            conn = self.get_conn()
            with conn.cursor() as cur:
                cur.execute("DELETE FROM budgets WHERE user_id=%s AND category=%s", (uid, cat))
                conn.commit()
            st.cache_data.clear()
            return True
        except: return False

    def get_metas(self, uid: str) -> pd.DataFrame:
        try:
            conn = self.get_conn()
            return pd.read_sql_query("SELECT category, limit_amount FROM budgets WHERE user_id=%s", conn, params=(uid,))
        except: return pd.DataFrame()

    def add_recurring(self, uid: str, cat: str, amt: float, desc: str, type_: str, day: int) -> bool:
        try:
            conn = self.get_conn()
            with conn.cursor() as cur:
                cur.execute("INSERT INTO recurring (user_id, category, amount, description, type, day_of_month, last_processed) VALUES (%s, %s, %s, %s, %s, %s, '')", 
                           (uid, cat, amt, desc, type_, int(day)))
                conn.commit()
            return True
        except: return False

    def process_recurring_items(self, uid: str, fuso_br=None) -> int:
        try:
            import pytz
            local_tz = fuso_br if fuso_br else pytz.timezone('America/Sao_Paulo')
            today = datetime.now(local_tz).date()
            curr_month = today.strftime('%Y-%m')
            count = 0
            conn = self.get_conn()
            with conn.cursor() as cur:
                cur.execute("SELECT id, category, amount, description, type, day_of_month, last_processed FROM recurring WHERE user_id=%s", (uid,))
                for rid, cat, amt, desc, tp, day, last in cur.fetchall():
                    if last == curr_month: continue
                    if today.day >= day:
                        self.add_transaction(uid, today, amt, cat, f"{desc} (Recorrente)", tp)
                        cur.execute("UPDATE recurring SET last_processed=%s WHERE id=%s", (curr_month, rid))
                        count += 1
                conn.commit()
            return count
        except: return 0

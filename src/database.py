import streamlit as st
import psycopg2
import logging
import pandas as pd
from datetime import datetime
from typing import List, Tuple, Any
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
    Encapsula CRUD, conexões, migrações e OTIMIZAÇÃO DE PERFORMANCE.
    """
    
    _instance = None

    def __new__(cls):
        # Singleton: Garante apenas uma instância na memória
        if cls._instance is None:
            cls._instance = super(RobustDatabase, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance
    
    def __init__(self):
        # Evita recriar tabelas a cada clique (Performance)
        if not self.initialized:
            self.init_tables()
            self.initialized = True

    def get_conn(self):
        """
        Retorna conexão (Singleton Cache).
        """
        @st.cache_resource(ttl=3600)
        def _get_cached_connection():
            if "DATABASE_URL" not in st.secrets:
                # Fallback SQLite OTIMIZADO
                import sqlite3
                conn = sqlite3.connect('smartwallet.db', check_same_thread=False)
                try: conn.execute("PRAGMA journal_mode=WAL;")
                except: pass
                return conn
            return psycopg2.connect(st.secrets["DATABASE_URL"])
        return _get_cached_connection()

    def init_tables(self) -> None:
        """Inicializa esquema, migrações e ÍNDICES DE PERFORMANCE."""
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT, created_at TEXT)")
                    
                    cur.execute("""CREATE TABLE IF NOT EXISTS transactions (
                        id INTEGER PRIMARY KEY, user_id TEXT, date TEXT, amount REAL, category TEXT, description TEXT, type TEXT,
                        FOREIGN KEY(user_id) REFERENCES users(username))""")
                    
                    cur.execute("""CREATE TABLE IF NOT EXISTS budgets (
                        id INTEGER PRIMARY KEY, user_id TEXT, category TEXT, limit_amount REAL,
                        FOREIGN KEY(user_id) REFERENCES users(username))""")
                    
                    cur.execute("""CREATE TABLE IF NOT EXISTS recurring (
                        id INTEGER PRIMARY KEY, user_id TEXT, category TEXT, amount REAL, description TEXT, type TEXT, day_of_month INT, last_processed TEXT,
                        FOREIGN KEY(user_id) REFERENCES users(username))""")
                    
                    cur.execute("""CREATE TABLE IF NOT EXISTS custom_categories (
                        id INTEGER PRIMARY KEY, user_id TEXT, name TEXT,
                        FOREIGN KEY(user_id) REFERENCES users(username))""")
                    
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_trans_user_date ON transactions(user_id, date);")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_trans_category ON transactions(category);")
                    
                    try:
                        cur.execute("ALTER TABLE transactions ADD COLUMN proof_data BLOB")
                        cur.execute("ALTER TABLE transactions ADD COLUMN proof_name TEXT")
                    except: pass

                    conn.commit()
        except Exception as e:
            logging.critical(f"Database Init Failed: {e}")

    
    def register(self, user: str, pwd: str) -> Tuple[bool, str]:
        if not user or not pwd: return False, "Campos vazios."
        if not SecurityManager.is_strong_password(pwd): return False, "Senha fraca."
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM users WHERE username = %s", (user,))
                    if cur.fetchone(): return False, "Usuário existe."
                    cur.execute("INSERT INTO users VALUES (%s, %s, %s)", 
                               (user, SecurityManager.hash_pwd(pwd), str(datetime.now())))
                    conn.commit()
            return True, "Sucesso."
        except Exception: return False, "Erro interno."

    def login(self, user: str, pwd: str) -> bool:
        if not user or not pwd: return False
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT username FROM users WHERE username=%s AND password_hash=%s", 
                               (user, SecurityManager.hash_pwd(pwd)))
                    return cur.fetchone() is not None
        except Exception: return False

    
    def get_categories(self, uid: str) -> List[str]:
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT name FROM custom_categories WHERE user_id=%s", (uid,))
                    custom = [row[0] for row in cur.fetchall()]
            return sorted(list(set(CATEGORIAS_BASE + custom)))
        except Exception: return sorted(CATEGORIAS_BASE)

    def add_category(self, uid: str, name: str) -> bool:
        if not name or name in CATEGORIAS_BASE: return False
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM custom_categories WHERE user_id=%s AND name=%s", (uid, name))
                    if cur.fetchone(): return False
                    cur.execute("INSERT INTO custom_categories (user_id, name) VALUES (%s, %s)", (uid, name))
                    conn.commit()
            st.cache_data.clear()
            return True
        except Exception: return False

    def delete_category(self, uid: str, name: str) -> bool:
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM custom_categories WHERE user_id=%s AND name=%s", (uid, name))
                    conn.commit()
            st.cache_data.clear()
            return True
        except Exception: return False

    
    def add_transaction(self, uid: str, date_val: Any, amt: float, cat: str, desc: str, type_: str, 
                        proof_file=None, proof_name: str=None) -> bool:
        try:
            clean_amt = DomainValidators.validate_amount(amt)
            clean_date = DomainValidators.validate_date(date_val)
            clean_type = DomainValidators.normalize_type(type_)
            
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    proof_bytes = proof_file if isinstance(proof_file, bytes) else (proof_file.getvalue() if proof_file else None)
                    p_data = psycopg2.Binary(proof_bytes) if proof_bytes and 'psycopg2' in str(type(conn)) else proof_bytes

                    cur.execute("""INSERT INTO transactions 
                        (user_id, date, amount, category, description, type, proof_data, proof_name) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (uid, clean_date, clean_amt, cat, desc, clean_type, p_data, proof_name))
                    conn.commit()
            st.cache_data.clear()
            return True
        except Exception as e:
            logging.error(f"Insert Error: {e}")
            return False

    def remove_transaction(self, tid: int, uid: str) -> bool:
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM transactions WHERE id=%s AND user_id=%s", (tid, uid))
                    conn.commit()
            st.cache_data.clear()
            return True
        except Exception: return False

    def get_totals(self, uid: str, start_date=None, end_date=None) -> Tuple[float, float]:
        """Usa agregação SQL para velocidade máxima."""
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
                    receita, despesa = 0.0, 0.0
                    for tipo, valor in results:
                        if DomainValidators.normalize_type(tipo) == "Receita": receita += valor
                        else: despesa += valor
                    return receita, despesa
        except Exception: return 0.0, 0.0

    def fetch_all(self, uid: str, limit: int=None, start_date=None, end_date=None) -> pd.DataFrame:
        """
        Busca otimizada. O 'ORDER BY' agora usa o índice criado na init_tables.
        """
        try:
            with self.get_conn() as conn:
                q = """SELECT id, date, amount, category, description, type, proof_name, proof_data 
                       FROM transactions WHERE user_id = %s"""
                p = [uid]
                
                if start_date and end_date:
                    q += " AND date >= %s AND date <= %s"
                    p.extend([str(start_date), str(end_date)])
                
                # Este ORDER BY agora é instantâneo graças ao INDEX
                q += " ORDER BY date DESC, id DESC"
                
                if limit:
                    q += " LIMIT %s"
                    p.append(limit)
                
                return pd.read_sql_query(q, conn, params=p)
        except Exception:
            return pd.DataFrame(columns=['id', 'date', 'amount', 'category', 'description', 'type'])

    def nuke_data(self, uid: str) -> bool:
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    for table in ["transactions", "budgets", "recurring", "custom_categories"]:
                        cur.execute(f"DELETE FROM {table} WHERE user_id=%s", (uid,))
                    conn.commit()
            st.cache_data.clear()
            return True
        except Exception: return False

    # --- Metas ---
    def set_meta(self, uid: str, cat: str, lim: float) -> bool:
        try:
            if float(lim) < 0: return False
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM budgets WHERE user_id=%s AND category=%s", (uid, cat))
                    if cur.fetchone():
                        cur.execute("UPDATE budgets SET limit_amount=%s WHERE user_id=%s AND category=%s", (float(lim), uid, cat))
                    else:
                        cur.execute("INSERT INTO budgets (user_id, category, limit_amount) VALUES (%s, %s, %s)", (uid, cat, float(lim)))
                    conn.commit()
            st.cache_data.clear()
            return True
        except Exception: return False

    def delete_meta(self, uid: str, cat: str) -> bool:
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM budgets WHERE user_id=%s AND category=%s", (uid, cat))
                    conn.commit()
            st.cache_data.clear()
            return True
        except Exception: return False

    def get_metas(self, uid: str) -> pd.DataFrame:
        try:
            with self.get_conn() as conn:
                return pd.read_sql_query("SELECT category, limit_amount FROM budgets WHERE user_id=%s", conn, params=(uid,))
        except Exception: return pd.DataFrame()

    # --- Recorrência ---
    def add_recurring(self, uid: str, cat: str, amt: float, desc: str, type_: str, day: int) -> bool:
        try:
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
                        if last_proc == current_month_str: continue
                        if today.day >= day:
                            self.add_transaction(uid, today, amt, cat, f"{desc} (Recorrente)", type_)
                            cur.execute("UPDATE recurring SET last_processed=%s WHERE id=%s", (current_month_str, rid))
                            count += 1
                    conn.commit()
            return count
        except Exception: return 0
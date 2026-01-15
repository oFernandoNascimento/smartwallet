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
    Encapsula todas as operações de CRUD, gerenciamento de conexões e migrações.
    """
    
    def __init__(self):
        self.init_tables()

    def get_conn(self):
        """
        Retorna uma conexão com o banco de dados (Singleton Cache).
        Utiliza 'DATABASE_URL' dos secrets do Streamlit.
        """
        @st.cache_resource(ttl=3600)
        def _get_cached_connection():
            if "DATABASE_URL" not in st.secrets:
                raise ConnectionError("DATABASE_URL not found in secrets.")
            return psycopg2.connect(st.secrets["DATABASE_URL"])
        return _get_cached_connection()

    def init_tables(self) -> None:
        """Inicializa o esquema do banco de dados e executa migrações automáticas se necessário."""
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
                    
                    # Migrações de Colunas (Idempotente)
                    try:
                        cur.execute("ALTER TABLE transactions ADD COLUMN proof_data BYTEA")
                        cur.execute("ALTER TABLE transactions ADD COLUMN proof_name TEXT")
                    except psycopg2.errors.DuplicateColumn:
                        conn.rollback() 
                    except Exception:
                        conn.rollback()

                    conn.commit()
        except Exception as e:
            logging.critical(f"Database Initialization Failed: {e}")

    # --- Autenticação ---
    
    def register(self, user: str, pwd: str) -> Tuple[bool, str]:
        """Registra um novo usuário no sistema."""
        if not user or not pwd: 
            return False, "Usuário e senha são obrigatórios."
        
        if not SecurityManager.is_strong_password(pwd):
            return False, "Senha fraca! Requer: 8 chars, letras e números."
            
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM users WHERE username = %s", (user,))
                    if cur.fetchone():
                        return False, "Usuário já cadastrado."

                    cur.execute("INSERT INTO users VALUES (%s, %s, %s)", 
                               (user, SecurityManager.hash_pwd(pwd), str(datetime.now())))
                    conn.commit()
            return True, "Usuário criado com sucesso."
        except Exception as e:
            logging.error(f"Registration Error: {e}")
            return False, "Erro interno no servidor."

    def login(self, user: str, pwd: str) -> bool:
        """Verifica as credenciais do usuário."""
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

    # --- Categorias ---
    
    def get_categories(self, uid: str) -> List[str]:
        """Retorna a lista de categorias do usuário (Base + Customizadas)."""
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT name FROM custom_categories WHERE user_id=%s", (uid,))
                    custom = [row[0] for row in cur.fetchall()]
            return sorted(list(set(CATEGORIAS_BASE + custom)))
        except Exception:
            return sorted(CATEGORIAS_BASE)

    def add_category(self, uid: str, name: str) -> bool:
        """Adiciona uma nova categoria personalizada."""
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
        """Remove uma categoria personalizada."""
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM custom_categories WHERE user_id=%s AND name=%s", (uid, name))
                    conn.commit()
            return True
        except Exception: return False

    # --- Transações ---
    
    def add_transaction(self, uid: str, date_val: Any, amt: float, cat: str, desc: str, type_: str, 
                        proof_file=None, proof_name: str=None) -> bool:
        """Registra uma nova transação financeira."""
        try:
            clean_amt = DomainValidators.validate_amount(amt)
            clean_date = DomainValidators.validate_date(date_val)
            clean_type = DomainValidators.normalize_type(type_)
            
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    proof_bytes = proof_file if isinstance(proof_file, bytes) else (proof_file.getvalue() if proof_file else None)
                    
                    cur.execute("""INSERT INTO transactions 
                        (user_id, date, amount, category, description, type, proof_data, proof_name) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (uid, clean_date, clean_amt, cat, desc, clean_type, 
                         psycopg2.Binary(proof_bytes) if proof_bytes else None, proof_name))
                    conn.commit()
            return True
        except Exception as e:
            logging.error(f"Transaction Insert Error: {e}")
            return False

    def remove_transaction(self, tid: int, uid: str) -> bool:
        """Remove uma transação pelo ID."""
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM transactions WHERE id=%s AND user_id=%s", (tid, uid))
                    conn.commit()
            return True
        except Exception: return False

    def get_totals(self, uid: str, start_date=None, end_date=None) -> Tuple[float, float]:
        """Calcula totais de Receita e Despesa para um período."""
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
                        norm_type = DomainValidators.normalize_type(tipo)
                        if norm_type == "Receita":
                            receita += valor
                        else:
                            despesa += valor
                    return receita, despesa
        except Exception: 
            return 0.0, 0.0

    def fetch_all(self, uid: str, limit: int=None, start_date=None, end_date=None) -> pd.DataFrame:
        """Recupera o histórico de transações como DataFrame."""
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
        """Limpa TODOS os dados do usuário (Reset de Conta)."""
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM transactions WHERE user_id=%s", (uid,))
                    cur.execute("DELETE FROM budgets WHERE user_id=%s", (uid,))
                    cur.execute("DELETE FROM recurring WHERE user_id=%s", (uid,))
                    conn.commit()
            return True
        except Exception: return False

    # --- Metas e Orçamentos ---
    
    def set_meta(self, uid: str, cat: str, lim: float) -> bool:
        """Define ou atualiza uma meta de orçamento para uma categoria."""
        try:
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
        """Remove uma meta de orçamento."""
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM budgets WHERE user_id=%s AND category=%s", (uid, cat))
                    conn.commit()
            return True
        except Exception: return False

    def get_metas(self, uid: str) -> pd.DataFrame:
        """Retorna todas as metas definidas pelo usuário."""
        try:
            with self.get_conn() as conn:
                return pd.read_sql_query("SELECT category, limit_amount FROM budgets WHERE user_id=%s", conn, params=(uid,))
        except Exception: return pd.DataFrame()

    # --- Transações Recorrentes ---
    
    def add_recurring(self, uid: str, cat: str, amt: float, desc: str, type_: str, day: int) -> bool:
        """Configura uma nova transação recorrente mensal."""
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
        """Processa e gera transações recorrentes pendentes para o mês atual."""
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
        except Exception:
            return 0
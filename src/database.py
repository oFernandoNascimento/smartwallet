# Arquivo: src/database.py
import streamlit as st
import psycopg2
import logging
import pandas as pd
from datetime import datetime
from src.auth import SecurityManager

# Configurações de Log
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

# Constantes
CATEGORIAS_BASE = [
    "Alimentação", "Transporte", "Moradia", "Lazer", "Saúde", 
    "Salário", "Investimentos", "Educação", "Viagem", "Compras", 
    "Assinaturas", "Presentes", "Outros"
]

class RobustDatabase:
    """
    Gerenciador de Banco de Dados Completo (Enterprise).
    Suporta: Recorrência, Metas, Filtros de Data e Uploads.
    """
    def __init__(self):
        self.init_tables()

    def get_conn(self):
        # Cache de recurso para manter a conexão viva
        @st.cache_resource(ttl=3600)
        def _get_cached_connection():
            return psycopg2.connect(st.secrets["DATABASE_URL"])
        return _get_cached_connection()

    def init_tables(self) -> None:
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    # Tabelas Essenciais
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
                    
                    # Migração segura para colunas de Comprovante
                    try:
                        cur.execute("ALTER TABLE transactions ADD COLUMN proof_data BYTEA")
                        cur.execute("ALTER TABLE transactions ADD COLUMN proof_name TEXT")
                        conn.commit()
                    except Exception:
                        conn.rollback()

                    conn.commit()
        except Exception as e:
            logging.error(f"DB Init Error: {e}")

    # --- Auth Methods ---
    def register(self, user, pwd):
        if not user or not pwd: return False, "Invalid input."
        if not SecurityManager.is_strong_password(pwd):
            return False, "Senha fraca! Use no mínimo 8 caracteres, letras e números."
            
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO users VALUES (%s, %s, %s)", (user, SecurityManager.hash_pwd(pwd), str(datetime.now())))
                    conn.commit()
            return True, "Usuário criado com sucesso."
        except Exception as e:
            logging.warning(f"Registration error: {e}")
            return False, "Usuário já existe."

    def login(self, user, pwd):
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT username FROM users WHERE username=%s AND password_hash=%s", (user, SecurityManager.hash_pwd(pwd)))
                    return cur.fetchone() is not None
        except Exception as e:
            logging.error(f"Login error: {e}")
            return False

    # --- Categories ---
    def get_categories(self, uid):
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT name FROM custom_categories WHERE user_id=%s", (uid,))
                    custom = [row[0] for row in cur.fetchall()]
            return sorted(list(set(CATEGORIAS_BASE + custom)))
        except Exception:
            return sorted(CATEGORIAS_BASE)

    def add_category(self, uid, name):
        if name in CATEGORIAS_BASE: return False
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO custom_categories (user_id, name) VALUES (%s, %s)", (uid, name))
                    conn.commit()
            return True
        except Exception: return False

    def delete_category(self, uid, name):
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM custom_categories WHERE user_id=%s AND name=%s", (uid, name))
                    conn.commit()
            return True
        except Exception: return False

    # --- Transactions ---
    def add_transaction(self, uid, date, amt, cat, desc, type_, proof_file=None, proof_name=None):
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    proof_bytes = proof_file.getvalue() if proof_file else None
                    cur.execute("""INSERT INTO transactions 
                        (user_id, date, amount, category, description, type, proof_data, proof_name) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (uid, str(date), float(amt), cat, desc, type_, psycopg2.Binary(proof_bytes) if proof_bytes else None, proof_name))
                    conn.commit()
            return True
        except Exception as e:
            logging.error(f"Add transaction error: {e}")
            return False

    def remove_transaction(self, tid, uid):
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM transactions WHERE id=%s AND user_id=%s", (tid, uid))
                    conn.commit()
            return True
        except Exception: return False

    # AQUI ESTAVA O ERRO: Adicionamos start_date e end_date
    def get_totals(self, uid, start_date=None, end_date=None):
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
                    r = dict(cur.fetchall())
                    return r.get('Receita', 0.0), r.get('Despesa', 0.0)
        except Exception: return 0.0, 0.0

    def fetch_all(self, uid, limit=None, start_date=None, end_date=None):
        try:
            with self.get_conn() as conn:
                q = "SELECT id, date, amount, category, description, type, proof_name, proof_data FROM transactions WHERE user_id = %s"
                p = [uid]
                if start_date and end_date:
                    q += " AND date >= %s AND date <= %s"
                    p.extend([str(start_date), str(end_date)])
                q += " ORDER BY date DESC, id DESC"
                if limit:
                    q += " LIMIT %s"
                    p.append(limit)
                
                df = pd.read_sql_query(q, conn, params=p)
            return df if not df.empty else pd.DataFrame(columns=['id', 'date', 'amount', 'category', 'description', 'type', 'proof_name', 'proof_data'])
        except Exception as e:
            return pd.DataFrame(columns=['id', 'date', 'amount', 'category', 'description', 'type'])

    def nuke_data(self, uid):
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM transactions WHERE user_id=%s", (uid,))
                    cur.execute("DELETE FROM budgets WHERE user_id=%s", (uid,))
                    cur.execute("DELETE FROM recurring WHERE user_id=%s", (uid,))
                    conn.commit()
            return True
        except Exception: return False

    # --- Budgets & Recurring (AQUI ESTAVA FALTANDO) ---
    def set_meta(self, uid, cat, lim):
        try:
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

    def delete_meta(self, uid, cat):
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM budgets WHERE user_id=%s AND category=%s", (uid, cat))
                    conn.commit()
            return True
        except Exception: return False

    def get_metas(self, uid):
        try:
            with self.get_conn() as conn:
                return pd.read_sql_query("SELECT category, limit_amount FROM budgets WHERE user_id=%s", conn, params=(uid,))
        except Exception: return pd.DataFrame()

    def add_recurring(self, uid, cat, amt, desc, type_, day):
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO recurring (user_id, category, amount, description, type, day_of_month, last_processed) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                                (uid, cat, float(amt), desc, type_, int(day), ''))
                    conn.commit()
            return True
        except Exception: return False

    # ESTA FUNÇÃO FALTAVA E CAUSOU O ERRO NO LOGIN
    def process_recurring_items(self, uid, fuso_br=None):
        """Processa contas fixas mensais."""
        try:
            # Pega o fuso do argumento ou usa um padrão
            import pytz
            local_tz = fuso_br if fuso_br else pytz.timezone('America/Sao_Paulo')
            today = datetime.now(local_tz).date()
            current_month_str = today.strftime('%Y-%m')
            
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, category, amount, description, type, day_of_month, last_processed FROM recurring WHERE user_id=%s", (uid,))
                    items = cur.fetchall()
                    
                    count = 0
                    for item in items:
                        rid, cat, amt, desc, type_, day, last_proc = item
                        if today.day >= day and last_proc != current_month_str:
                            self.add_transaction(uid, today, amt, cat, f"{desc} (Recorrente)", type_)
                            cur.execute("UPDATE recurring SET last_processed=%s WHERE id=%s", (current_month_str, rid))
                            count += 1
                    conn.commit()
            return count
        except Exception: return 0
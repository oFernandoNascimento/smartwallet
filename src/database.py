import streamlit as st
import logging
import pandas as pd
import threading
import traceback
import inspect
from datetime import datetime, date
from typing import List, Tuple, Any, Optional, Union
from src.auth import SecurityManager
from src.utils import DomainValidators

# Configurações de Log Avançadas
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(filename)s:%(lineno)d] - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("system_errors.log", mode='a')
    ]
)

# Constantes de Domínio
CATEGORIAS_BASE: List[str] = [
    "Alimentação", "Transporte", "Moradia", "Lazer", "Saúde", 
    "Salário", "Investimentos", "Educação", "Viagem", "Compras", 
    "Assinaturas", "Presentes", "Outros"
]

class RobustDatabase:
    """
    Gerenciador de Banco de Dados Enterprise (Refatorado).
    Encapsula CRUD, conexões, migrações e OTIMIZAÇÃO DE PERFORMANCE.
    Focado em Robustez, Thread-Safety e Auditoria.
    """
    
    _instance = None
    _lock = threading.Lock()  # Segurança para ambientes multithread

    def __new__(cls):
        # Singleton com Thread Safety
        with cls._lock:
            if cls._instance is None:
                logging.info("Inicializando nova instância Singleton do RobustDatabase.")
                cls._instance = super(RobustDatabase, cls).__new__(cls)
                cls._instance.initialized = False
                cls._instance.logger = logging.getLogger("RobustDatabase")
        return cls._instance
    
    def __init__(self):
        # Evita recriar tabelas a cada clique (Performance)
        if not self.initialized:
            self.logger.info("Iniciando verificação de tabelas e migrações.")
            self.init_tables()
            self.initialized = True
        else:
            self.logger.debug("Database já inicializado. Pulando setup.")

    def get_conn(self) -> Any:
        """
        Retorna conexão (Singleton Cache) com tratamento de falhas de driver.
        """
        @st.cache_resource(ttl=3600)
        def _get_cached_connection() -> Any:
            self.logger.info("Tentando estabelecer conexão com o banco de dados...")
            
            # Verifica se existe a URL do Supabase nos segredos
            if "DATABASE_URL" in st.secrets:
                self.logger.info("Secret 'DATABASE_URL' encontrada. Tentando conexão Postgres.")
                try:
                    import psycopg2
                    conn = psycopg2.connect(st.secrets["DATABASE_URL"])
                    self.logger.info("Conexão Postgres estabelecida com sucesso.")
                    return conn
                except ImportError:
                    self.logger.error("Erro Crítico: Biblioteca 'psycopg2' não instalada.")
                    st.error("Erro: Biblioteca 'psycopg2' não instalada. Adicione 'psycopg2-binary' ao requirements.txt ou pip install.")
                    raise
                except Exception as db_err:
                    self.logger.critical(f"Falha ao conectar no Postgres: {db_err}")
                    raise
            
            # Fallback SQLite OTIMIZADO (Se não tiver secrets ou falhar)
            self.logger.warning("Utilizando fallback para SQLite local.")
            try:
                import sqlite3
                conn = sqlite3.connect('smartwallet.db', check_same_thread=False)
                try: 
                    conn.execute("PRAGMA journal_mode=WAL;")
                    self.logger.debug("SQLite WAL mode ativado.")
                except Exception as wal_err: 
                    self.logger.warning(f"Não foi possível ativar WAL mode: {wal_err}")
                
                return conn
            except Exception as e:
                self.logger.critical(f"Falha catastrófica ao criar banco SQLite: {e}")
                raise

        try:
            return _get_cached_connection()
        except Exception as e:
            self.logger.critical(f"Erro irrecuperável em get_conn: {traceback.format_exc()}")
            st.error("Falha crítica de conexão com o Banco de Dados.")
            raise e

    def init_tables(self) -> None:
        """Inicializa esquema, migrações e ÍNDICES DE PERFORMANCE."""
        self.logger.info("Executando init_tables...")
        conn = None
        try:
            conn = self.get_conn()
            with conn: # Context manager para auto-commit/rollback
                with conn.cursor() as cur:
                    # Tabelas Core
                    self.logger.debug("Verificando/Criando tabela users.")
                    cur.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password_hash TEXT, created_at TEXT)")
                    
                    self.logger.debug("Verificando/Criando tabela transactions.")
                    cur.execute("""CREATE TABLE IF NOT EXISTS transactions (
                        id INTEGER PRIMARY KEY, user_id TEXT, date TEXT, amount REAL, category TEXT, description TEXT, type TEXT,
                        FOREIGN KEY(user_id) REFERENCES users(username))""")
                    
                    self.logger.debug("Verificando/Criando tabela budgets.")
                    cur.execute("""CREATE TABLE IF NOT EXISTS budgets (
                        id INTEGER PRIMARY KEY, user_id TEXT, category TEXT, limit_amount REAL,
                        FOREIGN KEY(user_id) REFERENCES users(username))""")
                    
                    self.logger.debug("Verificando/Criando tabela recurring.")
                    cur.execute("""CREATE TABLE IF NOT EXISTS recurring (
                        id INTEGER PRIMARY KEY, user_id TEXT, category TEXT, amount REAL, description TEXT, type TEXT, day_of_month INT, last_processed TEXT,
                        FOREIGN KEY(user_id) REFERENCES users(username))""")
                    
                    self.logger.debug("Verificando/Criando tabela custom_categories.")
                    cur.execute("""CREATE TABLE IF NOT EXISTS custom_categories (
                        id INTEGER PRIMARY KEY, user_id TEXT, name TEXT,
                        FOREIGN KEY(user_id) REFERENCES users(username))""")
                    
                    # Índices de Performance
                    self.logger.debug("Aplicando índices de performance.")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_trans_user_date ON transactions(user_id, date);")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_trans_category ON transactions(category);")
                    
                    # Migrações de Colunas
                    try:
                        self.logger.info("Tentando aplicar migrações de colunas (proof_data, proof_name).")
                        cur.execute("ALTER TABLE transactions ADD COLUMN proof_data BLOB")
                        cur.execute("ALTER TABLE transactions ADD COLUMN proof_name TEXT")
                    except Exception as migration_err:
                        self.logger.warning(f"Migração ignorada (provavelmente colunas já existem): {migration_err}")
                        pass

                    # Commit é automático pelo context manager do 'with conn', mas mantendo lógica original explicita
                    conn.commit()
                    self.logger.info("Inicialização do banco concluída com sucesso.")
        except Exception as e:
            self.logger.critical(f"Database Init Failed: {e}\n{traceback.format_exc()}")
            # Não relançamos o erro para não crashar a UI inteira, mas logamos criticamente.

    # --- Autenticação ---
    
    def register(self, user: str, pwd: str) -> Tuple[bool, str]:
        self.logger.info(f"Tentativa de registro para usuário: {user}")
        
        # Validação de Tipos Defensiva
        if not isinstance(user, str) or not isinstance(pwd, str):
            self.logger.error("Tipos de entrada inválidos para registro.")
            return False, "Dados inválidos (erro de tipo)."

        if not user or not pwd: 
            return False, "Campos vazios."
        
        if not SecurityManager.is_strong_password(pwd): 
            self.logger.warning(f"Senha fraca rejeitada para usuário: {user}")
            return False, "Senha fraca."
            
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM users WHERE username = %s", (user,))
                    if cur.fetchone(): 
                        self.logger.warning(f"Tentativa de registro duplicado: {user}")
                        return False, "Usuário existe."
                    
                    cur.execute("INSERT INTO users VALUES (%s, %s, %s)", 
                               (user, SecurityManager.hash_pwd(pwd), str(datetime.now())))
                    conn.commit()
            
            self.logger.info(f"Usuário {user} registrado com sucesso.")
            return True, "Sucesso."
        except Exception as e: 
            self.logger.error(f"Erro interno ao registrar usuário {user}: {e}\n{traceback.format_exc()}")
            return False, "Erro interno."

    def login(self, user: str, pwd: str) -> bool:
        # Validação Defensiva
        if not isinstance(user, str) or not isinstance(pwd, str):
            self.logger.error("Tentativa de login com tipos inválidos.")
            return False

        if not user or not pwd: 
            return False
            
        try:
            self.logger.debug(f"Verificando credenciais para: {user}")
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    # Hash pwd antes de comparar
                    pwd_hash = SecurityManager.hash_pwd(pwd)
                    cur.execute("SELECT username FROM users WHERE username=%s AND password_hash=%s", 
                               (user, pwd_hash))
                    result = cur.fetchone() is not None
                    
                    if result:
                        self.logger.info(f"Login bem-sucedido: {user}")
                    else:
                        self.logger.warning(f"Falha de login (credenciais inválidas): {user}")
                    return result
        except Exception as e: 
            self.logger.error(f"Erro ao processar login: {e}\n{traceback.format_exc()}")
            return False

    # --- Categorias ---
    
    def get_categories(self, uid: str) -> List[str]:
        if not uid or not isinstance(uid, str):
            self.logger.error(f"UID inválido em get_categories: {uid}")
            return sorted(CATEGORIAS_BASE)

        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT name FROM custom_categories WHERE user_id=%s", (uid,))
                    custom = [row[0] for row in cur.fetchall()]
            return sorted(list(set(CATEGORIAS_BASE + custom)))
        except Exception as e: 
            self.logger.error(f"Erro ao buscar categorias para {uid}: {e}")
            return sorted(CATEGORIAS_BASE)

    def add_category(self, uid: str, name: str) -> bool:
        if not name or not isinstance(name, str):
            return False
        if name in CATEGORIAS_BASE: 
            return False
            
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM custom_categories WHERE user_id=%s AND name=%s", (uid, name))
                    if cur.fetchone(): 
                        self.logger.info(f"Categoria já existente: {name}")
                        return False
                    cur.execute("INSERT INTO custom_categories (user_id, name) VALUES (%s, %s)", (uid, name))
                    conn.commit()
            st.cache_data.clear()
            self.logger.info(f"Categoria adicionada: {name} por {uid}")
            return True
        except Exception as e: 
            self.logger.error(f"Erro ao adicionar categoria: {e}")
            return False

    def delete_category(self, uid: str, name: str) -> bool:
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM custom_categories WHERE user_id=%s AND name=%s", (uid, name))
                    conn.commit()
            st.cache_data.clear()
            self.logger.info(f"Categoria removida: {name} por {uid}")
            return True
        except Exception as e: 
            self.logger.error(f"Erro ao remover categoria: {e}")
            return False

    # --- Transações ---
    
    def add_transaction(self, uid: str, date_val: Any, amt: float, cat: str, desc: str, type_: str, 
                        proof_file=None, proof_name: str=None) -> bool:
        self.logger.info(f"Iniciando transação para {uid}. Valor: {amt}, Tipo: {type_}")
        
        try:
            # Blindagem de Dados de Entrada
            if not isinstance(amt, (int, float)):
                self.logger.error(f"Valor inválido recebido: {amt} (tipo {type(amt)})")
                return False

            clean_amt = DomainValidators.validate_amount(amt)
            clean_date = DomainValidators.validate_date(date_val)
            clean_type = DomainValidators.normalize_type(type_)
            
            # Validação extra de segurança
            if clean_amt < 0:
                self.logger.warning("Tentativa de inserir transação com valor negativo.")
                # Não bloqueamos pois pode ser estorno, mas logamos.

            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    proof_bytes = proof_file if isinstance(proof_file, bytes) else (proof_file.getvalue() if proof_file else None)
                    
                    # Adaptação para Postgres (psycopg2) vs SQLite
                    p_data = proof_bytes
                    conn_type = str(type(conn))
                    
                    if 'psycopg2' in conn_type:
                        import psycopg2
                        p_data = psycopg2.Binary(proof_bytes) if proof_bytes else None
                        self.logger.debug("Adaptando BLOB para Postgres.")

                    cur.execute("""INSERT INTO transactions 
                        (user_id, date, amount, category, description, type, proof_data, proof_name) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (uid, clean_date, clean_amt, cat, desc, clean_type, p_data, proof_name))
                    conn.commit()
            
            st.cache_data.clear()
            self.logger.info("Transação inserida com sucesso.")
            return True
        except Exception as e:
            self.logger.error(f"Insert Error Transaction: {e}\n{traceback.format_exc()}")
            return False

    def remove_transaction(self, tid: int, uid: str) -> bool:
        if not tid or not uid:
            return False
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM transactions WHERE id=%s AND user_id=%s", (tid, uid))
                    rows_affected = cur.rowcount if hasattr(cur, 'rowcount') else -1
                    conn.commit()
            
            self.logger.info(f"Transação {tid} removida por {uid}. Rows: {rows_affected}")
            st.cache_data.clear()
            return True
        except Exception as e: 
            self.logger.error(f"Erro ao remover transação {tid}: {e}")
            return False

    # --- Leitura Otimizada ---
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
                    receita, despesa = 0.0, 0.0
                    for tipo, valor in results:
                        if not valor: continue # Proteção contra None
                        if DomainValidators.normalize_type(tipo) == "Receita": receita += valor
                        else: despesa += valor
                    return receita, despesa
        except Exception as e: 
            self.logger.error(f"Erro em get_totals: {e}")
            return 0.0, 0.0

    def fetch_all(self, uid: str, limit: int=None, start_date=None, end_date=None) -> pd.DataFrame:
        try:
            self.logger.debug(f"Fetching data for {uid}. Limit: {limit}")
            with self.get_conn() as conn:
                q = """SELECT id, date, amount, category, description, type, proof_name, proof_data 
                       FROM transactions WHERE user_id = %s"""
                p = [uid]
                if start_date and end_date:
                    q += " AND date >= %s AND date <= %s"
                    p.extend([str(start_date), str(end_date)])
                q += " ORDER BY date DESC, id DESC"
                if limit:
                    if not isinstance(limit, int): limit = 50 # Fallback defensivo
                    q += " LIMIT %s"
                    p.append(limit)
                
                df = pd.read_sql_query(q, conn, params=p)
                return df
        except Exception as e:
            self.logger.error(f"Erro em fetch_all: {e}")
            # Retorna DataFrame vazio estruturado para evitar crash no UI
            return pd.DataFrame(columns=['id', 'date', 'amount', 'category', 'description', 'type', 'proof_name', 'proof_data'])

    def nuke_data(self, uid: str) -> bool:
        self.logger.warning(f"INICIANDO EXCLUSÃO TOTAL DE DADOS PARA {uid}")
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    # Uso de transação para garantir que ou apaga tudo ou nada
                    for table in ["transactions", "budgets", "recurring", "custom_categories"]:
                        cur.execute(f"DELETE FROM {table} WHERE user_id=%s", (uid,))
                    conn.commit()
            st.cache_data.clear()
            self.logger.info(f"Dados deletados com sucesso para {uid}")
            return True
        except Exception as e: 
            self.logger.critical(f"Erro ao resetar conta de {uid}: {e}")
            return False

    # --- Metas ---
    def set_meta(self, uid: str, cat: str, lim: float) -> bool:
        try:
            if not isinstance(lim, (int, float)):
                self.logger.error(f"Limite inválido: {lim}")
                return False
            
            if float(lim) < 0: 
                return False
            
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
        except Exception as e: 
            self.logger.error(f"Erro set_meta: {e}")
            return False

    def delete_meta(self, uid: str, cat: str) -> bool:
        try:
            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM budgets WHERE user_id=%s AND category=%s", (uid, cat))
                    conn.commit()
            st.cache_data.clear()
            return True
        except Exception as e: 
            self.logger.error(f"Erro delete_meta: {e}")
            return False

    def get_metas(self, uid: str) -> pd.DataFrame:
        try:
            with self.get_conn() as conn:
                return pd.read_sql_query("SELECT category, limit_amount FROM budgets WHERE user_id=%s", conn, params=(uid,))
        except Exception as e: 
            self.logger.error(f"Erro get_metas: {e}")
            return pd.DataFrame()

    # --- Recorrência ---
    def add_recurring(self, uid: str, cat: str, amt: float, desc: str, type_: str, day: int) -> bool:
        try:
            clean_amt = DomainValidators.validate_amount(amt)
            clean_type = DomainValidators.normalize_type(type_)
            
            # Validação defensiva do dia
            try:
                d_int = int(day)
                if not (1 <= d_int <= 31): raise ValueError
            except:
                self.logger.error(f"Dia inválido para recorrência: {day}")
                return False

            with self.get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""INSERT INTO recurring 
                        (user_id, category, amount, description, type, day_of_month, last_processed) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (uid, cat, clean_amt, desc, clean_type, d_int, ''))
                    conn.commit()
            self.logger.info(f"Recorrência criada para {uid}")
            return True
        except Exception as e: 
            self.logger.error(f"Erro add_recurring: {e}")
            return False

    def process_recurring_items(self, uid: str, fuso_br=None) -> int:
        self.logger.info(f"Processando itens recorrentes para {uid}")
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
                        
                        # Defesa contra last_proc None
                        last_proc = last_proc if last_proc else ''
                        
                        if last_proc == current_month_str: continue
                        
                        # Lógica de dia (se hoje é >= dia agendado)
                        if today.day >= day:
                            self.logger.info(f"Processando item recorrente ID {rid}")
                            # Reutiliza o método blindado add_transaction
                            success = self.add_transaction(uid, today, amt, cat, f"{desc} (Recorrente)", type_)
                            
                            if success:
                                cur.execute("UPDATE recurring SET last_processed=%s WHERE id=%s", (current_month_str, rid))
                                count += 1
                            else:
                                self.logger.error(f"Falha ao inserir transação recorrente ID {rid}")
                    conn.commit()
            return count
        except Exception as e: 
            self.logger.error(f"Erro process_recurring_items: {e}\n{traceback.format_exc()}")
            return 0

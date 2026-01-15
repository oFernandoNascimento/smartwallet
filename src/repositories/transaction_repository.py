from src.database import RobustDatabase
import pandas as pd

class TransactionRepository:
    """
    Camada de Acesso a Dados (Data Access Layer).
    Isola o banco de dados do resto do sistema.
    """
    def __init__(self):
        # Reutiliza sua classe RobustDatabase existente (Singleton)
        self.db = RobustDatabase()

    def insert(self, uid, date, amount, cat, desc, type_, proof, proof_name):
        return self.db.add_transaction(uid, date, amount, cat, desc, type_, proof, proof_name)

    def get_financial_summary(self, uid, start=None, end=None):
        """
        Retorna apenas as colunas necessárias para calcular saldo,
        evitando trafegar dados inúteis.
        """
        df = self.db.fetch_all(uid, start_date=start, end_date=end)
        if df.empty:
            return []
        # Retorna lista de tuplas (tipo, valor)
        return list(zip(df['type'], df['amount']))

    def fetch_all_by_user(self, uid, limit=None):
        return self.db.fetch_all(uid, limit=limit)

    def delete(self, tid, uid):
        return self.db.remove_transaction(tid, uid)
import logging
import pandas as pd
import streamlit as st # Importado para o Cache
from typing import Tuple, Any, Optional

from src.utils import DomainValidators
from src.repositories.transaction_repository import TransactionRepository
from src.core.result import Result
# --------------------------------

logger = logging.getLogger(__name__)

class TransactionService:
    """
    Camada de Regra de Negócio.
    Agora retorna objetos Result[T] para maior segurança.
    """
    
    def __init__(self):
        self.repository = TransactionRepository()

    def register_transaction(self, user_id: str, date_val: Any, amount: float, category: str, 
                             description: str, type_: str, proof_file: Any = None) -> Result[str]:
        try:
            # 1. Validações
            clean_amt = DomainValidators.validate_amount(amount)
            clean_date = DomainValidators.validate_date(date_val)
            clean_type = DomainValidators.normalize_type(type_)
            
            if not description or len(description) > 255:
                return Result.failure("Descrição inválida (muito longa ou vazia).")

            # 2. Arquivo
            proof_bytes = proof_file.getvalue() if proof_file else None
            proof_name = proof_file.name if proof_file else None

            # 3. Persistência
            success = self.repository.insert(
                user_id, clean_date, clean_amt, category, 
                description, clean_type, proof_bytes, proof_name
            )

            if success:
                st.cache_data.clear() # <--- LIMPA O CACHE PARA ATUALIZAR A TELA
                return Result.success("Transação registrada com sucesso.")
            return Result.failure("Erro de banco de dados ao salvar.")

        except ValueError as ve:
            logger.warning(f"Erro validação: {ve}")
            return Result.failure(str(ve))
        except Exception as e:
            logger.critical(f"Erro serviço: {e}")
            return Result.failure("Erro interno no sistema.")

    # --- FUNÇÕES COM CACHE (PERFORMANCE) ---
    # O '_self' com underline diz pro Streamlit não tentar hashear a classe inteira
    
    @st.cache_data(show_spinner=False, ttl=300)
    def get_balance_view(_self, uid: str, start=None, end=None) -> Tuple[float, float, float]:
        data = _self.repository.get_financial_summary(uid, start, end)
        receita = 0.0
        despesa = 0.0
        for tipo, valor in data:
            if DomainValidators.normalize_type(tipo) == "Receita":
                receita += valor
            else:
                despesa += valor
        return receita, despesa, (receita - despesa)

    @st.cache_data(show_spinner=False, ttl=300)
    def get_statement(_self, uid: str, limit: Optional[int] = None) -> pd.DataFrame:
        return _self.repository.fetch_all_by_user(uid, limit)

    def delete_transaction(self, tid: int, uid: str) -> bool:
        success = self.repository.delete(tid, uid)
        if success:
            st.cache_data.clear() # <--- LIMPA O CACHE SE DELETAR
        return success
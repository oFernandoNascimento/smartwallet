import io
from typing import List, Dict, Any
from ofxparse import OfxParser

def parse_ofx_file(file_buffer: io.BytesIO) -> List[Dict[str, Any]]:
    """
    Processa um arquivo OFX em memória e retorna uma lista normalizada de transações.
    Retorna uma lista vazia em caso de falha no parse.
    """
    try:
        # Garante que o ponteiro de leitura esteja no início do arquivo
        file_buffer.seek(0)
        
        ofx = OfxParser.parse(file_buffer)
        
        # Acessa a primeira conta disponível no extrato
        account = ofx.account
        statement = account.statement
        
        transactions_data = []

        for transaction in statement.transactions:
            transactions_data.append({
                "date": transaction.date,
                "description": transaction.memo, # Alguns bancos usam .payee
                "amount": float(transaction.amount),
                "transaction_id": transaction.id,
                "type": transaction.type
            })

        return transactions_data

    except Exception as e:
        # Em produção, substitua por um logger real (ex: logging.error(e))
        print(f"[Erro no Importador OFX]: {e}")
        return []
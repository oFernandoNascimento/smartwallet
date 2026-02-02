import io
from typing import List, Dict, Any
from ofxparse import OfxParser

def parse_ofx_file(file_buffer: io.BytesIO) -> List[Dict[str, Any]]:
    try:
        file_buffer.seek(0)
        ofx = OfxParser.parse(file_buffer)
        
        if not ofx.account or not ofx.account.statement:
            return []
            
        transactions_data = []

        for t in ofx.account.statement.transactions:
            t_type = str(t.type).upper()
            val = float(t.amount)
            
            final_type = "Despesa" 
            
            if t_type == "CREDIT" or val > 0:
                final_type = "Receita"
            elif t_type == "DEBIT" or val < 0:
                final_type = "Despesa"
            
            desc = str(t.memo).split(' - ')[0] if t.memo else "Sem descrição"

            transactions_data.append({
                "date": t.date,
                "description": desc,
                "amount": abs(val),
                "transaction_id": t.id,
                "type": final_type,
                "category": "Outros" 
            })

        return transactions_data

    except Exception as e:
        print(f"Erro OFX: {e}")
        return []

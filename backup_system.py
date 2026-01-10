import shutil
import time
import os
from datetime import datetime

# Configurações
DB_ORIGINAL = "smartwallet.db"
PASTA_BACKUP = "backups_banco"

def realizar_backup():
    # Cria pasta se não existir
    if not os.path.exists(PASTA_BACKUP):
        os.makedirs(PASTA_BACKUP)
    
    # Gera nome com data e hora (Ex: smartwallet_2026-01-09_20-30.db)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    destino = f"{PASTA_BACKUP}/smartwallet_{timestamp}.db"
    
    try:
        shutil.copy2(DB_ORIGINAL, destino)
        print(f"✅ Backup realizado com sucesso: {destino}")
    except FileNotFoundError:
        print("❌ Arquivo de banco de dados não encontrado. Rode o sistema primeiro.")

if __name__ == "__main__":
    realizar_backup()
    
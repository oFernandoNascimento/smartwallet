import unittest
import os
import time
import gc # Garbage Collector (Coletor de lixo da memória)
from smart_wallet import SecureTransactionDAO

class TestSmartWalletSecurity(unittest.TestCase):
    
    def setUp(self):
        """Prepara o terreno ANTES de cada teste"""
        self.db_name = "test_wallet.db"
        self.force_cleanup() # Garante que começa limpo
        self.dao = SecureTransactionDAO(db_name=self.db_name)

    def tearDown(self):
        """Limpa a bagunça DEPOIS de cada teste"""
        self.force_cleanup()

    def force_cleanup(self):
        """Função poderosa para deletar o arquivo mesmo se o Windows bloquear"""
        # 1. Força o Python a fechar conexões abertas na memória
        self.dao = None
        gc.collect()
        
        # 2. Tenta apagar o arquivo
        if os.path.exists(self.db_name):
            for i in range(3): # Tenta 3 vezes
                try:
                    os.remove(self.db_name)
                    break # Se conseguiu, para
                except PermissionError:
                    time.sleep(0.5) # Espera meio segundo e tenta de novo
                except Exception:
                    pass

    def test_usuario_criacao_e_login(self):
        """Teste: Deve criar usuário e permitir login com senha correta"""
        user = "tester_qa"
        senha = "123_password"
        
        # 1. Tenta criar
        sucesso, msg = self.dao.create_user(user, senha)
        self.assertTrue(sucesso, f"Falha ao criar usuário: {msg}")
        
        # 2. Tenta logar com senha certa
        login_ok = self.dao.verify_login(user, senha)
        self.assertTrue(login_ok, "Deveria logar com a senha correta")
        
        # 3. Tenta logar com senha errada
        login_fail = self.dao.verify_login(user, "senha_errada")
        self.assertFalse(login_fail, "Não deveria logar com senha errada")

    def test_transacao_isolada(self):
        """Teste: Transação deve ser salva para o usuário correto"""
        user = "user_finance"
        self.dao.create_user(user, "123")
        
        # Insere transação
        salvou = self.dao.insert_transaction(user, "2026-01-10", 100.0, "Teste", "Desc", "Receita")
        self.assertTrue(salvou)
        
        # Busca dados
        df = self.dao.fetch_all(user)
        self.assertEqual(len(df), 1, "Deveria ter 1 transação salva")
        self.assertEqual(df.iloc[0]['amount'], 100.0)

if __name__ == '__main__':
    unittest.main()
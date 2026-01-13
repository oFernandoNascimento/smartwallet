# Arquivo: tests/test_utils.py
import unittest
import sys
import os

# Adiciona a pasta raiz ao caminho do Python para conseguir importar 'src'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import DomainValidators

class TestValidators(unittest.TestCase):
    
    def test_valor_positivo_sucesso(self):
        """Testa se um valor positivo (100) é aceito normalmente."""
        resultado = DomainValidators.validate_amount(100)
        self.assertEqual(resultado, 100.0)

    def test_rejeita_valor_negativo(self):
        """Testa se o sistema bloqueia valores negativos (-50)."""
        # Esperamos que isso gere um ValueError
        with self.assertRaises(ValueError):
            DomainValidators.validate_amount(-50)

    def test_rejeita_zero(self):
        """Testa se o sistema bloqueia valor zero."""
        with self.assertRaises(ValueError):
            DomainValidators.validate_amount(0)

if __name__ == '__main__':
    unittest.main()
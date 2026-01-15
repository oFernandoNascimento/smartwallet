import unittest
import sys
import os

# Configuração de caminho para permitir a importação do módulo src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils import DomainValidators

class TestValidators(unittest.TestCase):
    """
    Suite de testes unitários para a classe DomainValidators.
    Garante a integridade das regras de negócio para dados financeiros.
    """
    
    def test_valor_positivo_sucesso(self):
        """Verifica se valores positivos válidos são processados e convertidos corretamente."""
        resultado = DomainValidators.validate_amount(100)
        self.assertEqual(resultado, 100.0)

    def test_rejeita_valor_negativo(self):
        """Assegura que valores negativos levantem exceção (ValueError)."""
        with self.assertRaises(ValueError):
            DomainValidators.validate_amount(-50)

    def test_rejeita_zero(self):
        """Assegura que valor zero levante exceção, exigindo valores positivos."""
        with self.assertRaises(ValueError):
            DomainValidators.validate_amount(0)

if __name__ == '__main__':
    unittest.main()
# Arquivo: src/auth.py
import hashlib
import re
import logging
import os
import streamlit as st
from typing import Optional, Union

# Configuração de Logs para Auditoria de Segurança
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("SecurityModule")

class SecurityManager:
    """
    Gerenciador de Segurança, Autenticação e Criptografia.
    
    Responsável por garantir a integridade das credenciais e validar
    a força das senhas conforme as diretrizes de segurança da aplicação.
    """
    
    # Manteve-se a constante para garantir retrocompatibilidade (Regra: Nunca remover código)
    # Mas agora ela atua apenas como um fallback de emergência.
    DEFAULT_UNSAFE_SALT: str = "SmartWallet_2026_SecureSalt_#99"

    @staticmethod
    def _get_salt() -> str:
        """
        Recupera o SALT de criptografia de uma fonte segura (Environment/Secrets).
        
        Returns:
            str: O token de sal para o hash.
        """
        try:
            # Tenta recuperar de st.secrets (Produção) ou Variáveis de Ambiente
            salt: Optional[str] = None
            
            if "SECURITY_SALT" in st.secrets:
                salt = st.secrets["SECURITY_SALT"]
            elif "SECURITY_SALT" in os.environ:
                salt = os.environ["SECURITY_SALT"]
            
            if salt:
                return salt
            
            # Alerta de Segurança Crítico se cair no fallback
            logger.warning("SECURITY ALERT: Utilizando SALT hardcoded padrão. Configure 'SECURITY_SALT' nos secrets.")
            return SecurityManager.DEFAULT_UNSAFE_SALT
            
        except Exception as e:
            logger.error(f"Falha crítica ao recuperar SALT: {e}")
            # Em caso de erro total, usa o fallback para não derrubar a aplicação
            return SecurityManager.DEFAULT_UNSAFE_SALT

    @staticmethod
    def hash_pwd(pwd: str) -> str:
        """
        Gera um hash SHA-256 seguro para a senha fornecida utilizando Salt.

        Args:
            pwd (str): A senha em texto plano.

        Returns:
            str: O hash hexadecimal da senha.
        """
        try:
            if not pwd:
                raise ValueError("A senha não pode ser vazia para hashing.")

            salt: str = SecurityManager._get_salt()
            # Combinação do Salt + Senha para evitar ataques de Rainbow Table
            salted_pwd: str = pwd + salt
            
            password_hash: str = hashlib.sha256(salted_pwd.encode('utf-8')).hexdigest()
            
            # Log discreto para debug (sem expor a senha)
            logger.debug(f"Hash gerado com sucesso para senha de comprimento {len(pwd)}")
            
            return password_hash
            
        except Exception as e:
            logger.critical(f"Erro durante o processo de hashing: {e}")
            # Relança a exceção para ser tratada na camada superior (Fail Fast)
            raise e
    
    @staticmethod
    def is_strong_password(pwd: str) -> bool:
        """
        Valida se a senha atende aos requisitos mínimos de complexidade.
        
        Requisitos:
        - Mínimo de 8 caracteres.
        - Pelo menos 1 letra (maiúscula ou minúscula).
        - Pelo menos 1 número.

        Args:
            pwd (str): A senha a ser validada.

        Returns:
            bool: True se a senha for forte, False caso contrário.
        """
        try:
            if not isinstance(pwd, str):
                logger.error("Tentativa de validar senha que não é string.")
                return False

            # Verificações incrementais para clareza e robustez
            has_min_len: bool = len(pwd) >= 8
            has_letter: bool = bool(re.search(r"[A-Za-z]", pwd))
            has_number: bool = bool(re.search(r"[0-9]", pwd))
            
            is_valid: bool = has_min_len and has_letter and has_number
            
            if not is_valid:
                logger.info("Validação de senha falhou: Requisitos de complexidade não atendidos.")
            
            return is_valid

        except Exception as e:
            logger.error(f"Erro inesperado na validação de senha: {e}")
            # Por segurança, falha fechada (retorna False) em caso de erro
            return False
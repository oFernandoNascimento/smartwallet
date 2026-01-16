import hashlib
import re
import logging
import os
import streamlit as st
from typing import Optional, Union, Any

# Configuração de Logs para Auditoria de Segurança
logging.basicConfig(
    format='%(asctime)s - [%(name)s] - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("SecurityModule")

class SecurityManager:
    """
    Gerenciador de Segurança, Autenticação e Criptografia (Refatorado).
    
    Responsável por garantir a integridade das credenciais e validar
    a força das senhas conforme as diretrizes de segurança da aplicação.
    Inclui tratamento de erros e logs detalhados.
    """
    
    # Fallback de segurança para o Salt caso as variáveis de ambiente falhem
    DEFAULT_UNSAFE_SALT: str = "SmartWallet_2026_SecureSalt_#99"

    @staticmethod
    def _get_salt() -> str:
        """
        Recupera o SALT de criptografia de uma fonte segura.
        
        Returns:
            str: O token de sal para o hash.
        """
        try:
            salt: Optional[str] = None
            
            # Prioridade: Streamlit Secrets > Variáveis de Ambiente
            # Wrap em try-except específico para acesso a st.secrets para evitar crash se não configurado
            try:
                if "SECURITY_SALT" in st.secrets:
                    salt = st.secrets["SECURITY_SALT"]
            except Exception:
                logger.debug("st.secrets não disponível ou erro de acesso.")

            if not salt and "SECURITY_SALT" in os.environ:
                salt = os.environ["SECURITY_SALT"]
            
            if salt:
                return str(salt)
            
            logger.warning("SECURITY ALERT: Utilizando SALT padrão. Configure 'SECURITY_SALT' nos secrets.")
            return SecurityManager.DEFAULT_UNSAFE_SALT
            
        except Exception as e:
            logger.critical(f"Falha crítica ao recuperar SALT: {e}")
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
            # Validação defensiva de entrada
            if not isinstance(pwd, str):
                logger.error(f"Tentativa de hash em tipo não-string: {type(pwd)}")
                raise TypeError("A senha deve ser uma string.")

            if not pwd:
                raise ValueError("A senha não pode ser vazia para hashing.")

            salt: str = SecurityManager._get_salt()
            # Combinação do Salt + Senha para proteção contra Rainbow Tables
            salted_pwd: str = pwd + salt
            
            password_hash: str = hashlib.sha256(salted_pwd.encode('utf-8')).hexdigest()
            
            # NÃO logar o hash gerado, apenas o sucesso da operação
            logger.debug(f"Hash gerado com sucesso para senha de comprimento {len(pwd)}")
            
            return password_hash
            
        except Exception as e:
            logger.critical(f"Erro durante o processo de hashing: {e}")
            # Em caso de falha crítica de segurança, retornamos um hash vazio ou erro explícito para falhar o login
            raise e
    
    @staticmethod
    def is_strong_password(pwd: str) -> bool:
        """
        Valida se a senha atende aos requisitos mínimos de complexidade.
        
        Args:
            pwd (str): A senha a ser validada.

        Returns:
            bool: True se a senha for forte, False caso contrário.
        """
        try:
            if not isinstance(pwd, str):
                logger.error("Tentativa de validar senha que não é string.")
                return False
            
            if not pwd:
                return False

            # Definição clara de regras
            has_min_len: bool = len(pwd) >= 8
            has_letter: bool = bool(re.search(r"[A-Za-z]", pwd))
            has_number: bool = bool(re.search(r"[0-9]", pwd))
            # Opcional: Adicionar caracteres especiais para maior robustez futura
            # has_special = bool(re.search(r"[!@#$%^&*(),.?\":{}|<>]", pwd))
            
            is_valid: bool = has_min_len and has_letter and has_number
            
            if not is_valid:
                logger.info(f"Validação de senha falhou. Len: {len(pwd)}, Letra: {has_letter}, Num: {has_number}")
            
            return is_valid

        except Exception as e:
            logger.error(f"Erro inesperado na validação de senha: {e}")
            return False

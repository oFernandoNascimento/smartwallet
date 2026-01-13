# Arquivo: src/auth.py
import hashlib
import re

class SecurityManager:
    """
    Gerencia a segurança e senhas do SmartWallet.
    Separa a lógica de proteção do resto do app.
    """
    
    # Sal para tornar o hash da senha único e difícil de quebrar
    SALT = "SmartWallet_2026_SecureSalt_#99"

    @staticmethod
    def hash_pwd(pwd: str) -> str:
        """Recebe uma senha normal e transforma em um código seguro (Hash SHA-256)."""
        salted_pwd = pwd + SecurityManager.SALT
        return hashlib.sha256(salted_pwd.encode()).hexdigest()
    
    @staticmethod
    def is_strong_password(pwd: str) -> bool:
        """
        Valida se a senha é forte:
        - Mínimo 8 caracteres
        - Pelo menos 1 letra
        - Pelo menos 1 número
        """
        if len(pwd) < 8: return False
        if not re.search(r"[A-Za-z]", pwd): return False 
        if not re.search(r"[0-9]", pwd): return False 
        return True

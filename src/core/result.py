from typing import TypeVar, Generic, Optional

T = TypeVar('T')

class Result(Generic[T]):
    """
    Padrão 'Result' para tratamento de erros funcional.
    Evita o uso excessivo de try/catch no código principal.
    """
    def __init__(self, is_success: bool, data: Optional[T], error: Optional[str]):
        self.is_success = is_success
        self.data = data
        self.error = error

    @classmethod
    def success(cls, data: T) -> 'Result[T]':
        return cls(True, data, None)

    @classmethod
    def failure(cls, error: str) -> 'Result[T]':
        return cls(False, None, error)
"""
CloudForge - Módulo de Retry com Backoff Exponencial
Implementa retry automático para operações falhas com backoff exponencial e jitter.
"""

import functools
import random
import time
from typing import Any, Callable, Optional, Tuple, Type

from cloudforge.core.logger import get_logger

logger = get_logger(__name__)


class RetryError(Exception):
    """Exceção levantada quando todas as tentativas de retry falham."""

    def __init__(self, message: str, last_exception: Optional[Exception] = None, attempts: int = 0):
        super().__init__(message)
        self.last_exception = last_exception
        self.attempts = attempts


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    log_level: str = "warning",
) -> Callable:
    """
    Decorador para retry automático com backoff exponencial.

    Args:
        max_attempts: Número máximo de tentativas (default: 3)
        base_delay: Delay inicial em segundos (default: 1.0)
        max_delay: Delay máximo em segundos (default: 60.0)
        exponential_base: Base para cálculo exponencial (default: 2.0)
        jitter: Adiciona aleatoriedade para evitar thundering herd (default: True)
        retryable_exceptions: Tupla de exceções que devem ser retentadas.
                              Se None, todas as exceções são retentadas.
        log_level: Nível de log para mensagens de retry (default: "warning")

    Returns:
        Decorador que pode ser aplicado a funções

    Exemplo:
        @retry_with_backoff(max_attempts=5, retryable_exceptions=(TimeoutError,))
        def create_resource(params):
            # Operação que pode falhar temporariamente
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    # Verificar se a exceção é retentável
                    if retryable_exceptions and not isinstance(e, retryable_exceptions):
                        raise

                    # Calcular delay
                    delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    # Log do retry
                    log_func = getattr(logger, log_level, logger.warning)
                    log_func(
                        f"Tentativa {attempt}/{max_attempts} falhou para {func.__name__}: {e}. "
                        f"Próxima tentativa em {delay:.2f}s"
                    )

                    # Aguardar antes de próxima tentativa (se não for última)
                    if attempt < max_attempts:
                        time.sleep(delay)

            # Todas as tentativas falharam
            raise RetryError(
                f"{func.__name__} falhou após {max_attempts} tentativas",
                last_exception=last_exception,
                attempts=max_attempts,
            )

        return wrapper

    return decorator


class RetryConfig:
    """Configuração de retry para operações."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or (Exception,)

    def execute(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Executa uma função com retry configurado.

        Args:
            func: Função a ser executada
            *args: Argumentos posicionais para a função
            **kwargs: Argumentos nomeados para a função

        Returns:
            Resultado da função

        Raises:
            RetryError: Se todas as tentativas falharem
        """
        last_exception = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                return func(*args, **kwargs)

            except Exception as e:
                last_exception = e

                if not isinstance(e, self.retryable_exceptions):
                    raise

                delay = min(
                    self.base_delay * (self.exponential_base ** (attempt - 1)),
                    self.max_delay
                )
                if self.jitter:
                    delay = delay * (0.5 + random.random())

                logger.warning(
                    f"Tentativa {attempt}/{self.max_attempts} falhou: {e}. "
                    f"Retry em {delay:.2f}s"
                )

                if attempt < self.max_attempts:
                    time.sleep(delay)

        raise RetryError(
            f"Operação falhou após {self.max_attempts} tentativas",
            last_exception=last_exception,
            attempts=self.max_attempts,
        )


def retry_on_exception(
    exception_type: Type[Exception],
    max_attempts: int = 3,
    message: Optional[str] = None,
) -> Callable:
    """
    Decorador simplificado para retry em um tipo específico de exceção.

    Args:
        exception_type: Tipo de exceção que deve ser retentada
        max_attempts: Número máximo de tentativas
        message: Mensagem customizada de log

    Returns:
        Decorador

    Exemplo:
        @retry_on_exception(ConnectionError, max_attempts=5)
        def connect_to_database():
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)

                except exception_type as e:
                    last_exception = e
                    log_msg = message or f"{func.__name__} falhou ({exception_type.__name__})"
                    logger.warning(f"{log_msg} - tentativa {attempt}/{max_attempts}")

                    if attempt < max_attempts:
                        delay = 2 ** (attempt - 1)
                        time.sleep(delay)

            raise RetryError(
                f"{func.__name__} falhou após {max_attempts} tentativas",
                last_exception=last_exception,
                attempts=max_attempts,
            )

        return wrapper

    return decorator


# Exceções comuns de cloud que devem ser retentadas
CLOUD_RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,
)

# Para operações de API HTTP
HTTP_RETRYABLE_STATUS_CODES = (408, 429, 500, 502, 503, 504)


def is_retryable_http_status(status_code: int) -> bool:
    """Verifica se um status code HTTP deve ser retentado."""
    return status_code in HTTP_RETRYABLE_STATUS_CODES


def retry_cloud_operation(func: Callable) -> Callable:
    """
    Decorador convenience para operações de cloud.
    Retry automático para erros transitórios de rede/cloud.
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        last_exception = None

        for attempt in range(1, 4):  # 3 tentativas
            try:
                return func(*args, **kwargs)

            except CLOUD_RETRYABLE_EXCEPTIONS as e:
                last_exception = e
                delay = 2 ** (attempt - 1)
                logger.warning(
                    f"Erro transitório em {func.__name__}: {e}. "
                    f"Retry em {delay}s (tentativa {attempt}/3)"
                )
                time.sleep(delay)

            except Exception as e:
                # Erros não transitórios são levantados imediatamente
                raise

        raise RetryError(
            f"{func.__name__} falhou após 3 tentativas",
            last_exception=last_exception,
            attempts=3,
        )

    return wrapper

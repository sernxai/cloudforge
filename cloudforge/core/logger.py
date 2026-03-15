"""
CloudForge - Módulo de Logging Estruturado
Sistema de logs com múltiplos níveis, formatação e suporte a arquivo.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# Tema personalizado para logs
LOG_THEME = Theme({
    "logging.level.debug": "dim cyan",
    "logging.level.info": "bold green",
    "logging.level.warning": "bold yellow",
    "logging.level.error": "bold red",
    "logging.level.critical": "bold magenta",
})

console = Console(theme=LOG_THEME)


class CloudForgeLogger:
    """
    Logger estruturado para CloudForge.
    
    Features:
    - Logs em console com Rich (cores e formatação)
    - Logs em arquivo (opcional)
    - Múltiplos níveis (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - Contexto adicional (projeto, provider, resource)
    - Formatação JSON para integração com ferramentas externas
    """

    _instance: Optional["CloudForgeLogger"] = None
    _initialized: bool = False

    def __new__(cls, *args, **kwargs) -> "CloudForgeLogger":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        name: str = "cloudforge",
        level: str = "INFO",
        log_file: Optional[str] = None,
        enable_json: bool = False,
    ):
        if self._initialized:
            return

        self.name = name
        self.level = getattr(logging, level.upper(), logging.INFO)
        self.log_file = log_file
        self.enable_json = enable_json
        self.context: dict = {}

        self._setup_logger()
        self._initialized = True

    def _setup_logger(self) -> None:
        """Configura o logger principal."""
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(self.level)
        self.logger.handlers.clear()

        # Handler para console com Rich
        rich_handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            tracebacks_show_locals=self.level == logging.DEBUG,
            markup=True,
        )
        rich_handler.setLevel(self.level)

        if not self.enable_json:
            # Formato legível para humano
            rich_handler.setFormatter(logging.Formatter(
                fmt="%(message)s",
                datefmt="[%X]",
            ))
        else:
            # Formato JSON para máquinas
            rich_handler.setFormatter(logging.Formatter(
                fmt='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
                datefmt="%Y-%m-%dT%H:%M:%S",
            ))

        self.logger.addHandler(rich_handler)

        # Handler para arquivo (opcional)
        if self.log_file:
            log_path = Path(self.log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setLevel(self.level)
            file_handler.setFormatter(logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
            self.logger.addHandler(file_handler)

    def set_context(self, **kwargs) -> None:
        """
        Adiciona contexto aos logs (projeto, provider, resource, etc).
        
        Exemplo:
            logger.set_context(project="my-app", provider="aws", resource="vm-1")
        """
        self.context.update(kwargs)

    def clear_context(self) -> None:
        """Limpa o contexto atual."""
        self.context.clear()

    def _with_context(self, message: str) -> str:
        """Adiciona contexto à mensagem se existir."""
        if not self.context:
            return message

        context_str = " | ".join(f"{k}={v}" for k, v in self.context.items())
        return f"[{context_str}] {message}"

    def debug(self, message: str, *args, **kwargs) -> None:
        """Log de debug (detalhes técnicos)."""
        self.logger.debug(self._with_context(message), *args, **kwargs)

    def info(self, message: str, *args, **kwargs) -> None:
        """Log de informação (operações normais)."""
        self.logger.info(self._with_context(message), *args, **kwargs)

    def warning(self, message: str, *args, **kwargs) -> None:
        """Log de aviso (algo inesperado, mas não crítico)."""
        self.logger.warning(self._with_context(message), *args, **kwargs)

    def error(self, message: str, *args, **kwargs) -> None:
        """Log de erro (falha em operação)."""
        self.logger.error(self._with_context(message), *args, **kwargs)

    def critical(self, message: str, *args, **kwargs) -> None:
        """Log crítico (erro grave que pode parar o sistema)."""
        self.logger.critical(self._with_context(message), *args, **kwargs)

    def exception(self, message: str, *args, **kwargs) -> None:
        """Log de exceção (inclui traceback)."""
        self.logger.exception(self._with_context(message), *args, **kwargs)

    def success(self, message: str, *args, **kwargs) -> None:
        """Log de sucesso (operação concluída com êxito)."""
        # Rich não tem nível 'success', usamos INFO com marcação
        self.logger.info(f"[green]✓[/green] {message}", *args, **kwargs)

    def step(self, step_name: str, message: str, *args, **kwargs) -> None:
        """
        Log de passo de execução (para workflows).
        
        Exemplo:
            logger.step("CREATE", "Creating VM instance...")
        """
        self.logger.info(f"[bold cyan]→ {step_name}:[/bold cyan] {message}", *args, **kwargs)


def get_logger(
    name: str = "cloudforge",
    level: str = "INFO",
    log_file: Optional[str] = None,
) -> CloudForgeLogger:
    """
    Factory para obter um logger configurado.
    
    Args:
        name: Nome do logger
        level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Caminho opcional para arquivo de log
    
    Returns:
        Instância de CloudForgeLogger
    """
    return CloudForgeLogger(name=name, level=level, log_file=log_file)


# Logger global padrão
default_logger = CloudForgeLogger()


# Funções convenience para uso direto
def debug(msg: str, *args, **kwargs) -> None:
    default_logger.debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs) -> None:
    default_logger.info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs) -> None:
    default_logger.warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs) -> None:
    default_logger.error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs) -> None:
    default_logger.critical(msg, *args, **kwargs)


def exception(msg: str, *args, **kwargs) -> None:
    default_logger.exception(msg, *args, **kwargs)


def success(msg: str, *args, **kwargs) -> None:
    default_logger.success(msg, *args, **kwargs)


def step(step_name: str, msg: str, *args, **kwargs) -> None:
    default_logger.step(step_name, msg, *args, **kwargs)


def set_context(**kwargs) -> None:
    default_logger.set_context(**kwargs)


def clear_context() -> None:
    default_logger.clear_context()

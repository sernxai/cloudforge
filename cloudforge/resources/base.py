"""
CloudForge - Classes Base de Recursos
Interface abstrata para todos os tipos de recursos de infraestrutura.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResourceResult:
    """Resultado de uma operação sobre um recurso."""

    success: bool
    provider_id: str | None = None
    outputs: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    error: str | None = None


class BaseResource(ABC):
    """Classe abstrata que define a interface de um recurso de infraestrutura."""

    RESOURCE_TYPE: str = ""

    def __init__(self, name: str, config: dict[str, Any], provider: Any = None):
        self.name = name
        self.config = config
        self.provider = provider

    @abstractmethod
    def validate(self) -> list[str]:
        """
        Valida a configuração do recurso.
        Retorna lista de erros (vazia se válido).
        """
        pass

    @abstractmethod
    def create(self) -> ResourceResult:
        """Cria o recurso na nuvem."""
        pass

    @abstractmethod
    def update(self, changes: dict[str, Any]) -> ResourceResult:
        """Atualiza o recurso na nuvem."""
        pass

    @abstractmethod
    def delete(self, provider_id: str) -> ResourceResult:
        """Destrói o recurso na nuvem."""
        pass

    @abstractmethod
    def get_status(self, provider_id: str) -> dict[str, Any]:
        """Retorna o status atual do recurso na nuvem."""
        pass

    def get_defaults(self) -> dict[str, Any]:
        """Retorna valores padrão para configuração."""
        return {}

    def resolve_config(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Resolve a configuração final, aplicando defaults e
        substituindo referências a outros recursos.
        """
        defaults = self.get_defaults()
        resolved = {**defaults, **self.config}

        # Resolver referências a outputs de outros recursos
        if context:
            for key, value in resolved.items():
                if isinstance(value, str) and value.startswith("${"):
                    ref = value[2:-1]  # Remove ${ e }
                    parts = ref.split(".")
                    if len(parts) == 2:
                        res_name, output_key = parts
                        if res_name in context:
                            resolved[key] = context[res_name].get(
                                output_key, value
                            )
        return resolved

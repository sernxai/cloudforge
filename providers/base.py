"""
CloudForge - Classe Base de Provider
Interface abstrata para provedores de nuvem.
"""

from abc import ABC, abstractmethod
from typing import Any

from resources.base import ResourceResult


class ProviderError(Exception):
    """Erro genérico de provider."""

    pass


class BaseProvider(ABC):
    """Interface abstrata para provedores de nuvem."""

    PROVIDER_NAME: str = ""

    def __init__(self, region: str, credentials: dict[str, Any] | None = None):
        self.region = region
        self.credentials = credentials or {}
        self._clients: dict[str, Any] = {}

    @abstractmethod
    def authenticate(self) -> bool:
        """Autentica com o provedor. Retorna True se sucesso."""
        pass

    @abstractmethod
    def validate_credentials(self) -> bool:
        """Verifica se as credenciais são válidas."""
        pass

    @abstractmethod
    def create_resource(
        self, resource_type: str, params: dict[str, Any]
    ) -> ResourceResult:
        """Cria um recurso no provedor."""
        pass

    @abstractmethod
    def update_resource(
        self,
        resource_type: str,
        name: str,
        config: dict[str, Any],
        changes: dict[str, Any],
    ) -> ResourceResult:
        """Atualiza um recurso existente."""
        pass

    @abstractmethod
    def delete_resource(
        self, resource_type: str, provider_id: str
    ) -> ResourceResult:
        """Deleta um recurso."""
        pass

    @abstractmethod
    def get_resource_status(
        self, resource_type: str, provider_id: str
    ) -> dict[str, Any]:
        """Retorna o status de um recurso."""
        pass

    @abstractmethod
    def list_regions(self) -> list[str]:
        """Lista regiões disponíveis."""
        pass

    def get_client(self, service: str) -> Any:
        """Retorna cliente cacheado para um serviço."""
        return self._clients.get(service)

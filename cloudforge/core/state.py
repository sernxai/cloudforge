"""
CloudForge - Gerenciamento de Estado
Rastreia recursos provisionados em arquivo JSON local.
"""

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from copy import deepcopy


class StateError(Exception):
    """Erro de estado."""

    pass


class ResourceState:
    """Representa o estado de um recurso individual."""

    def __init__(
        self,
        name: str,
        resource_type: str,
        provider: str,
        config: dict,
        provider_id: str | None = None,
        status: str = "planned",
        outputs: dict | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
    ):
        self.name = name
        self.resource_type = resource_type
        self.provider = provider
        self.config = config
        self.provider_id = provider_id
        self.status = status  # planned, creating, active, updating, destroying, destroyed
        self.outputs = outputs or {}
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.updated_at = updated_at or self.created_at

    @property
    def config_hash(self) -> str:
        """Hash da configuração para detectar mudanças."""
        config_str = json.dumps(self.config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "resource_type": self.resource_type,
            "provider": self.provider,
            "config": self.config,
            "config_hash": self.config_hash,
            "provider_id": self.provider_id,
            "status": self.status,
            "outputs": self.outputs,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ResourceState":
        return cls(
            name=data["name"],
            resource_type=data["resource_type"],
            provider=data["provider"],
            config=data["config"],
            provider_id=data.get("provider_id"),
            status=data.get("status", "active"),
            outputs=data.get("outputs", {}),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


class StateManager:
    """Gerencia o estado da infraestrutura em arquivo JSON local."""

    STATE_VERSION = "1.0"

    def __init__(self, state_path: str = ".cloudforge/state.json"):
        self.state_path = Path(state_path)
        self._resources: dict[str, ResourceState] = {}
        self._metadata: dict[str, Any] = {}

    def load(self) -> None:
        """Carrega estado existente do disco."""
        if not self.state_path.exists():
            self._metadata = {
                "version": self.STATE_VERSION,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            return

        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise StateError(f"Erro ao ler arquivo de estado: {e}")

        self._metadata = data.get("metadata", {})
        for name, res_data in data.get("resources", {}).items():
            self._resources[name] = ResourceState.from_dict(res_data)

    def save(self) -> None:
        """Persiste estado atual no disco."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

        # Backup antes de salvar
        if self.state_path.exists():
            backup_path = self.state_path.with_suffix(".json.backup")
            backup_path.write_text(self.state_path.read_text(encoding="utf-8"), encoding="utf-8")

        self._metadata["updated_at"] = datetime.now(timezone.utc).isoformat()

        data = {
            "metadata": self._metadata,
            "resources": {
                name: rs.to_dict() for name, rs in self._cloudforge.resources.items()
            },
        }

        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_resource(self, name: str) -> ResourceState | None:
        """Retorna o estado de um recurso pelo nome."""
        return self._cloudforge.resources.get(name)

    def set_resource(self, resource: ResourceState) -> None:
        """Define/atualiza o estado de um recurso."""
        resource.updated_at = datetime.now(timezone.utc).isoformat()
        self._resources[resource.name] = resource

    def remove_resource(self, name: str) -> None:
        """Remove um recurso do estado."""
        self._cloudforge.resources.pop(name, None)

    def list_resources(self) -> list[ResourceState]:
        """Lista todos os recursos no estado."""
        return list(self._cloudforge.resources.values())

    def has_resource(self, name: str) -> bool:
        """Verifica se um recurso existe no estado."""
        return name in self._resources

    def get_active_resources(self) -> list[ResourceState]:
        """Retorna apenas recursos ativos."""
        return [r for r in self._cloudforge.resources.values() if r.status == "active"]

    def diff(self, desired_resources: list[dict]) -> dict[str, list]:
        """
        Compara estado atual com o desejado e retorna as diferenças.

        Returns:
            {
                "create": [recursos a criar],
                "update": [recursos a atualizar],
                "delete": [recursos a remover],
                "unchanged": [recursos sem mudança]
            }
        """
        desired_map = {r["name"]: r for r in desired_resources}
        current_names = set(self._cloudforge.resources.keys())
        desired_names = set(desired_map.keys())

        result = {
            "create": [],
            "update": [],
            "delete": [],
            "unchanged": [],
        }

        # Recursos a criar (existem no desejado, não no atual)
        for name in desired_names - current_names:
            result["create"].append(desired_map[name])

        # Recursos a deletar (existem no atual, não no desejado)
        for name in current_names - desired_names:
            current = self._resources[name]
            if current.status != "destroyed":
                result["delete"].append(current.to_dict())

        # Recursos que existem em ambos - verificar mudanças
        for name in current_names & desired_names:
            current = self._resources[name]
            desired = desired_map[name]

            # Comparar hash da config
            desired_hash = hashlib.sha256(
                json.dumps(desired.get("config", {}), sort_keys=True).encode()
            ).hexdigest()[:12]

            if current.config_hash != desired_hash:
                result["update"].append({
                    "current": current.to_dict(),
                    "desired": desired,
                })
            else:
                result["unchanged"].append(current.to_dict())

        return result

    def clear(self) -> None:
        """Limpa todo o estado."""
        self._cloudforge.resources.clear()

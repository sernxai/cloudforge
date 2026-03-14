"""
CloudForge - Parser de Configuração YAML
Lê e valida arquivos de definição de infraestrutura.
"""

import os
import yaml
import jsonschema
from typing import Any
from pathlib import Path

# Schema JSON para validação do YAML de infraestrutura
INFRASTRUCTURE_SCHEMA = {
    "type": "object",
    "required": ["project", "provider", "resources"],
    "properties": {
        "project": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string", "pattern": "^[a-z0-9-]+$"},
                "environment": {
                    "type": "string",
                    "enum": ["development", "staging", "production"],
                },
                "tags": {"type": "object"},
            },
        },
        "provider": {
            "type": "object",
            "required": ["name", "region"],
            "properties": {
                "name": {"type": "string", "enum": ["aws", "gcp", "azure"]},
                "region": {"type": "string"},
                "credentials": {"type": "object"},
            },
        },
        "resources": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type", "name", "config"],
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [
                            "vm",
                            "vpc",
                            "subnet",
                            "security_group",
                            "kubernetes",
                            "database",
                        ],
                    },
                    "name": {"type": "string", "pattern": "^[a-z0-9-]+$"},
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                    "config": {"type": "object"},
                },
            },
        },
        "deploy": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["docker"]},
                "image": {"type": "string"},
                "target": {"type": "string"},
                "replicas": {"type": "integer", "minimum": 1},
                "port": {"type": "integer"},
                "env": {"type": "object"},
            },
        },
    },
}


class ConfigError(Exception):
    """Erro de configuração."""

    pass


class Config:
    """Gerencia leitura e validação da configuração de infraestrutura."""

    def __init__(self, config_path: str = "infrastructure.yaml"):
        self.config_path = Path(config_path)
        self._data: dict[str, Any] = {}

    def load(self) -> dict[str, Any]:
        """Carrega e valida o arquivo YAML."""
        if not self.config_path.exists():
            raise ConfigError(
                f"Arquivo de configuração não encontrado: {self.config_path}"
            )

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"Erro ao parsear YAML: {e}")

        # Substituir variáveis de ambiente ${VAR_NAME}
        self._resolve_env_vars(self._data)

        # Validar contra o schema
        self._validate()

        return self._data

    def _resolve_env_vars(self, obj: Any) -> Any:
        """Substitui referências ${VAR} por variáveis de ambiente."""
        if isinstance(obj, str):
            import re

            pattern = r"\$\{([^}]+)\}"
            matches = re.findall(pattern, obj)
            for var_name in matches:
                env_value = os.environ.get(var_name, "")
                obj = obj.replace(f"${{{var_name}}}", env_value)
            return obj
        elif isinstance(obj, dict):
            for key, value in obj.items():
                obj[key] = self._resolve_env_vars(value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                obj[i] = self._resolve_env_vars(item)
        return obj

    def _validate(self) -> None:
        """Valida configuração contra o JSON Schema."""
        try:
            jsonschema.validate(instance=self._data, schema=INFRASTRUCTURE_SCHEMA)
        except jsonschema.ValidationError as e:
            raise ConfigError(f"Configuração inválida: {e.message}")

        # Validações adicionais
        self._validate_dependencies()
        self._validate_unique_names()

    def _validate_dependencies(self) -> None:
        """Verifica se todas as dependências referenciadas existem."""
        resource_names = {r["name"] for r in self._data.get("resources", [])}
        for resource in self._data.get("resources", []):
            for dep in resource.get("depends_on", []):
                if dep not in resource_names:
                    raise ConfigError(
                        f"Recurso '{resource['name']}' depende de '{dep}', "
                        f"que não existe."
                    )

    def _validate_unique_names(self) -> None:
        """Verifica se todos os nomes de recursos são únicos."""
        names = [r["name"] for r in self._data.get("resources", [])]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            raise ConfigError(
                f"Nomes de recursos duplicados: {', '.join(duplicates)}"
            )

    @property
    def project(self) -> dict:
        return self._data.get("project", {})

    @property
    def provider(self) -> dict:
        return self._data.get("provider", {})

    @property
    def resources(self) -> list[dict]:
        return self._data.get("resources", [])

    @property
    def deploy(self) -> dict | None:
        return self._data.get("deploy")

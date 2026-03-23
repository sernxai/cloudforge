"""
CloudForge - Parser de Configuração YAML
Lê e valida arquivos de definição de infraestrutura.
"""

import os
import yaml
import jsonschema
from typing import Any
from pathlib import Path

from cloudforge.core.schema import CLOUDFORGE_SCHEMA, SchemaValidator, SchemaValidationError


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
                self._data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"Erro ao parsear YAML: {e}")

        # Substituir variáveis de ambiente ${VAR_NAME}
        self._data = self._resolve_env_vars(self._data)

        # Validar contra o schema robusto
        self._validate()

        return self._data

    def _resolve_env_vars(self, obj: Any) -> Any:
        """Substitui referências ${VAR} por variáveis de ambiente ou credenciais cifradas."""
        if isinstance(obj, str):
            import re
            from cloudforge.core.auth import CredentialsManager
            
            mgr = CredentialsManager()
            # Carregar todas as credenciais em um mapa plano para busca rápida
            all_creds_map = {}
            for prov_creds in mgr.load_all().values():
                all_creds_map.update(prov_creds)

            pattern = r"\$\{([^}]+)\}"
            matches = re.findall(pattern, obj)
            for var_name in matches:
                # Prioridade: 1. Env vars, 2. Credenciais cifradas
                env_value = os.environ.get(var_name)
                if env_value is None:
                    env_value = all_creds_map.get(var_name, "")
                
                obj = obj.replace(f"${{{var_name}}}", env_value)
            return obj
        elif isinstance(obj, dict):
            return {k: self._resolve_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._resolve_env_vars(i) for i in obj]
        return obj

    def _validate(self) -> None:
        """Valida configuração contra o JSON Schema robusto."""
        validator = SchemaValidator(CLOUDFORGE_SCHEMA)
        is_valid, errors = validator.validate(self._data)

        if not is_valid:
            error_msgs = "\n  - ".join(errors)
            raise ConfigError(f"Configuração inválida:\n  - {error_msgs}")

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
    def providers(self) -> dict[str, dict]:
        """Retorna todos os providers definidos (multi-provider)."""
        # Suporte novo: bloco 'providers'
        if "providers" in self._data:
            return self._data["providers"]
        
        # Suporte legado: bloco 'provider' único
        if "provider" in self._data:
            return {"default": self._data["provider"]}
            
        return {}

    @property
    def provider(self) -> dict:
        """Retorna o provider default (para compatibilidade)."""
        return self.providers.get("default", {})

    @property
    def resources(self) -> list[dict]:
        return self._data.get("resources", [])

    def set(self, path: str, value: Any) -> None:
        """Define um valor na configuração usando um path separado por pontos."""
        # Recarregar sem var_resolve para não salvar os valores resolvidos de volta
        if not self._data:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}

        parts = path.split(".")
        current = self._data
        
        # Percorrer até o penúltimo nível
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        
        # Definir o valor no último nível
        key = parts[-1]
        
        # Tentar converter valor se for numérico ou booleano para manter tipos YAML
        if isinstance(value, str):
            if value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            elif value.isdigit():
                value = int(value)
            else:
                try:
                    value = float(value)
                except ValueError:
                    pass
        
        current[key] = value

    def save(self) -> None:
        """Salva a configuração de volta no arquivo YAML."""
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self._data, f, default_flow_style=False, allow_unicode=True)

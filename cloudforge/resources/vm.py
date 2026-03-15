"""
CloudForge - Recurso: Virtual Machine
Suporta EC2 (AWS), Compute Engine (GCP), Azure VM.
"""

from typing import Any
from cloudforge.resources.base import BaseResource, ResourceResult


class VMResource(BaseResource):
    """Gerencia máquinas virtuais em qualquer provedor."""

    RESOURCE_TYPE = "vm"

    # Mapeamento de tipos de instância entre provedores
    INSTANCE_TYPE_MAP = {
        "aws": {
            "small": "t3.small",
            "medium": "t3.medium",
            "large": "t3.large",
            "xlarge": "t3.xlarge",
        },
        "gcp": {
            "small": "e2-small",
            "medium": "e2-medium",
            "large": "e2-standard-2",
            "xlarge": "e2-standard-4",
        },
        "azure": {
            "small": "Standard_B1s",
            "medium": "Standard_B2s",
            "large": "Standard_D2s_v3",
            "xlarge": "Standard_D4s_v3",
        },
    }

    def get_defaults(self) -> dict[str, Any]:
        return {
            "instance_type": "medium",
            "disk_size_gb": 30,
            "os": "ubuntu-22.04",
            "associate_public_ip": True,
        }

    def validate(self) -> list[str]:
        errors = []
        config = {**self.get_defaults(), **self.config}

        if "instance_type" not in config:
            errors.append(f"VM '{self.name}': instance_type é obrigatório")

        disk_size = config.get("disk_size_gb", 0)
        if not isinstance(disk_size, (int, float)) or disk_size < 10:
            errors.append(f"VM '{self.name}': disk_size_gb deve ser >= 10")

        return errors

    def create(self) -> ResourceResult:
        """Cria a VM no provedor configurado."""
        provider_name = self.provider.PROVIDER_NAME if self.provider else "unknown"
        config = self.resolve_config()

        # Resolver tipo de instância para o provedor específico
        instance_type = config.get("instance_type", "medium")
        if instance_type in self.INSTANCE_TYPE_MAP.get(provider_name, {}):
            resolved_type = self.INSTANCE_TYPE_MAP[provider_name][instance_type]
        else:
            resolved_type = instance_type

        params = {
            "name": self.name,
            "instance_type": resolved_type,
            "disk_size_gb": config.get("disk_size_gb", 30),
            "image": config.get("os", "ubuntu-22.04"),
            "associate_public_ip": config.get("associate_public_ip", True),
            "subnet": config.get("subnet"),
            "security_group": config.get("security_group"),
            "key_pair": config.get("key_pair"),
            "user_data": config.get("user_data"),
            "tags": config.get("tags", {}),
        }

        return self.provider.create_resource("vm", params)

    def update(self, changes: dict[str, Any]) -> ResourceResult:
        config = self.resolve_config()
        return self.provider.update_resource("vm", self.name, config, changes)

    def delete(self, provider_id: str) -> ResourceResult:
        return self.provider.delete_resource("vm", provider_id)

    def get_status(self, provider_id: str) -> dict[str, Any]:
        return self.provider.get_resource_status("vm", provider_id)

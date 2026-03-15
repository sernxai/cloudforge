"""
CloudForge - Recurso: Kubernetes
Suporta EKS (AWS), GKE (GCP), AKS (Azure).
"""

from typing import Any
from cloudforge.resources.base import BaseResource, ResourceResult


class KubernetesResource(BaseResource):
    """Gerencia clusters Kubernetes gerenciados."""

    RESOURCE_TYPE = "kubernetes"

    NODE_TYPE_MAP = {
        "aws": {
            "small": "t3.small",
            "medium": "t3.medium",
            "large": "t3.large",
            "xlarge": "m5.xlarge",
        },
        "gcp": {
            "small": "e2-small",
            "medium": "e2-medium",
            "large": "e2-standard-2",
            "xlarge": "e2-standard-4",
        },
        "azure": {
            "small": "Standard_B2s",
            "medium": "Standard_D2s_v3",
            "large": "Standard_D4s_v3",
            "xlarge": "Standard_D8s_v3",
        },
    }

    def get_defaults(self) -> dict[str, Any]:
        return {
            "node_count": 3,
            "node_type": "medium",
            "kubernetes_version": "1.29",
            "min_nodes": 1,
            "max_nodes": 10,
            "auto_scaling": True,
            "disk_size_gb": 50,
        }

    def validate(self) -> list[str]:
        errors = []
        config = {**self.get_defaults(), **self.config}

        node_count = config.get("node_count", 0)
        if not isinstance(node_count, int) or node_count < 1:
            errors.append(
                f"Kubernetes '{self.name}': node_count deve ser >= 1"
            )

        min_nodes = config.get("min_nodes", 1)
        max_nodes = config.get("max_nodes", 10)
        if min_nodes > max_nodes:
            errors.append(
                f"Kubernetes '{self.name}': min_nodes ({min_nodes}) > "
                f"max_nodes ({max_nodes})"
            )

        if node_count < min_nodes or node_count > max_nodes:
            errors.append(
                f"Kubernetes '{self.name}': node_count ({node_count}) fora "
                f"do range [{min_nodes}, {max_nodes}]"
            )

        return errors

    def create(self) -> ResourceResult:
        provider_name = self.provider.PROVIDER_NAME if self.provider else "unknown"
        config = self.resolve_config()

        node_type = config.get("node_type", "medium")
        if node_type in self.NODE_TYPE_MAP.get(provider_name, {}):
            resolved_type = self.NODE_TYPE_MAP[provider_name][node_type]
        else:
            resolved_type = node_type

        params = {
            "name": self.name,
            "node_count": config["node_count"],
            "node_type": resolved_type,
            "kubernetes_version": config.get("kubernetes_version", "1.29"),
            "min_nodes": config.get("min_nodes", 1),
            "max_nodes": config.get("max_nodes", 10),
            "auto_scaling": config.get("auto_scaling", True),
            "disk_size_gb": config.get("disk_size_gb", 50),
            "subnet": config.get("subnet"),
            "vpc": config.get("vpc"),
            "tags": config.get("tags", {}),
        }

        return self.provider.create_resource("kubernetes", params)

    def update(self, changes: dict[str, Any]) -> ResourceResult:
        config = self.resolve_config()
        return self.provider.update_resource("kubernetes", self.name, config, changes)

    def delete(self, provider_id: str) -> ResourceResult:
        return self.provider.delete_resource("kubernetes", provider_id)

    def get_status(self, provider_id: str) -> dict[str, Any]:
        return self.provider.get_resource_status("kubernetes", provider_id)

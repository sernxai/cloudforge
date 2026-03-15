"""
CloudForge - Recurso: Cloud Run
Serviço serverless para containers no Google Cloud Platform.
"""

from typing import Any
from resources.base import BaseResource, ResourceResult


class CloudRunResource(BaseResource):
    """Gerencia serviços Cloud Run no GCP."""

    RESOURCE_TYPE = "cloud_run"

    def get_defaults(self) -> dict[str, Any]:
        return {
            "cpu": "1",
            "memory": "512Mi",
            "min_instances": 0,
            "max_instances": 100,
            "concurrency": 80,
            "timeout_seconds": 300,
            "port": 8080,
            "allow_unauthenticated": True,
            "ingress": "all",               # all | internal | internal-and-cloud-load-balancing
            "execution_environment": "gen2", # gen1 | gen2
            "cpu_boost": True,
            "session_affinity": False,
        }

    def validate(self) -> list[str]:
        errors = []
        config = {**self.get_defaults(), **self.config}

        if not config.get("image"):
            errors.append(
                f"CloudRun '{self.name}': 'image' é obrigatório "
                f"(ex: gcr.io/projeto/app:latest)"
            )

        cpu = config.get("cpu", "1")
        valid_cpus = ["1", "2", "4", "8", 1, 2, 4, 8]
        if cpu not in valid_cpus:
            errors.append(
                f"CloudRun '{self.name}': cpu deve ser 1, 2, 4 ou 8"
            )

        memory = config.get("memory", "")
        if isinstance(memory, str) and not (
            memory.endswith("Mi") or memory.endswith("Gi")
        ):
            errors.append(
                f"CloudRun '{self.name}': memory deve terminar em Mi ou Gi "
                f"(ex: 512Mi, 2Gi)"
            )

        min_inst = config.get("min_instances", 0)
        max_inst = config.get("max_instances", 100)
        if min_inst < 0:
            errors.append(
                f"CloudRun '{self.name}': min_instances deve ser >= 0"
            )
        if max_inst < 1:
            errors.append(
                f"CloudRun '{self.name}': max_instances deve ser >= 1"
            )
        if min_inst > max_inst:
            errors.append(
                f"CloudRun '{self.name}': min_instances ({min_inst}) "
                f"> max_instances ({max_inst})"
            )

        timeout = config.get("timeout_seconds", 300)
        if timeout < 1 or timeout > 3600:
            errors.append(
                f"CloudRun '{self.name}': timeout_seconds deve ser entre 1 e 3600"
            )

        ingress = config.get("ingress", "all")
        valid_ingress = ["all", "internal", "internal-and-cloud-load-balancing"]
        if ingress not in valid_ingress:
            errors.append(
                f"CloudRun '{self.name}': ingress deve ser: {', '.join(valid_ingress)}"
            )

        return errors

    def create(self) -> ResourceResult:
        config = self.resolve_config()
        params = {
            "name": self.name,
            "image": config["image"],
            "cpu": str(config.get("cpu", "1")),
            "memory": config.get("memory", "512Mi"),
            "min_instances": config.get("min_instances", 0),
            "max_instances": config.get("max_instances", 100),
            "concurrency": config.get("concurrency", 80),
            "timeout_seconds": config.get("timeout_seconds", 300),
            "port": config.get("port", 8080),
            "allow_unauthenticated": config.get("allow_unauthenticated", True),
            "ingress": config.get("ingress", "all"),
            "execution_environment": config.get("execution_environment", "gen2"),
            "cpu_boost": config.get("cpu_boost", True),
            "session_affinity": config.get("session_affinity", False),
            "env": config.get("env", {}),
            "secrets": config.get("secrets", {}),
            "vpc_connector": config.get("vpc_connector"),
            "service_account": config.get("service_account"),
            "labels": config.get("labels", {}),
            "tags": config.get("tags", {}),
        }
        return self.provider.create_resource("cloud_run", params)

    def update(self, changes: dict[str, Any]) -> ResourceResult:
        config = self.resolve_config()
        return self.provider.update_resource("cloud_run", self.name, config, changes)

    def delete(self, provider_id: str) -> ResourceResult:
        return self.provider.delete_resource("cloud_run", provider_id)

    def get_status(self, provider_id: str) -> dict[str, Any]:
        return self.provider.get_resource_status("cloud_run", provider_id)

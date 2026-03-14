"""
CloudForge - Recurso: Banco de Dados Gerenciado
Suporta RDS (AWS), Cloud SQL (GCP), Azure Database.
"""

from typing import Any
from resources.base import BaseResource, ResourceResult


class DatabaseResource(BaseResource):
    """Gerencia bancos de dados gerenciados."""

    RESOURCE_TYPE = "database"

    SUPPORTED_ENGINES = ["postgresql", "mysql", "mariadb", "sqlserver"]

    INSTANCE_TYPE_MAP = {
        "aws": {
            "small": "db.t3.small",
            "medium": "db.t3.medium",
            "large": "db.r5.large",
            "xlarge": "db.r5.xlarge",
        },
        "gcp": {
            "small": "db-f1-micro",
            "medium": "db-custom-2-7680",
            "large": "db-custom-4-15360",
            "xlarge": "db-custom-8-30720",
        },
        "azure": {
            "small": "B_Standard_B1ms",
            "medium": "GP_Standard_D2ds_v4",
            "large": "GP_Standard_D4ds_v4",
            "xlarge": "GP_Standard_D8ds_v4",
        },
    }

    def get_defaults(self) -> dict[str, Any]:
        return {
            "engine": "postgresql",
            "version": "15",
            "instance_type": "medium",
            "storage_gb": 50,
            "multi_az": False,
            "backup_retention_days": 7,
            "publicly_accessible": False,
            "storage_encrypted": True,
        }

    def validate(self) -> list[str]:
        errors = []
        config = {**self.get_defaults(), **self.config}

        engine = config.get("engine", "")
        if engine not in self.SUPPORTED_ENGINES:
            errors.append(
                f"Database '{self.name}': engine '{engine}' não suportado. "
                f"Use: {', '.join(self.SUPPORTED_ENGINES)}"
            )

        storage = config.get("storage_gb", 0)
        if not isinstance(storage, (int, float)) or storage < 20:
            errors.append(
                f"Database '{self.name}': storage_gb deve ser >= 20"
            )

        retention = config.get("backup_retention_days", 0)
        if not isinstance(retention, int) or retention < 0 or retention > 35:
            errors.append(
                f"Database '{self.name}': backup_retention_days "
                f"deve ser entre 0 e 35"
            )

        return errors

    def create(self) -> ResourceResult:
        provider_name = self.provider.PROVIDER_NAME if self.provider else "unknown"
        config = self.resolve_config()

        instance_type = config.get("instance_type", "medium")
        if instance_type in self.INSTANCE_TYPE_MAP.get(provider_name, {}):
            resolved_type = self.INSTANCE_TYPE_MAP[provider_name][instance_type]
        else:
            resolved_type = instance_type

        params = {
            "name": self.name,
            "engine": config["engine"],
            "version": config.get("version", "15"),
            "instance_type": resolved_type,
            "storage_gb": config.get("storage_gb", 50),
            "multi_az": config.get("multi_az", False),
            "backup_retention_days": config.get("backup_retention_days", 7),
            "publicly_accessible": config.get("publicly_accessible", False),
            "storage_encrypted": config.get("storage_encrypted", True),
            "vpc": config.get("vpc"),
            "subnet": config.get("subnet"),
            "security_group": config.get("security_group"),
            "master_username": config.get("master_username", "admin"),
            "database_name": config.get("database_name", self.name.replace("-", "_")),
            "tags": config.get("tags", {}),
        }

        return self.provider.create_resource("database", params)

    def update(self, changes: dict[str, Any]) -> ResourceResult:
        config = self.resolve_config()
        return self.provider.update_resource("database", self.name, config, changes)

    def delete(self, provider_id: str) -> ResourceResult:
        return self.provider.delete_resource("database", provider_id)

    def get_status(self, provider_id: str) -> dict[str, Any]:
        return self.provider.get_resource_status("database", provider_id)

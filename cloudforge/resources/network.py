"""
CloudForge - Recursos de Rede
VPC, Subnet, Security Group / Firewall.
"""

from typing import Any
from cloudforge.resources.base import BaseResource, ResourceResult


class VPCResource(BaseResource):
    """Gerencia VPCs / Virtual Networks."""

    RESOURCE_TYPE = "vpc"

    def get_defaults(self) -> dict[str, Any]:
        return {
            "cidr_block": "10.0.0.0/16",
            "enable_dns_support": True,
            "enable_dns_hostnames": True,
        }

    def validate(self) -> list[str]:
        errors = []
        config = {**self.get_defaults(), **self.config}

        cidr = config.get("cidr_block", "")
        if not cidr or "/" not in cidr:
            errors.append(f"VPC '{self.name}': cidr_block inválido: '{cidr}'")

        return errors

    def create(self) -> ResourceResult:
        config = self.resolve_config()
        params = {
            "name": self.name,
            "cidr_block": config["cidr_block"],
            "enable_dns_support": config.get("enable_dns_support", True),
            "enable_dns_hostnames": config.get("enable_dns_hostnames", True),
            "tags": config.get("tags", {}),
        }
        return self.provider.create_resource("vpc", params)

    def update(self, changes: dict[str, Any]) -> ResourceResult:
        config = self.resolve_config()
        return self.provider.update_resource("vpc", self.name, config, changes)

    def delete(self, provider_id: str) -> ResourceResult:
        return self.provider.delete_resource("vpc", provider_id)

    def get_status(self, provider_id: str) -> dict[str, Any]:
        return self.provider.get_resource_status("vpc", provider_id)


class SubnetResource(BaseResource):
    """Gerencia Subnets."""

    RESOURCE_TYPE = "subnet"

    def get_defaults(self) -> dict[str, Any]:
        return {
            "public": False,
        }

    def validate(self) -> list[str]:
        errors = []
        config = {**self.get_defaults(), **self.config}

        if not config.get("cidr_block"):
            errors.append(f"Subnet '{self.name}': cidr_block é obrigatório")
        if not config.get("vpc"):
            errors.append(f"Subnet '{self.name}': vpc é obrigatório")

        return errors

    def create(self) -> ResourceResult:
        config = self.resolve_config()
        params = {
            "name": self.name,
            "vpc": config["vpc"],
            "cidr_block": config["cidr_block"],
            "availability_zone": config.get("availability_zone"),
            "public": config.get("public", False),
            "tags": config.get("tags", {}),
        }
        return self.provider.create_resource("subnet", params)

    def update(self, changes: dict[str, Any]) -> ResourceResult:
        config = self.resolve_config()
        return self.provider.update_resource("subnet", self.name, config, changes)

    def delete(self, provider_id: str) -> ResourceResult:
        return self.provider.delete_resource("subnet", provider_id)

    def get_status(self, provider_id: str) -> dict[str, Any]:
        return self.provider.get_resource_status("subnet", provider_id)


class SecurityGroupResource(BaseResource):
    """Gerencia Security Groups / Firewalls."""

    RESOURCE_TYPE = "security_group"

    def get_defaults(self) -> dict[str, Any]:
        return {
            "ingress": [],
            "egress": [{"protocol": "-1", "cidr": "0.0.0.0/0"}],
        }

    def validate(self) -> list[str]:
        errors = []
        config = {**self.get_defaults(), **self.config}

        if not config.get("vpc"):
            errors.append(
                f"SecurityGroup '{self.name}': vpc é obrigatório"
            )

        for i, rule in enumerate(config.get("ingress", [])):
            if "port" not in rule and "port_range" not in rule:
                errors.append(
                    f"SecurityGroup '{self.name}': regra ingress [{i}] "
                    f"precisa de 'port' ou 'port_range'"
                )

        return errors

    def create(self) -> ResourceResult:
        config = self.resolve_config()
        params = {
            "name": self.name,
            "vpc": config.get("vpc"),
            "description": config.get("description", f"SG for {self.name}"),
            "ingress": config.get("ingress", []),
            "egress": config.get("egress", []),
            "tags": config.get("tags", {}),
        }
        return self.provider.create_resource("security_group", params)

    def update(self, changes: dict[str, Any]) -> ResourceResult:
        config = self.resolve_config()
        return self.provider.update_resource(
            "security_group", self.name, config, changes
        )

    def delete(self, provider_id: str) -> ResourceResult:
        return self.provider.delete_resource("security_group", provider_id)

    def get_status(self, provider_id: str) -> dict[str, Any]:
        return self.provider.get_resource_status("security_group", provider_id)

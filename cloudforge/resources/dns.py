"""
CloudForge - Recurso: DNS Records
Gerencia registros DNS em provedores como GoDaddy, Cloudflare, Route53.
"""

from typing import Any
from cloudforge.resources.base import BaseResource, ResourceResult


class DNSRecordResource(BaseResource):
    """Gerencia registros DNS (CNAME, A, TXT, MX, etc)."""

    RESOURCE_TYPE = "dns_record"

    VALID_RECORD_TYPES = ["A", "AAAA", "CNAME", "MX", "TXT", "NS", "SRV", "CAA"]

    def get_defaults(self) -> dict[str, Any]:
        return {
            "ttl": 3600,
            "record_type": "CNAME",
        }

    def validate(self) -> list[str]:
        errors = []
        config = {**self.get_defaults(), **self.config}

        if not config.get("domain"):
            errors.append(
                f"DNS '{self.name}': 'domain' é obrigatório "
                f"(ex: meudominio.com.br)"
            )

        if not config.get("record_name"):
            errors.append(
                f"DNS '{self.name}': 'record_name' é obrigatório "
                f"(ex: app, www, @)"
            )

        if not config.get("record_value"):
            errors.append(
                f"DNS '{self.name}': 'record_value' é obrigatório "
                f"(ex: ghs.googlehosted.com para Firebase)"
            )

        record_type = config.get("record_type", "CNAME")
        if record_type not in self.VALID_RECORD_TYPES:
            errors.append(
                f"DNS '{self.name}': record_type '{record_type}' inválido. "
                f"Use: {', '.join(self.VALID_RECORD_TYPES)}"
            )

        ttl = config.get("ttl", 3600)
        if not isinstance(ttl, int) or ttl < 600:
            errors.append(
                f"DNS '{self.name}': ttl deve ser inteiro >= 600"
            )

        # Validação específica por tipo
        if record_type == "CNAME" and config.get("record_name") == "@":
            errors.append(
                f"DNS '{self.name}': CNAME não pode ser usado na raiz (@). "
                f"Use registro A ou ALIAS."
            )

        if record_type == "MX":
            if not config.get("priority"):
                errors.append(
                    f"DNS '{self.name}': registros MX precisam de 'priority'"
                )

        return errors

    def create(self) -> ResourceResult:
        config = self.resolve_config()
        params = {
            "name": self.name,
            "domain": config["domain"],
            "record_name": config["record_name"],
            "record_type": config.get("record_type", "CNAME"),
            "record_value": config["record_value"],
            "ttl": config.get("ttl", 3600),
            "priority": config.get("priority"),
            "tags": config.get("tags", {}),
        }
        return self.provider.create_resource("dns_record", params)

    def update(self, changes: dict[str, Any]) -> ResourceResult:
        config = self.resolve_config()
        return self.provider.update_resource("dns_record", self.name, config, changes)

    def delete(self, provider_id: str) -> ResourceResult:
        return self.provider.delete_resource("dns_record", provider_id)

    def get_status(self, provider_id: str) -> dict[str, Any]:
        return self.provider.get_resource_status("dns_record", provider_id)

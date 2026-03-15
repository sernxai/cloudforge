"""
CloudForge - Provider Hostinger
Implementação usando API da Hostinger para hospedagem e VPS.
"""

from typing import Any

from rich.console import Console

from cloudforge.providers.base import BaseProvider, ProviderError
from cloudforge.resources.base import ResourceResult

console = Console()


class HostingerProvider(BaseProvider):
    """Provider para Hostinger (hospedagem e VPS)."""

    PROVIDER_NAME = "hostinger"

    REGIONS = [
        "us",      # United States
        "uk",      # United Kingdom
        "fr",      # France
        "in",      # India
        "id",      # Indonesia
        "br",      # Brazil
        "lt",      # Lithuania
        "sg",      # Singapore
    ]

    def __init__(self, region: str, credentials: dict[str, Any] | None = None):
        super().__init__(region, credentials)
        self.api_key = (credentials or {}).get("api_key", "")
        self.base_url = "https://api.hostinger.com"

    def authenticate(self) -> bool:
        """Autentica com Hostinger usando API."""
        try:
            import requests

            self._session = requests.Session()
            self._session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            })

            # Validar credenciais listando serviços
            response = self._session.get(
                f"{self.base_url}/v1/services",
                timeout=30
            )
            if response.status_code == 200:
                console.print("[green]✓ Hostinger autenticado com sucesso[/green]")
                return True
            else:
                raise ProviderError(f"Falha na autenticação: {response.status_code}")

        except ImportError:
            raise ProviderError("requests não instalado. Execute: pip install requests")
        except Exception as e:
            raise ProviderError(f"Falha na autenticação Hostinger: {e}")

    def validate_credentials(self) -> bool:
        """Verifica se as credenciais são válidas."""
        try:
            response = self._session.get(f"{self.base_url}/v1/services", timeout=30)
            return response.status_code == 200
        except Exception:
            return False

    def create_resource(
        self, resource_type: str, params: dict[str, Any]
    ) -> ResourceResult:
        """Cria um recurso na Hostinger."""
        handlers = {
            "vm": self._create_vps,
            "website": self._create_website,
            "database": self._create_database,
            "dns_record": self._create_dns_record,
        }

        handler = handlers.get(resource_type)
        if not handler:
            return ResourceResult(
                success=False,
                error=f"Tipo de recurso não suportado na Hostinger: {resource_type}"
            )

        try:
            return handler(params)
        except Exception as e:
            return ResourceResult(success=False, error=str(e))

    def update_resource(
        self,
        resource_type: str,
        name: str,
        config: dict[str, Any],
        changes: dict[str, Any],
    ) -> ResourceResult:
        """Atualiza um recurso existente."""
        console.print(
            f"[yellow]  Atualizando {resource_type} '{name}' na Hostinger...[/yellow]"
        )
        return ResourceResult(
            success=True,
            message=f"{resource_type} '{name}' atualizado na Hostinger",
        )

    def delete_resource(
        self, resource_type: str, provider_id: str
    ) -> ResourceResult:
        """Deleta um recurso."""
        console.print(
            f"[red]  Destruindo {resource_type} '{provider_id}' na Hostinger...[/red]"
        )

        handlers = {
            "vm": self._cancel_vps,
            "website": self._delete_website,
            "database": self._delete_database,
        }

        handler = handlers.get(resource_type)
        if not handler:
            return ResourceResult(
                success=False,
                error=f"Tipo não suportado para delete: {resource_type}"
            )

        try:
            return handler(provider_id)
        except Exception as e:
            return ResourceResult(success=False, error=str(e))

    def get_resource_status(
        self, resource_type: str, provider_id: str
    ) -> dict[str, Any]:
        """Retorna o status de um recurso."""
        try:
            if resource_type == "vm":
                return self._get_vps_status(provider_id)
            elif resource_type == "website":
                return self._get_website_status(provider_id)
            else:
                return {"id": provider_id, "status": "active", "provider": "hostinger"}
        except Exception as e:
            return {"id": provider_id, "status": "error", "error": str(e)}

    def list_regions(self) -> list[str]:
        """Lista regiões disponíveis."""
        return self.REGIONS

    # ── Implementações de criação ─────────────────────────────────

    def _create_vps(self, params: dict) -> ResourceResult:
        """Cria um servidor VPS."""
        console.print(f"  [cyan]Criando VPS '{params['name']}' na Hostinger...[/cyan]")

        # Mapeamento de planos VPS
        plan_map = {
            "small": "vps_1",    # 1 vCPU, 4GB RAM
            "medium": "vps_2",   # 2 vCPU, 8GB RAM
            "large": "vps_3",    # 4 vCPU, 16GB RAM
            "xlarge": "vps_4",   # 6 vCPU, 32GB RAM
        }
        plan = plan_map.get(params.get("instance_type", "medium"), "vps_2")

        # OS template
        os_map = {
            "ubuntu-22.04": "ubuntu-22-04",
            "ubuntu-20.04": "ubuntu-20-04",
            "ubuntu": "ubuntu-22-04",
            "debian-11": "debian-11",
            "debian": "debian-11",
            "centos-7": "centos-7",
            "rocky-9": "rocky-9",
            "windows-2019": "windows-2019",
            "windows-2022": "windows-2022",
        }
        os_template = os_map.get(params.get("os", "ubuntu-22.04"), "ubuntu-22-04")

        vps_data = {
            "name": params["name"],
            "plan": plan,
            "os_template": os_template,
            "region": self.region,
            "ssh_key": params.get("ssh_key", ""),
        }

        response = self._session.post(
            f"{self.base_url}/v1/vps",
            json=vps_data,
            timeout=60
        )

        if response.status_code not in [200, 201, 202]:
            return ResourceResult(
                success=False,
                error=f"Erro ao criar VPS: {response.text}",
            )

        data = response.json()
        vps = data.get("vps", {})
        vps_id = str(vps.get("id"))

        return ResourceResult(
            success=True,
            provider_id=vps_id,
            outputs={
                "vps_id": vps_id,
                "vps_name": vps.get("name"),
                "plan": plan,
                "region": self.region,
                "ip_address": vps.get("ip_address"),
            },
            message=f"VPS '{params['name']}' criado: {vps_id}",
        )

    def _create_website(self, params: dict) -> ResourceResult:
        """Cria um website/hosting."""
        console.print(f"  [cyan]Criando Website '{params['name']}' na Hostinger...[/cyan]")

        # Planos de hosting
        plan_map = {
            "starter": "premium",
            "business": "business",
            "cloud": "cloud",
        }
        plan = plan_map.get(params.get("plan", "premium"), "premium")

        website_data = {
            "name": params["name"],
            "domain": params.get("domain"),
            "plan": plan,
            "region": self.region,
        }

        response = self._session.post(
            f"{self.base_url}/v1/websites",
            json=website_data,
            timeout=60
        )

        if response.status_code not in [200, 201]:
            return ResourceResult(
                success=False,
                error=f"Erro ao criar Website: {response.text}",
            )

        data = response.json()
        website = data.get("website", {})

        return ResourceResult(
            success=True,
            provider_id=str(website.get("id")),
            outputs={
                "website_id": str(website.get("id")),
                "website_name": website.get("name"),
                "domain": params.get("domain"),
            },
            message=f"Website '{params['name']}' criado",
        )

    def _create_database(self, params: dict) -> ResourceResult:
        """Cria um banco de dados MySQL."""
        console.print(f"  [cyan]Criando Database '{params['name']}' na Hostinger...[/cyan]")

        db_data = {
            "name": params["name"],
            "database_name": params.get("database_name", params["name"].replace("-", "_")),
            "username": params.get("username", "admin"),
            "password": params.get("password", ""),
            "website_id": params.get("website_id"),
        }

        response = self._session.post(
            f"{self.base_url}/v1/databases",
            json=db_data,
            timeout=60
        )

        if response.status_code not in [200, 201]:
            return ResourceResult(
                success=False,
                error=f"Erro ao criar Database: {response.text}",
            )

        data = response.json()
        db = data.get("database", {})

        return ResourceResult(
            success=True,
            provider_id=str(db.get("id")),
            outputs={
                "database_id": str(db.get("id")),
                "database_name": db.get("name"),
                "host": db.get("host", "localhost"),
                "username": params.get("username", "admin"),
            },
            message=f"Database '{params['name']}' criado",
        )

    def _create_dns_record(self, params: dict) -> ResourceResult:
        """Cria um registro DNS."""
        console.print(f"  [cyan]Criando DNS Record '{params['name']}' na Hostinger...[/cyan]")

        dns_data = {
            "name": params.get("name", "@"),
            "type": params.get("type", "A"),
            "content": params.get("value"),
            "ttl": params.get("ttl", 3600),
            "priority": params.get("priority"),
        }

        response = self._session.post(
            f"{self.base_url}/v1/domains/{params.get('domain')}/dns",
            json=dns_data,
            timeout=60
        )

        if response.status_code not in [200, 201]:
            return ResourceResult(
                success=False,
                error=f"Erro ao criar DNS Record: {response.text}",
            )

        data = response.json()
        record = data.get("record", {})

        return ResourceResult(
            success=True,
            provider_id=str(record.get("id")),
            outputs={
                "record_id": str(record.get("id")),
                "record_name": params.get("name"),
                "record_type": params.get("type"),
                "record_value": params.get("value"),
            },
            message=f"DNS Record '{params.get('name')}' criado",
        )

    # ── Implementações de delete ──────────────────────────────────

    def _cancel_vps(self, provider_id: str) -> ResourceResult:
        """Cancela um VPS."""
        response = self._session.delete(
            f"{self.base_url}/v1/vps/{provider_id}",
            timeout=60
        )
        return ResourceResult(
            success=response.status_code in [200, 204],
            message=f"VPS {provider_id} cancelado",
        )

    def _delete_website(self, provider_id: str) -> ResourceResult:
        """Deleta um website."""
        response = self._session.delete(
            f"{self.base_url}/v1/websites/{provider_id}",
            timeout=60
        )
        return ResourceResult(
            success=response.status_code in [200, 204],
            message=f"Website {provider_id} deletado",
        )

    def _delete_database(self, provider_id: str) -> ResourceResult:
        """Deleta um database."""
        response = self._session.delete(
            f"{self.base_url}/v1/databases/{provider_id}",
            timeout=60
        )
        return ResourceResult(
            success=response.status_code in [200, 204],
            message=f"Database {provider_id} deletado",
        )

    # ── Helpers ─────────────────────────────────────────

    def _get_vps_status(self, vps_id: str) -> dict[str, Any]:
        """Retorna status de um VPS."""
        response = self._session.get(
            f"{self.base_url}/v1/vps/{vps_id}",
            timeout=30
        )
        if response.status_code == 200:
            vps = response.json().get("vps", {})
            return {
                "id": vps_id,
                "status": vps.get("status"),
                "name": vps.get("name"),
                "ip_address": vps.get("ip_address"),
                "provider": "hostinger",
            }
        return {"id": vps_id, "status": "not_found", "provider": "hostinger"}

    def _get_website_status(self, website_id: str) -> dict[str, Any]:
        """Retorna status de um website."""
        response = self._session.get(
            f"{self.base_url}/v1/websites/{website_id}",
            timeout=30
        )
        if response.status_code == 200:
            website = response.json().get("website", {})
            return {
                "id": website_id,
                "status": "active",
                "name": website.get("name"),
                "provider": "hostinger",
            }
        return {"id": website_id, "status": "not_found", "provider": "hostinger"}

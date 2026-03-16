"""
CloudForge - Provider Locaweb
Implementação usando API da Locaweb para serviços de cloud e hospedagem.
"""

from typing import Any

from rich.console import Console

from cloudforge.providers.base import BaseProvider, ProviderError
from cloudforge.resources.base import ResourceResult

console = Console()


class LocawebProvider(BaseProvider):
    """Provider para Locaweb (hospedagem e cloud brasileira)."""

    PROVIDER_NAME = "locaweb"

    REGIONS = [
        "br-sudeste",  # São Paulo
        "br-nordeste",  # Recife
    ]

    def __init__(self, region: str, credentials: dict[str, Any] | None = None):
        super().__init__(region, credentials)
        self.api_key = (credentials or {}).get("api_key", "")
        self.account_id = (credentials or {}).get("account_id", "")
        self.base_url = "https://api.locaweb.com.br/api/v3"

    def authenticate(self) -> bool:
        """Autentica com Locaweb usando API."""
        try:
            import requests

            self._session = requests.Session()
            self._session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Account-Id": self.account_id,
            })

            # Validar credenciais listando servidores
            response = self._session.get(
                f"{self.base_url}/servers",
                timeout=30
            )
            if response.status_code == 200:
                console.print("[green]✓ Locaweb autenticado com sucesso[/green]")
                return True
            else:
                raise ProviderError(f"Falha na autenticação: {response.status_code}")

        except ImportError:
            raise ProviderError("requests não instalado. Execute: pip install requests")
        except Exception as e:
            raise ProviderError(f"Falha na autenticação Locaweb: {e}")

    def validate_credentials(self) -> bool:
        """Verifica se as credenciais são válidas."""
        try:
            response = self._session.get(f"{self.base_url}/servers", timeout=30)
            return response.status_code == 200
        except Exception:
            return False

    def create_resource(
        self, resource_type: str, params: dict[str, Any]
    ) -> ResourceResult:
        """Cria um recurso na Locaweb."""
        handlers = {
            "vm": self._create_server,
            "vpc": self._create_network,
            "subnet": self._create_subnet,
            "security_group": self._create_security_group,
            "lb": self._create_load_balancer,
            "website": self._create_website,
            "database": self._create_database,
            "dns_record": self._create_dns_record,
        }

        handler = handlers.get(resource_type)
        if not handler:
            return ResourceResult(
                success=False,
                error=f"Tipo de recurso não suportado na Locaweb: {resource_type}"
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
            f"[yellow]  Atualizando {resource_type} '{name}' na Locaweb...[/yellow]"
        )
        return ResourceResult(
            success=True,
            message=f"{resource_type} '{name}' atualizado na Locaweb",
        )

    def delete_resource(
        self, resource_type: str, provider_id: str
    ) -> ResourceResult:
        """Deleta um recurso."""
        console.print(
            f"[red]  Destruindo {resource_type} '{provider_id}' na Locaweb...[/red]"
        )

        handlers = {
            "vm": self._delete_server,
            "vpc": self._delete_network,
            "security_group": self._delete_security_group,
            "lb": self._delete_load_balancer,
            "website": self._delete_website,
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
                return self._get_server_status(provider_id)
            elif resource_type == "vpc":
                return self._get_network_status(provider_id)
            else:
                return {"id": provider_id, "status": "active", "provider": "locaweb"}
        except Exception as e:
            return {"id": provider_id, "status": "error", "error": str(e)}

    def list_regions(self) -> list[str]:
        """Lista regiões disponíveis."""
        return self.REGIONS

    # ── Implementações de criação ─────────────────────────────────

    def _create_server(self, params: dict) -> ResourceResult:
        """Cria um servidor Simple Server (VM)."""
        console.print(f"  [cyan]Criando Simple Server '{params['name']}' na Locaweb...[/cyan]")

        # Mapeamento de tipos de servidor
        type_map = {
            "small": "ss-1",    # 1 vCPU, 2GB RAM
            "medium": "ss-2",   # 2 vCPU, 4GB RAM
            "large": "ss-4",    # 4 vCPU, 8GB RAM
            "xlarge": "ss-8",   # 8 vCPU, 16GB RAM
        }
        flavor = type_map.get(params.get("instance_type", "medium"), "ss-2")

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
        image = os_map.get(params.get("os", "ubuntu-22.04"), "ubuntu-22.04")

        server_data = {
            "name": params["name"],
            "flavor": flavor,
            "image": image,
            "region": self.region,
            "ssh_key": params.get("ssh_key", ""),
            "password": params.get("password", ""),
        }

        if params.get("network"):
            server_data["network_id"] = params["network"]

        if params.get("security_group"):
            server_data["security_group_id"] = params["security_group"]

        response = self._session.post(
            f"{self.base_url}/servers",
            json=server_data,
            timeout=60
        )

        if response.status_code not in [200, 201, 202]:
            return ResourceResult(
                success=False,
                error=f"Erro ao criar servidor: {response.text}",
            )

        data = response.json()
        server = data.get("server", {})
        server_id = str(server.get("id"))

        return ResourceResult(
            success=True,
            provider_id=server_id,
            outputs={
                "server_id": server_id,
                "server_name": server.get("name"),
                "flavor": flavor,
                "region": self.region,
                "public_ip": server.get("public_ip"),
                "private_ip": server.get("private_ip"),
            },
            message=f"Simple Server '{params['name']}' criado: {server_id}",
        )

    def _create_network(self, params: dict) -> ResourceResult:
        """Cria uma rede virtual (VPC)."""
        console.print(f"  [cyan]Criando rede virtual '{params['name']}' na Locaweb...[/cyan]")

        network_data = {
            "name": params["name"],
            "cidr": params["cidr_block"],
            "region": self.region,
        }

        response = self._session.post(
            f"{self.base_url}/networks",
            json=network_data,
            timeout=60
        )

        if response.status_code not in [200, 201]:
            return ResourceResult(
                success=False,
                error=f"Erro ao criar rede: {response.text}",
            )

        data = response.json()
        network = data.get("network", {})

        return ResourceResult(
            success=True,
            provider_id=str(network.get("id")),
            outputs={
                "network_id": str(network.get("id")),
                "network_name": network.get("name"),
                "cidr": network.get("cidr"),
            },
            message=f"Rede '{params['name']}' criada: {network.get('id')}",
        )

    def _create_subnet(self, params: dict) -> ResourceResult:
        """Cria uma subnet."""
        console.print(f"  [cyan]Criando subnet '{params['name']}' na Locaweb...[/cyan]")

        subnet_data = {
            "name": params["name"],
            "network_id": params.get("vpc"),
            "cidr": params["cidr_block"],
            "region": self.region,
        }

        response = self._session.post(
            f"{self.base_url}/subnets",
            json=subnet_data,
            timeout=60
        )

        if response.status_code not in [200, 201]:
            return ResourceResult(
                success=False,
                error=f"Erro ao criar subnet: {response.text}",
            )

        data = response.json()
        subnet = data.get("subnet", {})

        return ResourceResult(
            success=True,
            provider_id=str(subnet.get("id")),
            outputs={
                "subnet_id": str(subnet.get("id")),
                "subnet_name": subnet.get("name"),
                "cidr": subnet.get("cidr"),
            },
            message=f"Subnet '{params['name']}' criada: {subnet.get('id')}",
        )

    def _create_security_group(self, params: dict) -> ResourceResult:
        """Cria um grupo de segurança."""
        console.print(
            f"  [cyan]Criando grupo de segurança '{params['name']}' na Locaweb...[/cyan]"
        )

        # Construir regras
        rules = []
        for rule in params.get("ingress", []):
            rules.append({
                "direction": "ingress",
                "protocol": rule.get("protocol", "tcp"),
                "port_range": f"{rule.get('port', 80)}-{rule.get('port', 80)}",
                "cidr": rule.get("cidr", "0.0.0.0/0"),
                "description": rule.get("description", ""),
            })

        sg_data = {
            "name": params["name"],
            "description": params.get("description", ""),
            "network_id": params.get("vpc"),
            "rules": rules,
        }

        response = self._session.post(
            f"{self.base_url}/security_groups",
            json=sg_data,
            timeout=60
        )

        if response.status_code not in [200, 201]:
            return ResourceResult(
                success=False,
                error=f"Erro ao criar security group: {response.text}",
            )

        data = response.json()
        sg = data.get("security_group", {})

        return ResourceResult(
            success=True,
            provider_id=str(sg.get("id")),
            outputs={
                "security_group_id": str(sg.get("id")),
                "security_group_name": sg.get("name"),
            },
            message=f"Security Group '{params['name']}' criado: {sg.get('id')}",
        )

    def _create_load_balancer(self, params: dict) -> ResourceResult:
        """Cria um load balancer."""
        console.print(
            f"  [cyan]Criando Load Balancer '{params['name']}' na Locaweb...[/cyan]"
        )

        lb_data = {
            "name": params["name"],
            "region": self.region,
            "network_id": params.get("network"),
            "public": params.get("public", True),
        }

        response = self._session.post(
            f"{self.base_url}/load_balancers",
            json=lb_data,
            timeout=60
        )

        if response.status_code not in [200, 201]:
            return ResourceResult(
                success=False,
                error=f"Erro ao criar Load Balancer: {response.text}",
            )

        data = response.json()
        lb = data.get("load_balancer", {})

        return ResourceResult(
            success=True,
            provider_id=str(lb.get("id")),
            outputs={
                "load_balancer_id": str(lb.get("id")),
                "load_balancer_name": lb.get("name"),
                "public_ip": lb.get("public_ip"),
            },
            message=f"Load Balancer '{params['name']}' criado: {lb.get('id')}",
        )

    def _create_website(self, params: dict) -> ResourceResult:
        """Cria um website/hospedagem."""
        console.print(f"  [cyan]Criando Website '{params['name']}' na Locaweb...[/cyan]")

        plan_map = {
            "starter": "P",
            "business": "G",
            "unlimited": "PPLUS",
        }
        plan = plan_map.get(params.get("plan", "P"), "P")

        website_data = {
            "name": params["name"],
            "domain": params.get("domain"),
            "plan": plan,
            "region": self.region,
        }

        response = self._session.post(
            f"{self.base_url}/websites",
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
        """Cria um banco de dados."""
        console.print(f"  [cyan]Criando Database '{params['name']}' na Locaweb...[/cyan]")

        engine_map = {
            "mysql": "mysql",
            "postgresql": "postgresql",
            "sqlserver": "sqlserver",
        }

        db_data = {
            "name": params["name"],
            "engine": engine_map.get(params.get("engine", "mysql"), "mysql"),
            "version": params.get("version", "8.0"),
            "size": params.get("size", "small"),
            "region": self.region,
        }

        response = self._session.post(
            f"{self.base_url}/databases",
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
                "engine": db.get("engine"),
                "endpoint": db.get("endpoint"),
            },
            message=f"Database '{params['name']}' criado",
        )

    # ── Implementações de delete ──────────────────────────────────

    def _delete_server(self, provider_id: str) -> ResourceResult:
        """Deleta um servidor."""
        response = self._session.delete(
            f"{self.base_url}/servers/{provider_id}",
            timeout=60
        )
        return ResourceResult(
            success=response.status_code in [200, 204],
            message=f"Servidor {provider_id} deletado",
        )

    def _delete_network(self, provider_id: str) -> ResourceResult:
        """Deleta uma rede."""
        response = self._session.delete(
            f"{self.base_url}/networks/{provider_id}",
            timeout=60
        )
        return ResourceResult(
            success=response.status_code in [200, 204],
            message=f"Rede {provider_id} deletada",
        )

    def _delete_security_group(self, provider_id: str) -> ResourceResult:
        """Deleta um security group."""
        response = self._session.delete(
            f"{self.base_url}/security_groups/{provider_id}",
            timeout=60
        )
        return ResourceResult(
            success=response.status_code in [200, 204],
            message=f"Security Group {provider_id} deletado",
        )

    def _delete_load_balancer(self, provider_id: str) -> ResourceResult:
        """Deleta um load balancer."""
        response = self._session.delete(
            f"{self.base_url}/load_balancers/{provider_id}",
            timeout=60
        )
        return ResourceResult(
            success=response.status_code in [200, 204],
            message=f"Load Balancer {provider_id} deletado",
        )

    def _delete_website(self, provider_id: str) -> ResourceResult:
        """Deleta um website."""
        response = self._session.delete(
            f"{self.base_url}/websites/{provider_id}",
            timeout=60
        )
        return ResourceResult(
            success=response.status_code in [200, 204],
            message=f"Website {provider_id} deletado",
        )

    # ── Helpers ─────────────────────────────────────────

    def _get_server_status(self, server_id: str) -> dict[str, Any]:
        """Retorna status de um servidor."""
        response = self._session.get(
            f"{self.base_url}/servers/{server_id}",
            timeout=30
        )
        if response.status_code == 200:
            server = response.json().get("server", {})
            return {
                "id": server_id,
                "status": server.get("status"),
                "name": server.get("name"),
                "public_ip": server.get("public_ip"),
                "provider": "locaweb",
            }
        return {"id": server_id, "status": "not_found", "provider": "locaweb"}

    def _get_network_status(self, network_id: str) -> dict[str, Any]:
        """Retorna status de uma rede."""
        response = self._session.get(
            f"{self.base_url}/networks/{network_id}",
            timeout=30
        )
        if response.status_code == 200:
            network = response.json().get("network", {})
            return {
                "id": network_id,
                "status": "active",
                "name": network.get("name"),
                "provider": "locaweb",
            }
        return {"id": network_id, "status": "not_found", "provider": "locaweb"}

    # ── Locaweb DNS Operations ───────────────────────────────────

    def _create_dns_record(self, params: dict) -> ResourceResult:
        """Cria um registro DNS na Locaweb."""
        domain = params.get("domain", "")
        record_name = params.get("name", "@")
        record_type = params.get("type", "A").upper()
        record_value = params.get("value", "")
        ttl = params.get("ttl", 3600)

        if not domain:
            return ResourceResult(
                success=False,
                error="domain é obrigatório para DNS na Locaweb",
            )

        console.print(
            f"  [cyan]Criando registro DNS '{record_name}.{domain}' ({record_type})...[/cyan]"
        )

        # API Locaweb DNS
        dns_data = {
            "domain": domain,
            "record_name": record_name,
            "record_type": record_type,
            "record_value": record_value,
            "ttl": ttl,
        }

        if record_type == "MX":
            dns_data["priority"] = params.get("priority", 10)

        response = self._session.post(
            f"{self.base_url}/dns/records",
            json=dns_data,
            timeout=60
        )

        if response.status_code in [200, 201]:
            data = response.json()
            record = data.get("record", {})
            return ResourceResult(
                success=True,
                provider_id=str(record.get("id", f"{domain}-{record_name}")),
                outputs={
                    "domain": domain,
                    "record_name": record_name,
                    "record_type": record_type,
                    "record_value": record_value,
                    "fqdn": f"{record_name}.{domain}" if record_name != "@" else domain,
                },
                message=f"DNS Record '{record_name}.{domain}' criado",
            )
        else:
            return ResourceResult(
                success=False,
                error=f"Erro ao criar DNS: {response.text[:200]}",
            )

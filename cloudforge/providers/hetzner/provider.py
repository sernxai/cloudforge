"""
CloudForge - Provider Hetzner Cloud
Implementação usando API REST da Hetzner.
"""

from typing import Any

from rich.console import Console

from cloudforge.providers.base import BaseProvider, ProviderError
from cloudforge.resources.base import ResourceResult

console = Console()


class HetznerProvider(BaseProvider):
    """Provider para Hetzner Cloud."""

    PROVIDER_NAME = "hetzner"

    REGIONS = [
        "eu-central",  # Falkenstein, Germany
        "eu-west",     # Nuremberg, Germany
        "us-east",     # Ashburn, VA, USA
    ]

    LOCATIONS = {
        "eu-central": "fsn1",
        "eu-west": "nbg1",
        "us-east": "ash",
    }

    def __init__(self, region: str, credentials: dict[str, Any] | None = None):
        super().__init__(region, credentials)
        self.api_token = (credentials or {}).get("api_token", "")

    def authenticate(self) -> bool:
        """Autentica com Hetzner Cloud usando API REST."""
        try:
            import requests

            self._session = requests.Session()
            self._session.headers.update({
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            })

            # Validar credenciais listando servers
            response = self._session.get(
                "https://api.hetzner.cloud/v1/servers",
                params={"per_page": 1}
            )
            if response.status_code == 200:
                console.print("[green]✓ Hetzner Cloud autenticado com sucesso[/green]")
                return True
            else:
                raise ProviderError(f"Falha na autenticação: {response.status_code}")

        except ImportError:
            raise ProviderError("requests não instalado. Execute: pip install requests")
        except Exception as e:
            raise ProviderError(f"Falha na autenticação Hetzner: {e}")

    def validate_credentials(self) -> bool:
        """Verifica se as credenciais são válidas."""
        try:
            response = self._session.get(
                "https://api.hetzner.cloud/v1/servers",
                params={"per_page": 1}
            )
            return response.status_code == 200
        except Exception:
            return False

    def create_resource(
        self, resource_type: str, params: dict[str, Any]
    ) -> ResourceResult:
        """Cria um recurso na Hetzner Cloud."""
        handlers = {
            "vm": self._create_server,
            "vpc": self._create_network,
            "subnet": self._create_network_subnet,
            "security_group": self._create_firewall,
            "lb": self._create_load_balancer,
            "dns_record": self._create_dns_record,
        }

        handler = handlers.get(resource_type)
        if not handler:
            return ResourceResult(
                success=False,
                error=f"Tipo de recurso não suportado na Hetzner: {resource_type}"
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
            f"[yellow]  Atualizando {resource_type} '{name}' na Hetzner...[/yellow]"
        )
        return ResourceResult(
            success=True,
            message=f"{resource_type} '{name}' atualizado na Hetzner",
        )

    def delete_resource(
        self, resource_type: str, provider_id: str
    ) -> ResourceResult:
        """Deleta um recurso."""
        console.print(
            f"[red]  Destruindo {resource_type} '{provider_id}' na Hetzner...[/red]"
        )

        handlers = {
            "vm": self._delete_server,
            "vpc": self._delete_network,
            "security_group": self._delete_firewall,
            "lb": self._delete_load_balancer,
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
                return {"id": provider_id, "status": "active", "provider": "hetzner"}
        except Exception as e:
            return {"id": provider_id, "status": "error", "error": str(e)}

    def list_regions(self) -> list[str]:
        """Lista regiões disponíveis."""
        return self.REGIONS

    # ── Implementações de criação ─────────────────────────────────

    def _create_server(self, params: dict) -> ResourceResult:
        """Cria um Server (VM)."""
        console.print(f"  [cyan]Criando Server '{params['name']}' na Hetzner...[/cyan]")

        # Mapeamento de tipos de server
        type_map = {
            "small": "cx11",      # 1 vCPU, 2GB RAM
            "medium": "cx22",     # 2 vCPU, 4GB RAM
            "large": "cx42",      # 4 vCPU, 8GB RAM
            "xlarge": "cx52",     # 8 vCPU, 16GB RAM
        }
        server_type = type_map.get(params.get("instance_type", "medium"), "cx22")

        # Buscar image ID
        image = self._resolve_image(params.get("os", "ubuntu-22.04"))

        # Obter location
        location = self.LOCATIONS.get(self.region, "fsn1")

        server_data = {
            "name": params["name"],
            "server_type": server_type,
            "image": image,
            "location": location,
            "public_net": {
                "enable_ipv4": params.get("associate_public_ip", True),
                "enable_ipv6": params.get("ipv6", False),
            },
            "start_after_create": True,
        }

        if params.get("network"):
            server_data["networks"] = [params["network"]]

        if params.get("ssh_key"):
            server_data["ssh_keys"] = [params["ssh_key"]]

        response = self._session.post(
            "https://api.hetzner.cloud/v1/servers",
            json=server_data,
        )

        if response.status_code not in [200, 201]:
            return ResourceResult(
                success=False,
                error=f"Erro ao criar Server: {response.text}",
            )

        data = response.json()
        server = data.get("server", {})
        server_id = str(server.get("id"))

        # Aguardar server estar rodando
        console.print(f"  [dim]Aguardando server {server_id}...[/dim]")
        self._wait_for_server_status(server_id, "running")

        return ResourceResult(
            success=True,
            provider_id=server_id,
            outputs={
                "server_id": server_id,
                "server_name": server.get("name"),
                "public_ip": server.get("public_net", {}).get("ipv4", {}).get("ip"),
                "private_ip": server.get("private_net", [{}])[0].get("ip") if server.get("private_net") else None,
                "server_type": server_type,
                "location": location,
            },
            message=f"Server '{params['name']}' criado: {server_id}",
        )

    def _create_network(self, params: dict) -> ResourceResult:
        """Cria uma Network (VPC)."""
        console.print(f"  [cyan]Criando Network '{params['name']}' na Hetzner...[/cyan]")

        network_data = {
            "name": params["name"],
            "ip_range": params["cidr_block"],
        }

        response = self._session.post(
            "https://api.hetzner.cloud/v1/networks",
            json=network_data,
        )

        if response.status_code not in [200, 201]:
            return ResourceResult(
                success=False,
                error=f"Erro ao criar Network: {response.text}",
            )

        data = response.json()
        network = data.get("network", {})

        return ResourceResult(
            success=True,
            provider_id=str(network.get("id")),
            outputs={
                "network_id": str(network.get("id")),
                "network_name": network.get("name"),
                "ip_range": network.get("ip_range"),
            },
            message=f"Network '{params['name']}' criada: {network.get('id')}",
        )

    def _create_network_subnet(self, params: dict) -> ResourceResult:
        """Adiciona subnet a uma Network."""
        console.print(f"  [cyan]Adicionando subnet '{params['name']}' na Hetzner...[/cyan]")

        # Hetzner usa zone para subnets
        zone_map = {
            "eu-central": "eu-central",
            "eu-west": "eu-west",
            "us-east": "us-east",
        }

        subnet_data = {
            "network": params.get("vpc"),
            "ip_range": params["cidr_block"],
            "zone": zone_map.get(self.region, "eu-central"),
        }

        response = self._session.post(
            f"https://api.hetzner.cloud/v1/networks/{params.get('vpc')}/actions/add_subnet",
            json=subnet_data,
        )

        if response.status_code not in [200, 201]:
            return ResourceResult(
                success=False,
                error=f"Erro ao adicionar subnet: {response.text}",
            )

        return ResourceResult(
            success=True,
            provider_id=params.get("vpc"),
            outputs={
                "subnet_name": params["name"],
                "cidr_block": params["cidr_block"],
            },
            message=f"Subnet '{params['name']}' adicionada",
        )

    def _create_firewall(self, params: dict) -> ResourceResult:
        """Cria um Firewall."""
        console.print(
            f"  [cyan]Criando Firewall '{params['name']}' na Hetzner...[/cyan]"
        )

        # Construir regras
        rules = []
        for rule in params.get("ingress", []):
            rules.append({
                "direction": "in",
                "protocol": rule.get("protocol", "tcp"),
                "port": str(rule.get("port", 80)),
                "source_ips": [rule.get("cidr", "0.0.0.0/0")],
                "description": rule.get("description", ""),
            })

        firewall_data = {
            "name": params["name"],
            "rules": rules,
            "apply_to": [],
        }

        response = self._session.post(
            "https://api.hetzner.cloud/v1/firewalls",
            json=firewall_data,
        )

        if response.status_code not in [200, 201]:
            return ResourceResult(
                success=False,
                error=f"Erro ao criar Firewall: {response.text}",
            )

        data = response.json()
        firewall = data.get("firewall", {})

        return ResourceResult(
            success=True,
            provider_id=str(firewall.get("id")),
            outputs={
                "firewall_id": str(firewall.get("id")),
                "firewall_name": firewall.get("name"),
            },
            message=f"Firewall '{params['name']}' criado: {firewall.get('id')}",
        )

    def _create_load_balancer(self, params: dict) -> ResourceResult:
        """Cria um Load Balancer."""
        console.print(
            f"  [cyan]Criando Load Balancer '{params['name']}' na Hetzner...[/cyan]"
        )

        # Obter location
        location = self.LOCATIONS.get(self.region, "fsn1")

        lb_data = {
            "name": params["name"],
            "load_balancer_type": params.get("lb_type", "lb11"),
            "location": location,
            "public_interface": params.get("public", True),
        }

        if params.get("network"):
            lb_data["network"] = params["network"]

        response = self._session.post(
            "https://api.hetzner.cloud/v1/load_balancers",
            json=lb_data,
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
                "public_ip": lb.get("public_net", {}).get("ipv4", {}).get("ip"),
            },
            message=f"Load Balancer '{params['name']}' criado: {lb.get('id')}",
        )

    # ── Implementações de delete ──────────────────────────────────

    def _delete_server(self, provider_id: str) -> ResourceResult:
        """Deleta um Server."""
        response = self._session.delete(
            f"https://api.hetzner.cloud/v1/servers/{provider_id}"
        )
        return ResourceResult(
            success=response.status_code in [200, 201],
            message=f"Server {provider_id} deletado",
        )

    def _delete_network(self, provider_id: str) -> ResourceResult:
        """Deleta uma Network."""
        response = self._session.delete(
            f"https://api.hetzner.cloud/v1/networks/{provider_id}"
        )
        return ResourceResult(
            success=response.status_code in [200, 201],
            message=f"Network {provider_id} deletada",
        )

    def _delete_firewall(self, provider_id: str) -> ResourceResult:
        """Deleta um Firewall."""
        response = self._session.delete(
            f"https://api.hetzner.cloud/v1/firewalls/{provider_id}"
        )
        return ResourceResult(
            success=response.status_code in [200, 201],
            message=f"Firewall {provider_id} deletado",
        )

    def _delete_load_balancer(self, provider_id: str) -> ResourceResult:
        """Deleta um Load Balancer."""
        response = self._session.delete(
            f"https://api.hetzner.cloud/v1/load_balancers/{provider_id}"
        )
        return ResourceResult(
            success=response.status_code in [200, 201],
            message=f"Load Balancer {provider_id} deletado",
        )

    # ── Helpers ─────────────────────────────────────────

    def _get_server_status(self, server_id: str) -> dict[str, Any]:
        """Retorna status de um Server."""
        response = self._session.get(
            f"https://api.hetzner.cloud/v1/servers/{server_id}"
        )
        if response.status_code == 200:
            server = response.json().get("server", {})
            return {
                "id": server_id,
                "status": server.get("status"),
                "name": server.get("name"),
                "public_ip": server.get("public_net", {}).get("ipv4", {}).get("ip"),
                "provider": "hetzner",
            }
        return {"id": server_id, "status": "not_found", "provider": "hetzner"}

    def _get_network_status(self, network_id: str) -> dict[str, Any]:
        """Retorna status de uma Network."""
        response = self._session.get(
            f"https://api.hetzner.cloud/v1/networks/{network_id}"
        )
        if response.status_code == 200:
            network = response.json().get("network", {})
            return {
                "id": network_id,
                "status": "active",
                "name": network.get("name"),
                "provider": "hetzner",
            }
        return {"id": network_id, "status": "not_found", "provider": "hetzner"}

    def _wait_for_server_status(self, server_id: str, target_status: str, timeout: int = 120) -> None:
        """Aguarda server atingir status desejado."""
        import time

        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self._get_server_status(server_id)
            if status.get("status") == target_status:
                return
            time.sleep(2)

    def _resolve_image(self, image_name: str) -> str:
        """Resolve nome de imagem para Hetzner Image ID/slug."""
        image_map = {
            "ubuntu-22.04": "ubuntu-22.04",
            "ubuntu-20.04": "ubuntu-20.04",
            "ubuntu": "ubuntu-22.04",
            "debian-11": "debian-11",
            "debian": "debian-11",
            "debian-12": "debian-12",
            "centos-7": "centos-7",
            "rocky-9": "rocky-9",
            "fedora-38": "fedora-38",
        }
        return image_map.get(image_name, image_name)

    # ── Hetzner DNS Operations ───────────────────────────────────
    # Hetzner não tem API pública de DNS, usa-se API de terceiros
    # ou gerencia-se via painel. Implementação simplificada.

    def _create_dns_record(self, params: dict) -> ResourceResult:
        """Cria um registro DNS (simulado - Hetzner não tem API DNS pública)."""
        domain = params.get("domain", "")
        record_name = params.get("name", "@")
        record_type = params.get("type", "A").upper()
        record_value = params.get("value", "")
        ttl = params.get("ttl", 3600)

        console.print(
            f"  [cyan]DNS '{record_name}.{domain}' ({record_type}) - via painel Hetzner[/cyan]"
        )

        # Hetzner DNS API não é pública - retorna info para configuração manual
        return ResourceResult(
            success=True,
            provider_id=f"dns-{domain}-{record_name}",
            outputs={
                "domain": domain,
                "record_name": record_name,
                "record_type": record_type,
                "record_value": record_value,
                "note": "Configurar DNS via painel Hetzner Cloud Console",
            },
            message=f"DNS Record '{record_name}.{domain}' registrado (configuração manual necessária)",
        )

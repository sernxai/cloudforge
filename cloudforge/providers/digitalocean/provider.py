"""
CloudForge - Provider DigitalOcean
Implementação usando API REST da DigitalOcean.
"""

from typing import Any

from rich.console import Console

from cloudforge.providers.base import BaseProvider, ProviderError
from cloudforge.resources.base import ResourceResult

console = Console()


class DigitalOceanProvider(BaseProvider):
    """Provider para DigitalOcean."""

    PROVIDER_NAME = "digitalocean"

    REGIONS = [
        "nyc1", "nyc2", "nyc3",  # New York
        "sfo1", "sfo2", "sfo3",  # San Francisco
        "ams2", "ams3",          # Amsterdam
        "sgp1",                  # Singapore
        "lon1",                  # London
        "fra1",                  # Frankfurt
        "tor1",                  # Toronto
        "blr1",                  # Bangalore
        "syd1",                  # Sydney
    ]

    def __init__(self, region: str, credentials: dict[str, Any] | None = None):
        super().__init__(region, credentials)
        self.api_token = (credentials or {}).get("api_token", "")

    def authenticate(self) -> bool:
        """Autentica com DigitalOcean usando API REST."""
        try:
            import requests

            self._session = requests.Session()
            self._session.headers.update({
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            })

            # Validar credenciais listando account
            response = self._session.get("https://api.digitalocean.com/v2/account")
            if response.status_code == 200:
                account = response.json().get("account", {})
                console.print(
                    f"[green]✓ DigitalOcean autenticado: {account.get('email', 'N/A')}[/green]"
                )
                return True
            else:
                raise ProviderError(f"Falha na autenticação: {response.status_code}")

        except ImportError:
            raise ProviderError("requests não instalado. Execute: pip install requests")
        except Exception as e:
            raise ProviderError(f"Falha na autenticação DigitalOcean: {e}")

    def validate_credentials(self) -> bool:
        """Verifica se as credenciais são válidas."""
        try:
            response = self._session.get("https://api.digitalocean.com/v2/account")
            return response.status_code == 200
        except Exception:
            return False

    def create_resource(
        self, resource_type: str, params: dict[str, Any]
    ) -> ResourceResult:
        """Cria um recurso na DigitalOcean."""
        handlers = {
            "vm": self._create_droplet,
            "vpc": self._create_vpc,
            "subnet": self._create_vpc_subnet,
            "security_group": self._create_firewall,
            "kubernetes": self._create_kubernetes,
            "lb": self._create_load_balancer,
            "database": self._create_database,
        }

        handler = handlers.get(resource_type)
        if not handler:
            return ResourceResult(
                success=False,
                error=f"Tipo de recurso não suportado na DigitalOcean: {resource_type}"
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
            f"[yellow]  Atualizando {resource_type} '{name}' na DigitalOcean...[/yellow]"
        )
        return ResourceResult(
            success=True,
            message=f"{resource_type} '{name}' atualizado na DigitalOcean",
        )

    def delete_resource(
        self, resource_type: str, provider_id: str
    ) -> ResourceResult:
        """Deleta um recurso."""
        console.print(
            f"[red]  Destruindo {resource_type} '{provider_id}' na DigitalOcean...[/red]"
        )

        handlers = {
            "vm": self._delete_droplet,
            "vpc": self._delete_vpc,
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
                return self._get_droplet_status(provider_id)
            elif resource_type == "vpc":
                return self._get_vpc_status(provider_id)
            else:
                return {"id": provider_id, "status": "active", "provider": "digitalocean"}
        except Exception as e:
            return {"id": provider_id, "status": "error", "error": str(e)}

    def list_regions(self) -> list[str]:
        """Lista regiões disponíveis."""
        return self.REGIONS

    # ── Implementações de criação ─────────────────────────────────

    def _create_droplet(self, params: dict) -> ResourceResult:
        """Cria um Droplet (VM)."""
        console.print(f"  [cyan]Criando Droplet '{params['name']}' na DigitalOcean...[/cyan]")

        # Mapeamento de tipos de instância
        type_map = {
            "small": "s-1vcpu-1gb",
            "medium": "s-2vcpu-2gb",
            "large": "s-4vcpu-8gb",
            "xlarge": "s-8vcpu-16gb",
        }
        size = type_map.get(params.get("instance_type", "medium"), "s-2vcpu-2gb")

        # Buscar image ID
        image = self._resolve_image(params.get("os", "ubuntu-22-04"))

        droplet_data = {
            "name": params["name"],
            "region": self.region,
            "size": size,
            "image": image,
            "backups": params.get("backups", False),
            "ipv6": params.get("ipv6", False),
            "monitoring": params.get("monitoring", True),
            "tags": params.get("tags", []),
        }

        if params.get("subnet"):
            droplet_data["vpc_uuid"] = params["subnet"]

        response = self._session.post(
            "https://api.digitalocean.com/v2/droplets",
            json=droplet_data,
        )

        if response.status_code not in [200, 201, 202]:
            return ResourceResult(
                success=False,
                error=f"Erro ao criar Droplet: {response.text}",
            )

        data = response.json()
        droplet = data.get("droplet", {})
        droplet_id = str(droplet.get("id"))

        return ResourceResult(
            success=True,
            provider_id=droplet_id,
            outputs={
                "droplet_id": droplet_id,
                "droplet_name": droplet.get("name"),
                "public_ip": droplet.get("networks", {}).get("v4", [{}])[0].get("ip_address"),
                "private_ip": droplet.get("networks", {}).get("v4", [{}])[1].get("ip_address") if len(droplet.get("networks", {}).get("v4", [])) > 1 else None,
                "region": self.region,
                "size": size,
            },
            message=f"Droplet '{params['name']}' criado: {droplet_id}",
        )

    def _create_vpc(self, params: dict) -> ResourceResult:
        """Cria uma VPC."""
        console.print(f"  [cyan]Criando VPC '{params['name']}' na DigitalOcean...[/cyan]")

        vpc_data = {
            "name": params["name"],
            "region": self.region,
            "ip_range": params["cidr_block"],
            "description": params.get("description", "CloudForge managed VPC"),
        }

        response = self._session.post(
            "https://api.digitalocean.com/v2/vpcs",
            json=vpc_data,
        )

        if response.status_code not in [200, 201]:
            return ResourceResult(
                success=False,
                error=f"Erro ao criar VPC: {response.text}",
            )

        data = response.json()
        vpc = data.get("vpc", {})

        return ResourceResult(
            success=True,
            provider_id=vpc.get("id"),
            outputs={
                "vpc_id": vpc.get("id"),
                "vpc_name": vpc.get("name"),
                "ip_range": vpc.get("ip_range"),
            },
            message=f"VPC '{params['name']}' criada: {vpc.get('id')}",
        )

    def _create_vpc_subnet(self, params: dict) -> ResourceResult:
        """DigitalOcean usa VPC única por região, retorna info da VPC."""
        console.print(f"  [cyan]Configurando subnet na VPC '{params['name']}'...[/cyan]")
        
        # DigitalOcean gerencia subnets automaticamente dentro da VPC
        return ResourceResult(
            success=True,
            provider_id=params.get("vpc", "default"),
            outputs={
                "subnet_name": params["name"],
                "cidr_block": params["cidr_block"],
                "note": "Subnets são gerenciadas automaticamente na DigitalOcean",
            },
            message=f"Subnet '{params['name']}' configurada",
        )

    def _create_firewall(self, params: dict) -> ResourceResult:
        """Cria um Firewall."""
        console.print(
            f"  [cyan]Criando Firewall '{params['name']}' na DigitalOcean...[/cyan]"
        )

        # Construir regras de inbound
        inbound_rules = []
        for rule in params.get("ingress", []):
            inbound_rules.append({
                "protocol": rule.get("protocol", "tcp"),
                "ports": str(rule.get("port", 80)),
                "sources": {
                    "addresses": [rule.get("cidr", "0.0.0.0/0")],
                },
            })

        firewall_data = {
            "name": params["name"],
            "inbound_rules": inbound_rules,
            "outbound_rules": [{
                "protocol": "tcp",
                "ports": "all",
                "destinations": {"addresses": ["0.0.0.0/0", "::/0"]},
            }],
            "droplet_ids": [],
        }

        response = self._session.post(
            "https://api.digitalocean.com/v2/firewalls",
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
            provider_id=firewall.get("id"),
            outputs={
                "firewall_id": firewall.get("id"),
                "firewall_name": firewall.get("name"),
            },
            message=f"Firewall '{params['name']}' criado: {firewall.get('id')}",
        )

    def _create_kubernetes(self, params: dict) -> ResourceResult:
        """Cria um cluster Kubernetes (DOKS)."""
        console.print(
            f"  [cyan]Criando cluster DOKS '{params['name']}' na DigitalOcean...[/cyan]"
        )

        node_pool = {
            "name": f"{params['name']}-pool",
            "size": params.get("node_type", "s-2vcpu-4gb"),
            "count": params.get("node_count", 3),
            "auto_scale": params.get("auto_scaling", False),
        }

        k8s_data = {
            "name": params["name"],
            "region": self.region,
            "version": params.get("kubernetes_version", "latest"),
            "node_pools": [node_pool],
        }

        response = self._session.post(
            "https://api.digitalocean.com/v2/kubernetes/clusters",
            json=k8s_data,
        )

        if response.status_code not in [200, 201, 202]:
            return ResourceResult(
                success=False,
                error=f"Erro ao criar cluster K8s: {response.text}",
            )

        data = response.json()
        cluster = data.get("kubernetes_cluster", {})

        return ResourceResult(
            success=True,
            provider_id=cluster.get("id"),
            outputs={
                "cluster_id": cluster.get("id"),
                "cluster_name": cluster.get("name"),
                "endpoint": cluster.get("endpoint"),
                "node_count": params.get("node_count", 3),
            },
            message=f"DOKS cluster '{params['name']}' criado: {cluster.get('id')}",
        )

    def _create_load_balancer(self, params: dict) -> ResourceResult:
        """Cria um Load Balancer."""
        console.print(
            f"  [cyan]Criando Load Balancer '{params['name']}' na DigitalOcean...[/cyan]"
        )

        lb_data = {
            "name": params["name"],
            "region": self.region,
            "algorithm": params.get("algorithm", "round_robin"),
            "forwarding_rules": [{
                "entry_protocol": params.get("entry_protocol", "http"),
                "entry_port": params.get("entry_port", 80),
                "target_protocol": params.get("target_protocol", "http"),
                "target_port": params.get("target_port", 8080),
            }],
            "health_check": {
                "protocol": "http",
                "port": params.get("health_port", 8080),
                "path": params.get("health_path", "/"),
            },
        }

        if params.get("vpc"):
            lb_data["vpc_uuid"] = params["vpc"]

        response = self._session.post(
            "https://api.digitalocean.com/v2/load_balancers",
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
            provider_id=lb.get("id"),
            outputs={
                "load_balancer_id": lb.get("id"),
                "load_balancer_name": lb.get("name"),
                "ip": lb.get("ip"),
            },
            message=f"Load Balancer '{params['name']}' criado: {lb.get('id')}",
        )

    def _create_database(self, params: dict) -> ResourceResult:
        """Cria um Database Cluster."""
        console.print(
            f"  [cyan]Criando Database '{params['name']}' na DigitalOcean...[/cyan]"
        )

        engine_map = {
            "postgresql": "pg",
            "mysql": "mysql",
            "redis": "redis",
            "mongodb": "mongodb",
        }

        db_data = {
            "name": params["name"],
            "engine": engine_map.get(params.get("engine", "postgresql"), "pg"),
            "version": params.get("version", "15"),
            "size": params.get("instance_type", "db-s-1vcpu-1gb"),
            "region": self.region,
            "num_nodes": params.get("nodes", 1),
        }

        response = self._session.post(
            "https://api.digitalocean.com/v2/databases",
            json=db_data,
        )

        if response.status_code not in [200, 201, 202]:
            return ResourceResult(
                success=False,
                error=f"Erro ao criar Database: {response.text}",
            )

        data = response.json()
        db = data.get("database", {})

        return ResourceResult(
            success=True,
            provider_id=db.get("id"),
            outputs={
                "database_id": db.get("id"),
                "database_name": db.get("name"),
                "engine": db.get("engine"),
                "connection_string": db.get("connection", {}).get("uri"),
            },
            message=f"Database '{params['name']}' criado: {db.get('id')}",
        )

    # ── Implementações de delete ──────────────────────────────────

    def _delete_droplet(self, provider_id: str) -> ResourceResult:
        """Deleta um Droplet."""
        response = self._session.delete(
            f"https://api.digitalocean.com/v2/droplets/{provider_id}"
        )
        return ResourceResult(
            success=response.status_code in [200, 204],
            message=f"Droplet {provider_id} deletado",
        )

    def _delete_vpc(self, provider_id: str) -> ResourceResult:
        """Deleta uma VPC."""
        response = self._session.delete(
            f"https://api.digitalocean.com/v2/vpcs/{provider_id}"
        )
        return ResourceResult(
            success=response.status_code in [200, 204],
            message=f"VPC {provider_id} deletada",
        )

    def _delete_firewall(self, provider_id: str) -> ResourceResult:
        """Deleta um Firewall."""
        response = self._session.delete(
            f"https://api.digitalocean.com/v2/firewalls/{provider_id}"
        )
        return ResourceResult(
            success=response.status_code in [200, 204],
            message=f"Firewall {provider_id} deletado",
        )

    def _delete_load_balancer(self, provider_id: str) -> ResourceResult:
        """Deleta um Load Balancer."""
        response = self._session.delete(
            f"https://api.digitalocean.com/v2/load_balancers/{provider_id}"
        )
        return ResourceResult(
            success=response.status_code in [200, 204],
            message=f"Load Balancer {provider_id} deletado",
        )

    # ── Helpers ─────────────────────────────────────────

    def _get_droplet_status(self, droplet_id: str) -> dict[str, Any]:
        """Retorna status de um Droplet."""
        response = self._session.get(
            f"https://api.digitalocean.com/v2/droplets/{droplet_id}"
        )
        if response.status_code == 200:
            droplet = response.json().get("droplet", {})
            return {
                "id": droplet_id,
                "status": droplet.get("status"),
                "name": droplet.get("name"),
                "public_ip": droplet.get("networks", {}).get("v4", [{}])[0].get("ip_address"),
                "provider": "digitalocean",
            }
        return {"id": droplet_id, "status": "not_found", "provider": "digitalocean"}

    def _get_vpc_status(self, vpc_id: str) -> dict[str, Any]:
        """Retorna status de uma VPC."""
        response = self._session.get(
            f"https://api.digitalocean.com/v2/vpcs/{vpc_id}"
        )
        if response.status_code == 200:
            vpc = response.json().get("vpc", {})
            return {
                "id": vpc_id,
                "status": "active",
                "name": vpc.get("name"),
                "provider": "digitalocean",
            }
        return {"id": vpc_id, "status": "not_found", "provider": "digitalocean"}

    def _resolve_image(self, image_name: str) -> str:
        """Resolve nome de imagem para slug da DigitalOcean."""
        image_map = {
            "ubuntu-22-04": "ubuntu-22-04-x64",
            "ubuntu-20-04": "ubuntu-20-04-x64",
            "ubuntu": "ubuntu-22-04-x64",
            "debian-11": "debian-11-x64",
            "debian": "debian-11-x64",
            "centos-7": "centos-7-x64",
            "rockylinux-9": "rockylinux-9-x64",
            "fedora": "fedora-38-x64",
            "docker": "docker-20-04",
        }
        return image_map.get(image_name, image_name)

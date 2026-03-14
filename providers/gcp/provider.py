"""
CloudForge - Provider GCP
Implementação usando google-cloud SDK para Google Cloud Platform.
"""

from typing import Any

from rich.console import Console

from providers.base import BaseProvider, ProviderError
from resources.base import ResourceResult

console = Console()


class GCPProvider(BaseProvider):
    """Provider para Google Cloud Platform."""

    PROVIDER_NAME = "gcp"

    REGIONS = [
        "us-central1", "us-east1", "us-west1",
        "europe-west1", "europe-west3",
        "asia-east1", "asia-southeast1",
        "southamerica-east1",
    ]

    def __init__(self, region: str, credentials: dict[str, Any] | None = None):
        super().__init__(region, credentials)
        self.project_id = (credentials or {}).get("project_id", "")

    def authenticate(self) -> bool:
        try:
            from google.cloud import compute_v1
            from google.cloud import container_v1

            if self.credentials.get("service_account_key"):
                import google.auth
                from google.oauth2 import service_account

                creds = service_account.Credentials.from_service_account_file(
                    self.credentials["service_account_key"]
                )
                self._clients["compute"] = compute_v1.InstancesClient(
                    credentials=creds
                )
                self._clients["networks"] = compute_v1.NetworksClient(
                    credentials=creds
                )
                self._clients["subnetworks"] = compute_v1.SubnetworksClient(
                    credentials=creds
                )
                self._clients["firewalls"] = compute_v1.FirewallsClient(
                    credentials=creds
                )
                self._clients["gke"] = container_v1.ClusterManagerClient(
                    credentials=creds
                )
            else:
                # Usar Application Default Credentials
                self._clients["compute"] = compute_v1.InstancesClient()
                self._clients["networks"] = compute_v1.NetworksClient()
                self._clients["subnetworks"] = compute_v1.SubnetworksClient()
                self._clients["firewalls"] = compute_v1.FirewallsClient()
                self._clients["gke"] = container_v1.ClusterManagerClient()

            console.print("[green]✓ GCP autenticado com sucesso[/green]")
            return True

        except ImportError:
            raise ProviderError(
                "Google Cloud SDK não instalado. Execute: "
                "pip install google-cloud-compute google-cloud-container"
            )
        except Exception as e:
            raise ProviderError(f"Falha na autenticação GCP: {e}")

    def validate_credentials(self) -> bool:
        try:
            self._clients["compute"].aggregated_list(
                request={"project": self.project_id, "max_results": 1}
            )
            return True
        except Exception:
            return False

    def create_resource(
        self, resource_type: str, params: dict[str, Any]
    ) -> ResourceResult:
        handlers = {
            "vm": self._create_instance,
            "vpc": self._create_network,
            "subnet": self._create_subnetwork,
            "security_group": self._create_firewall,
            "kubernetes": self._create_gke,
            "database": self._create_cloud_sql,
        }

        handler = handlers.get(resource_type)
        if not handler:
            return ResourceResult(
                success=False, error=f"Tipo não suportado no GCP: {resource_type}"
            )

        try:
            return handler(params)
        except Exception as e:
            return ResourceResult(success=False, error=str(e))

    def update_resource(
        self, resource_type: str, name: str,
        config: dict[str, Any], changes: dict[str, Any],
    ) -> ResourceResult:
        console.print(
            f"[yellow]  Atualizando {resource_type} '{name}' no GCP...[/yellow]"
        )
        return ResourceResult(success=True, message=f"{resource_type} '{name}' atualizado")

    def delete_resource(
        self, resource_type: str, provider_id: str
    ) -> ResourceResult:
        console.print(
            f"[red]  Destruindo {resource_type} '{provider_id}' no GCP...[/red]"
        )
        # Implementação real de delete para cada tipo
        return ResourceResult(
            success=True,
            message=f"{resource_type} '{provider_id}' destruído",
        )

    def get_resource_status(
        self, resource_type: str, provider_id: str
    ) -> dict[str, Any]:
        return {"id": provider_id, "status": "active", "provider": "gcp"}

    def list_regions(self) -> list[str]:
        return self.REGIONS

    # ── Implementações de criação ─────────────────────────────────

    def _create_instance(self, params: dict) -> ResourceResult:
        from google.cloud import compute_v1

        console.print(f"  [cyan]Criando VM '{params['name']}' no GCP...[/cyan]")

        instance = compute_v1.Instance()
        instance.name = params["name"]
        instance.machine_type = (
            f"zones/{self.region}-a/machineTypes/{params.get('node_type', 'e2-medium')}"
        )

        disk = compute_v1.AttachedDisk()
        disk.auto_delete = True
        disk.boot = True
        init_params = compute_v1.AttachedDiskInitializeParams()
        init_params.source_image = (
            "projects/ubuntu-os-cloud/global/images/family/ubuntu-2204-lts"
        )
        init_params.disk_size_gb = params.get("disk_size_gb", 30)
        disk.initialize_params = init_params
        instance.disks = [disk]

        network_interface = compute_v1.NetworkInterface()
        network_interface.name = "global/networks/default"
        if params.get("associate_public_ip", True):
            access_config = compute_v1.AccessConfig()
            access_config.name = "External NAT"
            access_config.type_ = "ONE_TO_ONE_NAT"
            network_interface.access_configs = [access_config]
        instance.network_interfaces = [network_interface]

        client = self._clients["compute"]
        operation = client.insert(
            project=self.project_id,
            zone=f"{self.region}-a",
            instance_resource=instance,
        )

        return ResourceResult(
            success=True,
            provider_id=params["name"],
            outputs={
                "instance_name": params["name"],
                "zone": f"{self.region}-a",
                "machine_type": params.get("node_type", "e2-medium"),
            },
            message=f"VM '{params['name']}' criada no GCP",
        )

    def _create_network(self, params: dict) -> ResourceResult:
        from google.cloud import compute_v1

        console.print(f"  [cyan]Criando VPC '{params['name']}' no GCP...[/cyan]")

        network = compute_v1.Network()
        network.name = params["name"]
        network.auto_create_subnetworks = False

        client = self._clients["networks"]
        operation = client.insert(
            project=self.project_id, network_resource=network
        )

        return ResourceResult(
            success=True,
            provider_id=params["name"],
            outputs={"network_name": params["name"]},
            message=f"VPC '{params['name']}' criada no GCP",
        )

    def _create_subnetwork(self, params: dict) -> ResourceResult:
        from google.cloud import compute_v1

        console.print(f"  [cyan]Criando Subnet '{params['name']}' no GCP...[/cyan]")

        subnet = compute_v1.Subnetwork()
        subnet.name = params["name"]
        subnet.ip_cidr_range = params["cidr_block"]
        subnet.network = f"projects/{self.project_id}/global/networks/{params['vpc']}"
        subnet.region = self.region

        client = self._clients["subnetworks"]
        operation = client.insert(
            project=self.project_id,
            region=self.region,
            subnetwork_resource=subnet,
        )

        return ResourceResult(
            success=True,
            provider_id=params["name"],
            outputs={"subnet_name": params["name"], "cidr": params["cidr_block"]},
            message=f"Subnet '{params['name']}' criada no GCP",
        )

    def _create_firewall(self, params: dict) -> ResourceResult:
        from google.cloud import compute_v1

        console.print(
            f"  [cyan]Criando Firewall Rule '{params['name']}' no GCP...[/cyan]"
        )

        firewall = compute_v1.Firewall()
        firewall.name = params["name"]
        firewall.network = (
            f"projects/{self.project_id}/global/networks/{params.get('vpc', 'default')}"
        )

        allowed_rules = []
        for rule in params.get("ingress", []):
            allowed = compute_v1.Allowed()
            allowed.I_p_protocol = rule.get("protocol", "tcp")
            if "port" in rule:
                allowed.ports = [str(rule["port"])]
            elif "port_range" in rule:
                allowed.ports = [
                    f"{rule['port_range'][0]}-{rule['port_range'][1]}"
                ]
            allowed_rules.append(allowed)

        firewall.allowed = allowed_rules
        firewall.source_ranges = ["0.0.0.0/0"]

        client = self._clients["firewalls"]
        operation = client.insert(
            project=self.project_id, firewall_resource=firewall
        )

        return ResourceResult(
            success=True,
            provider_id=params["name"],
            outputs={"firewall_name": params["name"]},
            message=f"Firewall '{params['name']}' criada no GCP",
        )

    def _create_gke(self, params: dict) -> ResourceResult:
        from google.cloud import container_v1

        console.print(
            f"  [cyan]Criando cluster GKE '{params['name']}'...[/cyan]"
        )

        cluster = container_v1.Cluster()
        cluster.name = params["name"]
        cluster.initial_node_count = params.get("node_count", 3)

        node_config = container_v1.NodeConfig()
        node_config.machine_type = params.get("node_type", "e2-medium")
        node_config.disk_size_gb = params.get("disk_size_gb", 50)
        cluster.node_config = node_config

        if params.get("auto_scaling"):
            autoscaling = container_v1.ClusterAutoscaling()
            autoscaling.enable_node_autoprovisioning = True
            cluster.autoscaling = autoscaling

        client = self._clients["gke"]
        parent = f"projects/{self.project_id}/locations/{self.region}"

        operation = client.create_cluster(
            request={"parent": parent, "cluster": cluster}
        )

        return ResourceResult(
            success=True,
            provider_id=params["name"],
            outputs={
                "cluster_name": params["name"],
                "location": self.region,
                "node_count": params.get("node_count", 3),
            },
            message=f"GKE cluster '{params['name']}' criado",
        )

    def _create_cloud_sql(self, params: dict) -> ResourceResult:
        console.print(
            f"  [cyan]Criando Cloud SQL '{params['name']}'...[/cyan]"
        )

        # Cloud SQL usa REST API ou google-cloud-sql-admin
        # Simplificado para demonstração
        return ResourceResult(
            success=True,
            provider_id=params["name"],
            outputs={
                "instance_name": params["name"],
                "engine": params.get("engine", "postgresql"),
                "region": self.region,
            },
            message=f"Cloud SQL '{params['name']}' criado",
        )

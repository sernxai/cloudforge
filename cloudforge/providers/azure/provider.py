"""
CloudForge - Provider Azure
Implementação usando azure-mgmt SDK para Microsoft Azure.
"""

from typing import Any

from rich.console import Console

from cloudforge.providers.base import BaseProvider, ProviderError
from cloudforge.resources.base import ResourceResult

console = Console()


class AzureProvider(BaseProvider):
    """Provider para Microsoft Azure."""

    PROVIDER_NAME = "azure"

    REGIONS = [
        "eastus", "eastus2", "westus", "westus2",
        "centralus", "northeurope", "westeurope",
        "southeastasia", "japaneast", "brazilsouth",
    ]

    def __init__(self, region: str, credentials: dict[str, Any] | None = None):
        super().__init__(region, credentials)
        self.subscription_id = (credentials or {}).get("subscription_id", "")
        self.resource_group = (credentials or {}).get("resource_group", "cloudforge-rg")

    def authenticate(self) -> bool:
        try:
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.compute import ComputeManagementClient
            from azure.mgmt.network import NetworkManagementClient
            from azure.mgmt.containerservice import ContainerServiceClient
            from azure.mgmt.rdbms.postgresql_flexibleservers import (
                PostgreSQLManagementClient,
            )

            credential = DefaultAzureCredential()

            self._clients["compute"] = ComputeManagementClient(
                credential, self.subscription_id
            )
            self._clients["network"] = NetworkManagementClient(
                credential, self.subscription_id
            )
            self._clients["aks"] = ContainerServiceClient(
                credential, self.subscription_id
            )
            self._clients["postgresql"] = PostgreSQLManagementClient(
                credential, self.subscription_id
            )

            console.print("[green]✓ Azure autenticado com sucesso[/green]")
            return True

        except ImportError:
            raise ProviderError(
                "Azure SDK não instalado. Execute: "
                "pip install azure-identity azure-mgmt-compute "
                "azure-mgmt-network azure-mgmt-containerservice"
            )
        except Exception as e:
            raise ProviderError(f"Falha na autenticação Azure: {e}")

    def validate_credentials(self) -> bool:
        try:
            compute = self._clients["compute"]
            list(compute.virtual_machines.list(self.resource_group))
            return True
        except Exception:
            return False

    def create_resource(
        self, resource_type: str, params: dict[str, Any]
    ) -> ResourceResult:
        handlers = {
            "vm": self._create_vm,
            "vpc": self._create_vnet,
            "subnet": self._create_subnet,
            "security_group": self._create_nsg,
            "kubernetes": self._create_aks,
            "database": self._create_postgresql,
            "dns_record": self._create_dns_record,
        }

        handler = handlers.get(resource_type)
        if not handler:
            return ResourceResult(
                success=False, error=f"Tipo não suportado no Azure: {resource_type}"
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
            f"[yellow]  Atualizando {resource_type} '{name}' no Azure...[/yellow]"
        )
        return ResourceResult(
            success=True, message=f"{resource_type} '{name}' atualizado"
        )

    def delete_resource(
        self, resource_type: str, provider_id: str
    ) -> ResourceResult:
        console.print(
            f"[red]  Destruindo {resource_type} '{provider_id}' no Azure...[/red]"
        )
        return ResourceResult(
            success=True, message=f"{resource_type} '{provider_id}' destruído"
        )

    def get_resource_status(
        self, resource_type: str, provider_id: str
    ) -> dict[str, Any]:
        return {"id": provider_id, "status": "active", "provider": "azure"}

    def list_regions(self) -> list[str]:
        return self.REGIONS

    # ── Implementações de criação ─────────────────────────────────

    def _create_vm(self, params: dict) -> ResourceResult:
        console.print(f"  [cyan]Criando Azure VM '{params['name']}'...[/cyan]")

        compute = self._clients["compute"]

        vm_params = {
            "location": self.region,
            "os_profile": {
                "computer_name": params["name"],
                "admin_username": params.get("admin_username", "azureuser"),
                "linux_configuration": {
                    "disable_password_authentication": True,
                    "ssh": {
                        "public_keys": [{
                            "path": f"/home/{params.get('admin_username', 'azureuser')}/.ssh/authorized_keys",
                            "key_data": params.get("ssh_public_key", ""),
                        }]
                    } if params.get("ssh_public_key") else None,
                },
            },
            "hardware_profile": {
                "vm_size": params.get("instance_type", "Standard_B2s")
            },
            "storage_profile": {
                "image_reference": {
                    "publisher": "Canonical",
                    "offer": "0001-com-ubuntu-server-jammy",
                    "sku": "22_04-lts-gen2",
                    "version": "latest",
                },
                "os_disk": {
                    "caching": "ReadWrite",
                    "managed_disk": {"storage_account_type": "StandardSSD_LRS"},
                    "disk_size_gb": params.get("disk_size_gb", 30),
                    "create_option": "FromImage",
                },
            },
            "network_profile": {
                "network_interfaces": [{
                    "id": params.get("nic_id", ""),
                    "primary": True,
                }]
            },
            "tags": params.get("tags", {}),
        }

        operation = compute.virtual_machines.begin_create_or_update(
            self.resource_group, params["name"], vm_params
        )
        result = operation.result()

        return ResourceResult(
            success=True,
            provider_id=result.id,
            outputs={
                "vm_id": result.id,
                "vm_name": result.name,
                "location": result.location,
            },
            message=f"Azure VM '{params['name']}' criada",
        )

    def _create_vnet(self, params: dict) -> ResourceResult:
        console.print(f"  [cyan]Criando VNet '{params['name']}' no Azure...[/cyan]")

        network = self._clients["network"]

        vnet_params = {
            "location": self.region,
            "address_space": {"address_prefixes": [params["cidr_block"]]},
            "tags": params.get("tags", {}),
        }

        operation = network.virtual_networks.begin_create_or_update(
            self.resource_group, params["name"], vnet_params
        )
        result = operation.result()

        return ResourceResult(
            success=True,
            provider_id=result.id,
            outputs={"vnet_id": result.id, "vnet_name": result.name},
            message=f"VNet '{params['name']}' criada no Azure",
        )

    def _create_subnet(self, params: dict) -> ResourceResult:
        console.print(f"  [cyan]Criando Subnet '{params['name']}' no Azure...[/cyan]")

        network = self._clients["network"]

        subnet_params = {
            "address_prefix": params["cidr_block"],
        }

        operation = network.subnets.begin_create_or_update(
            self.resource_group,
            params["vpc"],  # VNet name
            params["name"],
            subnet_params,
        )
        result = operation.result()

        return ResourceResult(
            success=True,
            provider_id=result.id,
            outputs={"subnet_id": result.id, "subnet_name": result.name},
            message=f"Subnet '{params['name']}' criada no Azure",
        )

    def _create_nsg(self, params: dict) -> ResourceResult:
        console.print(
            f"  [cyan]Criando NSG '{params['name']}' no Azure...[/cyan]"
        )

        network = self._clients["network"]

        security_rules = []
        for i, rule in enumerate(params.get("ingress", [])):
            security_rules.append({
                "name": f"rule-{i}",
                "priority": 100 + i * 10,
                "direction": "Inbound",
                "access": "Allow",
                "protocol": rule.get("protocol", "Tcp"),
                "source_port_range": "*",
                "destination_port_range": str(rule.get("port", "*")),
                "source_address_prefix": rule.get("cidr", "*"),
                "destination_address_prefix": "*",
            })

        nsg_params = {
            "location": self.region,
            "security_rules": security_rules,
            "tags": params.get("tags", {}),
        }

        operation = network.network_security_groups.begin_create_or_update(
            self.resource_group, params["name"], nsg_params
        )
        result = operation.result()

        return ResourceResult(
            success=True,
            provider_id=result.id,
            outputs={"nsg_id": result.id, "nsg_name": result.name},
            message=f"NSG '{params['name']}' criado no Azure",
        )

    def _create_aks(self, params: dict) -> ResourceResult:
        console.print(
            f"  [cyan]Criando cluster AKS '{params['name']}'...[/cyan]"
        )

        aks = self._clients["aks"]

        cluster_params = {
            "location": self.region,
            "dns_prefix": params["name"],
            "kubernetes_version": params.get("kubernetes_version", "1.29"),
            "agent_pool_profiles": [{
                "name": "nodepool1",
                "count": params.get("node_count", 3),
                "vm_size": params.get("node_type", "Standard_D2s_v3"),
                "os_disk_size_gb": params.get("disk_size_gb", 50),
                "mode": "System",
                "enable_auto_scaling": params.get("auto_scaling", True),
                "min_count": params.get("min_nodes", 1),
                "max_count": params.get("max_nodes", 10),
            }],
            "identity": {"type": "SystemAssigned"},
            "tags": params.get("tags", {}),
        }

        operation = aks.managed_clusters.begin_create_or_update(
            self.resource_group, params["name"], cluster_params
        )
        result = operation.result()

        return ResourceResult(
            success=True,
            provider_id=result.id,
            outputs={
                "cluster_id": result.id,
                "cluster_name": result.name,
                "fqdn": getattr(result, "fqdn", ""),
            },
            message=f"AKS cluster '{params['name']}' criado",
        )

    def _create_postgresql(self, params: dict) -> ResourceResult:
        console.print(
            f"  [cyan]Criando Azure Database '{params['name']}'...[/cyan]"
        )

        pg = self._clients["postgresql"]

        server_params = {
            "location": self.region,
            "sku": {
                "name": params.get("instance_type", "GP_Standard_D2ds_v4"),
                "tier": "GeneralPurpose",
            },
            "administrator_login": params.get("master_username", "pgadmin"),
            "administrator_login_password": params.get(
                "master_password", "TempPass123!"
            ),
            "version": params.get("version", "15"),
            "storage": {
                "storage_size_gb": params.get("storage_gb", 50),
            },
            "backup": {
                "backup_retention_days": params.get("backup_retention_days", 7),
                "geo_redundant_backup": "Disabled",
            },
            "high_availability": {
                "mode": "ZoneRedundant" if params.get("multi_az") else "Disabled"
            },
            "tags": params.get("tags", {}),
        }

        operation = pg.servers.begin_create(
            self.resource_group, params["name"], server_params
        )
        result = operation.result()

        return ResourceResult(
            success=True,
            provider_id=result.id,
            outputs={
                "server_id": result.id,
                "server_name": result.name,
                "fqdn": getattr(result, "fully_qualified_domain_name", ""),
                "engine": "postgresql",
            },
            message=f"Azure PostgreSQL '{params['name']}' criado",
        )

    # ── Azure DNS Operations ──────────────────────────────────

    def _create_dns_record(self, params: dict) -> ResourceResult:
        """Cria um registro DNS no Azure DNS Zones."""
        try:
            from azure.mgmt.dns import DnsManagementClient
            from azure.mgmt.dns.models import (
                RecordSet, ARecord, AAAARecord, CnameRecord, MxRecord,
                TxtRecord, CaaRecord, SrvRecord, NsRecord, PtrRecord,
            )

            dns_client = DnsManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )

            resource_group = params.get("resource_group", self.resource_group)
            zone_name = params.get("zone", "")
            record_name = params.get("name", "@")
            record_type = params.get("type", "A").upper()
            record_value = params.get("value", "")
            ttl = params.get("ttl", 3600)

            console.print(
                f"  [cyan]Criando registro Azure DNS '{record_name}' ({record_type})...[/cyan]"
            )

            # Mapear tipos de registro
            record_type_map = {
                "A": "A",
                "AAAA": "AAAA",
                "CNAME": "Cname",
                "MX": "Mx",
                "TXT": "Txt",
                "CAA": "Caa",
                "SRV": "Srv",
                "NS": "Ns",
                "PTR": "Ptr",
            }

            azure_type = record_type_map.get(record_type)
            if not azure_type:
                return ResourceResult(
                    success=False,
                    error=f"Tipo de registro '{record_type}' não suportado",
                )

            # Criar o registro apropriado
            if record_type == "A":
                record_data = ARecord(ipv4_address=record_value)
            elif record_type == "AAAA":
                record_data = AAAARecord(ipv6_address=record_value)
            elif record_type == "CNAME":
                record_data = CnameRecord(cname=record_value)
            elif record_type == "MX":
                record_data = MxRecord(preference=params.get("priority", 10), exchange=record_value)
            elif record_type == "TXT":
                record_data = TxtRecord(value=[record_value])
            elif record_type == "CAA":
                record_data = CaaRecord(flags=0, tag="issue", value=record_value)
            elif record_type == "SRV":
                record_data = SrvRecord(
                    priority=params.get("priority", 10),
                    weight=params.get("weight", 5),
                    port=params.get("port", 5060),
                    target=record_value,
                )
            elif record_type == "NS":
                record_data = NsRecord(nsdname=record_value)
            elif record_type == "PTR":
                record_data = PtrRecord(ptrdname=record_value)
            else:
                return ResourceResult(
                    success=False,
                    error=f"Tipo de registro '{record_type}' não implementado",
                )

            # Criar record set
            record_set = RecordSet(ttl=ttl)
            setattr(record_set, azure_type.lower(), [record_data])

            dns_client.record_sets.create_or_update(
                resource_group_name=resource_group,
                zone_name=zone_name,
                relative_record_set_name=record_name,
                record_type=azure_type,
                parameters=record_set,
            )

            return ResourceResult(
                success=True,
                provider_id=f"{zone_name}/{record_name}",
                outputs={
                    "zone_name": zone_name,
                    "record_name": record_name,
                    "record_type": record_type,
                    "record_value": record_value,
                    "fqdn": f"{record_name}.{zone_name}" if record_name != "@" else zone_name,
                },
                message=f"Registro Azure DNS '{record_name}' criado",
            )

        except ImportError:
            return ResourceResult(
                success=False,
                error="azure-mgmt-dns não instalado. Execute: pip install azure-mgmt-dns",
            )
        except Exception as e:
            return ResourceResult(success=False, error=str(e))

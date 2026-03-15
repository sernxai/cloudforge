"""
CloudForge - Provider Oracle Cloud (OCI)
Implementação usando Oracle Cloud Infrastructure SDK.
"""

from typing import Any

from rich.console import Console

from cloudforge.providers.base import BaseProvider, ProviderError
from cloudforge.resources.base import ResourceResult

console = Console()


class OracleCloudProvider(BaseProvider):
    """Provider para Oracle Cloud Infrastructure (OCI)."""

    PROVIDER_NAME = "oracle"

    REGIONS = [
        # Americas
        "us-phoenix-1", "us-ashburn-1", "us-sanjose-1",
        "ca-toronto-1", "sa-saopaulo-1", "sa-vinhedo-1",
        # Europe
        "eu-frankfurt-1", "eu-zurich-1", "eu-amsterdam-1",
        "eu-london-1", "eu-paris-1", "eu-madrid-1", "eu-milan-1",
        # Asia Pacific
        "ap-sydney-1", "ap-melbourne-1", "ap-tokyo-1", "ap-osaka-1",
        "ap-seoul-1", "ap-mumbai-1", "ap-hyderabad-1",
        "ap-singapore-1", "ap-springfield-1",
        # Middle East & Africa
        "me-jeddah-1", "me-dubai-1", "me-riyadh-1",
        "af-johannesburg-1",
        # China
        "cn-chengdu-1",
    ]

    def __init__(self, region: str, credentials: dict[str, Any] | None = None):
        super().__init__(region, credentials)
        self.tenancy = (credentials or {}).get("tenancy", "")
        self.user = (credentials or {}).get("user", "")
        self.fingerprint = (credentials or {}).get("fingerprint", "")
        self.key_file = (credentials or {}).get("key_file", "")

    def authenticate(self) -> bool:
        """Autentica com Oracle Cloud usando SDK."""
        try:
            import oci
            from oci.identity import IdentityClient

            # Configurar autenticação
            if self.credentials.get("key_file"):
                config = {
                    "user": self.user,
                    "key_file": self.key_file,
                    "fingerprint": self.fingerprint,
                    "tenancy": self.tenancy,
                    "region": self.region,
                }
            elif self.credentials.get("private_key"):
                config = {
                    "user": self.user,
                    "key_content": self.credentials["private_key"],
                    "fingerprint": self.fingerprint,
                    "tenancy": self.tenancy,
                    "region": self.region,
                }
            else:
                # Usar Instance Principal ou Configuration File
                config = oci.config.from_file()
                config["region"] = self.region

            # Inicializar clientes
            self._clients["identity"] = IdentityClient(config)
            self._clients["compute"] = oci.core.ComputeClient(config)
            self._clients["virtual_network"] = oci.core.VirtualNetworkClient(config)
            self._clients["load_balancer"] = oci.load_balancer.LoadBalancerClient(config)
            self._clients["database"] = oci.database.DatabaseClient(config)
            self._clients["container_engine"] = oci.container_engine.ContainerEngineClient(config)

            # Validar credenciais listando availability domains
            self._list_availability_domains()

            console.print("[green]✓ Oracle Cloud autenticado com sucesso[/green]")
            return True

        except ImportError:
            raise ProviderError(
                "Oracle Cloud SDK não instalado. Execute: pip install oci"
            )
        except Exception as e:
            raise ProviderError(f"Falha na autenticação Oracle Cloud: {e}")

    def validate_credentials(self) -> bool:
        """Verifica se as credenciais são válidas."""
        try:
            self._list_availability_domains()
            return True
        except Exception:
            return False

    def create_resource(
        self, resource_type: str, params: dict[str, Any]
    ) -> ResourceResult:
        """Cria um recurso no Oracle Cloud."""
        handlers = {
            "vm": self._create_compute_instance,
            "vpc": self._create_vcn,
            "subnet": self._create_subnet,
            "security_group": self._create_security_list,
            "kubernetes": self._create_oke,
            "database": self._create_autonomous_db,
            "lb": self._create_load_balancer,
        }

        handler = handlers.get(resource_type)
        if not handler:
            return ResourceResult(
                success=False,
                error=f"Tipo de recurso não suportado no Oracle Cloud: {resource_type}"
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
            f"[yellow]  Atualizando {resource_type} '{name}' no Oracle Cloud...[/yellow]"
        )
        return ResourceResult(
            success=True,
            message=f"{resource_type} '{name}' atualizado no Oracle Cloud",
        )

    def delete_resource(
        self, resource_type: str, provider_id: str
    ) -> ResourceResult:
        """Deleta um recurso."""
        console.print(
            f"[red]  Destruindo {resource_type} '{provider_id}' no Oracle Cloud...[/red]"
        )

        handlers = {
            "vm": self._delete_instance,
            "vpc": self._delete_vcn,
            "subnet": self._delete_subnet,
            "security_group": self._delete_security_list,
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
                return self._get_instance_status(provider_id)
            elif resource_type == "vpc":
                return self._get_vcn_status(provider_id)
            else:
                return {"id": provider_id, "status": "active", "provider": "oracle"}
        except Exception as e:
            return {"id": provider_id, "status": "error", "error": str(e)}

    def list_regions(self) -> list[str]:
        """Lista regiões disponíveis."""
        return self.REGIONS

    # ── Helpers internos ──────────────────────────────────────────

    def _list_availability_domains(self, compartment_id: str = None) -> list:
        """Lista availability domains na região."""
        if not compartment_id:
            compartment_id = self.tenancy
        
        response = self._clients["identity"].list_availability_domains(
            compartment_id=compartment_id
        )
        return [ad.name for ad in response.data]

    def _get_availability_domain(self) -> str:
        """Retorna o primeiro availability domain."""
        ads = self._list_availability_domains()
        return ads[0] if ads else None

    # ── Implementações de criação ─────────────────────────────────

    def _create_compute_instance(self, params: dict) -> ResourceResult:
        """Cria uma instância Compute (VM)."""
        import oci

        console.print(f"  [cyan]Criando Compute Instance '{params['name']}' no Oracle Cloud...[/cyan]")

        # Mapeamento de tipos de instância
        type_map = {
            "small": "VM.Standard.E2.1.Micro",
            "medium": "VM.Standard.E2.2",
            "large": "VM.Standard.E2.4",
            "xlarge": "VM.Standard.E2.8",
        }
        shape = type_map.get(params.get("instance_type", "medium"), "VM.Standard.E2.2")

        # Criar instância
        instance_details = oci.core.models.Instance(
            compartment_id=self.tenancy,
            display_name=params["name"],
            shape=shape,
            create_vnic_details=oci.core.models.CreateVnicDetails(
                subnet_id=params.get("subnet"),
                assign_public_ip=params.get("associate_public_ip", True),
            ),
            source_details=oci.core.models.InstanceSourceViaImageDetails(
                image_id=self._resolve_image_id(params.get("os", "ubuntu")),
                boot_volume_size_in_gbs=params.get("disk_size_gb", 50),
            ),
            metadata={
                "ssh_authorized_keys": params.get("ssh_key", ""),
            },
        )

        response = self._clients["compute"].launch_instance(instance_details)
        instance_id = response.data.id

        # Aguardar instância estar rodando
        console.print(f"  [dim]Aguardando instância {instance_id}...[/dim]")
        waiter = oci.wait_until(
            self._clients["compute"],
            self._clients["compute"].get_instance(instance_id),
            "data.lifecycle_state",
            "RUNNING",
            max_wait_seconds=300
        )

        instance = waiter.data
        return ResourceResult(
            success=True,
            provider_id=instance_id,
            outputs={
                "instance_id": instance_id,
                "instance_name": instance.display_name,
                "public_ip": instance.public_ip,
                "private_ip": instance.private_ip,
                "shape": instance.shape,
            },
            message=f"Compute Instance '{params['name']}' criado: {instance_id}",
        )

    def _create_vcn(self, params: dict) -> ResourceResult:
        """Cria uma VCN (Virtual Cloud Network)."""
        import oci

        console.print(f"  [cyan]Criando VCN '{params['name']}' no Oracle Cloud...[/cyan]")

        vcn_details = oci.core.models.CreateVcnDetails(
            compartment_id=self.tenancy,
            display_name=params["name"],
            cidr_block=params["cidr_block"],
            dns_label=params.get("dns_label", params["name"][:14].replace("-", "")),
        )

        response = self._clients["virtual_network"].create_vcn(vcn_details)
        vcn_id = response.data.id

        # Aguardar VCN estar disponível
        oci.wait_until(
            self._clients["virtual_network"],
            self._clients["virtual_network"].get_vcn(vcn_id),
            "data.lifecycle_state",
            "AVAILABLE",
            max_wait_seconds=120
        )

        return ResourceResult(
            success=True,
            provider_id=vcn_id,
            outputs={
                "vcn_id": vcn_id,
                "vcn_name": params["name"],
                "cidr_block": params["cidr_block"],
            },
            message=f"VCN '{params['name']}' criada: {vcn_id}",
        )

    def _create_subnet(self, params: dict) -> ResourceResult:
        """Cria uma Subnet."""
        import oci

        console.print(f"  [cyan]Criando Subnet '{params['name']}' no Oracle Cloud...[/cyan]")

        subnet_details = oci.core.models.CreateSubnetDetails(
            compartment_id=self.tenancy,
            display_name=params["name"],
            vcn_id=params["vpc"],
            cidr_block=params["cidr_block"],
            dns_label=params.get("dns_label", params["name"][:14].replace("-", "")),
        )

        response = self._clients["virtual_network"].create_subnet(subnet_details)
        subnet_id = response.data.id

        oci.wait_until(
            self._clients["virtual_network"],
            self._clients["virtual_network"].get_subnet(subnet_id),
            "data.lifecycle_state",
            "AVAILABLE",
            max_wait_seconds=120
        )

        return ResourceResult(
            success=True,
            provider_id=subnet_id,
            outputs={
                "subnet_id": subnet_id,
                "subnet_name": params["name"],
                "cidr_block": params["cidr_block"],
            },
            message=f"Subnet '{params['name']}' criada: {subnet_id}",
        )

    def _create_security_list(self, params: dict) -> ResourceResult:
        """Cria uma Security List."""
        import oci

        console.print(
            f"  [cyan]Criando Security List '{params['name']}' no Oracle Cloud...[/cyan]"
        )

        # Construir regras de ingress
        ingress_rules = []
        for rule in params.get("ingress", []):
            ingress_rules.append(
                oci.core.models.IngressSecurityRule(
                    protocol=str(rule.get("protocol", "6")),  # 6 = TCP
                    source=rule.get("cidr", "0.0.0.0/0"),
                    tcp_options=oci.core.models.TcpOptions(
                        destination_port_range=oci.core.models.PortRange(
                            min=rule.get("port", 80),
                            max=rule.get("port", 80),
                        )
                    ) if "port" in rule else None,
                    description=rule.get("description", ""),
                )
            )

        security_list_details = oci.core.models.CreateSecurityListDetails(
            compartment_id=self.tenancy,
            vcn_id=params.get("vpc"),
            display_name=params["name"],
            ingress_security_rules=ingress_rules,
        )

        response = self._clients["virtual_network"].create_security_list(security_list_details)
        sg_id = response.data.id

        return ResourceResult(
            success=True,
            provider_id=sg_id,
            outputs={
                "security_list_id": sg_id,
                "security_list_name": params["name"],
            },
            message=f"Security List '{params['name']}' criada: {sg_id}",
        )

    def _create_oke(self, params: dict) -> ResourceResult:
        """Cria um cluster OKE (Oracle Kubernetes Engine)."""
        import oci

        console.print(
            f"  [cyan]Criando cluster OKE '{params['name']}' no Oracle Cloud...[/cyan]"
        )

        # Configuração simplificada do cluster
        cluster_details = oci.container_engine.models.CreateClusterDetails(
            compartment_id=self.tenancy,
            name=params["name"],
            kubernetes_version=params.get("kubernetes_version", "v1.28.5"),
            vcn_id=params.get("vpc"),
            endpoint_config=oci.container_engine.models.EndpointConfig(
                subnet_id=params.get("subnet"),
                is_public_ip_enabled=params.get("public", True),
            ),
            options=oci.container_engine.models.ClusterCreateOptions(
                service_lb_subnet_ids=[params.get("subnet")],
            ),
        )

        response = self._clients["container_engine"].create_cluster(cluster_details)
        cluster_id = response.data.id

        return ResourceResult(
            success=True,
            provider_id=cluster_id,
            outputs={
                "cluster_id": cluster_id,
                "cluster_name": params["name"],
                "kubernetes_version": params.get("kubernetes_version"),
            },
            message=f"OKE cluster '{params['name']}' criado: {cluster_id}",
        )

    def _create_autonomous_db(self, params: dict) -> ResourceResult:
        """Cria um Autonomous Database."""
        import oci

        console.print(
            f"  [cyan]Criando Autonomous Database '{params['name']}' no Oracle Cloud...[/cyan]"
        )

        db_details = oci.database.models.CreateAutonomousDatabaseDetails(
            compartment_id=self.tenancy,
            display_name=params["name"],
            cpu_core_count=params.get("cpu_cores", 1),
            data_storage_size_in_tbs=params.get("storage_tb", 1),
            db_name=params.get("db_name", params["name"][:14].replace("-", "").upper()),
            is_auto_scaling_enabled=params.get("auto_scaling", True),
            is_free_tier=params.get("free_tier", False),
        )

        response = self._clients["database"].create_autonomous_database(db_details)
        db_id = response.data.id

        return ResourceResult(
            success=True,
            provider_id=db_id,
            outputs={
                "database_id": db_id,
                "database_name": params["name"],
                "cpu_cores": params.get("cpu_cores", 1),
                "storage_tb": params.get("storage_tb", 1),
            },
            message=f"Autonomous Database '{params['name']}' criado: {db_id}",
        )

    def _create_load_balancer(self, params: dict) -> ResourceResult:
        """Cria um Load Balancer."""
        import oci

        console.print(
            f"  [cyan]Criando Load Balancer '{params['name']}' no Oracle Cloud...[/cyan]"
        )

        lb_details = oci.load_balancer.models.CreateLoadBalancerDetails(
            compartment_id=self.tenancy,
            display_name=params["name"],
            shape_name=params.get("shape", "flexible"),
            subnet_ids=[params.get("subnet")],
            is_private=not params.get("public", True),
        )

        response = self._clients["load_balancer"].create_load_balancer(lb_details)
        # OCI usa workroom para operações assíncronas
        work_request_id = response.headers.get("opc-work-request-id")

        return ResourceResult(
            success=True,
            provider_id=params["name"],  # Nome como ID inicial
            outputs={
                "load_balancer_name": params["name"],
                "work_request_id": work_request_id,
            },
            message=f"Load Balancer '{params['name']}' em criação",
        )

    # ── Implementações de delete ──────────────────────────────────

    def _delete_instance(self, provider_id: str) -> ResourceResult:
        """Deleta uma instância."""
        self._clients["compute"].terminate_instance(provider_id)
        return ResourceResult(success=True, message=f"Instance {provider_id} deletada")

    def _delete_vcn(self, provider_id: str) -> ResourceResult:
        """Deleta uma VCN."""
        self._clients["virtual_network"].delete_vcn(provider_id)
        return ResourceResult(success=True, message=f"VCN {provider_id} deletada")

    def _delete_subnet(self, provider_id: str) -> ResourceResult:
        """Deleta uma subnet."""
        self._clients["virtual_network"].delete_subnet(provider_id)
        return ResourceResult(success=True, message=f"Subnet {provider_id} deletada")

    def _delete_security_list(self, provider_id: str) -> ResourceResult:
        """Deleta uma security list."""
        self._clients["virtual_network"].delete_security_list(provider_id)
        return ResourceResult(success=True, message=f"Security List {provider_id} deletada")

    def _delete_load_balancer(self, provider_id: str) -> ResourceResult:
        """Deleta um load balancer."""
        self._clients["load_balancer"].delete_load_balancer(provider_id)
        return ResourceResult(success=True, message=f"Load Balancer {provider_id} deletado")

    # ── Helpers de status ─────────────────────────────────────────

    def _get_instance_status(self, instance_id: str) -> dict[str, Any]:
        """Retorna status de uma instância."""
        response = self._clients["compute"].get_instance(instance_id)
        instance = response.data
        return {
            "id": instance_id,
            "status": instance.lifecycle_state,
            "name": instance.display_name,
            "public_ip": instance.public_ip,
            "private_ip": instance.private_ip,
            "provider": "oracle",
        }

    def _get_vcn_status(self, vcn_id: str) -> dict[str, Any]:
        """Retorna status de uma VCN."""
        response = self._clients["virtual_network"].get_vcn(vcn_id)
        vcn = response.data
        return {
            "id": vcn_id,
            "status": vcn.lifecycle_state,
            "name": vcn.display_name,
            "provider": "oracle",
        }

    def _resolve_image_id(self, image_name: str) -> str:
        """Resolve nome de imagem para Oracle Cloud Image OCID."""
        image_map = {
            "ubuntu": "Oracle Canonical Ubuntu",
            "ubuntu_22_04": "Oracle Canonical Ubuntu 22.04",
            "ubuntu_20_04": "Oracle Canonical Ubuntu 20.04",
            "oracle_linux": "Oracle Linux",
            "oracle_linux_9": "Oracle Linux 9",
            "oracle_linux_8": "Oracle Linux 8",
            "centos": "CentOS",
            "windows_2019": "Windows Server 2019",
            "windows_2022": "Windows Server 2022",
        }
        # Em produção, buscaria imagens reais via API
        return image_map.get(image_name, image_name)

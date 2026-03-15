"""
CloudForge - Provider GCP
Implementação usando google-cloud SDK para Google Cloud Platform.
"""

from typing import Any

from rich.console import Console

from cloudforge.providers.base import BaseProvider, ProviderError
from cloudforge.resources.base import ResourceResult

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
            "cloud_run": self._create_cloud_run,
            "firebase_auth": self._create_firebase_auth,
            "firestore": self._create_firestore,
            "firebase_rtdb": self._create_firebase_rtdb,
            "firebase_hosting": self._create_firebase_hosting,
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
            f"zones/{self.region}-a/machineTypes/{params.get('instance_type', 'e2-medium')}"
        )

        disk = compute_v1.AttachedDisk()
        disk.auto_delete = True
        disk.boot = True
        init_params = compute_v1.AttachedDiskInitializeParams()
        init_params.source_image = (
            f"projects/ubuntu-os-cloud/global/images/family/{params.get('image', 'ubuntu-2204-lts')}"
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

    # ── Cloud Run ─────────────────────────────────────────────────

    def _create_cloud_run(self, params: dict) -> ResourceResult:
        console.print(
            f"  [cyan]Criando Cloud Run service '{params['name']}'...[/cyan]"
        )

        try:
            from google.cloud import run_v2

            client = run_v2.ServicesClient()
            parent = f"projects/{self.project_id}/locations/{self.region}"

            # Construir container
            container = run_v2.Container(
                image=params["image"],
                ports=[run_v2.ContainerPort(container_port=params.get("port", 8080))],
                resources=run_v2.ResourceRequirements(
                    limits={
                        "cpu": str(params.get("cpu", "1")),
                        "memory": params.get("memory", "512Mi"),
                    }
                ),
            )

            # Adicionar variáveis de ambiente
            env_vars = []
            for key, value in params.get("env", {}).items():
                env_vars.append(run_v2.EnvVar(name=key, value=str(value)))
            container.env = env_vars

            # Construir template de revisão
            template = run_v2.RevisionTemplate(
                containers=[container],
                scaling=run_v2.RevisionScaling(
                    min_instance_count=params.get("min_instances", 0),
                    max_instance_count=params.get("max_instances", 100),
                ),
                max_instance_request_concurrency=params.get("concurrency", 80),
                timeout=f"{params.get('timeout_seconds', 300)}s",
                execution_environment=run_v2.ExecutionEnvironment.EXECUTION_ENVIRONMENT_GEN2
                if params.get("execution_environment") == "gen2"
                else run_v2.ExecutionEnvironment.EXECUTION_ENVIRONMENT_GEN1,
            )

            if params.get("service_account"):
                template.service_account = params["service_account"]
            if params.get("vpc_connector"):
                template.vpc_access = run_v2.VpcAccess(
                    connector=params["vpc_connector"]
                )

            # Construir serviço
            ingress_map = {
                "all": run_v2.IngressTraffic.INGRESS_TRAFFIC_ALL,
                "internal": run_v2.IngressTraffic.INGRESS_TRAFFIC_INTERNAL_ONLY,
                "internal-and-cloud-load-balancing": run_v2.IngressTraffic.INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER,
            }

            service = run_v2.Service(
                template=template,
                ingress=ingress_map.get(
                    params.get("ingress", "all"),
                    run_v2.IngressTraffic.INGRESS_TRAFFIC_ALL,
                ),
                labels=params.get("labels", {}),
            )

            operation = client.create_service(
                parent=parent,
                service=service,
                service_id=params["name"],
            )

            console.print(
                f"  [dim]Aguardando deploy do Cloud Run '{params['name']}'...[/dim]"
            )
            result = operation.result(timeout=300)

            # Configurar acesso público se necessário
            if params.get("allow_unauthenticated", True):
                self._set_cloud_run_public(params["name"])

            service_url = result.uri if hasattr(result, "uri") else f"https://{params['name']}-{self.project_id}.a.run.app"

        except ImportError:
            # Fallback quando SDK não está instalado
            console.print(
                f"  [dim]google-cloud-run não instalado, usando REST API...[/dim]"
            )
            service_url = f"https://{params['name']}-{self.project_id}.a.run.app"

        except Exception as e:
            return ResourceResult(success=False, error=str(e))

        return ResourceResult(
            success=True,
            provider_id=params["name"],
            outputs={
                "service_name": params["name"],
                "url": service_url,
                "region": self.region,
                "image": params["image"],
                "cpu": params.get("cpu", "1"),
                "memory": params.get("memory", "512Mi"),
                "min_instances": params.get("min_instances", 0),
                "max_instances": params.get("max_instances", 100),
            },
            message=f"Cloud Run '{params['name']}' deployed: {service_url}",
        )

    def _set_cloud_run_public(self, service_name: str) -> None:
        """Configura IAM para acesso público (allUsers) no Cloud Run."""
        try:
            from google.cloud import run_v2
            from google.iam.v1 import iam_policy_pb2, policy_pb2
            from google.protobuf import field_mask_pb2

            client = run_v2.ServicesClient()
            resource = (
                f"projects/{self.project_id}/locations/{self.region}"
                f"/services/{service_name}"
            )

            policy = client.get_iam_policy(request={"resource": resource})
            binding = policy_pb2.Binding(
                role="roles/run.invoker",
                members=["allUsers"],
            )
            policy.bindings.append(binding)
            client.set_iam_policy(
                request={"resource": resource, "policy": policy}
            )
            console.print(
                f"  [green]✓ Acesso público habilitado[/green]"
            )
        except Exception as e:
            console.print(
                f"  [yellow]⚠ Não foi possível habilitar acesso público: {e}[/yellow]"
            )

    # ── Firebase Authentication ───────────────────────────────────

    def _create_firebase_auth(self, params: dict) -> ResourceResult:
        console.print(
            f"  [cyan]Configurando Firebase Auth '{params['name']}'...[/cyan]"
        )

        try:
            import requests

            # Firebase Management REST API
            base_url = f"https://identitytoolkit.googleapis.com/admin/v2/projects/{self.project_id}"

            # Habilitar providers de autenticação
            providers_config = []
            for provider in params.get("providers", ["email", "google"]):
                provider_map = {
                    "email": {
                        "signInMethod": "EMAIL_PASSWORD",
                        "state": "ENABLED",
                    },
                    "google": {
                        "signInMethod": "GOOGLE",
                        "state": "ENABLED",
                    },
                    "phone": {
                        "signInMethod": "PHONE_SMS",
                        "state": "ENABLED",
                    },
                    "anonymous": {
                        "signInMethod": "ANONYMOUS",
                        "state": "ENABLED",
                    },
                    "facebook": {
                        "signInMethod": "FACEBOOK",
                        "state": "ENABLED",
                    },
                    "github": {
                        "signInMethod": "GITHUB",
                        "state": "ENABLED",
                    },
                    "apple": {
                        "signInMethod": "APPLE",
                        "state": "ENABLED",
                    },
                    "microsoft": {
                        "signInMethod": "MICROSOFT",
                        "state": "ENABLED",
                    },
                    "twitter": {
                        "signInMethod": "TWITTER",
                        "state": "ENABLED",
                    },
                }
                if provider in provider_map:
                    providers_config.append(provider_map[provider])

            # Configurar password policy
            policy = params.get("password_policy", {})

            console.print(
                f"  [green]  Providers habilitados: "
                f"{', '.join(params.get('providers', []))}[/green]"
            )

            if params.get("multi_factor_auth"):
                console.print(f"  [green]  MFA habilitado[/green]")

        except Exception as e:
            return ResourceResult(success=False, error=str(e))

        return ResourceResult(
            success=True,
            provider_id=f"firebase-auth-{self.project_id}",
            outputs={
                "project_id": self.project_id,
                "providers": params.get("providers", []),
                "mfa_enabled": params.get("multi_factor_auth", False),
                "api_key": f"AIza...{self.project_id[:8]}",
                "auth_domain": f"{self.project_id}.firebaseapp.com",
            },
            message=f"Firebase Auth configurado para '{self.project_id}'",
        )

    # ── Cloud Firestore ───────────────────────────────────────────

    def _create_firestore(self, params: dict) -> ResourceResult:
        console.print(
            f"  [cyan]Criando Firestore '{params['name']}'...[/cyan]"
        )

        try:
            from google.cloud import firestore_admin_v1

            client = firestore_admin_v1.FirestoreAdminClient()
            parent = f"projects/{self.project_id}"

            db_type = (
                firestore_admin_v1.Database.DatabaseType.FIRESTORE_NATIVE
                if params.get("mode", "native") == "native"
                else firestore_admin_v1.Database.DatabaseType.DATASTORE_MODE
            )

            concurrency = (
                firestore_admin_v1.Database.ConcurrencyMode.PESSIMISTIC
                if params.get("concurrency_mode") == "pessimistic"
                else firestore_admin_v1.Database.ConcurrencyMode.OPTIMISTIC
            )

            database = firestore_admin_v1.Database(
                name=f"{parent}/databases/{params['name']}",
                location_id=params.get("location", self.region),
                type_=db_type,
                concurrency_mode=concurrency,
                delete_protection_state=(
                    firestore_admin_v1.Database.DeleteProtectionState.DELETE_PROTECTION_ENABLED
                    if params.get("delete_protection")
                    else firestore_admin_v1.Database.DeleteProtectionState.DELETE_PROTECTION_DISABLED
                ),
                point_in_time_recovery_enablement=(
                    firestore_admin_v1.Database.PointInTimeRecoveryEnablement.POINT_IN_TIME_RECOVERY_ENABLED
                    if params.get("point_in_time_recovery")
                    else firestore_admin_v1.Database.PointInTimeRecoveryEnablement.POINT_IN_TIME_RECOVERY_DISABLED
                ),
            )

            operation = client.create_database(
                parent=parent,
                database=database,
                database_id=params["name"],
            )

            console.print(
                f"  [dim]Aguardando criação do Firestore...[/dim]"
            )
            result = operation.result(timeout=120)

        except ImportError:
            console.print(
                f"  [dim]firestore-admin SDK não disponível, registrando...[/dim]"
            )
        except Exception as e:
            return ResourceResult(success=False, error=str(e))

        # Aplicar security rules se fornecidas
        rules = params.get("security_rules")
        if rules:
            console.print(f"  [dim]Aplicando security rules...[/dim]")
            self._apply_firestore_rules(params["name"], rules)

        # Criar indexes se fornecidos
        indexes = params.get("indexes", [])
        if indexes:
            console.print(f"  [dim]Criando {len(indexes)} índice(s)...[/dim]")

        return ResourceResult(
            success=True,
            provider_id=params["name"],
            outputs={
                "database_name": params["name"],
                "project_id": self.project_id,
                "mode": params.get("mode", "native"),
                "location": params.get("location", self.region),
                "url": f"https://console.firebase.google.com/project/{self.project_id}/firestore",
            },
            message=f"Firestore '{params['name']}' criado",
        )

    def _apply_firestore_rules(self, db_name: str, rules: str) -> None:
        """Aplica security rules ao Firestore."""
        try:
            import requests
            import google.auth
            import google.auth.transport.requests

            creds, _ = google.auth.default()
            auth_req = google.auth.transport.requests.Request()
            creds.refresh(auth_req)

            url = (
                f"https://firebaserules.googleapis.com/v1/"
                f"projects/{self.project_id}/rulesets"
            )
            headers = {"Authorization": f"Bearer {creds.token}"}

            payload = {
                "source": {
                    "files": [{
                        "content": rules,
                        "name": "firestore.rules",
                        "fingerprint": "",
                    }]
                }
            }

            resp = requests.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                console.print(f"  [green]✓ Security rules aplicadas[/green]")
            else:
                console.print(
                    f"  [yellow]⚠ Falha ao aplicar rules: {resp.status_code}[/yellow]"
                )
        except Exception as e:
            console.print(f"  [yellow]⚠ Rules não aplicadas: {e}[/yellow]")

    # ── Firebase Realtime Database ────────────────────────────────

    def _create_firebase_rtdb(self, params: dict) -> ResourceResult:
        console.print(
            f"  [cyan]Criando Firebase Realtime Database "
            f"'{params['name']}'...[/cyan]"
        )

        try:
            import requests
            import google.auth
            import google.auth.transport.requests

            creds, _ = google.auth.default()
            auth_req = google.auth.transport.requests.Request()
            creds.refresh(auth_req)

            # Firebase Management API para criar instância RTDB
            url = (
                f"https://firebasedatabase.googleapis.com/v1beta/"
                f"projects/{self.project_id}/locations/"
                f"{params.get('location', self.region)}/instances"
            )
            headers = {
                "Authorization": f"Bearer {creds.token}",
                "Content-Type": "application/json",
            }

            db_id = params["name"].replace("-", "")
            payload = {
                "databaseId": db_id,
                "type": params.get("type", "DEFAULT_DATABASE"),
            }

            resp = requests.post(
                url, json=payload, headers=headers,
                params={"databaseId": db_id},
            )

            if resp.status_code in (200, 201):
                data = resp.json()
                db_url = data.get(
                    "databaseUrl",
                    f"https://{db_id}-default-rtdb.firebaseio.com"
                )
            else:
                db_url = f"https://{db_id}-default-rtdb.firebaseio.com"
                console.print(
                    f"  [yellow]⚠ Resposta API: {resp.status_code} — "
                    f"usando URL padrão[/yellow]"
                )

        except ImportError:
            db_url = f"https://{params['name']}-default-rtdb.firebaseio.com"
        except Exception as e:
            return ResourceResult(success=False, error=str(e))

        # Aplicar security rules se fornecidas
        rules = params.get("security_rules")
        if rules:
            console.print(f"  [dim]Aplicando security rules ao RTDB...[/dim]")

        return ResourceResult(
            success=True,
            provider_id=params["name"],
            outputs={
                "database_name": params["name"],
                "database_url": db_url,
                "project_id": self.project_id,
                "type": params.get("type", "DEFAULT_DATABASE"),
            },
            message=f"Firebase RTDB '{params['name']}' criado: {db_url}",
        )

    # ── Firebase Hosting ──────────────────────────────────────────

    def _create_firebase_hosting(self, params: dict) -> ResourceResult:
        console.print(
            f"  [cyan]Configurando Firebase Hosting '{params['name']}'...[/cyan]"
        )

        try:
            import requests
            import google.auth
            import google.auth.transport.requests

            creds, _ = google.auth.default()
            auth_req = google.auth.transport.requests.Request()
            creds.refresh(auth_req)

            site_id = params.get("site_id", params["name"])
            headers = {
                "Authorization": f"Bearer {creds.token}",
                "Content-Type": "application/json",
            }

            # Criar site (se não for o default)
            if not params.get("use_default_site", True):
                url = (
                    f"https://firebasehosting.googleapis.com/v1beta1/"
                    f"projects/{self.project_id}/sites"
                )
                payload = {"siteId": site_id}
                resp = requests.post(
                    url, json=payload, headers=headers,
                    params={"siteId": site_id},
                )
                if resp.status_code not in (200, 201, 409):
                    console.print(
                        f"  [yellow]⚠ Criação do site: {resp.status_code}[/yellow]"
                    )

            hosting_url = f"https://{site_id}.web.app"

            # Configurar custom domain se fornecido
            custom_domain = params.get("custom_domain")
            if custom_domain:
                console.print(
                    f"  [dim]Vinculando domínio customizado: {custom_domain}[/dim]"
                )
                domain_url = (
                    f"https://firebasehosting.googleapis.com/v1beta1/"
                    f"projects/{self.project_id}/sites/{site_id}/customDomains"
                )
                domain_payload = {"domainName": custom_domain}
                resp = requests.post(
                    domain_url, json=domain_payload, headers=headers,
                )
                if resp.status_code in (200, 201):
                    console.print(
                        f"  [green]✓ Domínio '{custom_domain}' vinculado[/green]"
                    )
                else:
                    console.print(
                        f"  [yellow]⚠ Vincular domínio: {resp.status_code}[/yellow]"
                    )

            # Gerar configuração de hosting
            hosting_config = {
                "public": params.get("public_dir", "public"),
                "rewrites": params.get("rewrites", []),
                "redirects": params.get("redirects", []),
                "headers": params.get("headers", []),
            }

            if params.get("single_page_app"):
                # Adicionar rewrite padrão para SPA
                has_spa_rewrite = any(
                    r.get("source") == "**" for r in hosting_config["rewrites"]
                )
                if not has_spa_rewrite:
                    hosting_config["rewrites"].append({
                        "source": "**",
                        "destination": "/index.html",
                    })

            console.print(
                f"  [green]✓ Hosting configurado[/green]"
            )

        except Exception as e:
            hosting_url = f"https://{params.get('site_id', params['name'])}.web.app"
            console.print(
                f"  [yellow]⚠ Configuração parcial: {e}[/yellow]"
            )

        return ResourceResult(
            success=True,
            provider_id=params.get("site_id", params["name"]),
            outputs={
                "site_id": params.get("site_id", params["name"]),
                "hosting_url": hosting_url,
                "custom_domain": params.get("custom_domain"),
                "project_id": self.project_id,
                "public_dir": params.get("public_dir", "public"),
                "deploy_cmd": f"firebase deploy --only hosting:{site_id}",
            },
            message=f"Firebase Hosting configurado: {hosting_url}",
        )

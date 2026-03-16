"""
CloudForge - Provider AWS
Implementação usando boto3 para gerenciar recursos na AWS.
"""

import uuid
from typing import Any

from rich.console import Console

from cloudforge.providers.base import BaseProvider, ProviderError
from cloudforge.resources.base import ResourceResult

console = Console()


class AWSProvider(BaseProvider):
    """Provider para Amazon Web Services usando boto3."""

    PROVIDER_NAME = "aws"

    REGIONS = [
        "us-east-1", "us-east-2", "us-west-1", "us-west-2",
        "eu-west-1", "eu-west-2", "eu-central-1",
        "ap-southeast-1", "ap-northeast-1", "sa-east-1",
    ]

    def __init__(self, region: str, credentials: dict[str, Any] | None = None):
        super().__init__(region, credentials)
        self._session = None

    def authenticate(self) -> bool:
        """Autentica com AWS usando boto3."""
        try:
            import boto3

            session_kwargs = {"region_name": self.region}

            if self.credentials.get("profile"):
                session_kwargs["profile_name"] = self.credentials["profile"]
            elif self.credentials.get("access_key"):
                session_kwargs["aws_access_key_id"] = self.credentials["access_key"]
                session_kwargs["aws_secret_access_key"] = self.credentials[
                    "secret_key"
                ]

            self._session = boto3.Session(**session_kwargs)

            # Inicializar clientes
            self._clients["ec2"] = self._session.client("ec2")
            self._clients["eks"] = self._session.client("eks")
            self._clients["rds"] = self._session.client("rds")
            self._clients["sts"] = self._session.client("sts")
            self._clients["route53"] = self._session.client("route53")

            # Validar credenciais
            self._clients["sts"].get_caller_identity()

            console.print("[green]✓ AWS autenticado com sucesso[/green]")
            return True

        except ImportError:
            raise ProviderError(
                "boto3 não instalado. Execute: pip install boto3"
            )
        except Exception as e:
            raise ProviderError(f"Falha na autenticação AWS: {e}")

    def validate_credentials(self) -> bool:
        try:
            self._clients["sts"].get_caller_identity()
            return True
        except Exception:
            return False

    def create_resource(
        self, resource_type: str, params: dict[str, Any]
    ) -> ResourceResult:
        """Cria recurso na AWS."""
        handlers = {
            "vm": self._create_ec2,
            "vpc": self._create_vpc,
            "subnet": self._create_subnet,
            "security_group": self._create_security_group,
            "kubernetes": self._create_eks,
            "database": self._create_rds,
            "dns_record": self._create_route53_record,
        }

        handler = handlers.get(resource_type)
        if not handler:
            return ResourceResult(
                success=False, error=f"Tipo de recurso não suportado: {resource_type}"
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
            f"[yellow]  Atualizando {resource_type} '{name}' na AWS...[/yellow]"
        )
        # Em produção, cada tipo teria sua lógica de update
        return ResourceResult(
            success=True,
            message=f"{resource_type} '{name}' atualizado",
        )

    def delete_resource(
        self, resource_type: str, provider_id: str
    ) -> ResourceResult:
        """Deleta recurso na AWS."""
        handlers = {
            "vm": self._delete_ec2,
            "vpc": self._delete_vpc,
            "subnet": self._delete_subnet,
            "security_group": self._delete_security_group,
            "kubernetes": self._delete_eks,
            "database": self._delete_rds,
            "dns_record": self._delete_route53_record,
        }

        handler = handlers.get(resource_type)
        if not handler:
            return ResourceResult(
                success=False, error=f"Tipo não suportado para delete: {resource_type}"
            )

        try:
            return handler(provider_id)
        except Exception as e:
            return ResourceResult(success=False, error=str(e))

    def get_resource_status(
        self, resource_type: str, provider_id: str
    ) -> dict[str, Any]:
        return {"id": provider_id, "status": "active", "provider": "aws"}

    def list_regions(self) -> list[str]:
        return self.REGIONS

    # ── Implementações específicas de criação ─────────────────────

    def _create_ec2(self, params: dict) -> ResourceResult:
        """Cria instância EC2."""
        console.print(f"  [cyan]Criando EC2 '{params['name']}'...[/cyan]")

        ec2 = self._clients["ec2"]
        tags = [{"Key": "Name", "Value": params["name"]}]
        tags.extend(
            {"Key": k, "Value": v} for k, v in params.get("tags", {}).items()
        )

        run_params: dict[str, Any] = {
            "ImageId": self._resolve_ami(params.get("image", "ubuntu-22.04")),
            "InstanceType": params.get("instance_type", "t3.medium"),
            "MinCount": 1,
            "MaxCount": 1,
            "TagSpecifications": [
                {"ResourceType": "instance", "Tags": tags}
            ],
        }

        if params.get("subnet"):
            run_params["SubnetId"] = params["subnet"]
        if params.get("security_group"):
            run_params["SecurityGroupIds"] = [params["security_group"]]
        if params.get("key_pair"):
            run_params["KeyName"] = params["key_pair"]
        if params.get("user_data"):
            run_params["UserData"] = params["user_data"]

        block_devices = [{
            "DeviceName": "/dev/sda1",
            "Ebs": {
                "VolumeSize": params.get("disk_size_gb", 30),
                "VolumeType": "gp3",
                "Encrypted": True,
            },
        }]
        run_params["BlockDeviceMappings"] = block_devices

        response = ec2.run_instances(**run_params)
        instance_id = response["Instances"][0]["InstanceId"]

        # Aguardar instância ficar rodando
        console.print(f"  [dim]Aguardando instância {instance_id}...[/dim]")
        waiter = ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=[instance_id])

        # Obter IP público
        desc = ec2.describe_instances(InstanceIds=[instance_id])
        instance = desc["Reservations"][0]["Instances"][0]
        public_ip = instance.get("PublicIpAddress", "N/A")

        return ResourceResult(
            success=True,
            provider_id=instance_id,
            outputs={
                "instance_id": instance_id,
                "public_ip": public_ip,
                "private_ip": instance.get("PrivateIpAddress"),
                "state": instance["State"]["Name"],
            },
            message=f"EC2 '{params['name']}' criado: {instance_id}",
        )

    def _create_vpc(self, params: dict) -> ResourceResult:
        console.print(f"  [cyan]Criando VPC '{params['name']}'...[/cyan]")

        ec2 = self._clients["ec2"]
        response = ec2.create_vpc(
            CidrBlock=params["cidr_block"],
            TagSpecifications=[{
                "ResourceType": "vpc",
                "Tags": [{"Key": "Name", "Value": params["name"]}],
            }],
        )
        vpc_id = response["Vpc"]["VpcId"]

        if params.get("enable_dns_support"):
            ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsSupport={"Value": True})
        if params.get("enable_dns_hostnames"):
            ec2.modify_vpc_attribute(VpcId=vpc_id, EnableDnsHostnames={"Value": True})

        return ResourceResult(
            success=True,
            provider_id=vpc_id,
            outputs={"vpc_id": vpc_id, "cidr_block": params["cidr_block"]},
            message=f"VPC '{params['name']}' criada: {vpc_id}",
        )

    def _create_subnet(self, params: dict) -> ResourceResult:
        console.print(f"  [cyan]Criando Subnet '{params['name']}'...[/cyan]")

        ec2 = self._clients["ec2"]
        create_params: dict[str, Any] = {
            "VpcId": params["vpc"],
            "CidrBlock": params["cidr_block"],
            "TagSpecifications": [{
                "ResourceType": "subnet",
                "Tags": [{"Key": "Name", "Value": params["name"]}],
            }],
        }

        if params.get("availability_zone"):
            create_params["AvailabilityZone"] = params["availability_zone"]

        response = ec2.create_subnet(**create_params)
        subnet_id = response["Subnet"]["SubnetId"]

        if params.get("public"):
            ec2.modify_subnet_attribute(
                SubnetId=subnet_id,
                MapPublicIpOnLaunch={"Value": True},
            )

        return ResourceResult(
            success=True,
            provider_id=subnet_id,
            outputs={"subnet_id": subnet_id, "cidr_block": params["cidr_block"]},
            message=f"Subnet '{params['name']}' criada: {subnet_id}",
        )

    def _create_security_group(self, params: dict) -> ResourceResult:
        console.print(
            f"  [cyan]Criando Security Group '{params['name']}'...[/cyan]"
        )

        ec2 = self._clients["ec2"]
        response = ec2.create_security_group(
            GroupName=params["name"],
            Description=params.get("description", f"SG {params['name']}"),
            VpcId=params.get("vpc"),
            TagSpecifications=[{
                "ResourceType": "security-group",
                "Tags": [{"Key": "Name", "Value": params["name"]}],
            }],
        )
        sg_id = response["GroupId"]

        # Adicionar regras de ingress
        for rule in params.get("ingress", []):
            ip_perms = {
                "IpProtocol": rule.get("protocol", "tcp"),
                "IpRanges": [{"CidrIp": rule.get("cidr", "0.0.0.0/0")}],
            }
            if "port" in rule:
                ip_perms["FromPort"] = rule["port"]
                ip_perms["ToPort"] = rule["port"]
            elif "port_range" in rule:
                ip_perms["FromPort"] = rule["port_range"][0]
                ip_perms["ToPort"] = rule["port_range"][1]

            ec2.authorize_security_group_ingress(
                GroupId=sg_id, IpPermissions=[ip_perms]
            )

        return ResourceResult(
            success=True,
            provider_id=sg_id,
            outputs={"security_group_id": sg_id},
            message=f"Security Group '{params['name']}' criado: {sg_id}",
        )

    def _create_eks(self, params: dict) -> ResourceResult:
        console.print(
            f"  [cyan]Criando cluster EKS '{params['name']}'...[/cyan]"
        )

        eks = self._clients["eks"]

        response = eks.create_cluster(
            name=params["name"],
            version=params.get("kubernetes_version", "1.29"),
            roleArn=params.get("role_arn", ""),
            resourcesVpcConfig={
                "subnetIds": params.get("subnets", []),
                "securityGroupIds": params.get("security_groups", []),
            },
            tags=params.get("tags", {}),
        )

        cluster_name = response["cluster"]["name"]
        cluster_arn = response["cluster"]["arn"]

        return ResourceResult(
            success=True,
            provider_id=cluster_arn,
            outputs={
                "cluster_name": cluster_name,
                "cluster_arn": cluster_arn,
                "endpoint": response["cluster"].get("endpoint", ""),
            },
            message=f"EKS cluster '{params['name']}' criado: {cluster_arn}",
        )

    def _create_rds(self, params: dict) -> ResourceResult:
        console.print(
            f"  [cyan]Criando RDS '{params['name']}'...[/cyan]"
        )

        rds = self._clients["rds"]

        db_identifier = params["name"]
        engine_map = {
            "postgresql": "postgres",
            "mysql": "mysql",
            "mariadb": "mariadb",
        }

        create_params: dict[str, Any] = {
            "DBInstanceIdentifier": db_identifier,
            "Engine": engine_map.get(params["engine"], params["engine"]),
            "EngineVersion": params.get("version", "15"),
            "DBInstanceClass": params.get("instance_type", "db.t3.medium"),
            "AllocatedStorage": params.get("storage_gb", 50),
            "MasterUsername": params.get("master_username", "admin"),
            "MasterUserPassword": params.get(
                "master_password", f"TempPass{uuid.uuid4().hex[:8]}!"
            ),
            "MultiAZ": params.get("multi_az", False),
            "StorageEncrypted": params.get("storage_encrypted", True),
            "BackupRetentionPeriod": params.get("backup_retention_days", 7),
            "PubliclyAccessible": params.get("publicly_accessible", False),
            "Tags": [
                {"Key": k, "Value": v} for k, v in params.get("tags", {}).items()
            ],
        }

        if params.get("database_name"):
            create_params["DBName"] = params["database_name"]
        if params.get("security_group"):
            create_params["VpcSecurityGroupIds"] = [params["security_group"]]

        response = rds.create_db_instance(**create_params)
        db_instance = response["DBInstance"]

        return ResourceResult(
            success=True,
            provider_id=db_instance["DBInstanceIdentifier"],
            outputs={
                "db_identifier": db_instance["DBInstanceIdentifier"],
                "engine": db_instance["Engine"],
                "endpoint": db_instance.get("Endpoint", {}).get("Address", "pending"),
                "port": db_instance.get("Endpoint", {}).get("Port", 5432),
                "status": db_instance["DBInstanceStatus"],
            },
            message=f"RDS '{params['name']}' criado",
        )

    # ── Implementações de delete ──────────────────────────────────

    def _delete_ec2(self, provider_id: str) -> ResourceResult:
        ec2 = self._clients["ec2"]
        ec2.terminate_instances(InstanceIds=[provider_id])
        return ResourceResult(success=True, message=f"EC2 {provider_id} terminado")

    def _delete_vpc(self, provider_id: str) -> ResourceResult:
        ec2 = self._clients["ec2"]
        ec2.delete_vpc(VpcId=provider_id)
        return ResourceResult(success=True, message=f"VPC {provider_id} deletada")

    def _delete_subnet(self, provider_id: str) -> ResourceResult:
        ec2 = self._clients["ec2"]
        ec2.delete_subnet(SubnetId=provider_id)
        return ResourceResult(success=True, message=f"Subnet {provider_id} deletada")

    def _delete_security_group(self, provider_id: str) -> ResourceResult:
        ec2 = self._clients["ec2"]
        ec2.delete_security_group(GroupId=provider_id)
        return ResourceResult(success=True, message=f"SG {provider_id} deletado")

    def _delete_eks(self, provider_id: str) -> ResourceResult:
        eks = self._clients["eks"]
        # provider_id aqui é o ARN, extrair o nome
        cluster_name = provider_id.split("/")[-1]
        eks.delete_cluster(name=cluster_name)
        return ResourceResult(success=True, message=f"EKS {cluster_name} deletado")

    def _delete_rds(self, provider_id: str) -> ResourceResult:
        rds = self._clients["rds"]
        rds.delete_db_instance(
            DBInstanceIdentifier=provider_id,
            SkipFinalSnapshot=True,
        )
        return ResourceResult(success=True, message=f"RDS {provider_id} deletado")

    # ── Route53 DNS Operations ──────────────────────────────────

    def _create_route53_record(self, params: dict) -> ResourceResult:
        """Cria um registro DNS no Route53."""
        route53 = self._clients["route53"]
        
        hosted_zone = params.get("hosted_zone")
        record_name = params.get("name", "")
        record_type = params.get("type", "A")
        record_value = params.get("value", "")
        ttl = params.get("ttl", 300)

        console.print(
            f"  [cyan]Criando registro Route53 '{record_name}' ({record_type})...[/cyan]"
        )

        # Se hosted_zone não fornecido, tentar encontrar pelo domínio
        if not hosted_zone:
            domain = params.get("domain", "")
            if domain:
                zones = route53.list_hosted_zones_by_name(DNSName=domain)["HostedZones"]
                if zones:
                    hosted_zone = zones[0]["Id"]
                    console.print(f"  [dim]Hosted Zone encontrada: {hosted_zone}[/dim]")

        if not hosted_zone:
            return ResourceResult(
                success=False,
                error="hosted_zone não fornecida e não foi possível encontrar pelo domínio",
            )

        # Criar registro
        response = route53.change_resource_record_sets(
            HostedZoneId=hosted_zone,
            ChangeBatch={
                "Comment": f"Created by CloudForge: {record_name}",
                "Changes": [
                    {
                        "Action": "CREATE",
                        "ResourceRecordSets": [
                            {
                                "Name": record_name,
                                "Type": record_type,
                                "TTL": ttl,
                                "ResourceRecords": [{"Value": record_value}],
                            }
                        ],
                    }
                ],
            },
        )

        change_id = response["ChangeInfo"]["Id"]

        return ResourceResult(
            success=True,
            provider_id=f"{hosted_zone}/{record_name}",
            outputs={
                "hosted_zone": hosted_zone,
                "record_name": record_name,
                "record_type": record_type,
                "record_value": record_value,
                "change_id": change_id,
            },
            message=f"Registro Route53 '{record_name}' criado",
        )

    def _delete_route53_record(self, provider_id: str) -> ResourceResult:
        """Deleta um registro DNS do Route53."""
        route53 = self._clients["route53"]
        
        # provider_id formato: hosted_zone/record_name
        parts = provider_id.split("/")
        if len(parts) != 2:
            return ResourceResult(
                success=False,
                error=f"Formato inválido de provider_id: {provider_id}",
            )

        hosted_zone, record_name = parts

        console.print(
            f"  [red]Deletando registro Route53 '{record_name}'...[/red]"
        )

        # Primeiro, obter o registro atual para saber o valor
        try:
            records = route53.list_resource_record_sets(
                HostedZoneId=hosted_zone,
                StartRecordName=record_name,
            )["ResourceRecordSets"]

            record_to_delete = None
            for record in records:
                if record["Name"] == record_name or record["Name"] == f"{record_name}.":
                    record_to_delete = record
                    break

            if not record_to_delete:
                return ResourceResult(
                    success=False,
                    error=f"Registro '{record_name}' não encontrado",
                )

            # Deletar registro
            route53.change_resource_record_sets(
                HostedZoneId=hosted_zone,
                ChangeBatch={
                    "Changes": [
                        {
                            "Action": "DELETE",
                            "ResourceRecordSets": [record_to_delete],
                        }
                    ],
                },
            )

            return ResourceResult(
                success=True,
                message=f"Registro Route53 '{record_name}' deletado",
            )

        except Exception as e:
            return ResourceResult(success=False, error=str(e))

    def _resolve_ami(self, image_name: str) -> str:
        """Resolve nome de imagem amigável para AMI ID."""
        ami_map = {
            "ubuntu-22.04": "ami-0c7217cdde317cfec",
            "ubuntu-20.04": "ami-0261755bbcb8c4a84",
            "amazon-linux-2": "ami-0fa1ca9559f1892ec",
            "debian-12": "ami-06db4d78cb1d3bbf9",
        }
        return ami_map.get(image_name, image_name)

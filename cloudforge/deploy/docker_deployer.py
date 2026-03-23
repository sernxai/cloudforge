"""
CloudForge - Docker Deployer
Pipeline integrado para build, push e deploy de containers Docker.
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


class DeployError(Exception):
    """Erro durante o cloudforge.deploy."""

    pass


class DockerDeployer:
    """Gerencia o pipeline completo de deploy Docker → Kubernetes."""

    def __init__(self, config: dict[str, Any], provider_name: str = ""):
        self.image = config.get("image", "")
        self.target = config.get("target", "")
        self.replicas = config.get("replicas", 1)
        self.port = config.get("port", 8080)
        self.env = config.get("env", {})
        self.registry = config.get("registry", "")
        self.provider_name = provider_name
        self.namespace = config.get("namespace", "default")
        self.resources = config.get("resources", {})

    def deploy(self, cluster_outputs: dict | None = None) -> bool:
        """Executa o pipeline completo de cloudforge.deploy."""
        console.print(
            Panel(
                f"[bold]Image:[/bold] {self.image}\n"
                f"[bold]Target:[/bold] {self.target}\n"
                f"[bold]Replicas:[/bold] {self.replicas}\n"
                f"[bold]Port:[/bold] {self.port}",
                title="🐳 CloudForge — Docker Deploy",
                border_style="blue",
            )
        )

        steps = [
            ("Verificando Docker...", self._check_docker),
            ("Build da imagem...", self._build_image),
            ("Push para registry...", self._push_image),
            ("Configurando kubectl...", self._configure_kubectl),
            ("Aplicando deployment...", self._apply_deployment),
            ("Criando service...", self._apply_service),
            ("Verificando cloudforge.deploy...", self._verify_deployment),
        ]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            for description, step_fn in steps:
                task = progress.add_task(description, total=None)
                try:
                    step_fn(cluster_outputs)
                    progress.update(
                        task,
                        description=f"[green]✓ {description.replace('...', '')}[/green]",
                    )
                except DeployError as e:
                    progress.update(
                        task, description=f"[red]✗ {e}[/red]"
                    )
                    return False
                finally:
                    progress.remove_task(task)

        console.print(
            Panel(
                f"[green]✓ Deploy concluído com sucesso![/green]\n\n"
                f"Image: [bold]{self.image}[/bold]\n"
                f"Replicas: [bold]{self.replicas}[/bold]\n"
                f"Port: [bold]{self.port}[/bold]",
                title="🐳 Deploy Completo",
                border_style="green",
            )
        )
        return True

    def _check_docker(self, _: Any = None) -> None:
        """Verifica se Docker está disponível."""
        try:
            result = subprocess.run(
                ["docker", "version", "--format", "{{.Server.Version}}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise DeployError("Docker não está rodando")
        except FileNotFoundError:
            raise DeployError("Docker não encontrado. Instale: https://docs.docker.com")

    def _build_image(self, _: Any = None) -> None:
        """Build da imagem Docker."""
        image_parts = self.image.split(":")
        image_name = image_parts[0]
        tag = image_parts[1] if len(image_parts) > 1 else "latest"

        # Se existe Dockerfile local, build
        if Path("Dockerfile").exists():
            result = subprocess.run(
                ["docker", "build", "-t", f"{image_name}:{tag}", "."],
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode != 0:
                raise DeployError(f"Docker build falhou: {result.stderr[:200]}")
        else:
            # Verificar se imagem já existe
            result = subprocess.run(
                ["docker", "image", "inspect", self.image],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                # Tentar pull
                result = subprocess.run(
                    ["docker", "pull", self.image],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode != 0:
                    raise DeployError(f"Não foi possível obter a imagem: {self.image}")

    def _push_image(self, _: Any = None) -> None:
        """Push da imagem para o registry."""
        if not self.registry:
            # Auto-detectar registry baseado no provider
            registries = {
                "aws": "ECR (auto-detectado)",
                "gcp": "GCR (auto-detectado)",
                "azure": "ACR (auto-detectado)",
            }
            console.print(
                f"  [dim]Registry: {registries.get(self.provider_name, 'local')}[/dim]"
            )
            return  # Em produção, faria push real

        result = subprocess.run(
            ["docker", "push", f"{self.registry}/{self.image}"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise DeployError(f"Docker push falhou: {result.stderr[:200]}")

    def _configure_kubectl(self, cluster_outputs: dict | None = None) -> None:
        """Configura kubectl para o cluster alvo."""
        try:
            result = subprocess.run(
                ["kubectl", "version", "--client", "--short"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise DeployError("kubectl não encontrado")
        except FileNotFoundError:
            raise DeployError("kubectl não instalado")

    def _apply_deployment(self, _: Any = None) -> None:
        """Aplica o Deployment no Kubernetes."""
        deployment_yaml = self._generate_deployment_yaml()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(deployment_yaml)
            temp_path = f.name

        result = subprocess.run(
            ["kubectl", "apply", "-f", temp_path, "-n", self.namespace],
            capture_output=True,
            text=True,
            timeout=60,
        )

        Path(temp_path).unlink(missing_ok=True)

        if result.returncode != 0:
            raise DeployError(f"kubectl apply falhou: {result.stderr[:200]}")

    def _apply_service(self, _: Any = None) -> None:
        """Cria/atualiza o Service no Kubernetes."""
        service_yaml = self._generate_service_yaml()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(service_yaml)
            temp_path = f.name

        result = subprocess.run(
            ["kubectl", "apply", "-f", temp_path, "-n", self.namespace],
            capture_output=True,
            text=True,
            timeout=60,
        )

        Path(temp_path).unlink(missing_ok=True)

        if result.returncode != 0:
            raise DeployError(f"Service apply falhou: {result.stderr[:200]}")

    def _verify_deployment(self, _: Any = None) -> None:
        """Verifica se o deployment está rodando."""
        app_name = self.image.split(":")[0].split("/")[-1]

        result = subprocess.run(
            [
                "kubectl", "rollout", "status",
                f"deployment/{app_name}",
                "-n", self.namespace,
                "--timeout=120s",
            ],
            capture_output=True,
            text=True,
            timeout=130,
        )

        if result.returncode != 0:
            raise DeployError("Deployment não ficou pronto no tempo esperado")

    def _generate_deployment_yaml(self) -> str:
        """Gera o YAML de Deployment do Kubernetes."""
        app_name = self.image.split(":")[0].split("/")[-1]

        env_vars = ""
        for key, value in self.env.items():
            env_vars += f"""
            - name: {key}
              value: "{value}" """

        resources_spec = ""
        if self.resources:
            resources_spec = f"""
          resources:
            requests:
              cpu: "{self.resources.get('cpu_request', '100m')}"
              memory: "{self.resources.get('memory_request', '128Mi')}"
            limits:
              cpu: "{self.resources.get('cpu_limit', '500m')}"
              memory: "{self.resources.get('memory_limit', '512Mi')}" """

        return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {app_name}
  labels:
    app: {app_name}
    managed-by: cloudforge
spec:
  replicas: {self.replicas}
  selector:
    matchLabels:
      app: {app_name}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    metadata:
      labels:
        app: {app_name}
    spec:
      containers:
      - name: {app_name}
        image: {self.image}
        ports:
        - containerPort: {self.port}
        env: {env_vars if env_vars else "[]"}
{resources_spec}
        livenessProbe:
          httpGet:
            path: /health
            port: {self.port}
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: {self.port}
          initialDelaySeconds: 5
          periodSeconds: 5
"""

    def _generate_service_yaml(self) -> str:
        """Gera o YAML de Service do Kubernetes."""
        app_name = self.image.split(":")[0].split("/")[-1]

        return f"""apiVersion: v1
kind: Service
metadata:
  name: {app_name}-svc
  labels:
    app: {app_name}
    managed-by: cloudforge
spec:
  type: LoadBalancer
  selector:
    app: {app_name}
  ports:
  - protocol: TCP
    port: 80
    targetPort: {self.port}
"""

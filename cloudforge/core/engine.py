"""
CloudForge - Motor de Orquestração
Coordena o fluxo completo: config → plan → apply → state.
"""

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from cloudforge.core.config import Config
from cloudforge.core.state import StateManager, ResourceState
from cloudforge.core.planner import Planner, ExecutionPlan, ActionType
from cloudforge.core.graph import DependencyGraph
from cloudforge.providers.base import BaseProvider
from cloudforge.resources.base import BaseResource, ResourceResult
from cloudforge.resources.vm import VMResource
from cloudforge.resources.network import VPCResource, SubnetResource, SecurityGroupResource
from cloudforge.resources.kubernetes import KubernetesResource
from cloudforge.resources.database import DatabaseResource
from cloudforge.resources.cloud_run import CloudRunResource
from cloudforge.resources.firebase import (
    FirebaseAuthResource,
    FirestoreResource,
    FirebaseRealtimeDBResource,
    FirebaseHostingResource,
)
from cloudforge.resources.dns import DNSRecordResource

console = Console()

# Mapeamento: tipo de recurso → provider padrão
# Recursos sem entrada aqui usam o provider principal
RESOURCE_PROVIDER_MAP = {
    "dns_record": "godaddy",
}

# Registry de tipos de recurso
RESOURCE_CLASSES: dict[str, type[BaseResource]] = {
    "vm": VMResource,
    "vpc": VPCResource,
    "subnet": SubnetResource,
    "security_group": SecurityGroupResource,
    "kubernetes": KubernetesResource,
    "database": DatabaseResource,
    "cloud_run": CloudRunResource,
    "firebase_auth": FirebaseAuthResource,
    "firestore": FirestoreResource,
    "firebase_rtdb": FirebaseRealtimeDBResource,
    "firebase_hosting": FirebaseHostingResource,
    "dns_record": DNSRecordResource,
}


def get_provider(name: str, region: str, credentials: dict | None = None) -> BaseProvider:
    """Factory para instanciar o provider correto."""
    if name == "aws":
        from cloudforge.providers.aws.provider import AWSProvider
        return AWSProvider(region, credentials)
    elif name == "gcp":
        from cloudforge.providers.gcp.provider import GCPProvider
        return GCPProvider(region, credentials)
    elif name == "azure":
        from cloudforge.providers.azure.provider import AzureProvider
        return AzureProvider(region, credentials)
    elif name == "godaddy":
        from cloudforge.providers.godaddy.provider import GoDaddyProvider
        return GoDaddyProvider(region, credentials)
    else:
        raise ValueError(f"Provider desconhecido: {name}")


class Engine:
    """Motor principal do CloudForge. Coordena todo o fluxo de IaC."""

    def __init__(
        self,
        config_path: str = "infrastructure.yaml",
        state_path: str = ".cloudforge/state.json",
    ):
        self.config = Config(config_path)
        self.state = StateManager(state_path)
        self.provider: BaseProvider | None = None
        self._external_providers: dict[str, BaseProvider] = {}
        self._resource_outputs: dict[str, dict] = {}

    def init(self, provider_name: str, region: str) -> None:
        """Inicializa um novo projeto CloudForge."""
        import yaml
        from pathlib import Path

        template = {
            "project": {
                "name": "meu-projeto",
                "environment": "development",
                "tags": {"managed_by": "cloudforge"},
            },
            "provider": {
                "name": provider_name,
                "region": region,
                "credentials": {},
            },
            "resources": [
                {
                    "type": "vpc",
                    "name": "main-vpc",
                    "config": {"cidr_block": "10.0.0.0/16"},
                },
                {
                    "type": "subnet",
                    "name": "public-subnet",
                    "depends_on": ["main-vpc"],
                    "config": {
                        "vpc": "main-vpc",
                        "cidr_block": "10.0.1.0/24",
                        "public": True,
                    },
                },
            ],
        }

        config_path = Path("infrastructure.yaml")
        if config_path.exists():
            console.print(
                "[yellow]⚠ infrastructure.yaml já existe. Nenhuma mudança feita.[/yellow]"
            )
            return

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(template, f, default_flow_style=False, allow_unicode=True)

        Path(".cloudforge").mkdir(exist_ok=True)
        Path(".cloudforge/.gitignore").write_text("state.json\nstate.json.backup\n")

        console.print(
            Panel(
                f"[green]✓ Projeto CloudForge inicializado![/green]\n\n"
                f"Provider: [bold]{provider_name}[/bold]\n"
                f"Região: [bold]{region}[/bold]\n\n"
                f"Arquivo criado: [cyan]infrastructure.yaml[/cyan]\n"
                f"Edite-o e execute: [bold]cloudforge plan[/bold]",
                title="☁️  CloudForge Init",
                border_style="green",
            )
        )

    def validate(self) -> bool:
        """Valida a configuração e todos os recursos."""
        console.print("[bold]Validando configuração...[/bold]\n")

        try:
            data = self.config.load()
        except Exception as e:
            console.print(f"[red]✗ Erro de configuração: {e}[/red]")
            return False

        # Validar recursos individualmente
        all_errors: list[str] = []
        for res_data in self.config.resources:
            res_class = RESOURCE_CLASSES.get(res_data["type"])
            if not res_class:
                all_errors.append(f"Tipo de recurso desconhecido: {res_data['type']}")
                continue

            resource = res_class(
                name=res_data["name"],
                config=res_data.get("config", {}),
            )
            errors = resource.validate()
            all_errors.extend(errors)

        # Validar grafo de dependências
        try:
            graph = DependencyGraph.from_resources(self.config.resources)
            graph.topological_sort()
        except Exception as e:
            all_errors.append(str(e))

        if all_errors:
            console.print("[red]✗ Validação falhou:[/red]\n")
            for err in all_errors:
                console.print(f"  [red]• {err}[/red]")
            return False

        console.print(
            f"[green]✓ Configuração válida! "
            f"({len(self.config.resources)} recursos definidos)[/green]"
        )
        return True

    def plan(self) -> ExecutionPlan:
        """Gera plano de execução (dry-run)."""
        data = self.config.load()
        self.state.load()

        # Construir grafo e ordem
        graph = DependencyGraph.from_resources(self.config.resources)
        order = graph.topological_sort()

        # Calcular diff
        diff = self.state.diff(self.config.resources)

        # Gerar plano
        planner = Planner(
            project_name=self.config.project.get("name", ""),
            provider_name=self.config.provider.get("name", ""),
        )
        plan = planner.create_plan(diff, order)

        # Exibir plano
        plan.display(console)

        return plan

    def apply(self, auto_approve: bool = False) -> bool:
        """Aplica o plano de execução."""
        plan = self.plan()

        if not plan.has_changes:
            return True

        # Confirmação
        if not auto_approve:
            console.print()
            response = console.input(
                "[bold yellow]Deseja aplicar essas mudanças? (yes/no): [/bold yellow]"
            )
            if response.lower() not in ("yes", "y", "sim", "s"):
                console.print("[yellow]Aplicação cancelada.[/yellow]")
                return False

        console.print()
        console.print(
            Panel("Aplicando mudanças...", title="☁️  CloudForge Apply", border_style="cyan")
        )

        # Inicializar provider principal
        provider_config = self.config.provider
        self.provider = get_provider(
            provider_config["name"],
            provider_config["region"],
            provider_config.get("credentials"),
        )
        self.provider.authenticate()

        # Inicializar providers externos (ex: GoDaddy para DNS)
        for ext_name, ext_creds in self.config.external_cloudforge.providers.items():
            try:
                ext_provider = get_provider(ext_name, "global", ext_creds)
                ext_provider.authenticate()
                self._external_providers[ext_name] = ext_provider
            except Exception as e:
                console.print(
                    f"[yellow]⚠ Provider externo '{ext_name}': {e}[/yellow]"
                )

        success = True

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:

            # Processar creates
            for action in plan.creates:
                task = progress.add_task(
                    f"Criando {action.resource_type} '{action.resource_name}'...",
                    total=None,
                )

                result = self._apply_create(action)

                if result.success:
                    progress.update(task, description=(
                        f"[green]✓ {action.resource_type} "
                        f"'{action.resource_name}' criado[/green]"
                    ))
                else:
                    progress.update(task, description=(
                        f"[red]✗ Falha ao criar "
                        f"'{action.resource_name}': {result.error}[/red]"
                    ))
                    success = False

                progress.remove_task(task)

            # Processar updates
            for action in plan.updates:
                task = progress.add_task(
                    f"Atualizando {action.resource_type} '{action.resource_name}'...",
                    total=None,
                )

                result = self._apply_update(action)

                status = "[green]✓ atualizado[/green]" if result.success else f"[red]✗ falha: {result.error}[/red]"
                progress.update(
                    task,
                    description=f"{action.resource_name}: {status}",
                )
                if not result.success:
                    success = False

                progress.remove_task(task)

            # Processar deletes (ordem reversa)
            for action in reversed(plan.deletes):
                task = progress.add_task(
                    f"Destruindo {action.resource_type} '{action.resource_name}'...",
                    total=None,
                )

                result = self._apply_delete(action)

                status = "[green]✓ destruído[/green]" if result.success else f"[red]✗ falha: {result.error}[/red]"
                progress.update(
                    task,
                    description=f"{action.resource_name}: {status}",
                )
                if not result.success:
                    success = False

                progress.remove_task(task)

        # Salvar estado
        self.state.save()

        console.print()
        if success:
            console.print(
                Panel(
                    "[green]✓ Todas as mudanças aplicadas com sucesso![/green]",
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel(
                    "[yellow]⚠ Aplicação concluída com erros. "
                    "Verifique o estado.[/yellow]",
                    border_style="yellow",
                )
            )

        return success

    def destroy(self, auto_approve: bool = False) -> bool:
        """Destrói toda a infraestrutura."""
        self.state.load()

        active = self.state.get_active_resources()
        if not active:
            console.print("[green]✓ Nenhum recurso ativo para destruir.[/green]")
            return True

        console.print(
            Panel(
                f"[red bold]⚠ ATENÇÃO: {len(active)} recurso(s) serão destruídos![/red bold]",
                title="☁️  CloudForge Destroy",
                border_style="red",
            )
        )

        for res in active:
            console.print(f"  [red]- {res.resource_type}: {res.name}[/red]")

        if not auto_approve:
            console.print()
            response = console.input(
                "[bold red]Confirma a destruição? "
                "Digite 'destroy' para confirmar: [/bold red]"
            )
            if response != "destroy":
                console.print("[yellow]Destruição cancelada.[/yellow]")
                return False

        # Inicializar provider principal
        provider_config = self.config.load()
        prov = self.config.provider
        self.provider = get_provider(
            prov["name"], prov["region"], prov.get("credentials")
        )
        self.provider.authenticate()

        # Inicializar providers externos
        for ext_name, ext_creds in self.config.external_cloudforge.providers.items():
            try:
                ext_provider = get_provider(ext_name, "global", ext_creds)
                ext_provider.authenticate()
                self._external_providers[ext_name] = ext_provider
            except Exception as e:
                console.print(
                    f"[yellow]⚠ Provider externo '{ext_name}': {e}[/yellow]"
                )

        # Destruir em ordem reversa topológica
        graph = DependencyGraph.from_resources(self.config.resources)
        reverse_order = graph.reverse_topological_sort()

        success = True
        for name in reverse_order:
            res_state = self.state.get_resource(name)
            if not res_state or res_state.status != "active":
                continue

            console.print(
                f"  [red]Destruindo {res_state.resource_type} '{name}'...[/red]"
            )

            provider = self._get_provider_for_resource(res_state.resource_type)
            result = provider.delete_resource(
                res_state.resource_type, res_state.provider_id or name
            )

            if result.success:
                res_state.status = "destroyed"
                self.state.set_resource(res_state)
                console.print(f"  [green]✓ '{name}' destruído[/green]")
            else:
                console.print(f"  [red]✗ Falha ao destruir '{name}': {result.error}[/red]")
                success = False

        # Limpar estado se tudo foi destruído
        if success:
            self.state.clear()

        self.state.save()
        return success

    # ── Helpers internos ──────────────────────────────────────────

    def _get_provider_for_resource(self, resource_type: str) -> BaseProvider:
        """Retorna o provider correto para um tipo de recurso."""
        # Verificar se o recurso tem provider externo mapeado
        ext_name = RESOURCE_PROVIDER_MAP.get(resource_type)
        if ext_name and ext_name in self._external_providers:
            return self._external_providers[ext_name]
        # Caso contrário, usar o provider principal
        return self.provider

    def _apply_create(self, action) -> ResourceResult:
        """Aplica criação de um recurso."""
        res_class = RESOURCE_CLASSES.get(action.resource_type)
        if not res_class:
            return ResourceResult(
                success=False,
                error=f"Tipo desconhecido: {action.resource_type}",
            )

        # Resolver provider correto para este recurso
        provider = self._get_provider_for_resource(action.resource_type)

        resource = res_class(
            name=action.resource_name,
            config=action.config,
            provider=provider,
        )

        # Resolver referências a outputs de outros recursos
        resolved_config = resource.resolve_config(self._resource_outputs)
        resource.config = resolved_config

        result = resource.create()

        if result.success:
            # Salvar no estado
            state_entry = ResourceState(
                name=action.resource_name,
                resource_type=action.resource_type,
                provider=self.config.provider.get("name", ""),
                config=action.config,
                provider_id=result.provider_id,
                status="active",
                outputs=result.outputs,
            )
            self.state.set_resource(state_entry)

            # Guardar outputs para referência cruzada
            self._resource_outputs[action.resource_name] = result.outputs

        return result

    def _apply_update(self, action) -> ResourceResult:
        """Aplica atualização de um recurso."""
        provider = self._get_provider_for_resource(action.resource_type)
        return provider.update_resource(
            action.resource_type,
            action.resource_name,
            action.config,
            action.changes or {},
        )

    def _apply_delete(self, action) -> ResourceResult:
        """Aplica deleção de um recurso."""
        provider = self._get_provider_for_resource(action.resource_type)
        res_state = self.state.get_resource(action.resource_name)
        provider_id = res_state.provider_id if res_state else action.resource_name

        result = provider.delete_resource(action.resource_type, provider_id)

        if result.success:
            self.state.remove_resource(action.resource_name)

        return result

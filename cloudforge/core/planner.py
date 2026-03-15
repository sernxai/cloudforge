"""
CloudForge - Planejador de Execução
Gera planos de execução a partir das diferenças entre estado atual e desejado.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box


class ActionType(Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    UNCHANGED = "unchanged"


@dataclass
class PlannedAction:
    """Uma ação planejada sobre um recurso."""

    action: ActionType
    resource_name: str
    resource_type: str
    config: dict[str, Any] = field(default_factory=dict)
    changes: dict[str, Any] | None = None  # Para updates: o que mudou

    @property
    def symbol(self) -> str:
        symbols = {
            ActionType.CREATE: "[bold green]+[/bold green]",
            ActionType.UPDATE: "[bold yellow]~[/bold yellow]",
            ActionType.DELETE: "[bold red]-[/bold red]",
            ActionType.UNCHANGED: "[dim]=[/dim]",
        }
        return symbols[self.action]

    @property
    def action_label(self) -> str:
        labels = {
            ActionType.CREATE: "[green]criar[/green]",
            ActionType.UPDATE: "[yellow]atualizar[/yellow]",
            ActionType.DELETE: "[red]destruir[/red]",
            ActionType.UNCHANGED: "[dim]sem mudança[/dim]",
        }
        return labels[self.action]


@dataclass
class ExecutionPlan:
    """Plano completo de execução."""

    actions: list[PlannedAction] = field(default_factory=list)
    provider_name: str = ""
    project_name: str = ""

    @property
    def has_changes(self) -> bool:
        return any(a.action != ActionType.UNCHANGED for a in self.actions)

    @property
    def creates(self) -> list[PlannedAction]:
        return [a for a in self.actions if a.action == ActionType.CREATE]

    @property
    def updates(self) -> list[PlannedAction]:
        return [a for a in self.actions if a.action == ActionType.UPDATE]

    @property
    def deletes(self) -> list[PlannedAction]:
        return [a for a in self.actions if a.action == ActionType.DELETE]

    def display(self, console: Console | None = None) -> None:
        """Exibe o plano formatado no terminal."""
        console = console or Console()

        if not self.has_changes:
            console.print(
                Panel(
                    "[green]✓ Infraestrutura atualizada. Nenhuma mudança necessária.[/green]",
                    title="CloudForge Plan",
                    border_style="green",
                )
            )
            return

        # Cabeçalho
        console.print()
        header_text = (
            f"[bold]Projeto:[/bold] {self.project_name or 'N/A'}\n"
            f"[bold]Provider:[/bold] {self.provider_name or 'N/A'}"
        )
        console.print(
            Panel(
                header_text,
                title="☁️  CloudForge — Plano de Execução",
                border_style="cyan",
            )
        )

        # Tabela de ações
        table = Table(
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
            padding=(0, 1),
            expand=True
        )
        table.add_column("", width=3)
        table.add_column("Recurso", style="bold")
        table.add_column("Tipo")
        table.add_column("Ação")
        table.add_column("Detalhes")

        for action in self.actions:
            details = ""
            if action.action == ActionType.CREATE:
                details = ", ".join(
                    f"{k}={v}" for k, v in list(action.config.items())[:3]
                )
            elif action.action == ActionType.UPDATE and action.changes:
                details = ", ".join(
                    f"{k}: {v.get('old', '?')} → {v.get('new', '?')}"
                    for k, v in list(action.changes.items())[:3]
                )

            table.add_row(
                action.symbol,
                action.resource_name,
                action.resource_type,
                action.action_label,
                details or "-",
            )

        console.print(table)

        # Resumo
        summary = (
            f"  [green]+{len(self.creates)} criar[/green]  "
            f"[yellow]~{len(self.updates)} atualizar[/yellow]  "
            f"[red]-{len(self.deletes)} destruir[/red]"
        )
        console.print(Panel(summary, title="Resumo", border_style="cyan"))


class Planner:
    """Gera planos de execução a partir do diff de estado."""

    def __init__(self, project_name: str = "", provider_name: str = ""):
        self.project_name = project_name
        self.provider_name = provider_name

    def create_plan(
        self, diff: dict[str, list], resource_order: list[str]
    ) -> ExecutionPlan:
        """
        Cria um plano de execução ordenado a partir do diff de estado.

        Args:
            diff: Saída de StateManager.diff()
            resource_order: Ordem topológica dos recursos
        """
        plan = ExecutionPlan(
            project_name=self.project_name,
            provider_name=self.provider_name,
        )

        # Mapear ações por nome de recurso
        action_map: dict[str, PlannedAction] = {}

        for resource in diff["create"]:
            action_map[resource["name"]] = PlannedAction(
                action=ActionType.CREATE,
                resource_name=resource["name"],
                resource_type=resource["type"],
                config=resource.get("config", {}),
            )

        for resource in diff["update"]:
            desired = resource["desired"]
            current = resource["current"]
            changes = self._compute_changes(
                current.get("config", {}), desired.get("config", {})
            )
            action_map[desired["name"]] = PlannedAction(
                action=ActionType.UPDATE,
                resource_name=desired["name"],
                resource_type=desired["type"],
                config=desired.get("config", {}),
                changes=changes,
            )

        for resource in diff["delete"]:
            action_map[resource["name"]] = PlannedAction(
                action=ActionType.DELETE,
                resource_name=resource["name"],
                resource_type=resource["resource_type"],
            )

        for resource in diff["unchanged"]:
            action_map[resource["name"]] = PlannedAction(
                action=ActionType.UNCHANGED,
                resource_name=resource["name"],
                resource_type=resource["resource_type"],
            )

        # Ordenar ações pela ordem topológica
        ordered_names = [n for n in resource_order if n in action_map]
        # Adicionar recursos que não estão na ordem (ex: a serem deletados)
        remaining = [n for n in action_map if n not in ordered_names]
        ordered_names.extend(remaining)

        plan.actions = [action_map[name] for name in ordered_names]
        return plan

    def _compute_changes(
        self, current_config: dict, desired_config: dict
    ) -> dict[str, dict]:
        """Calcula diferenças entre configurações."""
        changes = {}
        all_keys = set(current_config.keys()) | set(desired_config.keys())

        for key in all_keys:
            old_val = current_config.get(key)
            new_val = desired_config.get(key)
            if old_val != new_val:
                changes[key] = {"old": old_val, "new": new_val}

        return changes

#!/usr/bin/env python3
"""
CloudForge CLI — Infrastructure as Code em Python
Uso: cloudforge [COMMAND] [OPTIONS]
"""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel


console = Console()

BANNER = """[bold cyan]
   _____ _                 _ _____                    
  / ____| |               | |  ___|                   
 | |    | | ___  _   _  __| | |_ ___  _ __ __ _  ___ 
 | |    | |/ _ \\| | | |/ _` |  _/ _ \\| '__/ _` |/ _ \\
 | |____| | (_) | |_| | (_| | || (_) | | | (_| |  __/
  \\_____|_|\\___/ \\__,_|\\__,_\\_| \\___/|_|  \\__, |\\___|
                                            __/ |     
                                           |___/      
[/bold cyan]"""


@click.group()
@click.version_option(version="1.0.0", prog_name="CloudForge")
def cli():
    """☁️  CloudForge — Infrastructure as Code em Python

    Defina, provisione e gerencie infraestrutura multi-cloud
    usando arquivos YAML declarativos.
    """
    pass


@cli.command()
@click.option(
    "--provider", "-p",
    type=click.Choice(["aws", "gcp", "azure"]),
    required=True,
    help="Provedor de nuvem",
)
@click.option(
    "--region", "-r",
    default="us-east-1",
    help="Região do provedor (default: us-east-1)",
)
def init(provider: str, region: str):
    """Inicializa um novo projeto CloudForge."""
    console.print(BANNER)

    from cloudforge.core.engine import Engine

    engine = Engine()
    engine.init(provider, region)


@cli.command()
@click.option(
    "--config", "-c",
    default="infrastructure.yaml",
    help="Caminho do arquivo de configuração",
)
def validate(config: str):
    """Valida a configuração de infraestrutura."""
    from cloudforge.core.engine import Engine

    engine = Engine(config_path=config)
    valid = engine.validate()
    sys.exit(0 if valid else 1)


@cli.command()
@click.option(
    "--config", "-c",
    default="infrastructure.yaml",
    help="Caminho do arquivo de configuração",
)
@click.option(
    "--state", "-s",
    default=".cloudforge/state.json",
    help="Caminho do arquivo de estado",
)
def plan(config: str, state: str):
    """Gera plano de execução (dry-run)."""
    console.print(BANNER)

    from cloudforge.core.engine import Engine

    engine = Engine(config_path=config, state_path=state)
    engine.plan()


@cli.command()
@click.option(
    "--config", "-c",
    default="infrastructure.yaml",
    help="Caminho do arquivo de configuração",
)
@click.option(
    "--state", "-s",
    default=".cloudforge/state.json",
    help="Caminho do arquivo de estado",
)
@click.option(
    "--auto-approve",
    is_flag=True,
    default=False,
    help="Pular confirmação interativa",
)
def apply(config: str, state: str, auto_approve: bool):
    """Aplica a infraestrutura definida."""
    console.print(BANNER)

    from cloudforge.core.engine import Engine

    engine = Engine(config_path=config, state_path=state)
    success = engine.apply(auto_approve=auto_approve)
    sys.exit(0 if success else 1)


@cli.command()
@click.option(
    "--config", "-c",
    default="infrastructure.yaml",
    help="Caminho do arquivo de configuração",
)
@click.option(
    "--state", "-s",
    default=".cloudforge/state.json",
    help="Caminho do arquivo de estado",
)
@click.option(
    "--auto-approve",
    is_flag=True,
    default=False,
    help="Pular confirmação interativa",
)
def destroy(config: str, state: str, auto_approve: bool):
    """Destrói toda a infraestrutura provisionada."""
    console.print(BANNER)

    from cloudforge.core.engine import Engine

    engine = Engine(config_path=config, state_path=state)
    success = engine.destroy(auto_approve=auto_approve)
    sys.exit(0 if success else 1)


@cli.command()
@click.option(
    "--image", "-i",
    required=True,
    help="Imagem Docker (ex: myapp:latest)",
)
@click.option(
    "--target", "-t",
    required=True,
    help="Nome do cluster K8s alvo",
)
@click.option(
    "--replicas",
    default=3,
    help="Número de réplicas",
)
@click.option(
    "--port",
    default=8080,
    help="Porta da aplicação",
)
@click.option(
    "--config", "-c",
    default="infrastructure.yaml",
    help="Caminho do arquivo de configuração",
)
def deploy(image: str, target: str, replicas: int, port: int, config: str):
    """Deploy de aplicação Docker no cluster Kubernetes."""
    console.print(BANNER)

    from cloudforge.core.engine import Engine
    from cloudforge.deploy.docker_deployer import DockerDeployer

    engine = Engine(config_path=config)
    data = engine.config.load()

    deploy_config = data.get("deploy", {})
    deploy_config.update({
        "image": image,
        "target": target,
        "replicas": replicas,
        "port": port,
    })

    deployer = DockerDeployer(
        config=deploy_config,
        provider_name=engine.config.provider.get("name", ""),
    )
    success = deployer.deploy()
    sys.exit(0 if success else 1)


@cli.command()
@click.option(
    "--state", "-s",
    default=".cloudforge/state.json",
    help="Caminho do arquivo de estado",
)
def status(state: str):
    """Exibe o estado atual da infraestrutura."""
    from cloudforge.core.state import StateManager
    from rich.table import Table
    from rich import box

    sm = StateManager(state)
    sm.load()

    resources = sm.list_resources()

    if not resources:
        console.print("[dim]Nenhum recurso no estado.[/dim]")
        return

    table = Table(
        title="☁️  Estado da Infraestrutura",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Nome", style="bold")
    table.add_column("Tipo")
    table.add_column("Provider")
    table.add_column("Status")
    table.add_column("Provider ID", max_width=30)
    table.add_column("Atualizado em")

    status_styles = {
        "active": "[green]active[/green]",
        "creating": "[yellow]creating[/yellow]",
        "updating": "[yellow]updating[/yellow]",
        "destroying": "[red]destroying[/red]",
        "destroyed": "[dim]destroyed[/dim]",
        "planned": "[cyan]planned[/cyan]",
    }

    for res in resources:
        table.add_row(
            res.name,
            res.resource_type,
            res.provider,
            status_styles.get(res.status, res.status),
            res.provider_id or "-",
            res.updated_at[:19] if res.updated_at else "-",
        )

    console.print(table)


@cli.command()
@click.option(
    "--state", "-s",
    default=".cloudforge/state.json",
    help="Caminho do arquivo de estado",
)
@click.argument("resource_name")
def output(state: str, resource_name: str):
    """Exibe outputs de um recurso específico."""
    from cloudforge.core.state import StateManager
    import json

    sm = StateManager(state)
    sm.load()

    res = sm.get_resource(resource_name)
    if not res:
        console.print(f"[red]Recurso '{resource_name}' não encontrado.[/red]")
        sys.exit(1)

    console.print(
        Panel(
            json.dumps(res.outputs, indent=2, ensure_ascii=False),
            title=f"Outputs: {resource_name}",
            border_style="cyan",
        )
    )


if __name__ == "__main__":
    cli()

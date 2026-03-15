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
from rich.table import Table
from rich import box


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
    type=click.Choice(["aws", "gcp", "azure", "alibaba", "oracle", "digitalocean", "hetzner", "hostinger", "locaweb"]),
    required=True,
    help="Provedor de nuvem",
)
@click.option(
    "--region", "-r",
    default="us-east-1",
    help="Região do provedor (default varia por provider)",
)
def init(provider: str, region: str):
    """Inicializa um novo projeto CloudForge."""
    console.print(BANNER)

    from cloudforge.core.engine import Engine

    engine = Engine()
    engine.init(provider, region)


@cli.command()
def providers():
    """Lista todos os providers disponíveis e seus parâmetros."""
    console.print(BANNER)
    
    from cloudforge.core.engine import PROVIDER_REGISTRY
    
    table = Table(
        title="☁️  CloudForge Providers Disponíveis",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Provider", style="bold green")
    table.add_column("Nome Interno")
    table.add_column("Regiões")
    table.add_column("Recursos Suportados")
    table.add_column("Instalação")
    
    for provider_name, provider_info in PROVIDER_REGISTRY.items():
        try:
            # Instanciar provider para obter informações
            if provider_name == "aws":
                from cloudforge.providers.aws.provider import AWSProvider
                p = AWSProvider("us-east-1", {})
            elif provider_name == "gcp":
                from cloudforge.providers.gcp.provider import GCPProvider
                p = GCPProvider("us-central1", {})
            elif provider_name == "azure":
                from cloudforge.providers.azure.provider import AzureProvider
                p = AzureProvider("eastus", {})
            elif provider_name == "alibaba":
                from cloudforge.providers.alibaba.provider import AlibabaCloudProvider
                p = AlibabaCloudProvider("cn-hangzhou", {})
            elif provider_name == "godaddy":
                from cloudforge.providers.godaddy.provider import GoDaddyProvider
                p = GoDaddyProvider("global", {})
            elif provider_name == "cloudflare":
                from cloudforge.providers.cloudflare.provider import CloudflareProvider
                p = CloudflareProvider("global", {})
            else:
                continue
            
            regions = len(p.list_regions())
            resources = provider_info.get("resources", [])
            install_cmd = provider_info.get("install", "pip install cloudforge")
            
            table.add_row(
                provider_info.get("display_name", provider_name),
                f"[dim]{provider_name}[/dim]",
                f"{regions} regiões",
                ", ".join(resources[:5]) + ("..." if len(resources) > 5 else ""),
                f"[cyan]{install_cmd}[/cyan]",
            )
        except Exception as e:
            table.add_row(
                provider_info.get("display_name", provider_name),
                f"[dim]{provider_name}[/dim]",
                "[yellow]N/A[/yellow]",
                "[yellow]N/A[/yellow]",
                f"[dim]{provider_info.get('install', 'N/A')}[/dim]",
            )
    
    console.print(table)
    
    # Detalhar recursos por provider
    console.print("\n[bold]📦 Recursos por Provider:[/bold]\n")
    
    for provider_name, provider_info in PROVIDER_REGISTRY.items():
        resources = provider_info.get("resources", [])
        if resources:
            console.print(f"[green]{provider_info.get('display_name', provider_name)}:[/green]")
            for res in resources:
                console.print(f"  • {res}")
            console.print()
    
    # Dicas de uso
    console.print(
        Panel(
            "[bold]💡 Dicas de uso:[/bold]\n\n"
            "1. Instale apenas os providers que você vai usar:\n"
            "   [cyan]pip install cloudforge[aws][/cyan]  # Apenas AWS\n"
            "   [cyan]pip install cloudforge[gcp][/cyan]  # Apenas GCP\n"
            "   [cyan]pip install cloudforge[alibaba][/cyan]  # Apenas Alibaba\n\n"
            "2. Para instalar todos os providers:\n"
            "   [cyan]pip install cloudforge[all][/cyan]\n\n"
            "3. Inicialize um projeto com o provider desejado:\n"
            "   [cyan]cloudforge init --provider alibaba --region cn-hangzhou[/cyan]",
            title="📚 Como Usar",
            border_style="blue",
        )
    )


@cli.command()
@click.argument("provider_name", required=False)
@click.option(
    "--upgrade", "-u",
    is_flag=True,
    default=False,
    help="Fazer upgrade das dependências existentes",
)
def install_deps(provider_name: str | None, upgrade: bool):
    """Instala dependências de um provider específico.
    
    Se nenhum provider for especificado, lista as opções disponíveis.
    
    Exemplos:
        cloudforge install-deps aws       # Instala dependências da AWS
        cloudforge install-deps gcp       # Instala dependências do GCP
        cloudforge install-deps alibaba   # Instala dependências do Alibaba
        cloudforge install-deps           # Lista providers disponíveis
    """
    from cloudforge.core.engine import PROVIDER_REGISTRY
    
    console.print(BANNER)
    
    if not provider_name:
        # Listar providers disponíveis
        table = Table(
            title="📦 Providers Disponíveis para Instalação",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Provider", style="bold green")
        table.add_column("Comando")
        table.add_column("Descrição")
        
        for name, info in PROVIDER_REGISTRY.items():
            table.add_row(
                info.get("display_name", name),
                f"[cyan]cloudforge install-deps {name}[/cyan]",
                info.get("description", f"Provider {name}"),
            )
        
        console.print(table)
        return
    
    # Verificar se provider existe
    if provider_name not in PROVIDER_REGISTRY:
        console.print(f"[red]✗ Provider '{provider_name}' não encontrado.[/red]")
        console.print("\nProviders disponíveis:")
        for name in PROVIDER_REGISTRY.keys():
            console.print(f"  • {name}")
        sys.exit(1)
    
    provider_info = PROVIDER_REGISTRY[provider_name]
    deps = provider_info.get("dependencies", [])
    
    if not deps:
        console.print(f"[yellow]⚠ Provider '{provider_name}' não possui dependências extras.[/yellow]")
        return
    
    console.print(
        Panel(
            f"[bold]Provider:[/bold] {provider_info.get('display_name', provider_name)}\n"
            f"[bold]Dependências:[/bold] {len(deps)} pacote(s)\n\n"
            f"[cyan]{', '.join(deps)}[/cyan]",
            title=f"📦 Instalando dependências para {provider_name}",
            border_style="green",
        )
    )
    
    # Instalar dependências
    import subprocess
    
    flag = "--upgrade" if upgrade else "--quiet"
    for dep in deps:
        console.print(f"  Instalando {dep}...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", flag, dep],
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                console.print(f"  [green]✓ {dep} instalado[/green]")
            else:
                console.print(f"  [red]✗ Erro ao instalar {dep}[/red]")
        except subprocess.TimeoutExpired:
            console.print(f"  [red]✗ Timeout ao instalar {dep}[/red]")
        except Exception as e:
            console.print(f"  [red]✗ Erro: {e}[/red]")
    
    console.print(
        Panel(
            "[green]✓ Instalação concluída![/green]\n\n"
            f"Agora você pode usar: [cyan]cloudforge init --provider {provider_name}[/cyan]",
            title="Instalação Finalizada",
            border_style="green",
        )
    )


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

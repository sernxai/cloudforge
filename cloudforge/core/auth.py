"""
CloudForge - Gestão Segura de Credenciais e Guia de Configuração.
Lida com armazenamento cifrado de chaves e guia interativo para o usuário.
"""

import os
import json
import base64
import getpass
from pathlib import Path
from typing import Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich import box

console = Console()

class CredentialsManager:
    """Gerencia o armazenamento cifrado de credenciais (API Keys, Secrets)."""

    def __init__(self, storage_path: str = ".cloudforge/credentials.enc"):
        self.storage_path = Path(storage_path)
        self._key: bytes = self._get_or_create_key()

    def _get_or_create_key(self) -> bytes:
        """Obtém ou gera uma chave de cifragem baseada na máquina/usuário."""
        import hashlib
        import socket
        
        user = getpass.getuser()
        host = socket.gethostname()
        seed = f"cloudforge-salt-{user}@{host}"
        return hashlib.sha256(seed.encode()).digest()

    def _xor_crypt(self, data: bytes) -> bytes:
        """Cifra/Decifra dados usando XOR (simples, sem dependências extras)."""
        key = self._key
        return bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])

    def save(self, provider: str, credentials: dict[str, str]) -> None:
        """Salva credenciais cifradas para um provider."""
        all_creds = self.load_all()
        all_creds[provider] = credentials
        
        # Serializar e cifrar
        raw_data = json.dumps(all_creds).encode("utf-8")
        encrypted = self._xor_crypt(raw_data)
        
        # Salvar em base64
        self.storage_path.parent.mkdir(exist_ok=True)
        with open(self.storage_path, "wb") as f:
            f.write(base64.b64encode(encrypted))

    def load_all(self) -> dict[str, dict[str, str]]:
        """Carrega todas as credenciais decifradas."""
        if not self.storage_path.exists():
            return {}
        
        try:
            with open(self.storage_path, "rb") as f:
                encoded = f.read()
            
            encrypted = base64.b64decode(encoded)
            decrypted = self._xor_crypt(encrypted)
            return json.loads(decrypted.decode("utf-8"))
        except Exception:
            return {}

    def get(self, provider: str) -> Optional[dict[str, str]]:
        """Retorna credenciais para um provider específico."""
        return self.load_all().get(provider)


AUTH_GUIDES: dict[str, dict[str, Any]] = {
    "aws": {
        "title": "Amazon Web Services (AWS)",
        "steps": [
            "1. Acesse o Console IAM: [blue]https://console.aws.amazon.com/iamv2/home#/users[/blue]",
            "2. Selecione seu usuário ou crie um novo para o CloudForge.",
            "3. Vá na aba 'Security credentials' (Credenciais de segurança).",
            "4. Role até 'Access keys' e clique em 'Create access key'.",
            "5. Escolha 'Command Line Interface (CLI)' e avance.",
            "6. Copie a 'Access Key ID' e a 'Secret Access Key'."
        ],
        "fields": [
            {"name": "AWS_ACCESS_KEY_ID", "label": "Access Key ID", "secret": False},
            {"name": "AWS_SECRET_ACCESS_KEY", "label": "Secret Access Key", "secret": True}
        ]
    },
    "gcp": {
        "title": "Google Cloud Platform (GCP)",
        "steps": [
            "1. Acesse: [blue]https://console.cloud.google.com/apis/credentials[/blue]",
            "2. Clique em 'Create Credentials' -> 'Service Account'.",
            "3. Dê um nome (ex: cloudforge-sa) e clique em 'Create and Continue'.",
            "4. Atribua o papel (Role) de 'Editor' ou 'Owner' e finalize.",
            "5. Na lista, clique na Service Account criada -> aba 'Keys'.",
            "6. Clique em 'Add Key' -> 'Create new key' -> JSON.",
            "7. O arquivo será baixado. Copie o ID do projeto e o caminho do JSON."
        ],
        "fields": [
            {"name": "GCP_PROJECT_ID", "label": "Project ID", "secret": False},
            {"name": "GOOGLE_APPLICATION_CREDENTIALS", "label": "Path do JSON Key", "secret": False}
        ]
    },
    "cloudflare": {
        "title": "Cloudflare",
        "steps": [
            "1. Acesse o Dashboard: [blue]https://dash.cloudflare.com/profile/api-tokens[/blue]",
            "2. Clique em 'Create Token'.",
            "3. Use o template 'Edit Cloudflare DNS' ou 'Full Access'.",
            "4. Configure as permissões e clique em 'Continue to summary'.",
            "5. Clique em 'Create Token' e copie o código gerado."
        ],
        "fields": [
            {"name": "CLOUDFLARE_API_TOKEN", "label": "API Token", "secret": True}
        ]
    },
    "alibaba": {
        "title": "Alibaba Cloud (Aliyun)",
        "steps": [
            "1. Acesse o console RAM: [blue]https://ram.console.aliyun.com/manage/ak[/blue]",
            "2. Clique em 'Create AccessKey'.",
            "3. Salve o 'AccessKey ID' e o 'AccessKey Secret'.",
            "4. Certifique-se de que o usuário tem permissões (AdministratorAccess)."
        ],
        "fields": [
            {"name": "ALIBABA_ACCESS_KEY_ID", "label": "AccessKey ID", "secret": False},
            {"name": "ALIBABA_ACCESS_KEY_SECRET", "label": "AccessKey Secret", "secret": True}
        ]
    },
    "godaddy": {
        "title": "GoDaddy",
        "steps": [
            "1. Acesse o Developer Portal: [blue]https://developer.godaddy.com/keys[/blue]",
            "2. Clique em 'Create New API Key'.",
            "3. Escolha o ambiente 'Production'.",
            "4. Dê um nome (ex: CloudForge) e clique em 'Next'.",
            "5. [bold red]IMPORTANTE:[/bold red] Copie a Key e o Secret agora, eles não serão exibidos novamente."
        ],
        "fields": [
            {"name": "GODADDY_API_KEY", "label": "API Key", "secret": False},
            {"name": "GODADDY_API_SECRET", "label": "API Secret", "secret": True}
        ]
    }
}

class GuidedSetup:
    """Interface interativa para configuração de API Keys."""

    def __init__(self):
        self.mgr = CredentialsManager()

    def run(self, provider_id: Optional[str] = None):
        """Executa o guia de configuração."""
        if not provider_id:
            provider_id = self._select_provider()
        
        if provider_id not in AUTH_GUIDES:
            console.print(f"[red]✗ Guia não disponível para '{provider_id}'.[/red]")
            return

        guide = AUTH_GUIDES[provider_id]
        
        console.print(Panel(
            f"[bold cyan]Guia de Configuração: {guide['title']}[/bold cyan]",
            subtitle="CloudForge Guided Setup",
            border_style="cyan"
        ))

        for step in guide["steps"]:
            console.print(f"  {step}")
        
        console.print("\n[bold]Insira as credenciais quando estiver pronto (ou deixe vazio para pular):[/bold]")
        
        creds: dict[str, str] = {}
        for field in guide["fields"]:
            field_name = str(field["name"])
            field_label = str(field["label"])
            field_secret = bool(field["secret"])

            if field_secret:
                val = Prompt.ask(f"  {field_label}", password=True)
            else:
                val = Prompt.ask(f"  {field_label}")
            
            if val:
                creds[field_name] = val
        
        if creds:
            self.mgr.save(provider_id, creds)
            console.print(f"\n[green]✓ Credenciais para [bold]{provider_id}[/bold] salvas com sucesso (cifradas).[/green]")
            console.print("[dim]Elas serão usadas automaticamente pelo CloudForge.[/dim]")
        else:
            console.print("\n[yellow]⚠ Nenhuma informação inserida. Pulando...[/yellow]")

    def _select_provider(self) -> str:
        """Menu de seleção de provider."""
        table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
        table.add_column("ID", style="dim", width=15)
        table.add_column("Provedor")

        for pid, guide in AUTH_GUIDES.items():
            table.add_row(pid, guide["title"])
        
        console.print(Panel(table, title="Selecione um Provedor para Configurar"))
        
        return Prompt.ask("Digite o ID do provedor", choices=list(AUTH_GUIDES.keys()))

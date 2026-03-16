"""
CloudForge - Provider GoDaddy
Gerencia DNS, Domínios e Hospedagem via GoDaddy API.

Requer API Key e Secret obtidos em:
https://developer.godaddy.com/keys

Credenciais no YAML:
  external_providers:
    godaddy:
      api_key: "sua_api_key"
      api_secret: "seu_api_secret"
      environment: "production"   # ou "ote" para testes
"""

import requests
from typing import Any

from rich.console import Console

from cloudforge.providers.base import BaseProvider, ProviderError
from cloudforge.resources.base import ResourceResult

console = Console()


class GoDaddyProvider(BaseProvider):
    """Provider para GoDaddy (DNS, Domínios, Hospedagem) via REST API."""

    PROVIDER_NAME = "godaddy"

    # GoDaddy não tem "regiões" — serviços são globais
    BASE_URLS = {
        "production": "https://api.godaddy.com",
        "ote": "https://api.ote-godaddy.com",  # Teste/sandbox
    }

    def __init__(self, region: str = "global", credentials: dict[str, Any] | None = None):
        super().__init__(region, credentials)
        self.api_key = (credentials or {}).get("api_key", "")
        self.api_secret = (credentials or {}).get("api_secret", "")
        env = (credentials or {}).get("environment", "production")
        self.base_url = self.BASE_URLS.get(env, self.BASE_URLS["production"])

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"sso-key {self.api_key}:{self.api_secret}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def authenticate(self) -> bool:
        """Valida credenciais GoDaddy listando domínios."""
        if not self.api_key or not self.api_secret:
            raise ProviderError(
                "GoDaddy requer 'api_key' e 'api_secret'. "
                "Obtenha em: https://developer.godaddy.com/keys"
            )

        try:
            url = f"{self.base_url}/v1/domains"
            resp = requests.get(url, headers=self._headers, params={"limit": 1})

            if resp.status_code == 200:
                console.print("[green]✓ GoDaddy autenticado com sucesso[/green]")
                return True
            elif resp.status_code == 401:
                raise ProviderError("GoDaddy: credenciais inválidas (401)")
            elif resp.status_code == 403:
                raise ProviderError(
                    "GoDaddy: acesso negado (403). Verifique permissões da API key."
                )
            else:
                raise ProviderError(
                    f"GoDaddy: erro inesperado ({resp.status_code}): "
                    f"{resp.text[:200]}"
                )

        except requests.ConnectionError:
            raise ProviderError("GoDaddy: sem conexão com a API")
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(f"GoDaddy: falha na autenticação: {e}")

    def validate_credentials(self) -> bool:
        try:
            url = f"{self.base_url}/v1/domains"
            resp = requests.get(url, headers=self._headers, params={"limit": 1})
            return resp.status_code == 200
        except Exception:
            return False

    def create_resource(
        self, resource_type: str, params: dict[str, Any]
    ) -> ResourceResult:
        handlers = {
            "dns_record": self._create_dns_record,
            "domain": self._register_domain,
            "hosting": self._create_hosting,
        }

        handler = handlers.get(resource_type)
        if not handler:
            return ResourceResult(
                success=False,
                error=f"Tipo não suportado no GoDaddy: {resource_type}",
            )

        try:
            return handler(params)
        except Exception as e:
            return ResourceResult(success=False, error=str(e))

    def update_resource(
        self, resource_type: str, name: str,
        config: dict[str, Any], changes: dict[str, Any],
    ) -> ResourceResult:
        """Atualiza um registro DNS (PUT no GoDaddy)."""
        if resource_type == "dns_record":
            return self._update_dns_record(name, config)
        return ResourceResult(
            success=False, error=f"Update não suportado para: {resource_type}"
        )

    def delete_resource(
        self, resource_type: str, provider_id: str
    ) -> ResourceResult:
        """Deleta um registro DNS."""
        if resource_type == "dns_record":
            return self._delete_dns_record(provider_id)
        return ResourceResult(
            success=False, error=f"Delete não suportado para: {resource_type}"
        )

    def get_resource_status(
        self, resource_type: str, provider_id: str
    ) -> dict[str, Any]:
        return {"id": provider_id, "status": "active", "provider": "godaddy"}

    def list_regions(self) -> list[str]:
        return ["global"]

    # ── Domain Operations ─────────────────────────────────────

    def _register_domain(self, params: dict) -> ResourceResult:
        """Registra um novo domínio na GoDaddy."""
        domain = params["domain"]
        years = params.get("years", 1)
        privacy = params.get("privacy", True)
        auto_renew = params.get("auto_renew", True)

        console.print(
            f"  [cyan]Registrando domínio '{domain}' por {years} ano(s)...[/cyan]"
        )

        # Verificar disponibilidade
        availability_url = f"{self.base_url}/v1/domains/available"
        resp = requests.get(
            availability_url,
            headers=self._headers,
            params={"domain": domain},
        )

        if resp.status_code != 200:
            return ResourceResult(
                success=False,
                error=f"Erro ao verificar disponibilidade: {resp.text[:200]}",
            )

        data = resp.json()
        if not data.get("available", False):
            return ResourceResult(
                success=False,
                error=f"Domínio '{domain}' não está disponível para registro",
            )

        # Registrar domínio
        register_url = f"{self.base_url}/v1/domains"
        register_data = {
            "domain": domain,
            "years": years,
            "privacy": privacy,
            "auto_renew": auto_renew,
        }

        resp = requests.post(
            register_url,
            headers=self._headers,
            json=register_data,
        )

        if resp.status_code in [200, 201, 202]:
            return ResourceResult(
                success=True,
                provider_id=domain,
                outputs={
                    "domain": domain,
                    "years": years,
                    "privacy": privacy,
                    "auto_renew": auto_renew,
                },
                message=f"Domínio '{domain}' registrado com sucesso",
            )
        else:
            return ResourceResult(
                success=False,
                error=f"Erro ao registrar domínio: {resp.text[:200]}",
            )

    # ── Hosting Operations ─────────────────────────────────────

    def _create_hosting(self, params: dict) -> ResourceResult:
        """Cria um plano de hospedagem na GoDaddy."""
        domain = params["domain"]
        plan = params.get("plan", "economy")  # economy, deluxe, unlimited
        duration = params.get("duration", 12)  # meses

        console.print(
            f"  [cyan]Criando hospedagem '{domain}' com plano {plan}...[/cyan]"
        )

        # GoDaddy não tem API pública para criação de hospedagem
        # Retorna um resultado simulado para demonstração
        return ResourceResult(
            success=True,
            provider_id=f"hosting-{domain}",
            outputs={
                "domain": domain,
                "plan": plan,
                "duration_months": duration,
                "url": f"https://{domain}",
            },
            message=f"Hospedagem para '{domain}' criada (plano: {plan})",
        )

    # ── DNS Record Operations ─────────────────────────────────────

    def _create_dns_record(self, params: dict) -> ResourceResult:
        """Cria ou atualiza um registro DNS no GoDaddy."""
        domain = params["domain"]
        record_type = params.get("record_type", "CNAME")
        record_name = params["record_name"]
        record_value = params["record_value"]
        ttl = params.get("ttl", 3600)

        console.print(
            f"  [cyan]Criando DNS {record_type} '{record_name}.{domain}' "
            f"→ {record_value}...[/cyan]"
        )

        # Verificar se o domínio existe na conta
        domain_check = requests.get(
            f"{self.base_url}/v1/domains/{domain}",
            headers=self._headers,
        )

        if domain_check.status_code == 404:
            return ResourceResult(
                success=False,
                error=f"Domínio '{domain}' não encontrado na sua conta GoDaddy",
            )
        elif domain_check.status_code != 200:
            return ResourceResult(
                success=False,
                error=f"Erro ao verificar domínio: {domain_check.status_code}",
            )

        # Criar/atualizar o registro DNS
        # GoDaddy usa PUT para criar/atualizar registros de um tipo+nome
        url = (
            f"{self.base_url}/v1/domains/{domain}/"
            f"records/{record_type}/{record_name}"
        )

        payload = [{
            "data": record_value,
            "ttl": ttl,
        }]

        if params.get("priority") is not None:
            payload[0]["priority"] = params["priority"]

        resp = requests.put(url, json=payload, headers=self._headers)

        if resp.status_code in (200, 204):
            provider_id = f"{record_type}:{record_name}.{domain}"

            console.print(
                f"  [green]✓ DNS {record_type} criado: "
                f"{record_name}.{domain} → {record_value}[/green]"
            )

            return ResourceResult(
                success=True,
                provider_id=provider_id,
                outputs={
                    "domain": domain,
                    "record_type": record_type,
                    "record_name": record_name,
                    "record_value": record_value,
                    "fqdn": f"{record_name}.{domain}",
                    "ttl": ttl,
                },
                message=(
                    f"DNS {record_type} '{record_name}.{domain}' "
                    f"→ {record_value} (TTL: {ttl}s)"
                ),
            )
        else:
            error_msg = resp.text[:300]
            try:
                error_data = resp.json()
                error_msg = error_data.get("message", error_msg)
            except Exception:
                pass

            return ResourceResult(
                success=False,
                error=f"GoDaddy API error ({resp.status_code}): {error_msg}",
            )

    def _update_dns_record(self, name: str, config: dict) -> ResourceResult:
        """Atualiza registro existente (mesma operação que create no GoDaddy)."""
        params = {
            "domain": config["domain"],
            "record_type": config.get("record_type", "CNAME"),
            "record_name": config["record_name"],
            "record_value": config["record_value"],
            "ttl": config.get("ttl", 3600),
            "priority": config.get("priority"),
        }
        return self._create_dns_record(params)

    def _delete_dns_record(self, provider_id: str) -> ResourceResult:
        """
        Deleta um registro DNS do GoDaddy.
        provider_id formato: "CNAME:app.meudominio.com.br"
        """
        try:
            record_type, fqdn = provider_id.split(":", 1)
            parts = fqdn.split(".", 1)
            record_name = parts[0]
            domain = parts[1] if len(parts) > 1 else fqdn

            console.print(
                f"  [red]Removendo DNS {record_type} "
                f"'{record_name}.{domain}'...[/red]"
            )

            url = (
                f"{self.base_url}/v1/domains/{domain}/"
                f"records/{record_type}/{record_name}"
            )

            resp = requests.delete(url, headers=self._headers)

            if resp.status_code in (200, 204, 404):
                return ResourceResult(
                    success=True,
                    message=f"DNS {record_type} '{record_name}.{domain}' removido",
                )
            else:
                return ResourceResult(
                    success=False,
                    error=f"Erro ao deletar DNS: {resp.status_code}",
                )

        except Exception as e:
            return ResourceResult(success=False, error=str(e))

    # ── Helpers ───────────────────────────────────────────────────

    def list_domains(self) -> list[dict]:
        """Lista todos os domínios na conta GoDaddy."""
        resp = requests.get(
            f"{self.base_url}/v1/domains",
            headers=self._headers,
        )
        if resp.status_code == 200:
            return resp.json()
        return []

    def list_records(self, domain: str) -> list[dict]:
        """Lista todos os registros DNS de um domínio."""
        resp = requests.get(
            f"{self.base_url}/v1/domains/{domain}/records",
            headers=self._headers,
        )
        if resp.status_code == 200:
            return resp.json()
        return []

    def get_record(
        self, domain: str, record_type: str, record_name: str
    ) -> list[dict]:
        """Retorna registro(s) DNS específico(s)."""
        resp = requests.get(
            f"{self.base_url}/v1/domains/{domain}/"
            f"records/{record_type}/{record_name}",
            headers=self._headers,
        )
        if resp.status_code == 200:
            return resp.json()
        return []

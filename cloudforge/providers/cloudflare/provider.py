"""
CloudForge - Provider Cloudflare
Manage DNS records via Cloudflare API v4.

Requires an API Token with 'Zone.DNS' edit permissions.
Obtain at: https://dash.cloudflare.com/profile/api-tokens

YAML Configuration:
  external_providers:
    cloudflare:
      api_token: "your_api_token"
"""

import requests
from typing import Any
from rich.console import Console

from cloudforge.providers.base import BaseProvider, ProviderError
from cloudforge.resources.base import ResourceResult

console = Console()

class CloudflareProvider(BaseProvider):
    """Provider for Cloudflare DNS via REST API v4."""

    PROVIDER_NAME = "cloudflare"

    def __init__(self, region: str = "global", credentials: dict[str, Any] | None = None):
        super().__init__(region, credentials)
        self.api_token = (credentials or {}).get("api_token", "")
        self.base_url = "https://api.cloudflare.com/client/v4"
        self._zone_ids: dict[str, str] = {}

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    def authenticate(self) -> bool:
        """Validates API token by calling /user/tokens/verify."""
        if not self.api_token:
            raise ProviderError("Cloudflare requires 'api_token'.")

        try:
            url = f"{self.base_url}/user/tokens/verify"
            resp = requests.get(url, headers=self._headers)
            data = resp.json()

            if resp.status_code == 200 and data.get("success"):
                console.print("[green]✓ Cloudflare authenticated successfully[/green]")
                return True
            else:
                error_msg = data.get("errors", [{}])[0].get("message", "Unknown error")
                raise ProviderError(f"Cloudflare authentication failed: {error_msg}")

        except Exception as e:
            raise ProviderError(f"Cloudflare: failed to authenticate: {e}")

    def validate_credentials(self) -> bool:
        try:
            return self.authenticate()
        except Exception:
            return False

    def create_resource(self, resource_type: str, params: dict[str, Any]) -> ResourceResult:
        handlers = {
            "dns_record": self._create_dns_record,
            "cdn": self._create_cdn,
            "worker": self._create_worker,
            "pages": self._create_pages,
            "ssl_tls": self._configure_ssl_tls,
        }
        handler = handlers.get(resource_type)
        if not handler:
            return ResourceResult(success=False, error=f"Unsupported type: {resource_type}")
        try:
            return handler(params)
        except Exception as e:
            return ResourceResult(success=False, error=str(e))

    def update_resource(self, resource_type: str, name: str, config: dict[str, Any], changes: dict[str, Any]) -> ResourceResult:
        if resource_type == "dns_record":
            return self._update_dns_record(name, config)
        return ResourceResult(success=False, error=f"Update not supported for: {resource_type}")

    def delete_resource(self, resource_type: str, provider_id: str) -> ResourceResult:
        if resource_type == "dns_record":
            return self._delete_dns_record(provider_id)
        return ResourceResult(success=False, error=f"Delete not supported for: {resource_type}")

    def get_resource_status(self, resource_type: str, provider_id: str) -> dict[str, Any]:
        return {"id": provider_id, "status": "active", "provider": "cloudflare"}

    def list_regions(self) -> list[str]:
        return ["global"]

    # ── DNS Record Operations ─────────────────────────────────────

    def _get_zone_id(self, domain: str) -> str:
        """Look up zone_id for a domain name."""
        if domain in self._zone_ids:
            return self._zone_ids[domain]

        url = f"{self.base_url}/zones"
        resp = requests.get(url, headers=self._headers, params={"name": domain})
        data = resp.json()

        if resp.status_code == 200 and data.get("result"):
            zone_id = data["result"][0]["id"]
            self._zone_ids[domain] = zone_id
            return zone_id
        
        raise ProviderError(f"Could not find Cloudflare zone for domain: {domain}")

    def _create_dns_record(self, params: dict) -> ResourceResult:
        domain = params["domain"]
        record_type = params.get("record_type", "CNAME")
        record_name = params["record_name"]
        record_value = params["record_value"]
        ttl = params.get("ttl", 3600)
        # Cloudflare minimum TTL is 60 or 1 (for automatic)
        if ttl < 60 and ttl != 1:
            ttl = 1 # Automatic

        try:
            zone_id = self._get_zone_id(domain)
            full_name = f"{record_name}.{domain}" if record_name != "@" else domain

            console.print(f"  [cyan]Creating Cloudflare DNS {record_type} '{full_name}' → {record_value}...[/cyan]")

            # Check if record already exists to perform update or avoid duplicates
            check_url = f"{self.base_url}/zones/{zone_id}/dns_records"
            check_resp = requests.get(check_url, headers=self._headers, params={"name": full_name, "type": record_type})
            check_data = check_resp.json()

            payload = {
                "type": record_type,
                "name": full_name,
                "content": record_value,
                "ttl": ttl,
                "proxied": params.get("proxied", False)
            }
            if params.get("priority"):
                payload["priority"] = params["priority"]

            if check_data.get("result"):
                # Update existing
                record_id = check_data["result"][0]["id"]
                url = f"{self.base_url}/zones/{zone_id}/dns_records/{record_id}"
                resp = requests.put(url, headers=self._headers, json=payload)
            else:
                # Create new
                url = f"{self.base_url}/zones/{zone_id}/dns_records"
                resp = requests.post(url, headers=self._headers, json=payload)

            data = resp.json()
            if resp.status_code in (200, 201) and data.get("success"):
                record_id = data["result"]["id"]
                provider_id = f"{zone_id}:{record_id}"
                console.print(f"  [green]✓ Cloudflare DNS {record_type} created: {full_name}[/green]")
                return ResourceResult(
                    success=True,
                    provider_id=provider_id,
                    outputs={
                        "domain": domain,
                        "record_type": record_type,
                        "record_name": record_name,
                        "fqdn": full_name,
                        "record_value": record_value,
                        "record_id": record_id,
                        "zone_id": zone_id
                    }
                )
            else:
                error = data.get("errors", [{}])[0].get("message", "Unknown error")
                return ResourceResult(success=False, error=f"Cloudflare API Error: {error}")

        except Exception as e:
            return ResourceResult(success=False, error=str(e))

    def _update_dns_record(self, name: str, config: dict) -> ResourceResult:
        return self._create_dns_record(config)

    def _delete_dns_record(self, provider_id: str) -> ResourceResult:
        try:
            zone_id, record_id = provider_id.split(":")
            url = f"{self.base_url}/zones/{zone_id}/dns_records/{record_id}"
            resp = requests.delete(url, headers=self._headers)
            data = resp.json()

            if resp.status_code == 200 and data.get("success"):
                return ResourceResult(success=True, message=f"Cloudflare DNS record deleted")
            else:
                error = data.get("errors", [{}])[0].get("message", "Unknown error")
                return ResourceResult(success=False, error=f"Cloudflare delete error: {error}")
        except Exception as e:
            return ResourceResult(success=False, error=str(e))

    # ── Cloudflare CDN/Cache Operations ──────────────────────────

    def _create_cdn(self, params: dict) -> ResourceResult:
        """Configura CDN/Cache no Cloudflare."""
        domain = params.get("domain", "")
        cache_level = params.get("cache_level", "aggressive")
        auto_minify = params.get("auto_minify", True)
        rocket_loader = params.get("rocket_loader", False)
        always_online = params.get("always_online", True)

        if not domain:
            return ResourceResult(
                success=False,
                error="domain é obrigatório para CDN",
            )

        zone_id = self._get_zone_id(domain)
        if not zone_id:
            return ResourceResult(
                success=False,
                error=f"Zona '{domain}' não encontrada",
            )

        console.print(
            f"  [cyan]Configurando CDN para '{domain}'...[/cyan]"
        )

        # Configurar cache level
        cache_url = f"{self.base_url}/zones/{zone_id}/settings/cache_level"
        cache_data = {"value": cache_level}
        requests.patch(cache_url, headers=self._headers, json=cache_data)

        # Configurar auto minify
        if auto_minify:
            minify_url = f"{self.base_url}/zones/{zone_id}/settings/minify"
            minify_data = {"value": {"css": "on", "html": "on", "js": "on"}}
            requests.patch(minify_url, headers=self._headers, json=minify_data)

        # Configurar rocket loader
        if rocket_loader:
            rocket_url = f"{self.base_url}/zones/{zone_id}/settings/rocket_loader"
            rocket_data = {"value": "on"}
            requests.patch(rocket_url, headers=self._headers, json=rocket_data)

        # Configurar always online
        if always_online:
            online_url = f"{self.base_url}/zones/{zone_id}/settings/always_online"
            online_data = {"value": "on"}
            requests.patch(online_url, headers=self._headers, json=online_data)

        return ResourceResult(
            success=True,
            provider_id=f"cdn-{domain}",
            outputs={
                "domain": domain,
                "zone_id": zone_id,
                "cache_level": cache_level,
                "auto_minify": auto_minify,
                "rocket_loader": rocket_loader,
                "always_online": always_online,
                "cdn_url": f"https://{domain}",
            },
            message=f"CDN configurado para '{domain}'",
        )

    # ── Cloudflare Workers Operations ────────────────────────────

    def _create_worker(self, params: dict) -> ResourceResult:
        """Cria/deploy de Cloudflare Worker."""
        worker_name = params.get("name", "my-worker")
        script = params.get("script", "")
        route = params.get("route", "")
        domain = params.get("domain", "")

        if not script:
            return ResourceResult(
                success=False,
                error="script é obrigatório para Worker",
            )

        console.print(
            f"  [cyan]Criando Worker '{worker_name}'...[/cyan]"
        )

        # Deploy do worker
        worker_url = f"{self.base_url}/accounts/{self._get_account_id()}/workers/scripts/{worker_name}"
        worker_data = script

        resp = requests.put(
            worker_url,
            headers={**self._headers, "Content-Type": "application/javascript"},
            data=worker_data,
        )

        if resp.status_code == 200:
            # Adicionar route se fornecida
            if route and domain:
                zone_id = self._get_zone_id(domain)
                route_url = f"{self.base_url}/zones/{zone_id}/workers/routes"
                route_data = {"pattern": route, "script": worker_name}
                requests.post(route_url, headers=self._headers, json=route_data)

            return ResourceResult(
                success=True,
                provider_id=worker_name,
                outputs={
                    "worker_name": worker_name,
                    "route": route,
                    "url": f"https://{worker_name}.workers.dev",
                },
                message=f"Worker '{worker_name}' criado",
            )
        else:
            return ResourceResult(
                success=False,
                error=f"Erro ao criar Worker: {resp.text[:200]}",
            )

    # ── Cloudflare Pages Operations ──────────────────────────────

    def _create_pages(self, params: dict) -> ResourceResult:
        """Cria projeto Cloudflare Pages."""
        project_name = params.get("name", "my-pages")
        production_branch = params.get("branch", "main")

        console.print(
            f"  [cyan]Criando Pages project '{project_name}'...[/cyan]"
        )

        # Nota: Pages requer integração com Git provider
        # Esta é uma implementação simplificada
        return ResourceResult(
            success=True,
            provider_id=project_name,
            outputs={
                "project_name": project_name,
                "production_branch": production_branch,
                "url": f"https://{project_name}.pages.dev",
                "note": "Configurar Git integration via Cloudflare Dashboard",
            },
            message=f"Pages project '{project_name}' registrado",
        )

    # ── SSL/TLS Configuration ────────────────────────────────────

    def _configure_ssl_tls(self, params: dict) -> ResourceResult:
        """Configura SSL/TLS no Cloudflare."""
        domain = params.get("domain", "")
        ssl_mode = params.get("mode", "full")  # off, flexible, full, strict
        always_https = params.get("always_https", True)
        min_tls = params.get("min_tls", "1.2")

        if not domain:
            return ResourceResult(
                success=False,
                error="domain é obrigatório para SSL/TLS",
            )

        zone_id = self._get_zone_id(domain)
        if not zone_id:
            return ResourceResult(
                success=False,
                error=f"Zona '{domain}' não encontrada",
            )

        console.print(
            f"  [cyan]Configurando SSL/TLS para '{domain}' (mode: {ssl_mode})...[/cyan]"
        )

        # Configurar SSL mode
        ssl_url = f"{self.base_url}/zones/{zone_id}/settings/ssl"
        ssl_data = {"value": ssl_mode}
        requests.patch(ssl_url, headers=self._headers, json=ssl_data)

        # Configurar always use HTTPS
        if always_https:
            https_url = f"{self.base_url}/zones/{zone_id}/settings/always_use_https"
            https_data = {"value": "on"}
            requests.patch(https_url, headers=self._headers, json=https_data)

        # Configurar minimum TLS version
        tls_url = f"{self.base_url}/zones/{zone_id}/settings/min_tls_version"
        tls_data = {"value": f"1.{min_tls}"}
        requests.patch(tls_url, headers=self._headers, json=tls_data)

        return ResourceResult(
            success=True,
            provider_id=f"ssl-{domain}",
            outputs={
                "domain": domain,
                "zone_id": zone_id,
                "ssl_mode": ssl_mode,
                "always_https": always_https,
                "min_tls": min_tls,
            },
            message=f"SSL/TLS configurado para '{domain}'",
        )

    # ── Helper Methods ───────────────────────────────────────────

    def _get_zone_id(self, domain: str) -> str | None:
        """Obtém zone ID pelo domínio."""
        if domain in self._zone_ids:
            return self._zone_ids[domain]

        url = f"{self.base_url}/zones"
        params = {"name": domain}
        resp = requests.get(url, headers=self._headers, params=params)

        if resp.status_code == 200:
            data = resp.json()
            zones = data.get("result", [])
            if zones:
                self._zone_ids[domain] = zones[0]["id"]
                return zones[0]["id"]
        return None

    def _get_account_id(self) -> str:
        """Obtém account ID."""
        url = f"{self.base_url}/accounts"
        resp = requests.get(url, headers=self._headers)

        if resp.status_code == 200:
            data = resp.json()
            accounts = data.get("result", [])
            if accounts:
                return accounts[0]["id"]
        return ""

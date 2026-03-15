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
        if resource_type == "dns_record":
            return self._create_dns_record(params)
        return ResourceResult(success=False, error=f"Unsupported type: {resource_type}")

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

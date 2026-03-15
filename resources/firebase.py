"""
CloudForge - Recursos Firebase
Firebase Authentication, Firestore, Realtime Database e Hosting.
"""

from typing import Any
from resources.base import BaseResource, ResourceResult


# ═══════════════════════════════════════════════════════════════════════════════
# Firebase Authentication
# ═══════════════════════════════════════════════════════════════════════════════


class FirebaseAuthResource(BaseResource):
    """Gerencia configuração do Firebase Authentication."""

    RESOURCE_TYPE = "firebase_auth"

    VALID_PROVIDERS = [
        "email",
        "google",
        "facebook",
        "github",
        "twitter",
        "apple",
        "microsoft",
        "phone",
        "anonymous",
    ]

    def get_defaults(self) -> dict[str, Any]:
        return {
            "providers": ["email", "google"],
            "email_password_enabled": True,
            "email_link_enabled": False,
            "multi_factor_auth": False,
            "password_policy": {
                "min_length": 8,
                "require_uppercase": True,
                "require_lowercase": True,
                "require_numeric": True,
                "require_special": False,
            },
            "authorized_domains": [],
            "block_functions": {
                "before_create": None,
                "before_sign_in": None,
            },
        }

    def validate(self) -> list[str]:
        errors = []
        config = {**self.get_defaults(), **self.config}

        providers = config.get("providers", [])
        for p in providers:
            if p not in self.VALID_PROVIDERS:
                errors.append(
                    f"FirebaseAuth '{self.name}': provider '{p}' não suportado. "
                    f"Use: {', '.join(self.VALID_PROVIDERS)}"
                )

        # Verificar se providers que precisam de OAuth têm client_id
        oauth_providers = {"google", "facebook", "github", "twitter", "apple", "microsoft"}
        oauth_config = config.get("oauth", {})
        for p in providers:
            if p in oauth_providers and p != "google":
                if p not in oauth_config:
                    errors.append(
                        f"FirebaseAuth '{self.name}': provider '{p}' requer "
                        f"configuração OAuth (client_id/client_secret)"
                    )

        policy = config.get("password_policy", {})
        min_len = policy.get("min_length", 6)
        if min_len < 6 or min_len > 30:
            errors.append(
                f"FirebaseAuth '{self.name}': password min_length deve ser entre 6 e 30"
            )

        return errors

    def create(self) -> ResourceResult:
        config = self.resolve_config()
        params = {
            "name": self.name,
            "providers": config.get("providers", ["email", "google"]),
            "email_password_enabled": config.get("email_password_enabled", True),
            "email_link_enabled": config.get("email_link_enabled", False),
            "multi_factor_auth": config.get("multi_factor_auth", False),
            "password_policy": config.get("password_policy", {}),
            "oauth": config.get("oauth", {}),
            "authorized_domains": config.get("authorized_domains", []),
            "block_functions": config.get("block_functions", {}),
            "tags": config.get("tags", {}),
        }
        return self.provider.create_resource("firebase_auth", params)

    def update(self, changes: dict[str, Any]) -> ResourceResult:
        config = self.resolve_config()
        return self.provider.update_resource("firebase_auth", self.name, config, changes)

    def delete(self, provider_id: str) -> ResourceResult:
        return self.provider.delete_resource("firebase_auth", provider_id)

    def get_status(self, provider_id: str) -> dict[str, Any]:
        return self.provider.get_resource_status("firebase_auth", provider_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Cloud Firestore
# ═══════════════════════════════════════════════════════════════════════════════


class FirestoreResource(BaseResource):
    """Gerencia instâncias Cloud Firestore."""

    RESOURCE_TYPE = "firestore"

    def get_defaults(self) -> dict[str, Any]:
        return {
            "mode": "native",           # native | datastore
            "location": "us-central1",  # Será sobrescrito pela região do provider
            "delete_protection": False,
            "point_in_time_recovery": False,
            "concurrency_mode": "pessimistic",  # pessimistic | optimistic
        }

    def validate(self) -> list[str]:
        errors = []
        config = {**self.get_defaults(), **self.config}

        mode = config.get("mode", "native")
        if mode not in ("native", "datastore"):
            errors.append(
                f"Firestore '{self.name}': mode deve ser 'native' ou 'datastore'"
            )

        # Validar security rules se fornecidas
        rules = config.get("security_rules")
        if rules and not isinstance(rules, str):
            errors.append(
                f"Firestore '{self.name}': security_rules deve ser uma string "
                f"com o caminho do arquivo ou o conteúdo das regras"
            )

        # Validar indexes se fornecidos
        indexes = config.get("indexes", [])
        for i, idx in enumerate(indexes):
            if "collection" not in idx:
                errors.append(
                    f"Firestore '{self.name}': index [{i}] precisa de 'collection'"
                )
            if "fields" not in idx or not idx.get("fields"):
                errors.append(
                    f"Firestore '{self.name}': index [{i}] precisa de 'fields' (lista)"
                )

        return errors

    def create(self) -> ResourceResult:
        config = self.resolve_config()
        params = {
            "name": self.name,
            "mode": config.get("mode", "native"),
            "location": config.get("location"),
            "delete_protection": config.get("delete_protection", False),
            "point_in_time_recovery": config.get("point_in_time_recovery", False),
            "concurrency_mode": config.get("concurrency_mode", "pessimistic"),
            "security_rules": config.get("security_rules"),
            "indexes": config.get("indexes", []),
            "tags": config.get("tags", {}),
        }
        return self.provider.create_resource("firestore", params)

    def update(self, changes: dict[str, Any]) -> ResourceResult:
        config = self.resolve_config()
        return self.provider.update_resource("firestore", self.name, config, changes)

    def delete(self, provider_id: str) -> ResourceResult:
        return self.provider.delete_resource("firestore", provider_id)

    def get_status(self, provider_id: str) -> dict[str, Any]:
        return self.provider.get_resource_status("firestore", provider_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Firebase Realtime Database
# ═══════════════════════════════════════════════════════════════════════════════


class FirebaseRealtimeDBResource(BaseResource):
    """Gerencia instâncias do Firebase Realtime Database."""

    RESOURCE_TYPE = "firebase_rtdb"

    def get_defaults(self) -> dict[str, Any]:
        return {
            "type": "DEFAULT_DATABASE",  # DEFAULT_DATABASE | USER_DATABASE
            "location": "us-central1",
        }

    def validate(self) -> list[str]:
        errors = []
        config = {**self.get_defaults(), **self.config}

        db_type = config.get("type", "DEFAULT_DATABASE")
        if db_type not in ("DEFAULT_DATABASE", "USER_DATABASE"):
            errors.append(
                f"FirebaseRTDB '{self.name}': type deve ser "
                f"'DEFAULT_DATABASE' ou 'USER_DATABASE'"
            )

        rules = config.get("security_rules")
        if rules and not isinstance(rules, str):
            errors.append(
                f"FirebaseRTDB '{self.name}': security_rules deve ser string"
            )

        return errors

    def create(self) -> ResourceResult:
        config = self.resolve_config()
        params = {
            "name": self.name,
            "type": config.get("type", "DEFAULT_DATABASE"),
            "location": config.get("location"),
            "security_rules": config.get("security_rules"),
            "tags": config.get("tags", {}),
        }
        return self.provider.create_resource("firebase_rtdb", params)

    def update(self, changes: dict[str, Any]) -> ResourceResult:
        config = self.resolve_config()
        return self.provider.update_resource("firebase_rtdb", self.name, config, changes)

    def delete(self, provider_id: str) -> ResourceResult:
        return self.provider.delete_resource("firebase_rtdb", provider_id)

    def get_status(self, provider_id: str) -> dict[str, Any]:
        return self.provider.get_resource_status("firebase_rtdb", provider_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Firebase Hosting
# ═══════════════════════════════════════════════════════════════════════════════


class FirebaseHostingResource(BaseResource):
    """Gerencia sites do Firebase Hosting."""

    RESOURCE_TYPE = "firebase_hosting"

    def get_defaults(self) -> dict[str, Any]:
        return {
            "public_dir": "public",
            "single_page_app": True,
            "clean_urls": True,
        }

    def validate(self) -> list[str]:
        errors = []
        config = {**self.get_defaults(), **self.config}

        if not config.get("site_id") and not config.get("use_default_site", True):
            errors.append(
                f"FirebaseHosting '{self.name}': 'site_id' é obrigatório "
                f"quando use_default_site é false"
            )

        # Validar rewrites
        for i, rewrite in enumerate(config.get("rewrites", [])):
            if "source" not in rewrite:
                errors.append(
                    f"FirebaseHosting '{self.name}': rewrite [{i}] precisa de 'source'"
                )
            if "destination" not in rewrite and "function" not in rewrite and "run" not in rewrite:
                errors.append(
                    f"FirebaseHosting '{self.name}': rewrite [{i}] precisa de "
                    f"'destination', 'function' ou 'run'"
                )

        # Validar custom_domain
        custom_domain = config.get("custom_domain")
        if custom_domain and not isinstance(custom_domain, str):
            errors.append(
                f"FirebaseHosting '{self.name}': custom_domain deve ser string"
            )

        return errors

    def create(self) -> ResourceResult:
        config = self.resolve_config()
        params = {
            "name": self.name,
            "site_id": config.get("site_id", self.name),
            "use_default_site": config.get("use_default_site", True),
            "public_dir": config.get("public_dir", "public"),
            "single_page_app": config.get("single_page_app", True),
            "clean_urls": config.get("clean_urls", True),
            "custom_domain": config.get("custom_domain"),
            "rewrites": config.get("rewrites", []),
            "redirects": config.get("redirects", []),
            "headers": config.get("headers", []),
            "tags": config.get("tags", {}),
        }
        return self.provider.create_resource("firebase_hosting", params)

    def update(self, changes: dict[str, Any]) -> ResourceResult:
        config = self.resolve_config()
        return self.provider.update_resource("firebase_hosting", self.name, config, changes)

    def delete(self, provider_id: str) -> ResourceResult:
        return self.provider.delete_resource("firebase_hosting", provider_id)

    def get_status(self, provider_id: str) -> dict[str, Any]:
        return self.provider.get_resource_status("firebase_hosting", provider_id)

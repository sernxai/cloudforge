"""
CloudForge - Schema de Validação JSON
Define e valida a estrutura do arquivo infrastructure.yaml usando jsonschema.
"""

from typing import Any

import jsonschema
from jsonschema import Draft7Validator, ValidationError

from cloudforge.core.logger import get_logger

logger = get_logger(__name__)


# Schema JSON para validação da configuração CloudForge
CLOUDFORGE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://cloudforge.dev/schemas/infrastructure.v1.json",
    "title": "CloudForge Infrastructure Configuration",
    "description": "Schema para arquivos de configuração CloudForge",
    "type": "object",
    "required": ["project", "provider", "resources"],
    "additionalProperties": True,
    "properties": {
        "project": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 63,
                    "pattern": "^[a-z][a-z0-9-]*$",
                    "description": "Nome do projeto (lowercase, letras, números, hífens)"
                },
                "environment": {
                    "type": "string",
                    "enum": ["development", "staging", "production", "test"],
                    "default": "development"
                },
                "description": {
                    "type": "string",
                    "maxLength": 500
                },
                "tags": {
                    "type": "object",
                    "additionalProperties": {"type": "string"}
                }
            }
        },
        "provider": {
            "type": "object",
            "required": ["name", "region"],
            "properties": {
                "name": {
                    "type": "string",
                    "enum": ["aws", "gcp", "azure", "alibaba"],
                    "description": "Provedor de nuvem"
                },
                "region": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Região do provedor"
                },
                "credentials": {
                    "type": "object",
                    "additionalProperties": True
                },
                "profile": {
                    "type": "string",
                    "description": "Perfil de credenciais (ex: AWS profile)"
                }
            }
        },
        "external_cloudforge": {
            "type": "object",
            "description": "Configuração de providers externos (DNS, etc)",
            "properties": {
                "providers": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"type": "string"},
                            "credentials": {"type": "object"}
                        }
                    }
                }
            }
        },
        "resources": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["type", "name"],
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [
                            "vm", "vpc", "subnet", "security_group",
                            "kubernetes", "database", "cloud_run",
                            "firebase_auth", "firestore", "firebase_rtdb",
                            "firebase_hosting", "dns_record", "slb"
                        ],
                        "description": "Tipo de recurso"
                    },
                    "name": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 63,
                        "pattern": "^[a-z][a-z0-9-]*$",
                        "description": "Nome único do recurso"
                    },
                    "config": {
                        "type": "object",
                        "additionalProperties": True
                    },
                    "depends_on": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de nomes de recursos dos quais este depende"
                    },
                    "tags": {
                        "type": "object",
                        "additionalProperties": {"type": "string"}
                    }
                }
            }
        },
        "deploy": {
            "type": "object",
            "description": "Configuração de deploy de aplicações",
            "properties": {
                "image": {"type": "string"},
                "target": {"type": "string"},
                "replicas": {"type": "integer", "minimum": 1},
                "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                "env": {"type": "object"},
                "resources": {
                    "type": "object",
                    "properties": {
                        "cpu": {"type": "string"},
                        "memory": {"type": "string"}
                    }
                }
            }
        },
        "variables": {
            "type": "object",
            "description": "Variáveis de ambiente e configuração",
            "additionalProperties": True
        }
    }
}

# Schemas específicos por tipo de recurso
RESOURCE_CONFIG_SCHEMAS = {
    "vm": {
        "type": "object",
        "properties": {
            "instance_type": {"type": "string", "enum": ["small", "medium", "large", "xlarge"]},
            "disk_size_gb": {"type": "integer", "minimum": 10},
            "os": {"type": "string"},
            "associate_public_ip": {"type": "boolean"},
            "subnet": {"type": "string"},
            "security_group": {"type": "string"},
            "key_pair": {"type": "string"},
            "user_data": {"type": "string"},
            "tags": {"type": "object"}
        }
    },
    "vpc": {
        "type": "object",
        "required": ["cidr_block"],
        "properties": {
            "cidr_block": {
                "type": "string",
                "pattern": "^([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2}$"
            },
            "enable_dns_support": {"type": "boolean"},
            "enable_dns_hostnames": {"type": "boolean"}
        }
    },
    "subnet": {
        "type": "object",
        "required": ["vpc", "cidr_block"],
        "properties": {
            "vpc": {"type": "string"},
            "cidr_block": {
                "type": "string",
                "pattern": "^([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2}$"
            },
            "public": {"type": "boolean"},
            "availability_zone": {"type": "string"}
        }
    },
    "security_group": {
        "type": "object",
        "required": ["vpc"],
        "properties": {
            "vpc": {"type": "string"},
            "description": {"type": "string"},
            "ingress": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "protocol": {"type": "string", "enum": ["tcp", "udp", "icmp"]},
                        "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                        "port_range": {"type": "array", "items": {"type": "integer"}},
                        "cidr": {"type": "string"},
                        "description": {"type": "string"}
                    }
                }
            },
            "egress": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "protocol": {"type": "string"},
                        "port": {"type": "integer"},
                        "cidr": {"type": "string"}
                    }
                }
            }
        }
    },
    "kubernetes": {
        "type": "object",
        "properties": {
            "node_count": {"type": "integer", "minimum": 1},
            "node_type": {"type": "string"},
            "kubernetes_version": {"type": "string"},
            "min_nodes": {"type": "integer", "minimum": 0},
            "max_nodes": {"type": "integer", "minimum": 1},
            "auto_scaling": {"type": "boolean"},
            "disk_size_gb": {"type": "integer", "minimum": 20}
        }
    },
    "database": {
        "type": "object",
        "required": ["engine"],
        "properties": {
            "engine": {
                "type": "string",
                "enum": ["postgresql", "mysql", "mariadb", "sqlserver"]
            },
            "version": {"type": "string"},
            "instance_type": {"type": "string"},
            "storage_gb": {"type": "integer", "minimum": 20},
            "multi_az": {"type": "boolean"},
            "backup_retention_days": {"type": "integer", "minimum": 0, "maximum": 35},
            "publicly_accessible": {"type": "boolean"},
            "master_username": {"type": "string"},
            "database_name": {"type": "string"}
        }
    },
    "cloud_run": {
        "type": "object",
        "required": ["image"],
        "properties": {
            "image": {"type": "string"},
            "cpu": {"type": "string"},
            "memory": {"type": "string"},
            "min_instances": {"type": "integer", "minimum": 0},
            "max_instances": {"type": "integer", "minimum": 1},
            "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 3600},
            "ingress": {
                "type": "string",
                "enum": ["all", "internal", "internal-and-cloud-load-balancing"]
            },
            "port": {"type": "integer", "minimum": 1, "maximum": 65535},
            "env": {"type": "object"},
            "execution_environment": {"type": "string", "enum": ["gen1", "gen2"]}
        }
    },
    "slb": {
        "type": "object",
        "required": ["name"],
        "properties": {
            "name": {"type": "string"},
            "public": {"type": "boolean"},
            "vpc": {"type": "string"},
            "subnet": {"type": "string"},
            "bandwidth": {"type": "integer", "minimum": 1},
            "charge_type": {"type": "string", "enum": ["PayByTraffic", "PayByBandwidth"]},
            "listeners": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "frontend_port": {"type": "integer"},
                        "backend_port": {"type": "integer"},
                        "bandwidth": {"type": "integer"}
                    }
                }
            }
        }
    },
    "dns_record": {
        "type": "object",
        "required": ["domain", "type", "name", "value"],
        "properties": {
            "domain": {"type": "string"},
            "type": {"type": "string", "enum": ["A", "AAAA", "CNAME", "MX", "TXT", "NS", "CAA"]},
            "name": {"type": "string"},
            "value": {"type": "string"},
            "ttl": {"type": "integer", "minimum": 60, "maximum": 86400},
            "priority": {"type": "integer", "minimum": 0, "maximum": 65535}
        }
    }
}


class SchemaValidationError(Exception):
    """Exceção para erros de validação de schema."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


class SchemaValidator:
    """Validador de schema para configuração CloudForge."""

    def __init__(self, schema: dict | None = None):
        self.schema = schema or CLOUDFORGE_SCHEMA
        self.validator = Draft7Validator(self.schema)

    def validate(self, config: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Valida uma configuração contra o schema.

        Args:
            config: Dicionário de configuração

        Returns:
            Tuple (is_valid, list_of_errors)
        """
        errors = []

        # Validar schema principal
        for error in self.validator.iter_errors(config):
            error_msg = self._format_validation_error(error)
            errors.append(error_msg)

        # Validar configs de recursos individualmente
        if "resources" in config:
            for resource in config["resources"]:
                resource_errors = self._validate_resource_config(resource)
                errors.extend(resource_errors)

        return len(errors) == 0, errors

    def validate_or_raise(self, config: dict[str, Any]) -> bool:
        """
        Valida configuração e lança exceção se inválida.

        Args:
            config: Dicionário de configuração

        Returns:
            True se válido

        Raises:
            SchemaValidationError: Se houver erros de validação
        """
        is_valid, errors = self.validate(config)

        if not is_valid:
            error_msg = f"Validação de schema falhou com {len(errors)} erro(s)"
            raise SchemaValidationError(error_msg, errors)

        return True

    def _format_validation_error(self, error: ValidationError) -> str:
        """Formata um erro de validação jsonschema de forma legível."""
        path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"

        # Mensagem mais amigável para erros comuns
        if error.validator == "required":
            missing_fields = ", ".join(error.validator_value)
            return f"Campo(s) obrigatório(s) faltando em '{path}': {missing_fields}"

        elif error.validator == "enum":
            allowed = ", ".join(str(v) for v in error.validator_value)
            return f"Valor inválido em '{path}': '{error.instance}'. Valores permitidos: {allowed}"

        elif error.validator == "pattern":
            return f"Formato inválido em '{path}': '{error.instance}' não corresponde ao padrão esperado"

        elif error.validator == "minimum":
            return f"Valor muito baixo em '{path}': {error.instance} (mínimo: {error.validator_value})"

        elif error.validator == "maximum":
            return f"Valor muito alto em '{path}': {error.instance} (máximo: {error.validator_value})"

        elif error.validator == "minLength":
            return f"Texto muito curto em '{path}': mínimo de {error.validator_value} caracteres"

        elif error.validator == "maxLength":
            return f"Texto muito longo em '{path}': máximo de {error.validator_value} caracteres"

        elif error.validator == "type":
            return f"Tipo inválido em '{path}': esperado {error.validator_value}, got {type(error.instance).__name__}"

        else:
            return f"Erro em '{path}': {error.message}"

    def _validate_resource_config(self, resource: dict[str, Any]) -> list[str]:
        """Valida a config de um recurso específico."""
        errors = []
        resource_type = resource.get("type")
        config = resource.get("config", {})

        if resource_type in RESOURCE_CONFIG_SCHEMAS:
            resource_schema = RESOURCE_CONFIG_SCHEMAS[resource_type]
            resource_validator = Draft7Validator(resource_schema)

            for error in resource_validator.iter_errors(config):
                error_msg = self._format_validation_error(error)
                errors.append(f"Recurso '{resource.get('name', 'unknown')}': {error_msg}")

        return errors


def validate_config(config: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Função convenience para validar configuração.

    Args:
        config: Dicionário de configuração

    Returns:
        Tuple (is_valid, list_of_errors)
    """
    validator = SchemaValidator()
    return validator.validate(config)


def validate_config_or_raise(config: dict[str, Any]) -> None:
    """
    Função convenience para validar configuração (lança exceção se inválida).

    Args:
        config: Dicionário de configuração

    Raises:
        SchemaValidationError: Se houver erros de validação
    """
    validator = SchemaValidator()
    validator.validate_or_raise(config)

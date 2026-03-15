"""
CloudForge — Testes Unitários
Cobre: Config, State, Graph, Planner, Resources, Alibaba Cloud, Logging, Retry, Schema
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

# Adicionar diretório do projeto ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import Config, ConfigError
from core.state import StateManager, ResourceState
from core.graph import DependencyGraph, CyclicDependencyError
from core.planner import Planner, ActionType
from core.logger import CloudForgeLogger, get_logger, retry_with_backoff, RetryError
from core.schema import SchemaValidator, validate_config, SchemaValidationError
from core.retry import retry_on_exception, retry_cloud_operation, RetryConfig
from resources.vm import VMResource
from resources.network import VPCResource, SubnetResource, SecurityGroupResource
from resources.kubernetes import KubernetesResource
from resources.database import DatabaseResource
from resources.cloud_run import CloudRunResource
from resources.firebase import (
    FirebaseAuthResource,
    FirestoreResource,
    FirebaseRealtimeDBResource,
    FirebaseHostingResource,
)
from resources.dns import DNSRecordResource


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_config_data():
    return {
        "project": {
            "name": "test-project",
            "environment": "development",
        },
        "provider": {
            "name": "aws",
            "region": "us-east-1",
        },
        "resources": [
            {
                "type": "vpc",
                "name": "test-vpc",
                "config": {"cidr_block": "10.0.0.0/16"},
            },
            {
                "type": "subnet",
                "name": "test-subnet",
                "depends_on": ["test-vpc"],
                "config": {
                    "vpc": "test-vpc",
                    "cidr_block": "10.0.1.0/24",
                    "public": True,
                },
            },
            {
                "type": "kubernetes",
                "name": "test-cluster",
                "depends_on": ["test-subnet"],
                "config": {
                    "node_count": 3,
                    "node_type": "medium",
                    "kubernetes_version": "1.29",
                },
            },
            {
                "type": "database",
                "name": "test-db",
                "depends_on": ["test-vpc"],
                "config": {
                    "engine": "postgresql",
                    "version": "15",
                    "instance_type": "medium",
                    "storage_gb": 50,
                },
            },
        ],
    }


@pytest.fixture
def config_file(sample_config_data, tmp_path):
    config_path = tmp_path / "infrastructure.yaml"
    with open(config_path, "w") as f:
        yaml.dump(sample_config_data, f)
    return str(config_path)


@pytest.fixture
def state_file(tmp_path):
    return str(tmp_path / ".cloudforge" / "state.json")


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: Config
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfig:
    def test_load_valid_config(self, config_file):
        config = Config(config_file)
        data = config.load()
        assert data["project"]["name"] == "test-project"
        assert data["provider"]["name"] == "aws"
        assert len(data["resources"]) == 4

    def test_config_file_not_found(self, tmp_path):
        config = Config(str(tmp_path / "nonexistent.yaml"))
        with pytest.raises(ConfigError, match="não encontrado"):
            config.load()

    def test_invalid_yaml(self, tmp_path):
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text(": : : invalid yaml {{{}}}}")
        config = Config(str(bad_yaml))
        with pytest.raises(ConfigError):
            config.load()

    def test_missing_required_field(self, tmp_path):
        incomplete = tmp_path / "incomplete.yaml"
        with open(incomplete, "w") as f:
            yaml.dump({"project": {"name": "test"}}, f)
        config = Config(str(incomplete))
        with pytest.raises(ConfigError, match="Configuração inválida"):
            config.load()

    def test_duplicate_resource_names(self, tmp_path):
        data = {
            "project": {"name": "test"},
            "provider": {"name": "aws", "region": "us-east-1"},
            "resources": [
                {"type": "vpc", "name": "dup-name", "config": {"cidr_block": "10.0.0.0/16"}},
                {"type": "vpc", "name": "dup-name", "config": {"cidr_block": "10.1.0.0/16"}},
            ],
        }
        cfg_path = tmp_path / "dup.yaml"
        with open(cfg_path, "w") as f:
            yaml.dump(data, f)
        config = Config(str(cfg_path))
        with pytest.raises(ConfigError, match="duplicados"):
            config.load()

    def test_invalid_dependency_reference(self, tmp_path):
        data = {
            "project": {"name": "test"},
            "provider": {"name": "aws", "region": "us-east-1"},
            "resources": [
                {
                    "type": "subnet",
                    "name": "orphan-subnet",
                    "depends_on": ["nonexistent-vpc"],
                    "config": {"vpc": "x", "cidr_block": "10.0.1.0/24"},
                },
            ],
        }
        cfg_path = tmp_path / "bad_dep.yaml"
        with open(cfg_path, "w") as f:
            yaml.dump(data, f)
        config = Config(str(cfg_path))
        with pytest.raises(ConfigError, match="não existe"):
            config.load()

    def test_env_var_resolution(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TEST_REGION", "eu-west-1")
        data = {
            "project": {"name": "test"},
            "provider": {"name": "aws", "region": "${TEST_REGION}"},
            "resources": [],
        }
        cfg_path = tmp_path / "env.yaml"
        with open(cfg_path, "w") as f:
            yaml.dump(data, f)
        config = Config(str(cfg_path))
        result = config.load()
        assert result["provider"]["region"] == "eu-west-1"

    def test_properties(self, config_file):
        config = Config(config_file)
        config.load()
        assert config.project["name"] == "test-project"
        assert config.provider["name"] == "aws"
        assert len(config.resources) == 4
        assert config.deploy is None


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: DependencyGraph
# ═══════════════════════════════════════════════════════════════════════════════


class TestDependencyGraph:
    def test_simple_order(self):
        graph = DependencyGraph()
        graph.add_node("vpc")
        graph.add_node("subnet")
        graph.add_edge("subnet", "vpc")  # subnet depende de vpc

        order = graph.topological_sort()
        assert order.index("vpc") < order.index("subnet")

    def test_complex_order(self):
        resources = [
            {"name": "vpc", "depends_on": []},
            {"name": "subnet", "depends_on": ["vpc"]},
            {"name": "sg", "depends_on": ["vpc"]},
            {"name": "cluster", "depends_on": ["subnet", "sg"]},
            {"name": "db", "depends_on": ["vpc"]},
        ]
        graph = DependencyGraph.from_resources(resources)
        order = graph.topological_sort()

        assert order.index("vpc") < order.index("subnet")
        assert order.index("vpc") < order.index("sg")
        assert order.index("subnet") < order.index("cluster")
        assert order.index("sg") < order.index("cluster")
        assert order.index("vpc") < order.index("db")

    def test_cyclic_dependency(self):
        graph = DependencyGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        graph.add_edge("c", "a")

        with pytest.raises(CyclicDependencyError, match="circular"):
            graph.topological_sort()

    def test_reverse_order(self):
        graph = DependencyGraph()
        graph.add_edge("subnet", "vpc")
        order = graph.topological_sort()
        reverse = graph.reverse_topological_sort()
        assert reverse == list(reversed(order))

    def test_get_dependencies(self):
        graph = DependencyGraph()
        graph.add_edge("cluster", "subnet")
        graph.add_edge("cluster", "sg")
        deps = graph.get_dependencies("cluster")
        assert deps == {"subnet", "sg"}

    def test_get_dependents(self):
        graph = DependencyGraph()
        graph.add_edge("subnet", "vpc")
        graph.add_edge("db", "vpc")
        dependents = graph.get_dependents("vpc")
        assert dependents == {"subnet", "db"}

    def test_independent_nodes(self):
        graph = DependencyGraph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        order = graph.topological_sort()
        assert set(order) == {"a", "b", "c"}


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: StateManager
# ═══════════════════════════════════════════════════════════════════════════════


class TestStateManager:
    def test_new_state(self, state_file):
        sm = StateManager(state_file)
        sm.load()
        assert sm.list_resources() == []

    def test_add_and_retrieve_resource(self, state_file):
        sm = StateManager(state_file)
        sm.load()

        res = ResourceState(
            name="test-vpc",
            resource_type="vpc",
            provider="aws",
            config={"cidr_block": "10.0.0.0/16"},
            provider_id="vpc-12345",
            status="active",
        )
        sm.set_resource(res)
        sm.save()

        # Recarregar
        sm2 = StateManager(state_file)
        sm2.load()
        loaded = sm2.get_resource("test-vpc")
        assert loaded is not None
        assert loaded.provider_id == "vpc-12345"
        assert loaded.status == "active"

    def test_remove_resource(self, state_file):
        sm = StateManager(state_file)
        sm.load()

        res = ResourceState(
            name="to-delete", resource_type="vm",
            provider="aws", config={},
        )
        sm.set_resource(res)
        assert sm.has_resource("to-delete")

        sm.remove_resource("to-delete")
        assert not sm.has_resource("to-delete")

    def test_diff_create(self, state_file):
        sm = StateManager(state_file)
        sm.load()

        desired = [
            {"name": "new-vpc", "type": "vpc", "config": {"cidr_block": "10.0.0.0/16"}}
        ]
        diff = sm.diff(desired)
        assert len(diff["create"]) == 1
        assert diff["create"][0]["name"] == "new-vpc"
        assert len(diff["delete"]) == 0

    def test_diff_delete(self, state_file):
        sm = StateManager(state_file)
        sm.load()

        res = ResourceState(
            name="old-vpc", resource_type="vpc",
            provider="aws", config={"cidr_block": "10.0.0.0/16"},
            status="active",
        )
        sm.set_resource(res)

        diff = sm.diff([])  # Nenhum recurso desejado
        assert len(diff["delete"]) == 1
        assert diff["delete"][0]["name"] == "old-vpc"

    def test_diff_update(self, state_file):
        sm = StateManager(state_file)
        sm.load()

        res = ResourceState(
            name="vpc", resource_type="vpc",
            provider="aws", config={"cidr_block": "10.0.0.0/16"},
            status="active",
        )
        sm.set_resource(res)

        desired = [
            {"name": "vpc", "type": "vpc", "config": {"cidr_block": "10.1.0.0/16"}}
        ]
        diff = sm.diff(desired)
        assert len(diff["update"]) == 1

    def test_diff_unchanged(self, state_file):
        sm = StateManager(state_file)
        sm.load()

        config = {"cidr_block": "10.0.0.0/16"}
        res = ResourceState(
            name="vpc", resource_type="vpc",
            provider="aws", config=config,
            status="active",
        )
        sm.set_resource(res)

        desired = [{"name": "vpc", "type": "vpc", "config": config}]
        diff = sm.diff(desired)
        assert len(diff["unchanged"]) == 1
        assert len(diff["create"]) == 0
        assert len(diff["update"]) == 0

    def test_backup_created_on_save(self, state_file):
        sm = StateManager(state_file)
        sm.load()
        sm.set_resource(ResourceState(
            name="x", resource_type="vm", provider="aws", config={}
        ))
        sm.save()
        sm.save()  # Segunda vez cria backup

        backup = Path(state_file).with_suffix(".json.backup")
        assert backup.exists()

    def test_config_hash(self):
        res1 = ResourceState(
            name="a", resource_type="vpc", provider="aws",
            config={"cidr": "10.0.0.0/16"},
        )
        res2 = ResourceState(
            name="b", resource_type="vpc", provider="aws",
            config={"cidr": "10.0.0.0/16"},
        )
        res3 = ResourceState(
            name="c", resource_type="vpc", provider="aws",
            config={"cidr": "10.1.0.0/16"},
        )
        assert res1.config_hash == res2.config_hash
        assert res1.config_hash != res3.config_hash


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: Planner
# ═══════════════════════════════════════════════════════════════════════════════


class TestPlanner:
    def test_create_plan_with_creates(self):
        planner = Planner(project_name="test", provider_name="aws")
        diff = {
            "create": [
                {"name": "vpc", "type": "vpc", "config": {"cidr_block": "10.0.0.0/16"}},
                {"name": "subnet", "type": "subnet", "config": {"cidr_block": "10.0.1.0/24"}},
            ],
            "update": [],
            "delete": [],
            "unchanged": [],
        }
        plan = planner.create_plan(diff, ["vpc", "subnet"])

        assert plan.has_changes
        assert len(plan.creates) == 2
        assert plan.actions[0].resource_name == "vpc"
        assert plan.actions[1].resource_name == "subnet"

    def test_plan_no_changes(self):
        planner = Planner()
        diff = {
            "create": [],
            "update": [],
            "delete": [],
            "unchanged": [{"name": "vpc", "resource_type": "vpc"}],
        }
        plan = planner.create_plan(diff, ["vpc"])
        assert not plan.has_changes

    def test_plan_mixed_actions(self):
        planner = Planner()
        diff = {
            "create": [{"name": "new-res", "type": "vm", "config": {}}],
            "update": [{
                "current": {"name": "upd-res", "resource_type": "vpc", "config": {"a": 1}},
                "desired": {"name": "upd-res", "type": "vpc", "config": {"a": 2}},
            }],
            "delete": [{"name": "old-res", "resource_type": "subnet"}],
            "unchanged": [],
        }
        plan = planner.create_plan(diff, ["upd-res", "new-res"])

        assert len(plan.creates) == 1
        assert len(plan.updates) == 1
        assert len(plan.deletes) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: Resources (validação)
# ═══════════════════════════════════════════════════════════════════════════════


class TestVMResource:
    def test_valid_config(self):
        vm = VMResource(name="test-vm", config={"instance_type": "medium"})
        assert vm.validate() == []

    def test_invalid_disk_size(self):
        vm = VMResource(name="test-vm", config={"disk_size_gb": 5})
        errors = vm.validate()
        assert any("disk_size_gb" in e for e in errors)

    def test_defaults(self):
        vm = VMResource(name="test-vm", config={})
        defaults = vm.get_defaults()
        assert defaults["instance_type"] == "medium"
        assert defaults["disk_size_gb"] == 30

    def test_instance_type_mapping(self):
        vm = VMResource(name="test-vm", config={})
        assert "t3.medium" in vm.INSTANCE_TYPE_MAP["aws"].values()
        assert "e2-medium" in vm.INSTANCE_TYPE_MAP["gcp"].values()
        assert "Standard_B2s" in vm.INSTANCE_TYPE_MAP["azure"].values()


class TestVPCResource:
    def test_valid_config(self):
        vpc = VPCResource(name="test-vpc", config={"cidr_block": "10.0.0.0/16"})
        assert vpc.validate() == []

    def test_invalid_cidr(self):
        vpc = VPCResource(name="test-vpc", config={"cidr_block": "invalid"})
        errors = vpc.validate()
        assert any("cidr_block" in e for e in errors)


class TestSubnetResource:
    def test_valid_config(self):
        subnet = SubnetResource(
            name="test-subnet",
            config={"vpc": "main-vpc", "cidr_block": "10.0.1.0/24"},
        )
        assert subnet.validate() == []

    def test_missing_vpc(self):
        subnet = SubnetResource(
            name="test-subnet", config={"cidr_block": "10.0.1.0/24"}
        )
        errors = subnet.validate()
        assert any("vpc" in e for e in errors)

    def test_missing_cidr(self):
        subnet = SubnetResource(name="test-subnet", config={"vpc": "main"})
        errors = subnet.validate()
        assert any("cidr_block" in e for e in errors)


class TestSecurityGroupResource:
    def test_valid_config(self):
        sg = SecurityGroupResource(
            name="test-sg",
            config={
                "vpc": "main-vpc",
                "ingress": [{"port": 80, "protocol": "tcp"}],
            },
        )
        assert sg.validate() == []

    def test_missing_vpc(self):
        sg = SecurityGroupResource(name="test-sg", config={})
        errors = sg.validate()
        assert any("vpc" in e for e in errors)

    def test_ingress_missing_port(self):
        sg = SecurityGroupResource(
            name="test-sg",
            config={"vpc": "main", "ingress": [{"protocol": "tcp"}]},
        )
        errors = sg.validate()
        assert any("port" in e for e in errors)


class TestKubernetesResource:
    def test_valid_config(self):
        k8s = KubernetesResource(
            name="test-cluster",
            config={"node_count": 3, "node_type": "medium"},
        )
        assert k8s.validate() == []

    def test_invalid_node_count(self):
        k8s = KubernetesResource(
            name="test-cluster", config={"node_count": 0}
        )
        errors = k8s.validate()
        assert any("node_count" in e for e in errors)

    def test_min_greater_than_max(self):
        k8s = KubernetesResource(
            name="test-cluster",
            config={"node_count": 3, "min_nodes": 10, "max_nodes": 5},
        )
        errors = k8s.validate()
        assert any("min_nodes" in e for e in errors)


class TestDatabaseResource:
    def test_valid_config(self):
        db = DatabaseResource(
            name="test-db",
            config={"engine": "postgresql", "storage_gb": 50},
        )
        assert db.validate() == []

    def test_unsupported_engine(self):
        db = DatabaseResource(
            name="test-db", config={"engine": "oracle", "storage_gb": 50}
        )
        errors = db.validate()
        assert any("engine" in e for e in errors)

    def test_storage_too_small(self):
        db = DatabaseResource(
            name="test-db",
            config={"engine": "postgresql", "storage_gb": 5},
        )
        errors = db.validate()
        assert any("storage_gb" in e for e in errors)

    def test_invalid_retention(self):
        db = DatabaseResource(
            name="test-db",
            config={
                "engine": "postgresql",
                "storage_gb": 50,
                "backup_retention_days": 100,
            },
        )
        errors = db.validate()
        assert any("backup_retention_days" in e for e in errors)


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: Resolve Config & Cross-References
# ═══════════════════════════════════════════════════════════════════════════════


class TestResourceConfig:
    def test_resolve_config_with_defaults(self):
        vm = VMResource(name="vm", config={"instance_type": "large"})
        resolved = vm.resolve_config()
        assert resolved["instance_type"] == "large"
        assert resolved["disk_size_gb"] == 30  # default

    def test_resolve_config_with_references(self):
        vm = VMResource(
            name="vm",
            config={"subnet": "${main-subnet.subnet_id}"},
        )
        context = {"main-subnet": {"subnet_id": "subnet-abc123"}}
        resolved = vm.resolve_config(context)
        assert resolved["subnet"] == "subnet-abc123"


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: Integração (end-to-end do fluxo plan)
# ═══════════════════════════════════════════════════════════════════════════════


class TestIntegration:
    def test_full_plan_flow(self, config_file, state_file):
        """Testa o fluxo completo: load config → build graph → diff → plan."""
        config = Config(config_file)
        data = config.load()

        state = StateManager(state_file)
        state.load()

        graph = DependencyGraph.from_resources(config.resources)
        order = graph.topological_sort()

        # VPC deve vir primeiro
        assert order[0] == "test-vpc"
        # Cluster deve vir depois de subnet
        assert order.index("test-subnet") < order.index("test-cluster")

        diff = state.diff(config.resources)
        assert len(diff["create"]) == 4  # Todos os recursos são novos
        assert len(diff["delete"]) == 0

        planner = Planner(project_name="test", provider_name="aws")
        plan = planner.create_plan(diff, order)

        assert plan.has_changes
        assert len(plan.creates) == 4
        assert plan.actions[0].resource_name == "test-vpc"

    def test_incremental_plan(self, config_file, state_file):
        """Testa que recursos existentes aparecem como unchanged."""
        config = Config(config_file)
        data = config.load()

        state = StateManager(state_file)
        state.load()

        # Simular que VPC já existe
        vpc_res = ResourceState(
            name="test-vpc",
            resource_type="vpc",
            provider="aws",
            config={"cidr_block": "10.0.0.0/16"},
            provider_id="vpc-123",
            status="active",
        )
        state.set_resource(vpc_res)

        diff = state.diff(config.resources)
        assert len(diff["create"]) == 3  # Sem a VPC
        assert len(diff["unchanged"]) == 1
        assert diff["unchanged"][0]["name"] == "test-vpc"


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: CloudRunResource
# ═══════════════════════════════════════════════════════════════════════════════


class TestCloudRunResource:
    def test_valid_config(self):
        cr = CloudRunResource(
            name="api",
            config={"image": "gcr.io/projeto/app:latest"},
        )
        assert cr.validate() == []

    def test_missing_image(self):
        cr = CloudRunResource(name="api", config={})
        errors = cr.validate()
        assert any("image" in e for e in errors)

    def test_invalid_cpu(self):
        cr = CloudRunResource(
            name="api",
            config={"image": "gcr.io/p/a", "cpu": "16"},
        )
        errors = cr.validate()
        assert any("cpu" in e for e in errors)

    def test_invalid_memory(self):
        cr = CloudRunResource(
            name="api",
            config={"image": "gcr.io/p/a", "memory": "500MB"},
        )
        errors = cr.validate()
        assert any("memory" in e for e in errors)

    def test_min_greater_than_max_instances(self):
        cr = CloudRunResource(
            name="api",
            config={"image": "gcr.io/p/a", "min_instances": 10, "max_instances": 5},
        )
        errors = cr.validate()
        assert any("min_instances" in e for e in errors)

    def test_invalid_timeout(self):
        cr = CloudRunResource(
            name="api",
            config={"image": "gcr.io/p/a", "timeout_seconds": 9999},
        )
        errors = cr.validate()
        assert any("timeout" in e for e in errors)

    def test_invalid_ingress(self):
        cr = CloudRunResource(
            name="api",
            config={"image": "gcr.io/p/a", "ingress": "public"},
        )
        errors = cr.validate()
        assert any("ingress" in e for e in errors)

    def test_defaults(self):
        cr = CloudRunResource(name="api", config={})
        defaults = cr.get_defaults()
        assert defaults["cpu"] == "1"
        assert defaults["memory"] == "512Mi"
        assert defaults["min_instances"] == 0
        assert defaults["max_instances"] == 100
        assert defaults["execution_environment"] == "gen2"


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: FirebaseAuthResource
# ═══════════════════════════════════════════════════════════════════════════════


class TestFirebaseAuthResource:
    def test_valid_config(self):
        auth = FirebaseAuthResource(
            name="auth",
            config={"providers": ["email", "google"]},
        )
        assert auth.validate() == []

    def test_invalid_provider(self):
        auth = FirebaseAuthResource(
            name="auth",
            config={"providers": ["email", "steam"]},
        )
        errors = auth.validate()
        assert any("steam" in e for e in errors)

    def test_invalid_password_policy(self):
        auth = FirebaseAuthResource(
            name="auth",
            config={"password_policy": {"min_length": 3}},
        )
        errors = auth.validate()
        assert any("min_length" in e for e in errors)

    def test_oauth_provider_without_config(self):
        auth = FirebaseAuthResource(
            name="auth",
            config={"providers": ["facebook"]},
        )
        errors = auth.validate()
        assert any("facebook" in e and "OAuth" in e for e in errors)

    def test_google_no_oauth_needed(self):
        """Google é automático no Firebase, não precisa de OAuth config."""
        auth = FirebaseAuthResource(
            name="auth",
            config={"providers": ["google"]},
        )
        assert auth.validate() == []

    def test_defaults(self):
        auth = FirebaseAuthResource(name="auth", config={})
        defaults = auth.get_defaults()
        assert "email" in defaults["providers"]
        assert "google" in defaults["providers"]
        assert defaults["email_password_enabled"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: FirestoreResource
# ═══════════════════════════════════════════════════════════════════════════════


class TestFirestoreResource:
    def test_valid_config(self):
        fs = FirestoreResource(
            name="main-db",
            config={"mode": "native", "location": "us-central1"},
        )
        assert fs.validate() == []

    def test_invalid_mode(self):
        fs = FirestoreResource(
            name="db", config={"mode": "graph"}
        )
        errors = fs.validate()
        assert any("mode" in e for e in errors)

    def test_invalid_rules_type(self):
        fs = FirestoreResource(
            name="db", config={"security_rules": 12345}
        )
        errors = fs.validate()
        assert any("security_rules" in e for e in errors)

    def test_index_missing_collection(self):
        fs = FirestoreResource(
            name="db",
            config={"indexes": [{"fields": [{"field": "name"}]}]},
        )
        errors = fs.validate()
        assert any("collection" in e for e in errors)

    def test_index_missing_fields(self):
        fs = FirestoreResource(
            name="db",
            config={"indexes": [{"collection": "users"}]},
        )
        errors = fs.validate()
        assert any("fields" in e for e in errors)

    def test_valid_inline_rules(self):
        fs = FirestoreResource(
            name="db",
            config={
                "security_rules": "rules_version = '2'; service cloud.firestore { ... }",
            },
        )
        assert fs.validate() == []


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: FirebaseRealtimeDBResource
# ═══════════════════════════════════════════════════════════════════════════════


class TestFirebaseRealtimeDBResource:
    def test_valid_config(self):
        rtdb = FirebaseRealtimeDBResource(
            name="main-rtdb",
            config={"type": "DEFAULT_DATABASE"},
        )
        assert rtdb.validate() == []

    def test_invalid_type(self):
        rtdb = FirebaseRealtimeDBResource(
            name="rtdb", config={"type": "CUSTOM_DB"}
        )
        errors = rtdb.validate()
        assert any("type" in e for e in errors)

    def test_valid_with_rules(self):
        rtdb = FirebaseRealtimeDBResource(
            name="rtdb",
            config={
                "security_rules": '{"rules": {".read": false, ".write": false}}',
            },
        )
        assert rtdb.validate() == []


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: FirebaseHostingResource
# ═══════════════════════════════════════════════════════════════════════════════


class TestFirebaseHostingResource:
    def test_valid_config(self):
        hosting = FirebaseHostingResource(
            name="site",
            config={"site_id": "my-app"},
        )
        assert hosting.validate() == []

    def test_missing_site_id_when_not_default(self):
        hosting = FirebaseHostingResource(
            name="site",
            config={"use_default_site": False},
        )
        errors = hosting.validate()
        assert any("site_id" in e for e in errors)

    def test_rewrite_missing_source(self):
        hosting = FirebaseHostingResource(
            name="site",
            config={"rewrites": [{"destination": "/index.html"}]},
        )
        errors = hosting.validate()
        assert any("source" in e for e in errors)

    def test_rewrite_missing_destination(self):
        hosting = FirebaseHostingResource(
            name="site",
            config={"rewrites": [{"source": "**"}]},
        )
        errors = hosting.validate()
        assert any("destination" in e or "function" in e or "run" in e for e in errors)

    def test_valid_with_custom_domain(self):
        hosting = FirebaseHostingResource(
            name="site",
            config={
                "site_id": "my-app",
                "custom_domain": "app.example.com",
            },
        )
        assert hosting.validate() == []


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: DNSRecordResource
# ═══════════════════════════════════════════════════════════════════════════════


class TestDNSRecordResource:
    def test_valid_cname(self):
        dns = DNSRecordResource(
            name="app-cname",
            config={
                "domain": "example.com",
                "record_name": "app",
                "record_type": "CNAME",
                "record_value": "myapp.web.app",
            },
        )
        assert dns.validate() == []

    def test_missing_domain(self):
        dns = DNSRecordResource(
            name="dns",
            config={"record_name": "app", "record_value": "x.y.z"},
        )
        errors = dns.validate()
        assert any("domain" in e for e in errors)

    def test_missing_record_name(self):
        dns = DNSRecordResource(
            name="dns",
            config={"domain": "example.com", "record_value": "x.y.z"},
        )
        errors = dns.validate()
        assert any("record_name" in e for e in errors)

    def test_missing_record_value(self):
        dns = DNSRecordResource(
            name="dns",
            config={"domain": "example.com", "record_name": "app"},
        )
        errors = dns.validate()
        assert any("record_value" in e for e in errors)

    def test_invalid_record_type(self):
        dns = DNSRecordResource(
            name="dns",
            config={
                "domain": "example.com",
                "record_name": "app",
                "record_value": "1.2.3.4",
                "record_type": "PTR",
            },
        )
        errors = dns.validate()
        assert any("record_type" in e for e in errors)

    def test_cname_on_root(self):
        dns = DNSRecordResource(
            name="dns",
            config={
                "domain": "example.com",
                "record_name": "@",
                "record_type": "CNAME",
                "record_value": "x.y.z",
            },
        )
        errors = dns.validate()
        assert any("CNAME" in e and "raiz" in e for e in errors)

    def test_mx_without_priority(self):
        dns = DNSRecordResource(
            name="dns",
            config={
                "domain": "example.com",
                "record_name": "mail",
                "record_type": "MX",
                "record_value": "mail.example.com",
            },
        )
        errors = dns.validate()
        assert any("priority" in e for e in errors)

    def test_ttl_too_low(self):
        dns = DNSRecordResource(
            name="dns",
            config={
                "domain": "example.com",
                "record_name": "app",
                "record_value": "x.y.z",
                "ttl": 60,
            },
        )
        errors = dns.validate()
        assert any("ttl" in e for e in errors)

    def test_valid_a_record(self):
        dns = DNSRecordResource(
            name="dns",
            config={
                "domain": "example.com",
                "record_name": "www",
                "record_type": "A",
                "record_value": "34.107.123.45",
            },
        )
        assert dns.validate() == []

    def test_valid_txt_record(self):
        dns = DNSRecordResource(
            name="dns",
            config={
                "domain": "example.com",
                "record_name": "_firebase",
                "record_type": "TXT",
                "record_value": "my-app-verification",
            },
        )
        assert dns.validate() == []


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: Config com novos tipos de recurso
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigNewResources:
    def test_cloud_run_in_config(self, tmp_path):
        data = {
            "project": {"name": "test"},
            "provider": {"name": "gcp", "region": "us-central1"},
            "resources": [
                {
                    "type": "cloud_run",
                    "name": "api",
                    "config": {"image": "gcr.io/p/a:latest"},
                },
            ],
        }
        cfg_path = tmp_path / "cr.yaml"
        with open(cfg_path, "w") as f:
            yaml.dump(data, f)
        config = Config(str(cfg_path))
        result = config.load()
        assert result["resources"][0]["type"] == "cloud_run"

    def test_firebase_resources_in_config(self, tmp_path):
        data = {
            "project": {"name": "test"},
            "provider": {"name": "gcp", "region": "us-central1"},
            "resources": [
                {
                    "type": "firebase_auth",
                    "name": "auth",
                    "config": {"providers": ["email"]},
                },
                {
                    "type": "firestore",
                    "name": "db",
                    "config": {"mode": "native"},
                },
                {
                    "type": "firebase_rtdb",
                    "name": "rtdb",
                    "config": {"type": "DEFAULT_DATABASE"},
                },
                {
                    "type": "firebase_hosting",
                    "name": "hosting",
                    "config": {"site_id": "my-app"},
                },
            ],
        }
        cfg_path = tmp_path / "fb.yaml"
        with open(cfg_path, "w") as f:
            yaml.dump(data, f)
        config = Config(str(cfg_path))
        result = config.load()
        assert len(result["resources"]) == 4

    def test_dns_record_in_config(self, tmp_path):
        data = {
            "project": {"name": "test"},
            "provider": {"name": "gcp", "region": "us-central1"},
            "external_providers": {
                "godaddy": {
                    "api_key": "test",
                    "api_secret": "test",
                },
            },
            "resources": [
                {
                    "type": "dns_record",
                    "name": "cname",
                    "config": {
                        "domain": "example.com",
                        "record_name": "app",
                        "record_value": "x.web.app",
                    },
                },
            ],
        }
        cfg_path = tmp_path / "dns.yaml"
        with open(cfg_path, "w") as f:
            yaml.dump(data, f)
        config = Config(str(cfg_path))
        result = config.load()
        assert result["resources"][0]["type"] == "dns_record"
        assert "godaddy" in result["external_providers"]


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: Alibaba Cloud Provider
# ═══════════════════════════════════════════════════════════════════════════════


class TestAlibabaCloudProvider:
    """Testes para o provider Alibaba Cloud."""

    def test_provider_name(self):
        from cloudforge.providers.alibaba.provider import AlibabaCloudProvider
        provider = AlibabaCloudProvider("cn-hangzhou", {})
        assert provider.PROVIDER_NAME == "alibaba"

    def test_list_regions(self):
        from cloudforge.providers.alibaba.provider import AlibabaCloudProvider
        provider = AlibabaCloudProvider("cn-hangzhou", {})
        regions = provider.list_regions()
        assert "cn-hangzhou" in regions
        assert "cn-shanghai" in regions
        assert "us-west-1" in regions
        assert "eu-central-1" in regions

    def test_region_zones_mapping(self):
        from cloudforge.providers.alibaba.provider import AlibabaCloudProvider
        provider = AlibabaCloudProvider("cn-hangzhou", {})
        assert "cn-hangzhou" in provider.REGION_ZONES
        assert len(provider.REGION_ZONES["cn-hangzhou"]) > 0

    def test_get_zone_for_region(self):
        from cloudforge.providers.alibaba.provider import AlibabaCloudProvider
        provider = AlibabaCloudProvider("cn-hangzhou", {})
        zone = provider._get_zone_for_region()
        assert zone.startswith("cn-hangzhou-")

    def test_resolve_image_id(self):
        from cloudforge.providers.alibaba.provider import AlibabaCloudProvider
        provider = AlibabaCloudProvider("cn-hangzhou", {})
        
        assert "ubuntu_22_04" in provider._resolve_image_id("ubuntu_22_04")
        assert "centos_7" in provider._resolve_image_id("centos_7")
        assert "windows_2019" in provider._resolve_image_id("windows_2019")

    def test_authenticate_requires_credentials(self):
        from cloudforge.providers.alibaba.provider import AlibabaCloudProvider
        from cloudforge.providers.base import ProviderError
        
        provider = AlibabaCloudProvider("cn-hangzhou", {})
        # Sem credenciais, autenticação deve falhar
        with pytest.raises(ProviderError):
            provider.authenticate()

    def test_validate_credentials_without_auth(self):
        from cloudforge.providers.alibaba.provider import AlibabaCloudProvider
        provider = AlibabaCloudProvider("cn-hangzhou", {})
        # Sem autenticação prévia, deve retornar False
        assert provider.validate_credentials() == False


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: Logging
# ═══════════════════════════════════════════════════════════════════════════════


class TestLogging:
    """Testes para o módulo de logging."""

    def test_logger_singleton(self):
        logger1 = CloudForgeLogger()
        logger2 = CloudForgeLogger()
        assert logger1 is logger2

    def test_get_logger(self):
        logger = get_logger("test")
        assert logger is not None
        assert isinstance(logger, CloudForgeLogger)

    def test_set_context(self):
        logger = get_logger("test_ctx")
        logger.set_context(project="test", resource="vm-1")
        assert logger.context == {"project": "test", "resource": "vm-1"}

    def test_clear_context(self):
        logger = get_logger("test_clear")
        logger.set_context(a="b")
        logger.clear_context()
        assert logger.context == {}

    def test_log_levels(self, caplog):
        import logging
        logger = get_logger("test_levels", level="DEBUG")
        logger.logger.addHandler(caplog.handler)
        
        logger.debug("debug msg")
        logger.info("info msg")
        logger.warning("warning msg")
        logger.error("error msg")
        
        assert "debug msg" in caplog.text
        assert "info msg" in caplog.text
        assert "warning msg" in caplog.text
        assert "error msg" in caplog.text


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: Retry
# ═══════════════════════════════════════════════════════════════════════════════


class TestRetry:
    """Testes para o módulo de retry."""

    def test_retry_success_on_first_attempt(self):
        call_count = 0
        
        @retry_with_backoff(max_attempts=3)
        def succeed_immediately():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = succeed_immediately()
        assert result == "success"
        assert call_count == 1

    def test_retry_succeeds_after_failures(self):
        call_count = 0
        
        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        def succeed_after_two_failures():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temporary error")
            return "success"
        
        result = succeed_after_two_failures()
        assert result == "success"
        assert call_count == 3

    def test_retry_exhausts_all_attempts(self):
        call_count = 0
        
        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("permanent error")
        
        with pytest.raises(RetryError) as exc_info:
            always_fails()
        
        assert call_count == 3
        assert exc_info.value.attempts == 3

    def test_retry_only_on_specified_exceptions(self):
        call_count = 0
        
        @retry_with_backoff(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(ValueError,)
        )
        def raise_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("not retryable")
        
        with pytest.raises(TypeError):
            raise_type_error()
        
        assert call_count == 1  # Não retenta para TypeError

    def test_retry_on_exception_decorator(self):
        call_count = 0
        
        @retry_on_exception(ConnectionError, max_attempts=3, message="Connection failed")
        def flaky_connection():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("lost connection")
            return "connected"
        
        result = flaky_connection()
        assert result == "connected"
        assert call_count == 2

    def test_retry_config_execute(self):
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        call_count = 0
        
        def may_fail():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("timeout")
            return "ok"
        
        result = config.execute(may_fail)
        assert result == "ok"
        assert call_count == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: Schema Validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaValidation:
    """Testes para validação de schema."""

    def test_valid_config(self):
        config = {
            "project": {"name": "test-project"},
            "provider": {"name": "aws", "region": "us-east-1"},
            "resources": [
                {"type": "vpc", "name": "main-vpc", "config": {"cidr_block": "10.0.0.0/16"}}
            ],
        }
        is_valid, errors = validate_config(config)
        assert is_valid
        assert len(errors) == 0

    def test_missing_required_fields(self):
        config = {
            "project": {},  # Falta name
            "provider": {"name": "aws"},  # Falta region
            "resources": [],  # Vazio não é permitido
        }
        is_valid, errors = validate_config(config)
        assert not is_valid
        assert len(errors) > 0

    def test_invalid_provider_name(self):
        config = {
            "project": {"name": "test"},
            "provider": {"name": "invalid-provider", "region": "us-east-1"},
            "resources": [
                {"type": "vm", "name": "vm1", "config": {}}
            ],
        }
        is_valid, errors = validate_config(config)
        assert not is_valid
        assert any("invalid-provider" in str(e) or "enum" in str(e).lower() for e in errors)

    def test_invalid_resource_type(self):
        config = {
            "project": {"name": "test"},
            "provider": {"name": "aws", "region": "us-east-1"},
            "resources": [
                {"type": "invalid-type", "name": "res1", "config": {}}
            ],
        }
        is_valid, errors = validate_config(config)
        assert not is_valid
        assert any("invalid-type" in str(e) for e in errors)

    def test_invalid_vm_config(self):
        config = {
            "project": {"name": "test"},
            "provider": {"name": "aws", "region": "us-east-1"},
            "resources": [
                {
                    "type": "vm",
                    "name": "vm1",
                    "config": {"disk_size_gb": 5}  # Mínimo é 10
                }
            ],
        }
        is_valid, errors = validate_config(config)
        assert not is_valid
        assert any("disk_size" in str(e).lower() or "minimum" in str(e).lower() for e in errors)

    def test_invalid_cidr_block_format(self):
        config = {
            "project": {"name": "test"},
            "provider": {"name": "aws", "region": "us-east-1"},
            "resources": [
                {
                    "type": "vpc",
                    "name": "vpc1",
                    "config": {"cidr_block": "invalid-cidr"}
                }
            ],
        }
        is_valid, errors = validate_config(config)
        assert not is_valid
        assert any("cidr" in str(e).lower() or "pattern" in str(e).lower() for e in errors)

    def test_schema_validator_class(self):
        validator = SchemaValidator()
        config = {
            "project": {"name": "test"},
            "provider": {"name": "gcp", "region": "us-central1"},
            "resources": [
                {"type": "vpc", "name": "vpc1", "config": {"cidr_block": "10.0.0.0/16"}}
            ],
        }
        is_valid, errors = validator.validate(config)
        assert is_valid

    def test_validate_or_raise(self):
        from core.schema import validate_config_or_raise
        
        valid_config = {
            "project": {"name": "test"},
            "provider": {"name": "aws", "region": "us-east-1"},
            "resources": [
                {"type": "vpc", "name": "vpc1", "config": {"cidr_block": "10.0.0.0/16"}}
            ],
        }
        # Não deve levantar exceção
        validate_config_or_raise(valid_config)

    def test_validate_or_raise_raises_exception(self):
        from core.schema import validate_config_or_raise
        
        invalid_config = {
            "project": {},  # Inválido
            "provider": {"name": "invalid", "region": "x"},
            "resources": [],
        }
        with pytest.raises(SchemaValidationError):
            validate_config_or_raise(invalid_config)

    def test_alibaba_resource_type(self):
        """Testa que 'alibaba' é um provider válido e 'slb' é um tipo de recurso válido."""
        config = {
            "project": {"name": "test"},
            "provider": {"name": "alibaba", "region": "cn-hangzhou"},
            "resources": [
                {"type": "slb", "name": "lb1", "config": {"name": "my-lb"}},
            ],
        }
        is_valid, errors = validate_config(config)
        # slb deve ser um tipo válido
        assert all("slb" not in str(e) for e in errors)


# ═══════════════════════════════════════════════════════════════════════════════
# Testes: Integração com Alibaba Cloud no Config
# ═══════════════════════════════════════════════════════════════════════════════


class TestAlibabaConfigIntegration:
    """Testes de integração com Alibaba Cloud no Config."""

    def test_alibaba_provider_in_config(self, tmp_path):
        data = {
            "project": {"name": "alibaba-test"},
            "provider": {"name": "alibaba", "region": "cn-hangzhou"},
            "resources": [
                {
                    "type": "vpc",
                    "name": "main-vpc",
                    "config": {"cidr_block": "10.0.0.0/16"},
                },
            ],
        }
        cfg_path = tmp_path / "alibaba.yaml"
        with open(cfg_path, "w") as f:
            yaml.dump(data, f)
        config = Config(str(cfg_path))
        result = config.load()
        assert result["provider"]["name"] == "alibaba"

    def test_alibaba_vm_resource(self, tmp_path):
        data = {
            "project": {"name": "alibaba-vm-test"},
            "provider": {"name": "alibaba", "region": "cn-hangzhou"},
            "resources": [
                {
                    "type": "vm",
                    "name": "ecs-instance",
                    "config": {
                        "instance_type": "medium",
                        "os": "ubuntu_22_04",
                        "disk_size_gb": 40,
                    },
                },
            ],
        }
        cfg_path = tmp_path / "alibaba_vm.yaml"
        with open(cfg_path, "w") as f:
            yaml.dump(data, f)
        config = Config(str(cfg_path))
        result = config.load()
        assert len(result["resources"]) == 1
        assert result["resources"][0]["type"] == "vm"

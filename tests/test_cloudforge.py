"""
CloudForge — Testes Unitários
Cobre: Config, State, Graph, Planner, Resources
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
from resources.vm import VMResource
from resources.network import VPCResource, SubnetResource, SecurityGroupResource
from resources.kubernetes import KubernetesResource
from resources.database import DatabaseResource


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

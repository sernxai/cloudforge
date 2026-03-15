"""
CloudForge - Grafo de Dependências
Gerencia a ordem de criação/destruição de recursos via ordenação topológica.
"""

from collections import defaultdict, deque
from typing import Any


class CyclicDependencyError(Exception):
    """Erro quando existe dependência circular entre recursos."""

    pass


class DependencyGraph:
    """Grafo direcionado acíclico (DAG) para resolver ordem de recursos."""

    def __init__(self):
        self._graph: dict[str, set[str]] = defaultdict(set)
        self._reverse: dict[str, set[str]] = defaultdict(set)
        self._nodes: set[str] = set()

    def add_node(self, name: str) -> None:
        """Adiciona um nó (recurso) ao grafo."""
        self._nodes.add(name)

    def add_edge(self, source: str, target: str) -> None:
        """Adiciona dependência: source depende de target."""
        self._nodes.add(source)
        self._nodes.add(target)
        self._graph[source].add(target)
        self._reverse[target].add(source)

    def topological_sort(self) -> list[str]:
        """
        Retorna os nós em ordem topológica (dependências primeiro).
        Usa o algoritmo de Kahn.
        """
        # adj[dep] = {nodes that depend on dep}
        adj: dict[str, set[str]] = defaultdict(set)
        in_deg: dict[str, int] = {node: 0 for node in self._nodes}

        for node in self._nodes:
            for dep in self._graph[node]:
                # node depende de dep, então dep -> node
                adj[dep].add(node)
                in_deg[node] += 1

        queue = deque([n for n in self._nodes if in_deg[n] == 0])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for neighbor in adj[node]:
                in_deg[neighbor] -= 1
                if in_deg[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(self._nodes):
            remaining = self._nodes - set(result)
            raise CyclicDependencyError(
                f"Dependência circular detectada entre: {', '.join(remaining)}"
            )

        return result

    def reverse_topological_sort(self) -> list[str]:
        """Retorna ordem reversa (para destruição de recursos)."""
        return list(reversed(self.topological_sort()))

    def get_dependencies(self, name: str) -> set[str]:
        """Retorna dependências diretas de um recurso."""
        return self._graph.get(name, set())

    def get_dependents(self, name: str) -> set[str]:
        """Retorna recursos que dependem deste."""
        return self._reverse.get(name, set())

    @classmethod
    def from_resources(cls, resources: list[dict[str, Any]]) -> "DependencyGraph":
        """Constrói grafo a partir da lista de recursos do YAML."""
        graph = cls()
        for resource in resources:
            name = resource["name"]
            graph.add_node(name)
            for dep in resource.get("depends_on", []):
                graph.add_edge(name, dep)
        return graph
